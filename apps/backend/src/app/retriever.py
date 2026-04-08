import os
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance

from app.embedding_client import EmbeddingClient
from app.logging_config import logger


class Retriever:
    def __init__(self, qdrant_client: QdrantClient, embedding_client: EmbeddingClient):
        self.qdrant_client = qdrant_client
        self.embedding_client = embedding_client
        self.collection_name = "documents"
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            collections = [c.name for c in self.qdrant_client.get_collections().collections]

            if self.collection_name not in collections:
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
        except Exception as e:
            logger.error("Failed to initialize semantic cache collection:", e, exc_info=True)

    def search(self, query: str, limit: int = 5, vector: list[float] | None = None):
        if not vector:
            vector = self.embedding_client.embed(query=query)
        
        try:
            results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=vector,
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
            logger.error(f"Error searching Qdrant (Retriever): {e}", exc_info=True)
            return {"context_str": "", "sources": []}
