from unittest.mock import MagicMock

import fakeredis
import pytest
from _pytest.monkeypatch import MonkeyPatch
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from rq import Queue
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from qdrant_client import QdrantClient

from app.agent import AgentRouter
from app.cache import SemanticCache
from app.database import Base, get_db
from app.duckdb_engine import DuckDBEngine
from app.embedding_client import EmbeddingClient
from app.main import app
from app.auth import verify_token
from app.retriever import Retriever

# Setup In-Memory SQLite Database for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def override_auth(request):
    app.dependency_overrides[verify_token] = lambda: {"user_id": 1, "sub": "test_user"}
    yield
    app.dependency_overrides.pop(verify_token, None)


def patch_dependencies(monkeypatch: MonkeyPatch, embedding_client: EmbeddingClient, duckdb_engine: DuckDBEngine | None = None):
    qdrant_client = QdrantClient(location=":memory:")
    cache = SemanticCache(qdrant_client=qdrant_client, embedding_client=embedding_client)
    monkeypatch.setattr("app.main.semantic_cache", cache)
    retriever = Retriever(qdrant_client=qdrant_client, embedding_client=embedding_client)
    monkeypatch.setattr("app.main.retriever", retriever)
    agent_router = AgentRouter(retriever=retriever, duckdb_engine=duckdb_engine or DuckDBEngine())
    monkeypatch.setattr("app.main.agent_router", agent_router)


@pytest.fixture
def fake_redis_conn():
    return fakeredis.FakeStrictRedis()


@pytest.fixture
def fake_queue(fake_redis_conn: FakeStrictRedis) -> Queue:
    return Queue(connection=fake_redis_conn)
