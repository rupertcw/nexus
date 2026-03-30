import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "documents"

class Retriever:
    def __init__(self):
        # Allow passing qdrant url via env, but don't fail immediately if not available
        self.qdrant = QdrantClient(url=QDRANT_URL)
        # Using a fast embedding model that matches 384 dimensions
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def search(self, query: str, limit: int = 5):
        embedding = self.model.encode(query).tolist()
        
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
            
            return {
                "context_str": "\n\n".join(context_chunks),
                "sources": sources
            }
        except Exception as e:
            print(f"Error searching Qdrant: {e}")
            return {"context_str": "", "sources": []}
