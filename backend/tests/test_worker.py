from unittest.mock import MagicMock

# Import the worker functions directly
import worker


def test_process_file_job_pdf(mocker):
    # 1. Mock DB IO (Qdrant)
    mocker.patch("worker.QdrantClient")

    # 2. Mock Internal Function dependencies
    mocker.patch(
        "worker.get_text_from_pdf", return_value="Mock documentation chunk. " * 50
    )

    # 3. Mock External API IO (Embedding Service)
    mock_httpx = mocker.patch("worker.httpx.post")
    mock_httpx.return_value.json.return_value = {
        "embeddings": [[0.1] * 384, [0.2] * 384]
    }
    mock_httpx.return_value.status_code = 200

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
    mocker.patch("worker.QdrantClient")
    result = worker.process_file_job("unsupported.jpg")
    assert result["status"] == "skipped"
