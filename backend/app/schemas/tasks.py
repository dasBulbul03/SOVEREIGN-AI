from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: UUID
    goal: str = Field(min_length=3, max_length=8_000)
    mode: Literal["auto", "document", "coding", "procurement"] = "auto"
    test_command: Literal["pytest", "unittest", "compile"] = "pytest"
    input_file_ids: list[UUID] = Field(default_factory=list, max_length=20)
    knowledge_base_ids: list[UUID] = Field(default_factory=list, max_length=10)
    requested_outputs: list[
        Literal["docx", "xlsx", "patch", "repository", "sandbox_report"]
    ] = Field(
        default_factory=list, max_length=3
    )


class TaskStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    sequence: int
    kind: str
    status: str
    title: str
    detail: str
    tool_name: str | None
    input: dict[str, object]
    output: dict[str, object]
    duration_ms: int | None
    error_category: str | None
    created_at: datetime
    completed_at: datetime | None


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    logical_name: str
    revision: int
    display_name: str
    media_type: str
    size_bytes: int
    sha256: str
    validation_status: str
    created_at: datetime
    download_url: str | None = None


class ArtifactPreviewResponse(BaseModel):
    artifact_id: UUID
    display_name: str
    media_type: str
    preview_type: Literal["document", "spreadsheet", "text", "binary"]
    content: str
    truncated: bool


class TaskRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_id: UUID
    attempt: int
    status: str
    selected_model_id: UUID | None
    agent_profile: str
    route: dict[str, object]
    step_count: int
    retry_count: int
    cancel_requested: bool
    result_text: str | None
    citations: list[dict[str, object]]
    error_category: str | None
    error_message: str | None
    deadline_at: datetime
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    steps: list[TaskStepResponse] = Field(default_factory=list)
    artifacts: list[ArtifactResponse] = Field(default_factory=list)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    goal: str
    mode: str
    test_command: str
    task_type: str
    required_capabilities: list[str]
    input_file_ids: list[str]
    knowledge_base_ids: list[str]
    requested_outputs: list[str]
    status: str
    queue_position: int | None = None
    created_at: datetime
    updated_at: datetime
    latest_run: TaskRunResponse | None = None


class TaskAccepted(BaseModel):
    task_id: UUID
    run_id: UUID
    status: str
    created_at: datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    run_id: UUID | None
    event_type: str
    actor_type: str
    actor_id: UUID | None
    payload: dict[str, object]
    occurred_at: datetime
