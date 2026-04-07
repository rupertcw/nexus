import logging
import os
import sys

import httpx
import docx
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http import models
from rq import get_current_job

# Environment config
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
EMBEDDING_API_URL = os.environ.get("EMBEDDING_API_URL", "http://localhost:8001")
COLLECTION_NAME = "documents"

def setup_logging():
    # Use the uvicorn access logger format for consistency
    log_format = "%(levelname)s:     %(asctime)s - %(name)s - %(message)s"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        stream=sys.stdout,
    )

    return logging.getLogger("nexus-ingestion-worker")


# Initialize it
logger = setup_logging()


def get_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + "\n"
    return text


def get_text_from_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])


def chunk_text(text, chunk_size=512, overlap=51):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks


def _get_batch_embeddings(chunks: list[str]) -> list[list[float]]:
    if not chunks:
         return []
    try:
        response = httpx.post(f"{EMBEDDING_API_URL}/embed", json={"text": chunks}, timeout=30.0)
        response.raise_for_status()
        return response.json()["embeddings"]
    except Exception as e:
        logger.error(f"Failed to batch embed: {e}", exc_info=True)
        # Return empty list to signal failure, or zero vectors
        return [[0.0]*384 for _ in chunks]


def process_file_job(file_path: str):
    """Worker task that actually reads, chunks, embeds and inserts document."""
    logger.info(f"Worker Processing: {file_path}")
    job = get_current_job()
    if job:
        job.meta['progress_percentage'] = 0
        job.save_meta()
        
    qdrant = QdrantClient(url=QDRANT_URL)
    
    # Check Qdrant collection lazily
    try:
        qdrant.get_collection(collection_name=COLLECTION_NAME)
    except Exception:
        logger.error(f"Worker creating Qdrant collection: {COLLECTION_NAME}", exc_info=True)
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=384,
                distance=models.Distance.COSINE
            )
        )
    
    file = os.path.basename(file_path)
    if file_path.endswith('.pdf'):
        text = get_text_from_pdf(file_path)
    elif file_path.endswith('.docx'):
        text = get_text_from_docx(file_path)
    elif file_path.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        logger.warning(f"Unsupported extension: {file_path}")
        return {"status": "skipped", "file": file_path}
    
    chunks = chunk_text(text)
    if not chunks:
         return {"status": "success", "file": file_path, "chunks": 0}

    # Batch embeddings for performance (32 at a time)
    batch_size = 32
    docs_inserted = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        embeddings = _get_batch_embeddings(batch)
        
        points = []
        for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
            chunk_idx = i + j
            points.append(
                models.PointStruct(
                    id=hash(file_path + str(chunk_idx)) % ((1<<63)-1), 
                    vector=emb,
                    payload={
                        "filename": file,
                        "page": chunk_idx + 1,
                        "text": chunk
                    }
                )
            )
            
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        docs_inserted += len(points)
        
        if job:
            job.meta['progress_percentage'] = int((i / len(chunks)) * 100)
            job.save_meta()

    if job:
        job.meta['progress_percentage'] = 100
        job.save_meta()

    logger.info(f"Worker Finished {file_path}: inserted {docs_inserted} chunks.")
    return {"status": "success", "file": file_path, "chunks": docs_inserted}
