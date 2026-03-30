from fastapi.testclient import TestClient

def test_create_session(client: TestClient):
    response = client.post("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["title"] == "New Chat"

def test_get_sessions(client: TestClient):
    client.post("/sessions")
    response = client.get("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

def test_chat_interaction(client: TestClient):
    # 1. Create session
    sess_res = client.post("/sessions")
    session_id = sess_res.json()["id"]

    # 2. Send chat message
    chat_res = client.post("/chat", json={
        "session_id": session_id,
        "message": "What is the policy on remote work?"
    })
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert "response" in data
    assert "sources" in data
    assert len(data["sources"]) > 0

    # 3. Verify messages are saved
    msg_res = client.get(f"/sessions/{session_id}/messages")
    assert msg_res.status_code == 200
    messages = msg_res.json()
    assert len(messages) == 2 # User + Assistant
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
