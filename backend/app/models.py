from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, DECIMAL, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)  # Firebase user ID
    title = Column(String(255), nullable=False, default="New Chat")
    title_set = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(255), nullable=False, index=True)  # Firebase user ID
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    context_used = Column(JSON)  # Store context usage information
    context_data = Column(JSON)  # Store context data
    context_sources = Column(JSON)  # Store context sources with formatted data
    related_links = Column(JSON)  # Store related links (DOI, URL, URI, etc.)
    elapsed_time = Column(DECIMAL(10, 3))  # Store response time
    confidence = Column(JSON)  # Store confidence indicator (level and percentage)
    token_counts = Column(JSON)  # Store token consumption breakdown
    lucene_query = Column(Text)  # Store lucene query for heatmap and partner finder
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    session = relationship("ChatSession", back_populates="messages")

class UserPreferences(Base):
    __tablename__ = "user_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, unique=True, index=True)  # Firebase user ID
    neo4j_enabled = Column(Boolean, default=True)  # Enable/disable Neo4j data source
    qdrant_enabled = Column(Boolean, default=True)  # Enable/disable Qdrant data source
    elasticsearch_enabled = Column(Boolean, default=True)  # Enable/disable Elasticsearch data source
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) 