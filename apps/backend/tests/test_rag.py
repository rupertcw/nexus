from unittest.mock import patch, MagicMock

from qdrant_client import QdrantClient

from app.agent import DummyAgentLLM
from app.embedding_client import EmbeddingClient
from app.retriever import Retriever
from app.vector_db_client import VectorDBClient


def test_dummy_agent_llm(override_auth):
    retriever = MagicMock()
    duckdb = MagicMock()
    llm = DummyAgentLLM(duckdb_engine=duckdb, retriever=retriever)
    
    # Simulate first turn (prompt for search)
    msg = [{"role": "user", "content": "How do I deploy this?"}]
    res = llm.invoke("system", msg, tools=[])
    assert res["stop_reason"] == "tool_use"
    assert res["content"][0]["name"] == "search_documents"


def test_retriever_search(override_auth):
    mock_result = MagicMock()
    mock_result.payload = {
        "filename": "policy.pdf",
        "page": 2,
        "text": "Deploy via Kubernetes",
    }
    mock_result.score = 0.98
    vector_db_client = MagicMock(spec=VectorDBClient)
    vector_db_client.search.return_value = [mock_result]

    embedding_client = MagicMock(spec=EmbeddingClient)
    embedding_client.embed.return_value.return_value = [
        0.1,
        0.2,
        0.3,
    ]

    retriever = Retriever(embedding_client=MagicMock(), vector_db_client=vector_db_client, collection_name="test")
    res = retriever.search("deployment policy")

    assert "context_str" in res
    assert "sources" in res
    assert "Deploy via Kubernetes" in res["context_str"]
    assert len(res["sources"]) == 1
    assert res["sources"][0]["score"] == 0.98
    assert res["sources"][0]["filename"] == "policy.pdf"
