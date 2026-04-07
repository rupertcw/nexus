import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from app.embedding_client import EmbeddingClient
from app.logging_config import logger


class SemanticCache:
    def __init__(self, qdrant_client: QdrantClient, embedding_client: EmbeddingClient):
        self.qdrant_client = qdrant_client
        # Ensure identical or highly confident (0.92 Cosine Similarity) prompts are intercepted!
        self.threshold = float(os.environ.get("CACHE_THRESHOLD", "0.92"))
        self.embedding_client = embedding_client
        self.collection_name = "semantic_cache"
        self._ensure_collection()

    def _ensure_collection(self):
        clear_on_start = os.environ.get("NEXUS_CLEAR_CACHE_ON_START", "false").lower() == "true"
        try:
            collections = [c.name for c in self.qdrant_client.get_collections().collections]
            
            # If specified, purge existing cache for local debug or fresh deployment logic
            if clear_on_start and self.collection_name in collections:
                logger.info(f"NEXUS_CLEAR_CACHE_ON_START=true: Purging collection {self.collection_name}")
                self.qdrant_client.delete_collection(self.collection_name)
                collections.remove(self.collection_name)

            if self.collection_name not in collections:
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
        except Exception as e:
            logger.error("Failed to initialize semantic cache collection:", e, exc_info=True)

    def _get_embedding(self, query: str) -> list:
        try:
            response = self.embedding_client.embed(query)
            return response["embeddings"][0]
        except Exception as e:
            logger.error(f"Failed to get cache embedding: {e}", exc_info=True)
            raise

    def get(self, query: str) -> dict:
        """Returns a dict containing 'answer' if cached, or 'error' if retrieval failed."""
        try:
            embedding = self._get_embedding(query)
            results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=embedding,
                limit=1
            )
            if results and results[0].score >= self.threshold:
                return {"answer": results[0].payload.get("answer"), "error": None}
            return {"answer": None, "error": None}
        except Exception as e:
            return {"answer": None, "error": f"Semantic Cache Error: {e}"}

    def set(self, query: str, answer: str):
        try:
            embedding = self._get_embedding(query)
            point_id = str(uuid.uuid4())
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={"query": query, "answer": answer}
                )]
            )
        except Exception as e:
            # Try to recreate collection once if it's missing (404)
            if "404" in str(e):
                self._ensure_collection()
                try:
                    self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=[PointStruct(
                            id=str(uuid.uuid4()),
                            vector=embedding,
                            payload={"query": query, "answer": answer}
                        )]
                    )
                    return
                except Exception:
                    pass
            logger.error("Failed to save to semantic cache:", e, exc_info=True)
