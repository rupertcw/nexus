import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
CACHE_COLLECTION = "semantic_cache"

class SemanticCache:
    def __init__(self):
        self.qdrant = QdrantClient(url=QDRANT_URL)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        # Ensure identical or highly confident (0.92 Cosine Similarity) prompts are intercepted!
        self.threshold = float(os.environ.get("CACHE_THRESHOLD", "0.92"))
        self._ensure_collection()

    def _ensure_collection(self):
        clear_on_start = os.environ.get("NEXUS_CLEAR_CACHE_ON_START", "false").lower() == "true"
        try:
            collections = [c.name for c in self.qdrant.get_collections().collections]
            
            # If specified, purge existing cache for local debug or fresh deployment logic
            if clear_on_start and CACHE_COLLECTION in collections:
                print(f"NEXUS_CLEAR_CACHE_ON_START=true: Purging collection {CACHE_COLLECTION}")
                self.qdrant.delete_collection(CACHE_COLLECTION)
                collections.remove(CACHE_COLLECTION)

            if CACHE_COLLECTION not in collections:
                self.qdrant.create_collection(
                    collection_name=CACHE_COLLECTION,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
        except Exception as e:
            print("Failed to initialize semantic cache collection:", e)

    def get(self, query: str) -> dict:
        """Returns a dict containing 'answer' if cached, or 'error' if retrieval failed."""
        try:
            embedding = self.model.encode(query).tolist()
            results = self.qdrant.search(
                collection_name=CACHE_COLLECTION,
                query_vector=embedding,
                limit=1
            )
            if results and results[0].score >= self.threshold:
                return {"answer": results[0].payload.get("answer"), "error": None}
            return {"answer": None, "error": None}
        except Exception as e:
            # Silence expected 404s but return formatted error for UI
            if "404" in str(e):
                return {"answer": None, "error": "Semantic Cache collection 'semantic_cache' does not exist yet."}
            return {"answer": None, "error": f"Semantic Cache Error: {e}"}

    def set(self, query: str, answer: str):
        try:
            embedding = self.model.encode(query).tolist()
            point_id = str(uuid.uuid4())
            self.qdrant.upsert(
                collection_name=CACHE_COLLECTION,
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
                    self.qdrant.upsert(
                        collection_name=CACHE_COLLECTION,
                        points=[PointStruct(
                            id=str(uuid.uuid4()),
                            vector=embedding,
                            payload={"query": query, "answer": answer}
                        )]
                    )
                    return
                except Exception:
                    pass
            print("Failed to save to semantic cache:", e)
