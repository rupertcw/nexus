from unittest.mock import MagicMock

import jwt
import numpy as np
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

from app import duckdb_engine, embedding_client
from app.agent import AgentRouter
from app.embedding_client import EmbeddingClient
from tests.conftest import patch_dependencies


def test_jwt_verification(client: TestClient):
    """Test that secured routes reject unsigned or missing tokens."""
    # Attempt without headers
    res = client.get("/sessions")
    assert res.status_code == 403


def test_create_session(client: TestClient, override_auth):
    response = client.post("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["title"] == "New Chat"


def test_get_sessions(client: TestClient, override_auth):
    client.post("/sessions")
    response = client.get("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_chat_interaction(client: TestClient, monkeypatch: MonkeyPatch, override_auth):
    embedding_client = MagicMock(spec=EmbeddingClient)
    embedding_client.embed.return_value = {"embeddings": [[32.0, 10.3, 140.1]]}
    patch_dependencies(monkeypatch, embedding_client)

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


def test_hybrid_router_and_cache(client: TestClient, monkeypatch):
    """
    Simulates the End-to-End sequence: Auth -> Chat -> Hybrid DuckDB Router -> Semantic Caching Intercept.
    """

    # Ensure our Agent Router bypasses local files entirely and provides a definitive Mock output
    class SafeMockDuckDB:
        data_dir = "/tmp"

        def query(self, sql):
            return "MOCKED SQL RESULT DECLARED: travel_spend=300"

        def get_schema_context(self):
            return "Mock Schema Context"

    rng = np.random.default_rng()
    embedding_client = MagicMock(spec=EmbeddingClient)
    embedding_client.embed.return_value = {"embeddings": [rng.random(384)]}
    patch_dependencies(monkeypatch, embedding_client=embedding_client, duckdb_engine=SafeMockDuckDB())

    # Generate valid JWT signed by 'dev_secret'
    token = jwt.encode({"user_id": 99}, "dev_secret", algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    # Start Session
    res_session = client.post("/sessions", headers=headers)
    assert res_session.status_code == 200
    session_id = res_session.json()["id"]

    # 1. Perform Hybrid Chat triggering the keyword `spend` which redirects to DuckDB mocking
    payload = {"session_id": session_id, "message": "What is the travel spend?"}
    res_first = client.post("/chat", headers=headers, json=payload)
    data_first = res_first.json()

    assert res_first.status_code == 200
    assert "analyzed" in data_first["response"].lower() or "searched" in data_first["response"].lower()
    assert data_first["sources"] == []

    # 2. Perform EXACT Chat Query instantly hitting Semantic Cache Layer over Auth layer.
    res_cached = client.post("/chat", headers=headers, json=payload)
    data_cached = res_cached.json()

    assert res_cached.status_code == 200
    assert "analyzed" in data_cached["response"].lower() or "searched" in data_cached["response"].lower()

    # Crucial Validation: Semantic Cache provides its own 'Meta' Source!
    assert len(data_cached["sources"]) == 1
    assert "Semantic Cache" in data_cached["sources"][0]["filename"]
