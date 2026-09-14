import time
from datetime import UTC, datetime
from typing import Literal, cast

import httpx
from fastapi import APIRouter
from sqlalchemy import func, or_, select

from app.api.dependencies import AppSettings, CurrentUser, DatabaseSession
from app.db.models import (
    Artifact,
    AuditEvent,
    ModelHealthRecord,
    RegisteredModel,
    Task,
    TaskRun,
    TaskStep,
    Workspace,
)
from app.schemas.common import (
    EgressTestResponse,
    SecurityControlEvidence,
    SecurityEventResponse,
    SovereigntyMetrics,
    SovereigntyStatusResponse,
)

router = APIRouter(prefix="/security", tags=["security"])
PROBE_VERSION = "day6-v1"


def _organization_workspace(session: DatabaseSession, user: CurrentUser) -> Workspace:
    workspace = session.scalar(
        select(Workspace)
        .where(Workspace.organization_id == user.organization_id)
        .order_by(Workspace.created_at)
    )
    if workspace is None:
        workspace = Workspace(
            organization_id=user.organization_id,
            name=f"{user.organization.name} Workspace",
        )
        session.add(workspace)
        session.flush()
    return workspace


def _egress_from_event(event: AuditEvent | None) -> EgressTestResponse | None:
    if event is None:
        return None
    payload = event.payload
    raw_status = str(payload.get("status", "error"))
    if raw_status not in {"blocked", "egress_detected", "error"}:
        raw_status = "error"
    status = cast(Literal["blocked", "egress_detected", "error"], raw_status)
    return EgressTestResponse(
        status=status,
        target=str(payload.get("target", "controlled public probe")),
        duration_ms=int(payload.get("duration_ms", 0)),
        detail=str(payload.get("detail", "Probe evidence is incomplete.")),
        observed_at=event.occurred_at,
        enforcement=(
            "configured" if payload.get("enforcement") == "configured" else "unconfigured"
        ),
        probe_version=str(payload.get("probe_version", "unknown")),
    )


@router.post("/egress-test", response_model=EgressTestResponse)
async def egress_test(
    session: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
) -> EgressTestResponse:
    started = time.perf_counter()
    observed_at = datetime.now(UTC)
    target = settings.egress_probe_target
    try:
        async with httpx.AsyncClient(
            timeout=settings.egress_probe_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = await client.get(
                target, headers={"User-Agent": f"sovereign-egress-probe/{PROBE_VERSION}"}
            )
        status: Literal["blocked", "egress_detected", "error"] = "egress_detected"
        detail = f"Outbound HTTPS unexpectedly succeeded with status {response.status_code}."
    except (httpx.ConnectError, httpx.ConnectTimeout):
        status = "blocked"
        detail = "The API runtime could not establish an outbound connection."
    except httpx.HTTPError:
        status = "error"
        detail = "The controlled probe was inconclusive; no blocked-egress claim is made."
    duration_ms = int((time.perf_counter() - started) * 1000)
    result = EgressTestResponse(
        status=status,
        target=target,
        duration_ms=duration_ms,
        detail=detail,
        observed_at=observed_at,
        enforcement="configured" if settings.app_egress_enforced else "unconfigured",
        probe_version=PROBE_VERSION,
    )
    workspace = _organization_workspace(session, user)
    session.add(
        AuditEvent(
            workspace_id=workspace.id,
            event_type="EGRESS_PROBE_COMPLETED",
            actor_type="user",
            actor_id=user.id,
            payload=result.model_dump(mode="json"),
        )
    )
    session.commit()
    return result


@router.get("/status", response_model=SovereigntyStatusResponse)
def sovereignty_status(
    session: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
) -> SovereigntyStatusResponse:
    organization_id = user.organization_id
    organization_scope = Workspace.organization_id == organization_id

    run_count_query = (
        select(func.count(TaskRun.id))
        .join(Task, Task.id == TaskRun.task_id)
        .join(Workspace, Workspace.id == Task.workspace_id)
    )
    task_runs = int(session.scalar(run_count_query.where(organization_scope)) or 0)
    completed_runs = int(
        session.scalar(
            run_count_query.where(organization_scope, TaskRun.status == "completed")
        )
        or 0
    )
    failed_runs = int(
        session.scalar(
            run_count_query.where(
                organization_scope,
                TaskRun.status.in_(["failed", "cancelled", "timed_out"]),
            )
        )
        or 0
    )
    audit_events = int(
        session.scalar(
            select(func.count(AuditEvent.id))
            .join(Workspace, Workspace.id == AuditEvent.workspace_id)
            .where(organization_scope)
        )
        or 0
    )
    artifacts = int(
        session.scalar(
            select(func.count(Artifact.id))
            .join(Workspace, Workspace.id == Artifact.workspace_id)
            .where(organization_scope)
        )
        or 0
    )
    denial_filter = or_(
        AuditEvent.event_type.like("%DENIED%"),
        AuditEvent.event_type.in_(["PATCH_REJECTED", "POLICY_DENIED"]),
    )
    policy_denials = int(
        session.scalar(
            select(func.count(AuditEvent.id))
            .join(Workspace, Workspace.id == AuditEvent.workspace_id)
            .where(organization_scope, denial_filter)
        )
        or 0
    )
    steps = list(
        session.scalars(
            select(TaskStep)
            .join(TaskRun, TaskRun.id == TaskStep.run_id)
            .join(Task, Task.id == TaskRun.task_id)
            .join(Workspace, Workspace.id == Task.workspace_id)
            .where(organization_scope)
            .order_by(TaskStep.created_at.desc())
            .limit(1000)
        )
    )
    model_steps = [step for step in steps if step.kind in {"model", "patch", "multimodal"}]
    prompt_tokens = sum(int(step.output.get("prompt_tokens", 0) or 0) for step in model_steps)
    completion_tokens = sum(
        int(step.output.get("completion_tokens", 0) or 0) for step in model_steps
    )
    completed = list(
        session.scalars(
            select(TaskRun)
            .join(Task, Task.id == TaskRun.task_id)
            .join(Workspace, Workspace.id == Task.workspace_id)
            .where(
                organization_scope,
                TaskRun.started_at.is_not(None),
                TaskRun.completed_at.is_not(None),
            )
            .order_by(TaskRun.completed_at.desc())
            .limit(100)
        )
    )
    durations = [
        int((run.completed_at - run.started_at).total_seconds() * 1000)
        for run in completed
        if run.started_at is not None and run.completed_at is not None
    ]
    models = list(
        session.scalars(
            select(RegisteredModel)
            .where(RegisteredModel.enabled.is_(True))
            .order_by(RegisteredModel.priority.desc())
        )
    )
    ready_models = 0
    for model in models:
        latest = session.scalar(
            select(ModelHealthRecord)
            .where(ModelHealthRecord.model_id == model.id)
            .order_by(ModelHealthRecord.observed_at.desc())
        )
        if latest is not None and latest.status == "ready":
            ready_models += 1

    latest_event = session.scalar(
        select(AuditEvent)
        .join(Workspace, Workspace.id == AuditEvent.workspace_id)
        .where(organization_scope, AuditEvent.event_type == "EGRESS_PROBE_COMPLETED")
        .order_by(AuditEvent.occurred_at.desc())
    )
    latest_probe = _egress_from_event(latest_event)
    cloud_models = int(
        session.scalar(
            select(func.count(RegisteredModel.id)).where(RegisteredModel.provider != "ollama")
        )
        or 0
    )
    controls = [
        SecurityControlEvidence(
            key="api_egress",
            label="Application network",
            status="enforced" if settings.app_egress_enforced else "attention",
            detail=(
                "API is attached only to internal Docker networks."
                if settings.app_egress_enforced
                else "Application egress enforcement is not declared by this runtime."
            ),
        ),
        SecurityControlEvidence(
            key="ollama_gateway",
            label="Local inference gateway",
            status="enforced",
            detail="Only fixed Ollama tags, chat, and embedding operations are forwarded locally.",
        ),
        SecurityControlEvidence(
            key="sandbox_network",
            label="Coding sandbox",
            status="enforced",
            detail="Ephemeral code containers use network_mode none and bounded resources.",
        ),
        SecurityControlEvidence(
            key="cloud_models",
            label="Cloud model providers",
            status="verified" if cloud_models == 0 else "attention",
            detail=f"{cloud_models} non-Ollama model provider registrations detected.",
        ),
        SecurityControlEvidence(
            key="egress_probe",
            label="Observed outbound probe",
            status=(
                "verified"
                if latest_probe and latest_probe.status == "blocked"
                else "attention"
                if latest_probe and latest_probe.status == "egress_detected"
                else "unknown"
            ),
            detail=(
                latest_probe.detail
                if latest_probe
                else "No controlled probe has been recorded."
            ),
        ),
    ]
    if not settings.app_egress_enforced or cloud_models:
        overall: Literal["verified", "attention", "unknown"] = "attention"
    elif latest_probe is None or latest_probe.status == "error":
        overall = "unknown"
    elif latest_probe.status == "blocked":
        overall = "verified"
    else:
        overall = "attention"

    security_events = list(
        session.scalars(
            select(AuditEvent)
            .join(Workspace, Workspace.id == AuditEvent.workspace_id)
            .where(
                organization_scope,
                or_(
                    AuditEvent.event_type.like("%DENIED%"),
                    AuditEvent.event_type.like("%FAILED%"),
                    AuditEvent.event_type.like("%EGRESS%"),
                    AuditEvent.event_type.like("%CANCELLED%"),
                    AuditEvent.event_type.like("%TIMED_OUT%"),
                ),
            )
            .order_by(AuditEvent.occurred_at.desc())
            .limit(12)
        )
    )
    return SovereigntyStatusResponse(
        overall=overall,
        generated_at=datetime.now(UTC),
        controls=controls,
        metrics=SovereigntyMetrics(
            task_runs=task_runs,
            completed_runs=completed_runs,
            failed_runs=failed_runs,
            audit_events=audit_events,
            artifacts=artifacts,
            policy_denials=policy_denials,
            model_requests=len(model_steps),
            prompt_tokens=prompt_tokens or None,
            completion_tokens=completion_tokens or None,
            average_runtime_ms=(sum(durations) // len(durations)) if durations else None,
        ),
        enabled_models=len(models),
        ready_models=ready_models,
        latest_egress_probe=latest_probe,
        recent_security_events=[
            SecurityEventResponse(
                id=event.id,
                event_type=event.event_type,
                status=str(event.payload.get("status", "recorded")),
                detail=str(
                    event.payload.get("detail")
                    or event.payload.get("error_code")
                    or event.payload.get("category")
                    or "Security-relevant audit evidence recorded."
                ),
                occurred_at=event.occurred_at,
                run_id=event.run_id,
            )
            for event in security_events
        ],
    )
