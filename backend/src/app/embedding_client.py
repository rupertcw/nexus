import httpx


class EmbeddingClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def embed(self, query: str, timeout: int | float = 10.0) -> dict:
        response = httpx.post(
            f"{self.base_url}/embed",
            json={"text": query},
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
