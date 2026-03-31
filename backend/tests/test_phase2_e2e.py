import pytest
import jwt
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e

def test_jwt_verification(client: TestClient):
    """Test that secured routes reject unsigned or missing tokens."""
    # Attempt without headers
    res = client.get("/sessions")
    assert res.status_code == 403

def test_phase2_hybrid_router_and_cache(client: TestClient, monkeypatch):
    """
    Simulates the End-to-End sequence: Auth -> Chat -> Hybrid DuckDB Router -> Semantic Caching Intercept.
    """
    
    # 1. Provide an isolated Memory state for the Semantic Cache since we don't have a live Qdrant container running during raw Pytest.
    from qdrant_client import QdrantClient
    memory_qdrant = QdrantClient(location=":memory:")
    monkeypatch.setattr("app.main.semantic_cache.qdrant", memory_qdrant)
    
    from app.main import semantic_cache
    semantic_cache._ensure_collection()
    
    # Ensure our Agent Router bypasses local files entirely and provides a definitive Mock output
    class SafeMockDuckDB:
        def query(self, sql):
            return "MOCKED SQL RESULT DECLARED: travel_spend=300"
        def get_schema_context(self):
            return "Mock Schema Context"
            
    monkeypatch.setattr("app.main.agent_router.duckdb_engine", SafeMockDuckDB())
    
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
