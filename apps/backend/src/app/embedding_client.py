import httpx

from app.errors import EmbeddingServiceError


class EmbeddingClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.timeout = timeout
        self.client = httpx.Client(base_url=base_url, timeout=timeout)

    def embed(self, query: str, timeout: float | int | None = None) -> list[list[float]]:
        timeout = timeout if timeout is not None else self.timeout

        try:
            response = self.client.post(
                f"{self.client.base_url}/embed",
                json={"text": query},
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()["embeddings"]
        except httpx.HTTPStatusError as e:
            # We catch the specific HTTP error and raise our Domain error
            raise EmbeddingServiceError(f"Service returned {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            # Catch timeouts or connection issues
            raise EmbeddingServiceError(f"Could not reach embedding service: {e}")
        except Exception as e:
            # Catch unexpected JSON parsing issues, etc.
            raise EmbeddingServiceError(f"Unexpected embedding error: {e}")
