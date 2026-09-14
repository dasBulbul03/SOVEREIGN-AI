from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    status: str
    created_at: datetime


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    display_name: str
    media_type: str
    size_bytes: int
    sha256: str
    status: str
    indexed: bool = False
    created_at: datetime


class KnowledgeBaseCreate(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=2, max_length=120)


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    name: str
    active_index_version: int | None
    status: str
    created_at: datetime


class IngestionRequest(BaseModel):
    file_ids: list[UUID] = Field(min_length=1, max_length=20)


class IngestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    knowledge_base_id: UUID
    index_version: int
    status: str
    total_documents: int
    completed_documents: int
    failed_documents: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


class Citation(BaseModel):
    document_id: UUID
    display_name: str
    page_start: int
    page_end: int


class SearchHit(BaseModel):
    score: float
    text: str
    citation: Citation


class SearchResponse(BaseModel):
    knowledge_base_id: UUID
    index_version: int
    query: str
    hits: list[SearchHit]
    local: Literal[True] = True
