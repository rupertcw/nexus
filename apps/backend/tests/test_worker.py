from pathlib import Path
from unittest.mock import MagicMock

import worker


def test_process_file_job_txt_new(mocker, db, shared_datadir: Path):
    file_path = shared_datadir / "dummy.txt"

    mocker.patch("worker.vector_db_client")
    mocker.patch("worker.database.get_db", return_value=db)
    mock_embedding_client = mocker.patch("worker.embedding_client")
    mock_embedding_client.embed.return_value = [[0.1] * 384, [0.2] * 384]
    job = MagicMock(meta={})
    mocker.patch("worker.get_current_job", return_value=job)

    # Execute
    result = worker.process_file_job(str(file_path))

    # Assertions
    assert result["status"] == "success"
    assert result["file"] == str(file_path)
    assert result["chunks"] > 0
    assert job.meta.get("progress_percentage") == 100


def test_process_file_job_parquet_new(mocker, db, shared_datadir: Path):
    file_path = shared_datadir / "travel_spend.parquet"

    mocker.patch("worker.vector_db_client")
    mocker.patch("worker.database.get_db", return_value=db)
    job = MagicMock(meta={})
    mocker.patch("worker.get_current_job", return_value=job)

    # Execute
    result = worker.process_file_job(str(file_path))

    # Assertions
    assert result["status"] == "success"
    assert result["file"] == str(file_path)
    assert "chunks" not in result
    assert job.meta.get("progress_percentage") == 100


def test_process_file_job_unsupported_ext(mocker, db):
    mocker.patch("worker.vector_db_client")
    mocker.patch("worker._get_file_hash", return_value="document_hash")
    mocker.patch("worker.database.get_db", return_value=db)
    job = MagicMock(meta={})
    mocker.patch("worker.get_current_job", return_value=job)

    result = worker.process_file_job("unsupported.foo")

    assert result["status"] == "skipped"
