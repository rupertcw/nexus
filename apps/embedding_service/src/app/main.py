import os
from contextlib import asynccontextmanager
from typing import List, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.logging_config import logger

PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "sentence-transformers").lower()
DEVICE = os.environ.get("EMBEDDING_DEVICE", "cpu").lower()

model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Startup")
    global model
    logger.info(f"Loading embedding model with provider: {PROVIDER} on device: {DEVICE}")
    if PROVIDER == "fastembed":
        try:
            from fastembed import TextEmbedding
            # Fastembed only supports CPU officially anyway but this fits the interface
            model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            logger.info("FastEmbed initialized.")
        except ImportError:
            raise RuntimeError("fastembed not installed. Please check requirements.")
    else:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2", device=DEVICE)
            logger.info("SentenceTransformers initialized.")
        except ImportError:
            raise RuntimeError("sentence-transformers not installed. Please check requirements.")
    yield
    # Shutdown logic
    logger.info("Shutdown")


app = FastAPI(title="Embedding Service", lifespan=lifespan)


class EmbedRequest(BaseModel):
    text: Union[str, List[str]]

class EmbedResponse(BaseModel):
    embeddings: List[List[float]]

@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest):
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    texts = request.text if isinstance(request.text, list) else [request.text]
    logger.info(f"Queries: {texts}")
    
    if not texts:
        logger.info("No queries provided")
        return EmbedResponse(embeddings=[])
         
    try:
        if PROVIDER == "fastembed":
            logger.info(f"Using `fastembed` provider")
            # FastEmbed returns a generator of dense vectors
            embeddings = list(model.embed(texts))
            logger.info(f"Created embeddings: {embeddings}")
            embeddings_list = [emb.tolist() for emb in embeddings]
            logger.info(f"Converted embeddings to lists: {embeddings}")
        else:
            logger.info(f"Using `sentence-transformer` provider")
            # Sentence-Transformers encode
            embeddings = model.encode(texts)
            logger.info(f"Created embeddings: {embeddings}")
            embeddings_list = embeddings.tolist()
            logger.info(f"Converted embeddings to lists: {embeddings}")
            
        return EmbedResponse(embeddings=embeddings_list)
    except Exception as e:
        logger.exception(f"Failed to create embeddings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "provider": PROVIDER, "device": DEVICE}


@app.get("/metrics")
def metrics():
    # Placeholder for actual Prometheus metrics if needed
    return {}
