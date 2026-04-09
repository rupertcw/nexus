import os
import uuid

import docx
from pypdf import PdfReader
from rq import get_current_job
from rq.job import Job

import app.main
from app import logging_config
from app.main import vector_db_client, embedding_client
from app.vector_db_clients import VectorPoint

logger = logging_config.setup_logging("nexus-ingestion-worker")


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
        return embedding_client.embed(chunks, timeout=30.0)
    except Exception as e:
        logger.error(f"Failed to batch embed: {e}", exc_info=True)
        # Return empty list to signal failure, or zero vectors
        return [[0.0]*384 for _ in chunks]


def _update_batch_status(job: Job, status: str):
    if job and (batch_id := job.meta.get("batch_id")):
        job.connection.hincrby(f"batch:{batch_id}", status, 1)
        data = job.connection.hgetall(f"batch:{batch_id}")
        if int(data[b'completed']) + int(data[b'failed']) >= int(data[b'total']):
            job.connection.hset(f"batch:{batch_id}", "status", "finished")


def process_file_job(file_path: str):
    """Worker task that actually reads, chunks, embeds and inserts document."""
    logger.info(f"Worker Processing: {file_path}")
    collection_name = app.main.DOCUMENTS_COLLECTION_NAME
    job = get_current_job()

    if job:
        job.meta['progress_percentage'] = 0
        job.save_meta()

    try:
        vector_db_client.get_collection(collection_name=collection_name)
    except Exception:
        logger.error(f"Worker creating Qdrant collection: {collection_name}", exc_info=True)
        vector_db_client.create_collection(collection_name=collection_name)
    
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
        _update_batch_status(job, "completed")
        return {"status": "success", "file": file_path, "chunks": 0}

    # Batch embeddings for performance (32 at a time)
    batch_size = 32
    docs_inserted = 0

    try:
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            embeddings = _get_batch_embeddings(batch)

            points = []
            for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
                chunk_idx = i + j
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{file_path}_{chunk_idx}"))
                points.append(
                    VectorPoint(
                        id=point_id,
                        vector=emb,
                        payload={
                            "filename": file,
                            "page": chunk_idx + 1,
                            "text": chunk
                        }
                    )
                )

            vector_db_client.upsert(collection_name=collection_name, points=points)
            docs_inserted += len(points)

            if job:
                job.meta['progress_percentage'] = int((i / len(chunks)) * 100)
                job.save_meta()
    except Exception as e:
        _update_batch_status(job, "failure")
        logger.error(f"Worker Error: {e}", exc_info=True)

    if job:
        job.meta['progress_percentage'] = 100
        job.save_meta()

    _update_batch_status(job, "completed")

    logger.info(f"Worker Finished {file_path}: inserted {docs_inserted} chunks.")
    return {"status": "success", "file": file_path, "chunks": docs_inserted}
