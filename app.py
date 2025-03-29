
import streamlit as st
from agents import process_query  # Your real backend
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh  # Install via `pip install streamlit-autorefresh`

# Auto-refresh every 60 seconds (60000 ms)
st_autorefresh(interval=60000, key="time_refresh")

# CSS for green "New Chat" button and sidebar styling with transparent chat rectangles
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stButton"] > button[kind="secondary"] {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 9999;
        background-color: #5CB338;
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        display: flex;
        align-items: center;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background-color: #77B254;
    }
    .chat-button {
        margin: 5px 0;
        background-color: transparent;  /* Transparent background */
        border: 1px solid rgba(221, 221, 221, 0.5);  /* Semi-transparent border */
        border-radius: 5px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 5px;
    }
    .delete-button {
        background: none;
        border: none;
        cursor: pointer;
        padding: 0;
            }
    .scroll-down-btn {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: #5CB338;
        color: white;
        border: none;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        font-size: 20px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .scroll-down-btn:hover {
        background-color: #77B254;
    }
    
    
            
    </style>
""", unsafe_allow_html=True)
# JavaScript for scroll down button
scroll_js = """
<script>
function scrollToBottom() {
    window.scrollTo(0, document.body.scrollHeight);
}
</script>
"""
# Set page title
st.title("Conversational Code Generation Agent")

# Initialize session state for chats
if "chats" not in st.session_state:
    st.session_state.chats = [{"id": 1, "name": "Chat 1", "messages": [], "rerun_counters": {}, "timestamp": datetime.now()}]
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = 1

# Function to get the current chat
def get_current_chat():
    return next((chat for chat in st.session_state.chats if chat["id"] == st.session_state.current_chat_id), None)

# Function to update chat name based on first user prompt
def update_chat_name(chat):
    for message in chat["messages"]:
        if message["role"] == "user":
            chat["name"] = message["content"][:30] + "..." if len(message["content"]) > 30 else message["content"]
            break
    return chat["name"]

# Function to calculate time ago with minutes
def time_ago(timestamp):
    now = datetime.now()
    diff = now - timestamp
    minutes = diff.total_seconds() // 60  # Convert to minutes
    hours = diff.total_seconds() // 3600  # Convert to hours
    if minutes < 1:
        return "Just now"
    elif minutes < 60:
        return f"{int(minutes)} min ago"
    elif hours < 24:
        return f"{int(hours)} hr ago"
    else:
        days = hours // 24
        return f"{int(days)} day{'s' if days > 1 else ''} ago"

# Fixed "New Chat" button with logo (🪐 emoji)
if st.button("New Chat", key="fixed_new_chat"):
    new_chat_id = max(chat["id"] for chat in st.session_state.chats) + 1
    st.session_state.chats.append({"id": new_chat_id, "name": f"Chat {new_chat_id}", "messages": [], "rerun_counters": {}, "timestamp": datetime.now()})
    st.session_state.current_chat_id = new_chat_id
    st.rerun()

st.sidebar.markdown('<div class="fixed-sidebar">', unsafe_allow_html=True)

# Fixed "History" button with a book emoji (📚)
# if st.sidebar.button("📚 History", key="history_button"):
#     # Define what happens when the History button is clicked
#     st.sidebar.write("History functionality not implemented yet.")  # Placeholder for history functionality

# Sidebar for chat navigation
with st.sidebar:
    for chat in st.session_state.chats[:]:  # Use a copy to avoid iteration issues when removing
        chat_name = update_chat_name(chat)
        time_str = time_ago(chat["timestamp"])
        col1, col2 = st.columns([3, 1])  # Split sidebar into two columns
        with col1:
            if st.button(f"{chat_name} ({time_str})", key=f"chat_{chat['id']}", help=f"Switch to {chat_name}", use_container_width=True):
                st.session_state.current_chat_id = chat["id"]
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"clear_{chat['id']}", help=f"Delete {chat_name}", type="secondary", use_container_width=True):
                st.session_state.chats = [c for c in st.session_state.chats if c["id"] != chat["id"]]
                if st.session_state.current_chat_id == chat["id"]:
                    if st.session_state.chats:
                        st.session_state.current_chat_id = st.session_state.chats[0]["id"]
                    else:
                        st.session_state.chats = [{"id": 1, "name": "Chat 1", "messages": [], "rerun_counters": {}, "timestamp": datetime.now()}]
                        st.session_state.current_chat_id = 1
                st.rerun()
st.sidebar.markdown('</div>', unsafe_allow_html=True)
# Get the current chat’s messages and rerun_counters
current_chat = get_current_chat()
if current_chat is None:  # Handle case where no chats exist
    st.session_state.chats = [{"id": 1, "name": "Chat 1", "messages": [], "rerun_counters": {}, "timestamp": datetime.now()}]
    st.session_state.current_chat_id = 1
    current_chat = get_current_chat()
messages = current_chat["messages"]
rerun_counters = current_chat["rerun_counters"]

# Display conversation history
for idx, message in enumerate(messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)
        if message["role"] == "assistant":
            rerun_key = f"rerun_{idx}_{current_chat['id']}"
            if st.button(f"🔄 Re-run", key=rerun_key, help=f"Re-run this response (Prompt: {messages[idx-1]['content'][:30]}...)"):
                prompt = messages[idx - 1]["content"]
                with st.spinner("Re-generating code..."):
                    try:
                        response = process_query(prompt)
                        response = response.replace(
                            "Prompt user for", '<span style="color: blue;">Prompt user for</span>'
                        ).replace(
                            "Scan", '<span style="color: blue;">Scan</span>'
                        ).replace(
                            "Collect", '<span style="color: green;">Collect</span>'
                        ).replace(
                            "Read", '<span style="color: green;">Read</span>'
                        )
                    except Exception as e:
                        response = f"Error: Couldn’t re-run code. Details: {str(e)}"
                
                messages.append({"role": "user", "content": prompt})
                messages.append({"role": "assistant", "content": response})
                rerun_counters[idx] = rerun_counters.get(idx, 0) + 1
                st.rerun()


st.markdown(scroll_js, unsafe_allow_html=True)
st.markdown('<button class="scroll-down-btn" onclick="scrollToBottom()">↓</button>', unsafe_allow_html=True)
# User input via chat
prompt = st.chat_input("Ask me to generate some code! (e.g., 'Write a function to add two numbers')")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    messages.append({"role": "user", "content": prompt})
    current_chat["timestamp"] = datetime.now()  # Update timestamp on new message

    with st.spinner("Generating code..."):
        try:
            response = process_query(prompt)
            response = response.replace(
                "Prompt user for", '<span style="color: blue;">Prompt user for</span>'
            ).replace(
                "Scan", '<span style="color: blue;">Scan</span>'
            ).replace(
                "Collect", '<span style="color: green;">Collect</span>'
            ).replace(
                "Read", '<span style="color: green;">Read</span>'
            )
        except Exception as e:
            response = f"Error: Couldn’t generate code. Details: {str(e)}"

    with st.chat_message("assistant"):
        st.markdown(response, unsafe_allow_html=True)
    messages.append({"role": "assistant", "content": response})
    st.rerun()




