from unittest.mock import patch, MagicMock
from app.agent import DummyAgentLLM
from app.retriever import Retriever


def test_dummy_agent_llm():
    retriever = MagicMock()
    duckdb = MagicMock()
    llm = DummyAgentLLM(duckdb_engine=duckdb, retriever=retriever)
    
    # Simulate first turn (prompt for search)
    msg = [{"role": "user", "content": "How do I deploy this?"}]
    res = llm.invoke("system", msg, tools=[])
    assert res.stop_reason == "tool_use"
    assert res.content[0].name == "search_documents"


def test_retriever_search():
    # Mock QdrantClient to prevent real external DB connections during testing.
    with patch("app.retriever.QdrantClient") as MockClient:
        instance = MockClient.return_value

        mock_result = MagicMock()
        mock_result.payload = {
            "filename": "policy.pdf",
            "page": 2,
            "text": "Deploy via Kubernetes",
        }
        mock_result.score = 0.98

        # Patching search to return our mock result
        instance.search.return_value = [mock_result]

        # We also want to mock out SentenceTransformer to avoid loading ML models which would be slow
        with patch("app.retriever.SentenceTransformer") as MockModel:
            mock_model_instance = MockModel.return_value
            mock_model_instance.encode.return_value.tolist.return_value = [
                0.1,
                0.2,
                0.3,
            ]

            retriever = Retriever()
            res = retriever.search("deployment policy")

            assert "context_str" in res
            assert "sources" in res
            assert "Deploy via Kubernetes" in res["context_str"]
            assert len(res["sources"]) == 1
            assert res["sources"][0]["score"] == 0.98
            assert res["sources"][0]["filename"] == "policy.pdf"
