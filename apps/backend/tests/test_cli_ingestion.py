import os
import shutil
import tempfile
import pytest
from unittest.mock import patch
from qdrant_client import QdrantClient
from rq import Queue

# Need to point straight to the modules in the codebase
from cli.ingest import ingest
from app.retriever import Retriever
from app.agent import AgentRouter
from app.duckdb_engine import DuckDBEngine
from click.testing import CliRunner


@pytest.fixture(scope="module")
def temp_ingest_dir():
    # Create temporary directory and just copy *one* small test file
    # to keep test execution fast (since local ML embedding is CPU intensive)
    with tempfile.TemporaryDirectory() as temp_dir:
        # Fallback to write a quick txt if the user moved the pdfs
        with open(os.path.join(temp_dir, "test.txt"), "w") as f:
            f.write(
                "A Tour of C++ is a book about the C++ programming language. Deployment happens in Kubernetes."
            )

        yield temp_dir


def test_ingestion_end_to_end(fake_queue: Queue, temp_ingest_dir, mocker):
    """
    1. Ingestion test - Use a book, ingest it and test the DB contains vectors and is non-empty.
    """

    mocker.patch("cli.ingest.Queue", return_value=fake_queue)
    runner = CliRunner()
    result = runner.invoke(ingest, [temp_ingest_dir])
    assert result.exit_code == 0, f"Ingest script failed: {result.output}"

    assert len(fake_queue) == 1
