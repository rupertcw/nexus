import os
import duckdb


class DuckDBEngine:
    def __init__(self, data_dir: str):
        # The primary structured data directory for reading locally stored parquet/csv datasets
        self.data_dir = data_dir
        # Connect to lightweight in-memory DB
        self.conn = duckdb.connect(":memory:")

    def get_schema_context(self) -> str:
        """Exposes schema info querying from Postgres ParquetSchema table."""
        from app.database import SessionLocal
        from app.models import ParquetSchema

        try:
            with SessionLocal() as db:
                schemas = db.query(ParquetSchema).all()
                
                if not schemas:
                    return "No structured data tables available."
                    
                schema_lines = ["Available Structured Tables (Parquet Files):"]
                for schema in schemas:
                    schema_lines.append(f"- Table: '{schema.table_name}' at path '{schema.file_path}'")
                    schema_lines.append(f"  Columns: {schema.columns}")
                    
                return "\n".join(schema_lines)
        except Exception as e:
            return f"Error retrieving schemas: {e}"

    def query(self, sql_query: str) -> str:
        """Executes raw DuckDB SQL string safely and returns the Markdown output, shielded by a 5-second Python timeout."""
        import concurrent.futures
        import logging

        logger = logging.getLogger(__name__)
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
