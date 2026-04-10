from app.embedding_client import EmbeddingClient
from app.logging_config import logger
from app.vector_db_clients import VectorDBClient
import duckdb

from app.database import SessionLocal
from app.models import ParquetSchema
import concurrent.futures


class DocumentRetriever:
    def __init__(self, vector_db_client: VectorDBClient, embedding_client: EmbeddingClient, collection_name: str):
        self.vector_db_client = vector_db_client
        self.embedding_client = embedding_client
        self.collection_name = collection_name

    def search(self, query: str, limit: int = 5, vector: list[float] | None = None):
        if vector is None:
            vector = self.embedding_client.embed(query=query)[0]
        
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
                    "context_str": f"ERROR: The document database collection '{self.collection_name}' does not exist. Please run the ingestion script.",
                    "sources": []
                }
            logger.error(f"Error searching VectorDB (Retriever): {e}", exc_info=True)
            return {"context_str": "", "sources": []}


class AnalyticsRetriever:
    def __init__(self, data_dir: str):
        # The primary structured data directory for reading locally stored parquet/csv datasets
        self.data_dir = data_dir
        # Connect to lightweight in-memory DB
        self.conn = duckdb.connect(":memory:")

    def get_schema_context(self) -> str | None:
        """Exposes schema info querying from Postgres ParquetSchema table."""
        try:
            with SessionLocal() as db:
                schemas = db.query(ParquetSchema).all()

                if not schemas:
                    logger.warning(f"{self.__class__.__name__} found no registered schemas.")
                    return None

                schema_lines = ["Available Structured Tables (Parquet Files):"]
                for schema in schemas:
                    schema_lines.append(f"- Table: '{schema.table_name}' at path '{schema.file_path}'")
                    schema_lines.append(f"  Columns: {schema.columns}")

                return "\n".join(schema_lines)
        except Exception as e:
            return f"Error retrieving schemas: {e}"

    def query(self, sql_query: str) -> str:
        """Executes raw DuckDB SQL string safely and returns the Markdown output, shielded by a 5-second Python timeout."""
        logger.info(f"DuckDB Execution: {sql_query}")

        def _execute():
            # Result extraction via Pandas representation is easiest for LLM digestion
            result_df = self.conn.execute(sql_query).df()
            if result_df.empty:
                return "Query executed successfully. 0 rows returned."
            return result_df.to_markdown(index=False)

        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_execute)
                return future.result(timeout=5.0)
        except concurrent.futures.TimeoutError:
            return (
                "DuckDB SQL Execution Error: Operation timed out (exceeded 5 seconds)."
            )
        except Exception as e:
            return f"DuckDB SQL Execution Error: {e}"
