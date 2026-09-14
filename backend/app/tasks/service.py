import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import (
    Artifact,
    AuditEvent,
    KnowledgeBase,
    StoredFile,
    Task,
    TaskRun,
    TaskStep,
    User,
    Workspace,
)
from app.schemas.tasks import (
    ArtifactResponse,
    TaskAccepted,
    TaskCreate,
    TaskResponse,
    TaskRunResponse,
)


def owned_workspace(session: Session, workspace_id: uuid.UUID, user: User) -> Workspace:
    workspace = session.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id, Workspace.organization_id == user.organization_id
        )
    )
    if workspace is None:
        raise AppError("WORKSPACE_NOT_FOUND", "Workspace not found.", 404)
    return workspace


def validate_inputs(session: Session, payload: TaskCreate, user: User) -> None:
    owned_workspace(session, payload.workspace_id, user)
    if payload.mode == "coding" and not payload.input_file_ids:
        raise AppError("CODING_INPUT_REQUIRED", "Coding mode requires repository files.", 422)
    if payload.mode == "coding" and payload.knowledge_base_ids:
        raise AppError(
            "CODING_KNOWLEDGE_DENIED", "Coding mode does not accept knowledge bases.", 422
        )
    if payload.mode == "procurement" and not payload.input_file_ids:
        raise AppError(
            "PROCUREMENT_INPUT_REQUIRED",
            "Procurement mode requires at least one quotation file.",
            422,
        )
    if payload.mode == "procurement" and not {"xlsx", "docx"}.issubset(
        payload.requested_outputs
    ):
        raise AppError(
            "PROCUREMENT_ARTIFACTS_REQUIRED",
            "Procurement mode requires validated XLSX and DOCX outputs.",
            422,
        )
    files = list(
        session.scalars(select(StoredFile).where(StoredFile.id.in_(payload.input_file_ids)))
    )
    if len(files) != len(set(payload.input_file_ids)) or any(
        item.workspace_id != payload.workspace_id or item.status == "deleted" for item in files
    ):
        raise AppError("TASK_FILE_NOT_FOUND", "Every input file must belong to the workspace.", 404)
    bases = list(
        session.scalars(
            select(KnowledgeBase).where(KnowledgeBase.id.in_(payload.knowledge_base_ids))
        )
    )
    if len(bases) != len(set(payload.knowledge_base_ids)) or any(
        item.workspace_id != payload.workspace_id for item in bases
    ):
        raise AppError(
            "TASK_KNOWLEDGE_NOT_FOUND", "Every knowledge base must belong to the workspace.", 404
        )


def create_task(
    session: Session,
    payload: TaskCreate,
    user: User,
    settings: Settings,
    idempotency_key: str | None,
) -> TaskAccepted:
    validate_inputs(session, payload, user)
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode()).hexdigest()
    if idempotency_key:
        existing = session.scalar(
            select(Task).where(
                Task.created_by_user_id == user.id, Task.idempotency_key == idempotency_key
            )
        )
        if existing:
            if existing.request_hash != request_hash:
                raise AppError(
                    "IDEMPOTENCY_CONFLICT", "This idempotency key was used for another task.", 409
                )
            run = session.scalar(
                select(TaskRun)
                .where(TaskRun.task_id == existing.id)
                .order_by(TaskRun.attempt.desc())
            )
            if run is None:
                raise AppError("TASK_RUN_MISSING", "The existing task has no run.", 500)
            return TaskAccepted(
                task_id=existing.id,
                run_id=run.id,
                status=existing.status,
                created_at=existing.created_at,
            )
    now = datetime.now(UTC)
    task = Task(
        workspace_id=payload.workspace_id,
        created_by_user_id=user.id,
        goal=payload.goal.strip(),
        mode=payload.mode,
        test_command=payload.test_command,
        input_file_ids=[str(item) for item in payload.input_file_ids],
        knowledge_base_ids=[str(item) for item in payload.knowledge_base_ids],
        requested_outputs=list(payload.requested_outputs),
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    session.add(task)
    session.flush()
    run = TaskRun(
        task_id=task.id,
        deadline_at=now + timedelta(seconds=settings.task_timeout_seconds),
    )
    session.add(run)
    session.flush()
    session.add(
        TaskStep(
            run_id=run.id,
            sequence=1,
            kind="lifecycle",
            title="Task submitted",
            detail="Queued for the local agent worker.",
            output={"status": "queued"},
            completed_at=now,
        )
    )
    session.add(
        AuditEvent(
            workspace_id=task.workspace_id,
            run_id=run.id,
            event_type="TASK_CREATED",
            actor_type="user",
            actor_id=user.id,
            payload={
                "task_id": str(task.id),
                "mode": task.mode,
                "test_command": task.test_command,
                "requested_outputs": task.requested_outputs,
            },
        )
    )
    session.commit()
    return TaskAccepted(task_id=task.id, run_id=run.id, status=task.status, created_at=now)


def artifact_response(artifact: Artifact) -> ArtifactResponse:
    return ArtifactResponse.model_validate(artifact).model_copy(
        update={"download_url": f"/api/v1/artifacts/{artifact.id}/content"}
    )


def task_response(session: Session, task: Task) -> TaskResponse:
    run = session.scalar(
        select(TaskRun).where(TaskRun.task_id == task.id).order_by(TaskRun.attempt.desc())
    )
    run_response = None
    if run:
        steps = list(
            session.scalars(
                select(TaskStep).where(TaskStep.run_id == run.id).order_by(TaskStep.sequence)
            )
        )
        artifacts = list(session.scalars(select(Artifact).where(Artifact.run_id == run.id)))
        run_response = TaskRunResponse.model_validate(run).model_copy(
            update={"steps": steps, "artifacts": [artifact_response(item) for item in artifacts]}
        )
    queue_position = None
    if run and run.status == "queued":
        ahead = session.scalar(
            select(func.count())
            .select_from(TaskRun)
            .where(TaskRun.status == "queued", TaskRun.created_at < run.created_at)
        ) or 0
        queue_position = ahead + 1
    return TaskResponse.model_validate(task).model_copy(
        update={"latest_run": run_response, "queue_position": queue_position}
    )


def get_owned_task(session: Session, task_id: uuid.UUID, user: User) -> Task:
    task = session.scalar(
        select(Task)
        .join(Workspace, Workspace.id == Task.workspace_id)
        .where(Task.id == task_id, Workspace.organization_id == user.organization_id)
    )
    if task is None:
        raise AppError("TASK_NOT_FOUND", "Task not found.", 404)
    return task


def list_tasks(session: Session, user: User, limit: int) -> list[TaskResponse]:
    tasks = list(
        session.scalars(
            select(Task)
            .join(Workspace, Workspace.id == Task.workspace_id)
            .where(Workspace.organization_id == user.organization_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )
    )
    return [task_response(session, task) for task in tasks]


def cancel_task(session: Session, task: Task) -> TaskResponse:
    if task.status in {"completed", "failed", "cancelled", "timed_out"}:
        return task_response(session, task)
    run = session.scalar(
        select(TaskRun).where(TaskRun.task_id == task.id).order_by(TaskRun.attempt.desc())
    )
    current_time = datetime.now(UTC)
    if run and run.status == "queued":
        run.status = task.status = "cancelled"
        run.cancel_requested = True
        run.completed_at = current_time
    else:
        if run:
            run.cancel_requested = True
        task.status = "cancel_requested"
    task.updated_at = current_time
    session.commit()
    return task_response(session, task)


def retry_task(session: Session, task: Task, settings: Settings) -> TaskAccepted:
    if task.status not in {"failed", "cancelled", "timed_out"}:
        raise AppError(
            "TASK_NOT_RETRYABLE", "Only terminal unsuccessful tasks can be retried.", 409
        )
    latest = (
        session.scalar(select(func.max(TaskRun.attempt)).where(TaskRun.task_id == task.id)) or 0
    )
    now = datetime.now(UTC)
    run = TaskRun(
        task_id=task.id,
        attempt=latest + 1,
        deadline_at=now + timedelta(seconds=settings.task_timeout_seconds),
    )
    task.status, task.updated_at = "queued", now
    session.add(run)
    session.flush()
    session.add(
        TaskStep(
            run_id=run.id,
            sequence=1,
            kind="lifecycle",
            title="Retry queued",
            detail=f"Attempt {run.attempt} queued for the local worker.",
            output={"status": "queued"},
            completed_at=now,
        )
    )
    session.commit()
    return TaskAccepted(task_id=task.id, run_id=run.id, status=task.status, created_at=now)
