import os
from qdrant_client import QdrantClient

from app.embedding_client import EmbeddingClient
from app.logging_config import logger


class Retriever:
    def __init__(self, qdrant_client: QdrantClient, embedding_client: EmbeddingClient):
        self.qdrant_client = qdrant_client
        self.embedding_client = embedding_client
        self.collection_name = "documents"

    def _get_embedding(self, query: str) -> list:
        try:
            response = self.embedding_client.embed(query)
            return response["embeddings"][0]
        except Exception as e:
            logger.error(f"Error calling embedding service: {e}", exc_info=True)
            # Fallback zero vector or raise
            return [0.0] * 384

    def search(self, query: str, limit: int = 5):
        embedding = self._get_embedding(query)
        
        try:
            results = self.qdrant_client.search(
                collection_name=self.collection_name,
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
            logger.error(f"Error searching Qdrant (Retriever): {e}", exc_info=True)
            return {"context_str": "", "sources": []}
