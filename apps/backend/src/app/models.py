from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    sources = Column(Text, nullable=True)  # JSON serialized sources
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    session = relationship("Session", back_populates="messages")

class ParquetSchema(Base):
    __tablename__ = "parquet_schemas"
    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String, unique=True, index=True)
    file_path = Column(String)
    columns = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Document(Base):
    __tablename__ = "documents"

    # Unique ID for the record
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Original filename (e.g., "manual_v2.pdf")
    file_name = Column(String, nullable=False)

    # Absolute path on the server (e.g., "/documents/manual_v2.pdf")
    file_path = Column(String, nullable=False)

    # The SHA-256 fingerprint. Unique index is critical here!
    content_hash = Column(String, unique=True, index=True, nullable=False)

    # Useful for quick size-based heuristics
    file_size = Column(Integer)

    # Current state: 'INGESTED', 'FAILED', or 'PROCESSING'
    status = Column(String, default="PROCESSING")

    # Timestamps for auditing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
