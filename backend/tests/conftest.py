import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.llm import DummyLLM

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


class MockRetriever:
    def search(self, query: str, limit: int = 5):
        return {
            "context_str": "Source: MockDoc.pdf (Page 1)\nThis is mocked info.",
            "sources": [
                {
                    "filename": "MockDoc.pdf",
                    "page": 1,
                    "text_snippet": "This is mocked info.",
                    "score": 0.99,
                }
            ],
        }


@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    """Mock out LLM and Retriever across all tests so we don't hit Qdrant or Anthropic"""
    # Create the mocked instances
    mocked_retriever = MockRetriever()
    mocked_llm = DummyLLM()

    # Patch the main module's actual instances
    monkeypatch.setattr("app.main.retriever", mocked_retriever)
    monkeypatch.setattr("app.main.llm", mocked_llm)
