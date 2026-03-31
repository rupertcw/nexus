import json
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Session as ChatSession, Message
from app.retriever import Retriever
from app.duckdb_engine import DuckDBEngine
from app.cache import SemanticCache
from app.agent import AgentRouter
from app.auth import verify_token

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Knowledge Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Instance Initializations mapped across routes
retriever = Retriever()
duckdb_engine = DuckDBEngine()
semantic_cache = SemanticCache()
agent_router = AgentRouter(retriever=retriever, duckdb_engine=duckdb_engine)


class ChatRequest(BaseModel):
    session_id: int
    message: str


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
    db_session = (
        db.query(ChatSession).filter(ChatSession.id == session_id).first()
    )
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

    # --- Phase 2: Orchestration Pipeline ---

    sources = []

    # 1. Semantic Cache Interception
    cache_result = semantic_cache.get(request.message)
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
        agent_result = agent_router.run(request.message)
        response_text = agent_result["response"]
        sources.extend(agent_result["sources"])

        # 3. Store new reasoning back into Cache
        semantic_cache.set(request.message, response_text)

    asst_msg = Message(
        session_id=session.id,
        role="assistant",
        content=response_text,
        sources=json.dumps(sources),
    )
    db.add(asst_msg)
    db.commit()

    return {"response": response_text, "sources": sources}
