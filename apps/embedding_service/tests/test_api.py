import numpy as np
from fastapi.testclient import TestClient

from app.main import app


def test_embed_endpoint(mocker):
    # The global `model` variable drives inference — mock it to avoid loading the real model
    mock_model = mocker.MagicMock()
    mock_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384])
    mocker.patch("app.main.model", mock_model)

    with TestClient(app) as client:
        response = client.post("/embed", json={"text": ["hello", "world"]})

    if response.status_code != 200:
        print(f"DEBUG: Response detail: {response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert "embeddings" in data
    assert len(data["embeddings"]) == 2
    assert len(data["embeddings"][0]) == 384


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_embed_single_string(mocker):
    mock_model = mocker.MagicMock()
    mock_model.encode.return_value = np.array([[0.5] * 384])
    mocker.patch("app.main.model", mock_model)

    with TestClient(app) as client:
        response = client.post("/embed", json={"text": "single input"})

    assert response.status_code == 200
    data = response.json()
    assert len(data["embeddings"]) == 1

