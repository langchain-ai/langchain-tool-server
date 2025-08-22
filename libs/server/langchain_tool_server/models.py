"""Database models for tools and tool versions."""

import uuid
from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, String, Text, UUID, MetaData, Table, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Tool(Base):
    __tablename__ = "tools"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ToolVersion(Base):
    __tablename__ = "tool_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(50), nullable=False)
    schema_json = Column(JSONB, nullable=False)
    code = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ToolCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None


class ToolResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class ToolVersionCreate(BaseModel):
    tool_id: uuid.UUID
    version: str = Field(..., max_length=50)
    schema_json: Dict[str, Any]
    code: str


class ToolVersionResponse(BaseModel):
    id: uuid.UUID
    tool_id: uuid.UUID
    version: str
    schema_json: Dict[str, Any]
    code: str
    created_at: datetime