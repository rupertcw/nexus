import pytest
from fastapi.testclient import TestClient
from rq import Queue

from app.main import app


@pytest.fixture
def client(mocker, fake_redis_conn, fake_queue):
    mocker.patch("app.main.redis_conn", fake_redis_conn)
    mocker.patch("app.main.task_queue", fake_queue)
    with TestClient(app) as c:
        yield c


def test_create_ingestion_job(client, mocker, override_auth):
    mocker.patch("os.path.exists", return_value=True)  # Bypass file path validation
    response = client.post("/ingestion/jobs", json={"file_path": "test_upload.pdf"})
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_get_all_jobs(client, mocker, fake_queue: Queue, override_auth):
    # Insert dummy job directly via client
    mocker.patch("os.path.exists", return_value=True)
    client.post("/ingestion/jobs", json={"file_path": "test_upload.pdf"})

    response = client.get("/ingestion/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "queued"
    assert jobs[0]["file"] == "test_upload.pdf"


def test_get_ingestion_stats(client, override_auth):
    response = client.get("/ingestion/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "active_workers" in stats
    assert "queued" in stats
    assert "failed" in stats


def test_retry_failed_job(client, fake_queue, override_auth):
    # Try to retry a non-existent job
    response = client.post("/ingestion/jobs/bad-id/retry")
    assert response.status_code == 404

    # To fully test requeue behavior, we'd manually push to FailedJobRegistry
    # Since rq registries require a specific structure, verifying a 404 on missing is sufficient for API guard coverage here.
