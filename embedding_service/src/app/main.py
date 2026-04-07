import os
from typing import List, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Embedding Service")

PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "sentence-transformers").lower()
DEVICE = os.environ.get("EMBEDDING_DEVICE", "cpu").lower()

model = None
# Lazy load model depending on provider
@app.on_event("startup")
def load_model():
    global model
    print(f"Loading embedding model with provider: {PROVIDER} on device: {DEVICE}")
    if PROVIDER == "fastembed":
        try:
            from fastembed import TextEmbedding
            # Fastembed only supports CPU officially anyway but this fits the interface
            model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            print("FastEmbed initialized.")
        except ImportError:
            raise RuntimeError("fastembed not installed. Please check requirements.")
    else:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2", device=DEVICE)
            print("SentenceTransformers initialized.")
        except ImportError:
            raise RuntimeError("sentence-transformers not installed. Please check requirements.")

class EmbedRequest(BaseModel):
    text: Union[str, List[str]]

class EmbedResponse(BaseModel):
    embeddings: List[List[float]]

@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest):
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    texts = request.text if isinstance(request.text, list) else [request.text]
    
    if not texts:
         return EmbedResponse(embeddings=[])
         
    try:
        embeddings_list = []
        if PROVIDER == "fastembed":
            # FastEmbed returns a generator of dense vectors
            embeddings = list(model.embed(texts))
            embeddings_list = [emb.tolist() for emb in embeddings]
        else:
            # Sentence-Transformers encode
            embeddings = model.encode(texts)
            embeddings_list = embeddings.tolist()
            
        return EmbedResponse(embeddings=embeddings_list)
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok", "provider": PROVIDER, "device": DEVICE}

@app.get("/metrics")
def metrics():
    # Placeholder for actual Prometheus metrics if needed
    return {}
