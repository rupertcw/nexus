from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./nexus.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
