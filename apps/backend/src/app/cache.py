import uuid

from networkx.algorithms import threshold

from app.embedding_client import EmbeddingClient
from app.logging_config import logger
from app.vector_db_clients import VectorDBClient, VectorPoint


class SemanticCache:
    def __init__(self, vector_db_client: VectorDBClient, embedding_client: EmbeddingClient, collection_name: str, threshold: float = 0.92):
        self.vector_db_client = vector_db_client
        self.threshold = threshold
        self.embedding_client = embedding_client
        self.collection_name = collection_name

    def get(self, query: str, vector: list[float] | None = None) -> dict:
        """Returns a dict containing 'answer' if cached, or 'error' if retrieval failed."""
        try:
            if vector is None:
                vector = self.embedding_client.embed(query)
            results = self.vector_db_client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=1
            )
            if results and results[0].score >= self.threshold:
                return {"answer": results[0].payload.get("answer"), "error": None}
            return {"answer": None, "error": None}
        except Exception as e:
            return {"answer": None, "error": f"Semantic Cache Error: {e}"}

    def set(self, query: str, answer: str, vector: list[float] | None = None):
        try:
            if vector is None:
                vector = self.embedding_client.embed(query)
            point_id = str(uuid.uuid4())
            self.vector_db_client.upsert(
                collection_name=self.collection_name,
                points=[VectorPoint(
                    id=point_id,
                    vector=vector,
                    payload={"query": query, "answer": answer}
                )]
            )
        except Exception as e:
            # Try to recreate collection once if it's missing (404)
            if "404" in str(e):
                try:
                    self.vector_db_client.upsert(
                        collection_name=self.collection_name,
                        points=[VectorPoint(
                            id=str(uuid.uuid4()),
                            vector=vector,
                            payload={"query": query, "answer": answer}
                        )]
                    )
                    return
                except Exception:
                    pass
            logger.error(f"Failed to save to semantic cache: {e}", exc_info=True)
