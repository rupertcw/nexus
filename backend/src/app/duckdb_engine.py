import os
import duckdb


class DuckDBEngine:
    def __init__(self):
        # The primary structured data directory for reading locally stored parquet/csv datasets
        self.data_dir = os.environ.get("DATA_DIR", "/app/data")

        # Connect to lightweight in-memory DB
        self.conn = duckdb.connect(":memory:")

    def get_schema_context(self) -> str:
        """Exposes schema info of all mounted parquets so the Agent can dynamically form queries."""
        if not os.path.exists(self.data_dir):
            return "No parquet files found."

        files = [f for f in os.listdir(self.data_dir) if f.endswith(".parquet")]
        if not files:
            return "No parquet files found."

        schema_lines = ["Available Structured Tables (Parquet Files):"]
        for f in files:
            table_name = f.replace(".parquet", "")
            filepath = os.path.join(self.data_dir, f)
            try:
                # Query table headers explicitly
                res = self.conn.execute(
                    f"DESCRIBE SELECT * FROM '{filepath}'"
                ).fetchall()
                cols = [f"{row[0]} ({row[1]})" for row in res]
                schema_lines.append(f"- Table: '{table_name}' at path '{filepath}'")
                schema_lines.append(f"  Columns: {', '.join(cols)}")
            except Exception as e:
                schema_lines.append(
                    f"- Table: '{table_name}' (Error reading schema: {e})"
                )

        return "\n".join(schema_lines)

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
