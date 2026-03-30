import json
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Session as ChatSession, Message
from app.retriever import Retriever
from app.llm import get_llm

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Knowledge Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = Retriever()
llm = get_llm()


class ChatRequest(BaseModel):
    session_id: int
    message: str


@app.post("/sessions")
def create_session(db: Session = Depends(get_db)):
    db_session = ChatSession(title="New Chat")
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


@app.get("/sessions")
def get_sessions(db: Session = Depends(get_db)):
    return db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()


@app.get("/sessions/{session_id}/messages")
def get_messages(session_id: int, db: Session = Depends(get_db)):
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
            except:
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
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = Message(session_id=session.id, role="user", content=request.message)
    db.add(user_msg)
    db.commit()

    retrieval = retriever.search(request.message)
    context_str = retrieval.get("context_str", "")
    sources = retrieval.get("sources", [])

    response_text = llm.generate(request.message, context_str)

    # Name chat session after first user message
    if db.query(Message).filter(Message.session_id == session.id).count() <= 1:
        session.title = request.message[:30] + (
            "..." if len(request.message) > 30 else ""
        )
        db.add(session)

    asst_msg = Message(
        session_id=session.id,
        role="assistant",
        content=response_text,
        sources=json.dumps(sources),
    )
    db.add(asst_msg)
    db.commit()

    return {"response": response_text, "sources": sources}
