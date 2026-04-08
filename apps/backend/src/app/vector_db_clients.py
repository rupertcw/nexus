from abc import abstractmethod, ABCMeta
from functools import wraps
from typing import Sequence

import numpy as np
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, PointStruct

from app.logging_config import logger
from typing import Any

class VectorPoint(BaseModel):
    id: str
    vector: list[float]
    payload: dict[str, Any] | None


VectorPoints = list[VectorPoint]


def ensure_collection_exists(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        collection_name = kwargs.get("collection_name") or (args[0] if args else None)

        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                logger.warning(f"Collection `{collection_name}` missing. Attempting recovery...")

                self.create_collection(
                    collection_name=collection_name,
                    vectors_config=self.collection_vector_config
                )

                return func(self, *args, **kwargs)

            raise e

    return wrapper


class VectorDBClient(metaclass=ABCMeta):
    @abstractmethod
    def initialize(self):
        """Perform startup checks, like ensuring collections exist."""
        pass

    @abstractmethod
    def get_collections(self, **kwargs: Any):
        pass

    @abstractmethod
    def create_collection(self, collection_name: str, vectors_config: VectorParams) -> bool:
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str, timeout: int | None = None, **kwargs: Any) -> bool:
        pass

    @abstractmethod
    def search(
        self,
        collection_name: str,
        query_vector: np.typing.NDArray | Sequence[float] | tuple[str, list[float]],
        limit: int = 10,
        timeout: int | None = None,
        **kwargs: Any
    ):
        pass

    @abstractmethod
    def upsert(
        self,
        collection_name: str,
        points: VectorPoints,
        wait: bool = True,
        **kwargs: Any,
    ):
        pass


class QdrantVectorDBClient(VectorDBClient):
    def __init__(self, url: str, collection_names: list[str], collection_vector_config: VectorParams | None = None):
        self.url = url
        if url == ":memory:":
            self.client = QdrantClient(location=url)
        else:
            self.client = QdrantClient(url=url)
        self.collection_names = collection_names
        self.collection_vector_config = collection_vector_config or VectorParams(size=384, distance=Distance.COSINE)

    def initialize(self):
        existing_collection_names = {c.name for c in self.get_collections().collections}
        for collection_name in self.collection_names:
            if collection_name not in existing_collection_names:
                try:
                    self.create_collection(
                        collection_name=collection_name,
                        vectors_config=self.collection_vector_config,
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize `{collection_name}` collection: {e}", exc_info=True)

    def get_collections(self, **kwargs: Any):
        return self.client.get_collections(**kwargs)

    def create_collection(self, collection_name: str, vectors_config: VectorParams | None = None) -> bool:
        return self.client.create_collection(collection_name=collection_name, vectors_config=vectors_config or self.collection_vector_config)

    def delete_collection(self, collection_name: str, timeout: int | None = None, **kwargs: Any) -> bool:
        return self.client.delete_collection(**kwargs)

    @ensure_collection_exists
    def search(
        self,
        collection_name: str,
        query_vector: np.typing.NDArray | Sequence[float] | tuple[str, list[float]],
        limit: int = 10,
        timeout: int | None = None,
        **kwargs: Any
    ):
        return self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            timeout=timeout,
            **kwargs
        )

    @ensure_collection_exists
    def upsert(
        self,
        collection_name: str,
        points: VectorPoints,
        wait: bool = True,
        **kwargs: Any,
    ):
        qdrant_points = [
            PointStruct(
                id=p.id,
                vector=p.vector,
                payload=p.payload
            ) for p in points
        ]
        return self.client.upsert(
            collection_name=collection_name,
            points=qdrant_points,
            wait=wait,
            **kwargs,
        )


PROVIDERS: dict[str, type[VectorDBClient]] = {
    "qdrant": QdrantVectorDBClient,
}

def get(provider: str, **kwargs) -> VectorDBClient:
    """The public factory for this namespace."""

    client_cls = PROVIDERS.get(provider.lower())
    if not client_cls:
        valid_options = ", ".join(PROVIDERS.keys())
        raise ValueError(
            f"Unknown Vector DB provider '{provider}'. "
            f"Available options are: {valid_options}"
        )

    return client_cls(**kwargs)
