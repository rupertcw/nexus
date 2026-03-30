import os
import shutil
import tempfile
import pytest
from unittest.mock import patch
from qdrant_client import QdrantClient

# Need to point straight to the modules in the codebase
from cli.ingest import ingest
from app.retriever import Retriever
from app.llm import DummyLLM


@pytest.fixture(scope="module")
def shared_qdrant_client():
    # Use in-memory Qdrant instance for fast and isolated test execution
    client = QdrantClient(location=":memory:")
    yield client


@pytest.fixture(scope="module")
def temp_ingest_dir():
    # Create temporary directory and just copy *one* small test file
    # to keep test execution fast (since local ML embedding is CPU intensive)
    with tempfile.TemporaryDirectory() as temp_dir:
        docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_docs"))
        test_file = os.path.join(docs_dir, "A Tour of C++.pdf")

        if os.path.exists(test_file):
            shutil.copy(test_file, temp_dir)
        else:
            # Fallback to write a quick txt if the user moved the pdfs
            with open(os.path.join(temp_dir, "test.txt"), "w") as f:
                f.write(
                    "A Tour of C++ is a book about the C++ programming language. Deployment happens in Kubernetes."
                )

        yield temp_dir


def test_ingestion_end_to_end(shared_qdrant_client, temp_ingest_dir):
    """
    1. Ingestion test - Use a book, ingest it and test the DB contains vectors and is non-empty.
    """
    with patch("cli.ingest.QdrantClient", return_value=shared_qdrant_client):
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(ingest, [temp_ingest_dir])
        assert result.exit_code == 0, f"Ingest script failed: {result.output}"

        # Verify collection exists and contains items. The default collection name is 'documents'
        collection_info = shared_qdrant_client.get_collection("documents")
        assert collection_info.points_count > 0, (
            "The Vector database should be non-empty after ingestion."
        )


def test_retrieval_end_to_end(shared_qdrant_client):
    """
    2. Read test - Make a query about the book ingested in test 1.
    """
    with patch("app.retriever.QdrantClient", return_value=shared_qdrant_client):
        retriever = Retriever()
        # Querying specific domain knowledge likely mapped to "A Tour of C++"
        result = retriever.search("C++")

        assert len(result["sources"]) > 0, (
            "Retriever should return sources mapped to the ingested query."
        )
        assert "C++" in result["context_str"] or "c++" in result["context_str"].lower()

        # Full integration checking LLM usage
        llm = DummyLLM()
        response = llm.generate("Tell me about C++", result["context_str"])
        assert response is not None
        assert "C++" in response or "c++" in response.lower()
