from app.embedding_client import EmbeddingClient
from app.logging_config import logger
from app.vector_db_client import VectorDBClient


class Retriever:
    def __init__(self, vector_db_client: VectorDBClient, embedding_client: EmbeddingClient, collection_name: str):
        self.vector_db_client = vector_db_client
        self.embedding_client = embedding_client
        self.collection_name = collection_name

    def search(self, query: str, limit: int = 5, vector: list[float] | None = None):
        if vector is None:
            vector = self.embedding_client.embed(query=query)
        
        try:
            results = self.vector_db_client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit
            )

            if not results:
                return {
                    "context_str": "The search returned 0 results. The database may be empty or the query is too specific.",
                    "sources": []
                }
            
            context_chunks = []
            sources = []
            for result in results:
                payload = result.payload or {}
                text = payload.get("text", "")
                filename = payload.get("filename", "Unknown")
                page = payload.get("page", 1)
                
                context_chunks.append(f"Source: {filename} (Page {page})\n{text}")
                sources.append({
                    "filename": filename,
                    "page": page,
                    "text_snippet": text[:200] + "...",
                    "score": result.score
                })

            return {
                "context_str": "\n\n".join(context_chunks),
                "sources": sources
            }
        except Exception as e:
            # Silence expected 404 if collection hasn't been created by ingest.py yet
            if "404" in str(e):
                return {
                    "context_str": f"ERROR: The document database collection '{self.collection_namec}' does not exist. Please run the ingestion script.",
                    "sources": []
                }
            logger.error(f"Error searching VectorDB (Retriever): {e}", exc_info=True)
            return {"context_str": "", "sources": []}
