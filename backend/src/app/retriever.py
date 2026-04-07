import os
import httpx
from qdrant_client import QdrantClient

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
EMBEDDING_API_URL = os.environ.get("EMBEDDING_API_URL", "http://localhost:8001")
COLLECTION_NAME = "documents"

class Retriever:
    def __init__(self):
        # Allow passing qdrant url via env, but don't fail immediately if not available
        self.qdrant = QdrantClient(url=QDRANT_URL)

    def _get_embedding(self, query: str) -> list:
        try:
            response = httpx.post(
                f"{EMBEDDING_API_URL}/embed", 
                json={"text": query},
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()["embeddings"][0]
        except Exception as e:
            print(f"Error calling embedding service: {e}")
            # Fallback zero vector or raise
            return [0.0] * 384

    def search(self, query: str, limit: int = 5):
        embedding = self._get_embedding(query)
        
        try:
            results = self.qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=embedding,
                limit=limit
            )
            
            context_chunks = []
            sources = []
            for r in results:
                payload = r.payload or {}
                text = payload.get("text", "")
                filename = payload.get("filename", "Unknown")
                page = payload.get("page", 1)
                
                context_chunks.append(f"Source: {filename} (Page {page})\n{text}")
                sources.append({
                    "filename": filename,
                    "page": page,
                    "text_snippet": text[:200] + "...",
                    "score": r.score
                })
            
            if not results:
                return {
                    "context_str": "The search returned 0 results. The database may be empty or the query is too specific.",
                    "sources": []
                }

            return {
                "context_str": "\n\n".join(context_chunks),
                "sources": sources
            }
        except Exception as e:
            # Silence expected 404 if collection hasn't been created by ingest.py yet
            if "404" in str(e):
                return {
                    "context_str": "ERROR: The document database collection 'documents' does not exist. Please run the ingestion script.",
                    "sources": []
                }
            print(f"Error searching Qdrant (Retriever): {e}")
            return {"context_str": "", "sources": []}
