import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import mongomock

# Mock MongoDB
@pytest.fixture
def mock_db(monkeypatch):
    mock_client = mongomock.MongoClient()
    mock_db = mock_client["test_db"]
    mock_collection = mock_db["conversations"]
    monkeypatch.setattr("pymongo.MongoClient", lambda *args, **kwargs: mock_client)
    return mock_collection

# Test database functions
def test_store_conversation(mock_db):
    from app import store_conversation
    doc_id = store_conversation("test input", "test response")
    assert doc_id is not None
    assert mock_db.count_documents({}) == 1

def test_get_last_response(mock_db):
    from app import get_last_response
    mock_db.insert_one({"query": "test", "response": "test", "timestamp": datetime.utcnow()})
    response = get_last_response()
    assert response is not None
    assert "test" in response["query"]

# Test utility functions
def test_time_ago():
    from app import time_ago
    now = datetime.now()
    assert time_ago(now - timedelta(minutes=5)) == "5 min ago"
    assert time_ago(now - timedelta(hours=2)) == "2 hr ago"
    assert time_ago(now - timedelta(days=1)) == "1 day ago"

# Test Flask endpoint
def test_flask_endpoint():
    from app import app
    app.config['TESTING'] = True
    client = app.test_client()
    
    with patch('app.process_query', return_value="Test response"):
        response = client.post('/chat', json={'query': 'test'})
        assert response.status_code == 200
        assert response.json == {"response": "Test response"}