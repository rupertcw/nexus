import os
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.responses import JSONResponse
from rq import Worker
from rq.job import Job
from rq.registry import FinishedJobRegistry, StartedJobRegistry, FailedJobRegistry

from app import vector_db_clients
from app.database import Base, engine, get_db
from app.embedding_client import EmbeddingClient
from app.errors import EmbeddingServiceError
from app.models import Session as ChatSession, Message
from app.retriever import Retriever
from app.duckdb_engine import DuckDBEngine
from app.cache import SemanticCache
from app.agent import AgentRouter
from app.auth import verify_token
from app.logging_config import logger

SEMANTIC_CACHE_COLLECTION_NAME = "semantic_cache"
DOCUMENTS_COLLECTION_NAME = "documents"
DOCUMENTS_PATH = os.environ.get("DOCUMENTS_PATH", "/documents")

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Startup")
    vector_db_client.initialize()
    instrumentator.expose(app, endpoint="/metrics")

    yield

    logger.info("Shutdown")


app = FastAPI(title="AI Knowledge Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus instrumentation
instrumentator = Instrumentator().instrument(app)

redis_conn = Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
task_queue = Queue(connection=redis_conn)

# Global Instance Initializations mapped across routes
vector_db_client = vector_db_clients.get(
    provider="qdrant",
    url=os.environ.get("VECTOR_DB_URL", "http://localhost:6333"),
    collection_names=[SEMANTIC_CACHE_COLLECTION_NAME, DOCUMENTS_COLLECTION_NAME],
)
embedding_client = EmbeddingClient(
    base_url=os.environ.get("EMBEDDING_API_URL", "http://localhost:8001")
)
semantic_cache = SemanticCache(
    vector_db_client=vector_db_client,
    embedding_client=embedding_client,
    collection_name=SEMANTIC_CACHE_COLLECTION_NAME,
    threshold=float(os.environ.get("CACHE_THRESHOLD", "0.92"))
)
retriever = Retriever(
    vector_db_client=vector_db_client,
    embedding_client=embedding_client,
    collection_name=DOCUMENTS_COLLECTION_NAME
)
duckdb_engine = DuckDBEngine(data_dir=os.environ.get("DATA_DIR", "/app/data"))
agent_router = AgentRouter(retriever=retriever, duckdb_engine=duckdb_engine)


@app.exception_handler(EmbeddingServiceError)
async def embedding_exception_handler(request: Request, exc: EmbeddingServiceError):
    # Log it once in a central place
    logger.error(f"Global Embedding Failure: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": "AI processing is temporarily unavailable. Please try again later."},
    )


class ChatRequest(BaseModel):
    session_id: int
    message: str


class IngestJobRequest(BaseModel):
    file_path: str


@app.post("/sessions")
def create_session(
    db: Session = Depends(get_db), _token_validation=Depends(verify_token)
):
    db_session = ChatSession(title="New Chat")
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


@app.get("/sessions")
def get_sessions(
    db: Session = Depends(get_db), _token_validation=Depends(verify_token)
):
    return db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()


@app.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    _token_validation=Depends(verify_token),
):
    db_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(db_session)
    db.commit()
    return {"message": "Session deleted"}


@app.get("/sessions/{session_id}/messages")
def get_messages(
    session_id: int,
    db: Session = Depends(get_db),
    _token_validation=Depends(verify_token),
):
    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    res = []
    for msg in messages:
        sources_list = []
        if msg.sources:
            try:
                sources_list = json.loads(msg.sources)
            except Exception:
                pass
        res.append(
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "sources": sources_list,
                "created_at": msg.created_at,
            }
        )
    return res


@app.post("/chat")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    _token_validation=Depends(verify_token),
):
    session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = Message(session_id=session.id, role="user", content=request.message)
    db.add(user_msg)
    db.commit()

    # Name chat session after first user message
    if db.query(Message).filter(Message.session_id == session.id).count() <= 1:
        session.title = request.message[:30] + (
            "..." if len(request.message) > 30 else ""
        )
        db.add(session)

    vector = embedding_client.embed(query=request.message)[0]

    sources = []

    # 1. Semantic Cache Interception
    cache_result = semantic_cache.get(request.message, vector=vector)
    cached_answer = cache_result.get("answer")
    cache_error = cache_result.get("error")

    if cache_error:
        # User requested to see semantic cache errors bubbled up in UI
        sources.append(
            {
                "filename": "System: Cache Alert",
                "text_snippet": f"WARNING: {cache_error}",
                "page": "N/A",
                "score": 0.0,
            }
        )

    if cached_answer:
        response_text = cached_answer
        sources.append(
            {
                "filename": "Semantic Cache (Cosine > 0.92)",
                "text_snippet": "Bypassed LLM Agent generation for latency.",
                "page": "N/A",
                "score": 1.0,
            }
        )
    else:
        # 2. Hybrid Agent Execution
        agent_result = agent_router.run(request.message, vector=vector)
        response_text = agent_result["response"]
        sources.extend(agent_result["sources"])

        # 3. Store new reasoning back into Cache
        semantic_cache.set(request.message, response_text, vector=vector)

    asst_msg = Message(
        session_id=session.id,
        role="assistant",
        content=response_text,
        sources=json.dumps(sources),
    )
    db.add(asst_msg)
    db.commit()

    return {"response": response_text, "sources": sources}


@app.post("/ingestion/jobs")
def create_ingestion_job(
    request: IngestJobRequest, _token_validation=Depends(verify_token)
):
    logger.debug(f"Current working directory: {os.getcwd()}")
    if not Path(DOCUMENTS_PATH).exists():
        raise HTTPException(
            status_code=400, detail=f"Documents path `{DOCUMENTS_PATH}` does not exist on server."
        )
    logger.debug(f"Contents of {DOCUMENTS_PATH}: {os.listdir(DOCUMENTS_PATH)}")
    if not Path(request.file_path).exists():
        raise HTTPException(
            status_code=400, detail="File path does not exist on server."
        )

    job = task_queue.enqueue(
        "worker.process_file_job", request.file_path, job_timeout="1h"
    )
    return JSONResponse(status_code=201, content={"job_id": job.id, "status": job.get_status()})


@app.get("/ingestion/jobs/{job_id}")
def get_ingestion_job_status(job_id: str, _token_validation=Depends(verify_token)):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return {
            "job_id": job.id,
            "status": job.get_status(),
            "result": job.return_value(),
            "error": job.latest_result(),
        }
    except Exception:
        raise HTTPException(status_code=404, detail="Job not found")


@app.post("/ingestion/jobs/batch")
def create_batch_ingestion_jobs(
    _token_validation=Depends(verify_token)
):
    """Scan the root documents directory and enqueue all valid files."""
    if not Path(DOCUMENTS_PATH).exists():
        raise HTTPException(
            status_code=500, detail=f"Server data mount `{DOCUMENTS_PATH}` is missing."
        )

    batch_id = str(uuid.uuid4())

    files_to_process = []
    for root, _, files in os.walk(DOCUMENTS_PATH):
        for file in files:
            if file.endswith(('.pdf', '.docx', '.txt')):
                file_path = os.path.join(root, file)
                files_to_process.append(file_path)

    total_count = len(files_to_process)

    redis_conn.hset(f"batch:{batch_id}", mapping={
        "total": total_count,
        "completed": 0,
        "failed": 0,
        "status": "processing"
    })

    for file_path in files_to_process:
        task_queue.enqueue(
            "worker.process_file_job",
            file_path,
            job_timeout="1h",
            meta={'batch_id': batch_id}
        )

    return JSONResponse(
        status_code=201,
        content={
            "status": "batch_accepted",
            "batch_id": batch_id,
            "job_count": total_count,
        }
    )


@app.get("/ingestion/batches/{batch_id}")
def get_batch_status(batch_id: str):
    batch_data = redis_conn.hgetall(f"batch:{batch_id}")

    if not batch_data:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Convert bytes from Redis to strings/ints
    total = int(batch_data.get(b'total', 0))
    completed = int(batch_data.get(b'completed', 0))

    progress = (completed / total * 100) if total > 0 else 0

    return {
        "batch_id": batch_id,
        "status": batch_data.get(b'status').decode(),
        "progress": f"{progress:.2f}%",
        "details": {
            "total": total,
            "completed": completed,
            "failed": int(batch_data.get(b'failed', 0))
        }
    }


@app.get("/ingestion/jobs")
def get_all_jobs(_token_validation=Depends(verify_token)):
    jobs_data = []

    def _fetch_registry(registry, status):
        for jid in registry.get_job_ids():
            try:
                job = Job.fetch(jid, connection=redis_conn)
                jobs_data.append(
                    {
                        "id": job.id,
                        "status": status,
                        "created_at": getattr(
                            job, "enqueued_at", getattr(job, "created_at", None)
                        ),
                        "file": job.args[0] if job.args else "Unknown",
                        "progress": job.meta.get("progress_percentage", 0),
                        "error": job.exc_info,
                    }
                )
            except Exception:
                pass

    _fetch_registry(StartedJobRegistry(queue=task_queue), "started")
    _fetch_registry(FinishedJobRegistry(queue=task_queue), "finished")
    _fetch_registry(FailedJobRegistry(queue=task_queue), "failed")

    for jid in task_queue.job_ids:
        try:
            job = task_queue.fetch_job(jid)
            if job:
                jobs_data.append(
                    {
                        "id": job.id,
                        "status": "queued",
                        "created_at": getattr(
                            job, "enqueued_at", getattr(job, "created_at", None)
                        ),
                        "file": job.args[0] if job.args else "Unknown",
                        "progress": 0,
                        "error": None,
                    }
                )
        except Exception:
            pass

    return sorted(jobs_data, key=lambda x: str(x["created_at"]), reverse=True)


@app.get("/ingestion/stats")
def get_ingestion_stats(_token_validation=Depends(verify_token)):
    workers = Worker.all(connection=redis_conn)
    return {
        "active_workers": len(workers),
        "queued": len(task_queue),
        "active": len(StartedJobRegistry(queue=task_queue)),
        "finished": len(FinishedJobRegistry(queue=task_queue)),
        "failed": len(FailedJobRegistry(queue=task_queue)),
    }


@app.post("/ingestion/jobs/{job_id}/retry")
def retry_failed_job(job_id: str, _token_validation=Depends(verify_token)):
    registry = FailedJobRegistry(queue=task_queue)
    if job_id not in registry.get_job_ids():
        raise HTTPException(status_code=404, detail="Failed job not found")

    registry.requeue(job_id)
    return {"message": "Job requeued successfully"}
