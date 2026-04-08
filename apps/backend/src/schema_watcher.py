import os
import time
import duckdb

from app import logging_config
from app.database import SessionLocal, engine
from app.models import Base, ParquetSchema

# Need to ensure tables exist
Base.metadata.create_all(bind=engine)

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
SLEEP_S = 60


logger = logging_config.setup_logging("nexus-schema-watcher")


def extract_schema(filepath: str) -> str:
    try:
        conn = duckdb.connect(":memory:")
        res = conn.execute(f"DESCRIBE SELECT * FROM '{filepath}'").fetchall()
        cols = [f"{row[0]} ({row[1]})" for row in res]
        return ", ".join(cols)
    except Exception as e:
        logger.error(f"Error extracting schema from {filepath}: {e}", exc_info=True)
        return ""

def watch_directory():
    logger.info(f"Starting schema watcher on {DATA_DIR}...")
    while True:
        if os.path.exists(DATA_DIR):
            files = [f for f in os.listdir(DATA_DIR) if f.endswith(".parquet")]
            
            with SessionLocal() as db:
                # Get existing from DB
                existing_records = db.query(ParquetSchema).all()
                existing_map = {r.table_name: r for r in existing_records}
                
                # Check current files
                current_tables = set()
                for f in files:
                    table_name = f.replace(".parquet", "")
                    current_tables.add(table_name)
                    filepath = os.path.join(DATA_DIR, f)
                    
                    # Update or Create
                    schema_str = extract_schema(filepath)
                    if not schema_str:
                         continue

                    if table_name in existing_map:
                        if existing_map[table_name].columns != schema_str:
                            existing_map[table_name].columns = schema_str
                            db.commit()
                            logger.info(f"Updated schema for {table_name}")
                    else:
                        new_schema = ParquetSchema(
                            table_name=table_name,
                            file_path=filepath,
                            columns=schema_str
                        )
                        db.add(new_schema)
                        db.commit()
                        logger.info(f"Added new schema for {table_name}")
                
                # Delete removed parquets
                for table_name in list(existing_map.keys()):
                    if table_name not in current_tables:
                        db.delete(existing_map[table_name])
                        db.commit()
                        logger.info(f"Deleted schema for {table_name} (file removed)")

        time.sleep(SLEEP_S) # Scan every 1 minute

if __name__ == "__main__":
    watch_directory()
