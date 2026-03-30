from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    messages = relationship("Message", back_populates="session")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    sources = Column(Text, nullable=True)  # JSON serialized sources
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    session = relationship("Session", back_populates="messages")
