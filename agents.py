import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from crewai import Agent, Task, Crew
import litellm
from pymongo import MongoClient
from datetime import datetime

# Load environment variables
# Load environment variables
load_dotenv()

# Get MongoDB URI from environment variables
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("❗ MONGO_URI not found! Ensure it's set in Render environment variables or .env file.")

# MongoDB Connection
try:
    client = MongoClient(MONGO_URI)
    db = client["chatbot"]
    collection = db["conversations"]
    print("✅ Successfully connected to MongoDB!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# API Key Setup
API_KEY = os.getenv("GENERATIVE_API_KEY")
if not API_KEY:
    raise ValueError("❗ No API key? Add it to .env now!")

# Configure LiteLLM
litellm.api_key = API_KEY
os.environ["GEMINI_API_KEY"] = API_KEY
litellm.set_verbose = False

# Flask App
app = Flask(__name__)

# MongoDB Helpers
def store_conversation(user_input, response, previous_id=None):
    try:
        doc = {"query": user_input, "response": response, "timestamp": datetime.utcnow(), "previous_id": previous_id}
        result = collection.insert_one(doc)
        return str(result.inserted_id)
    except Exception as e:
        print(f"❗ Database glitch: {e}")
        return None

def get_last_response():
    return collection.find_one(sort=[("timestamp", -1)])

# Agents
interpreter = Agent(
    role="Intent Detector",
    goal="Figure out if the user wants new code, an explanation, or a tweak.",
    backstory="I’m the sharp-eyed sorter, decoding your intent in a flash!",
    llm="gemini/gemini-1.5-flash",
    verbose=False
)

code_generator = Agent(
    role="Code Crafter",
    goal="Whip up or refine code in the right language with examples.",
    backstory="I’m the code smith, forging solutions fast and clean and well organised!",
    llm="gemini/gemini-1.5-flash",
    verbose=False
)

explainer = Agent(
    role="Code Explainer",
    goal="Break down code or concepts clearly and step-by-step.",
    backstory="I’m the patient teacher, here to make sense of it all!",
    llm="gemini/gemini-1.5-flash",
    verbose=False
)

# Process user input
# ... (imports, setup, and agents remain unchanged)

def process_query(user_input):
    if not user_input:
        return "Hey, give me something to work with!"

    last_response = get_last_response()
    previous_id = str(last_response["_id"]) if last_response else None

    interpret_task = Task(
        description=f"User said: '{user_input}'. Last query: '{last_response['query'] if last_response else 'None'}'. "
                    f"Decide intent: 'new' (new code), 'explain' (explain code/concept), 'improve' (tweak last code). "
                    f"Look for keywords: 'write/make' for new/improve, 'explain/what' for explain. "
                    f"Return: 'Intent: <new/explain/improve>\nTask: <task or None>\nModification: <modification or None>\nLanguage: <language or None>'",
        expected_output="Intent, task, modification, language",
        agent=interpreter
    )
    initial_crew = Crew(agents=[interpreter], tasks=[interpret_task])
    interpret_result = initial_crew.kickoff().tasks_output[0].raw

    intent = interpret_result.split("Intent: ")[1].split("\n")[0]
    task = interpret_result.split("Task: ")[1].split("\n")[0] if "Task: " in interpret_result else "None"
    modification = interpret_result.split("Modification: ")[1].split("\n")[0] if "Modification: " in interpret_result else "None"
    language = interpret_result.split("Language: ")[1] if "Language: " in interpret_result else "None"

    if intent == "explain" and "code" not in user_input.lower() and task != "None":
        explain_task = Task(
            description=f"Explain '{task}' clearly and concisely. Format as: 'Explanation:\n<explanation>'",
            expected_output="Clear explanation",
            agent=explainer
        )
        explain_crew = Crew(agents=[explainer], tasks=[explain_task])
        response = explain_crew.kickoff().tasks_output[0].raw
        store_conversation(user_input, response, previous_id)
        return response

    if intent == "explain" and (last_response or "code" in user_input.lower()):
        if not last_response:
            return "No code to explain yet! Give me a task first."
        explain_format_instruction = "Step-by-Step Explanation:\n<steps>"
        explain_task = Task(
            description=f"Explain this code step-by-step:\n{last_response['response']}\n"
                        f"Detail how inputs are read (e.g., scanf/input) and how functions are called. "
                        f"Format as: '{explain_format_instruction}'",
            expected_output="Detailed breakdown",
            agent=explainer
        )
        explain_crew = Crew(agents=[explainer], tasks=[explain_task])
        response = f"Here’s the step-by-step breakdown of the last code:\n\n{explain_crew.kickoff().tasks_output[0].raw}"
        store_conversation(user_input, response, previous_id)
        return response

    if task == "None" and intent != "improve":
        return "I’m not sure what you want—new code, explanation, or tweak? Clarify, please!"

    if intent == "new" or (intent == "improve" and not last_response):
        languages = [language] if language != "None" else ["Python", "C"]
        intro = f"Here’s your {languages[0]} code for '{task}'!" if language != "None" else \
                "Here’s your code in Python and C since no language was specified!"
        
        format_lines = [f"{lang} Code:\n```{lang.lower()}\n<code>\n```" for lang in languages]
        format_instruction = "\n\n".join(format_lines)
        
        generate_task = Task(
            description=f"For '{task}', generate code in {', '.join(languages)}. Include user input examples. "
                        f"Format as: {format_instruction}",
            expected_output="Code snippets",
            agent=code_generator
        )
        code_crew = Crew(agents=[code_generator], tasks=[generate_task])
        code_output = code_crew.kickoff().tasks_output[0].raw

        explain_format_lines = [f"{lang}:\n<steps>" for lang in languages]
        explain_format_instruction = "Step-by-Step Explanation:\n" + " | ".join(explain_format_lines)
        
        explain_task = Task(
            description=f"Explain this code step-by-step:\n{code_output}\n"
                        f"Detail how inputs are read (e.g., scanf/input) and how functions are called. "
                        f"Format as: '{explain_format_instruction}'",
            expected_output="Detailed breakdown",
            agent=explainer
        )
        explain_crew = Crew(agents=[explainer], tasks=[explain_task])
        explanation = explain_crew.kickoff().tasks_output[0].raw

        if len(languages) > 1:
            comparison = "Which is Better?\n" + \
                        (f"- {languages[0]}: Enhanced for {modification}.\n" if language != "None" else \
                        f"- Python: Improved for {modification} with ease.\n- C: Optimized for {modification} with speed.")
        else:
            comparison = "" 
        # Build the response
        response_parts = [
            intro,
            code_output,
            explanation,
            comparison
        ]
        # Filter out empty parts and join with double newlines
        response = "\n\n".join(part for part in response_parts if part)
        store_conversation(user_input, response, previous_id)
        return response

    if intent == "improve" and last_response:
        languages = [language] if language != "None" else ["Python", "C"]
        intro = f"Tweaking the last code in {languages[0]}!" if language != "None" else \
                "Tweaking the last code in Python and C!"
        
        format_lines = [f"{lang} Code:\n```{lang.lower()}\n<code>\n```" for lang in languages]
        format_instruction = "\n\n".join(format_lines)
        
        generate_task = Task(
            description=f"Improve this code:\n{last_response['response']}\nApply tweak: '{modification}'. "
                        f"Use {', '.join(languages)}. Format as: {format_instruction}",
            expected_output="Improved code",
            agent=code_generator
        )
        code_crew = Crew(agents=[code_generator], tasks=[generate_task])
        code_output = code_crew.kickoff().tasks_output[0].raw

        explain_format_lines = [f"{lang}:\n<steps>" for lang in languages]
        explain_format_instruction = "Step-by-Step Explanation:\n" + " | ".join(explain_format_lines)
        
        explain_task = Task(
            description=f"Explain the improved code step-by-step:\n{code_output}\n"
                        f"Detail how inputs are read (e.g., scanf/input) and how functions are called. "
                        f"Format as: '{explain_format_instruction}'",
            expected_output="Detailed breakdown",
            agent=explainer
        )
        explain_crew = Crew(agents=[explainer], tasks=[explain_task])
        explanation = explain_crew.kickoff().tasks_output[0].raw

        if len(languages) > 1:
            comparison = "Which is Better?\n" + \
                        (f"- {languages[0]}: Enhanced for {modification}.\n" if language != "None" else \
                        f"- Python: Improved for {modification} with ease.\n- C: Optimized for {modification} with speed.")
        else:
            comparison = "" 
        # Build the response
        response_parts = [
            intro,
            code_output,
            explanation,
            comparison
        ]
        # Filter out empty parts and join with double newlines
        response = "\n\n".join(part for part in response_parts if part)

        store_conversation(user_input, response, previous_id)
        return response

# ... (Flask endpoint and main remain unchanged)

# Flask API Endpoint
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get("query", "")
    response = process_query(user_input)
    return jsonify({"response": response})

if __name__ == "__main__":
    print("🚀 Chatbot’s live at http://127.0.0.1:5000—let’s code!")
    app.run(port=5000, debug=False)
