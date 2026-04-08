import httpx

from app.errors import EmbeddingServiceError


class EmbeddingClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=timeout)

    def embed(self, query: str) -> list[float]:
        try:
            response = self.client.post(
                f"{self.base_url}/embed",
                json={"text": query},
            )
            response.raise_for_status()
            return response.json()["embeddings"][0]
        except httpx.HTTPStatusError as e:
            # We catch the specific HTTP error and raise our Domain error
            raise EmbeddingServiceError(f"Service returned {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            # Catch timeouts or connection issues
            raise EmbeddingServiceError(f"Could not reach embedding service: {e}")
        except Exception as e:
            # Catch unexpected JSON parsing issues, etc.
            raise EmbeddingServiceError(f"Unexpected embedding error: {e}")
