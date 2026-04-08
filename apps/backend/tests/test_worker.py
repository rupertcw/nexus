from unittest.mock import MagicMock

import worker


def test_process_file_job_pdf(mocker):
    # 1. Mock DB client
    mocker.patch("worker.vector_db_client")

    # 2. Mock Internal Function dependencies
    mocker.patch(
        "worker.get_text_from_pdf", return_value="Mock documentation chunk. " * 50
    )

    # 3. Mock External API IO (Embedding Service)
    mock_embedding_client = mocker.patch("worker.embedding_client")
    mock_embedding_client.embed.return_value = [[0.1] * 384, [0.2] * 384]

    # 4. Mock the active RQ context (Progress monitoring)
    mock_job_func = mocker.patch("worker.get_current_job")
    mock_job = MagicMock()
    mock_job.meta = {}
    mock_job_func.return_value = mock_job

    # Execute
    result = worker.process_file_job("dummy_path.pdf")

    # Assertions
    assert result["status"] == "success"
    assert result["file"] == "dummy_path.pdf"
    assert result["chunks"] > 0
    assert mock_job.meta.get("progress_percentage") == 100


def test_process_file_job_unsupported_ext(mocker):
    mocker.patch("worker.vector_db_client")
    result = worker.process_file_job("unsupported.jpg")
    assert result["status"] == "skipped"
