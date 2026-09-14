import asyncio
import hashlib
import re
import shutil
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.artifacts.code import publish_code_artifacts
from app.artifacts.docx import create_approval_docx
from app.artifacts.procurement import create_procurement_artifacts
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import (
    Artifact,
    AuditEvent,
    Organization,
    StoredFile,
    Task,
    TaskRun,
    TaskStep,
    User,
)
from app.db.session import SessionLocal
from app.model_providers.base import ChatRequest, ChatResult
from app.model_providers.ollama import OllamaModelProvider
from app.routing.router import classify_task, route_model
from app.services.code_repository import (
    extract_unified_diff,
    materialize_repository,
    repository_diff,
    repository_digest,
    repository_prompt,
    resolve_verification_command,
    restore_repository_files,
    snapshot_repository,
)
from app.services.hybrid_retrieval import gather_hybrid_evidence
from app.services.multimodal import enrich_multimodal_inputs
from app.services.procurement import compare_procurement, comparison_markdown
from app.services.sandbox_client import SandboxClient
from app.tools.registry import ToolContext, ToolRegistry

_worker_lock = asyncio.Lock()
_worker_wakeup = asyncio.Event()
_worker_stop = asyncio.Event()
_worker_event_loop: asyncio.AbstractEventLoop | None = None


def _coding_failure_summary(
    output: dict[str, object], files: dict[str, str], max_chars: int
) -> str:
    stdout = str(output.get("stdout", ""))
    stderr = str(output.get("stderr", ""))
    combined = (stdout + "\n" + stderr).strip()
    frames = re.findall(r'File "([^"]+)", line (\d+)', combined)
    for path, line_text in reversed(frames):
        candidate = path.replace("\\", "/")
        matched_path = next(
            (
                repository_path
                for repository_path in files
                if candidate == repository_path or candidate.endswith("/" + repository_path)
            ),
            None,
        )
        if matched_path is None:
            continue
        line_number = int(line_text)
        source_lines = files[matched_path].splitlines()
        current_line = (
            source_lines[line_number - 1]
            if 1 <= line_number <= len(source_lines)
            else "unavailable"
        )
        error_line = next(
            (line for line in reversed(combined.splitlines()) if line.strip()),
            "Verification failed.",
        )
        guidance = ""
        if "not JSON serializable" in error_line:
            guidance = (
                "\nRepair guidance: convert non-JSON values before serialization or provide a "
                "safe JSON default serializer."
            )
        elif error_line.startswith("KeyError:"):
            guidance = (
                "\nRepair guidance: make the producer and consumer use the same dictionary key."
            )
        elif error_line.startswith("AttributeError:"):
            guidance = (
                "\nRepair guidance: trace why the value is missing and correct the upstream lookup "
                "or method call."
            )
        elif error_line.startswith("TypeError:"):
            guidance = (
                "\nRepair guidance: normalize the incompatible value types at their source before "
                "performing the operation."
            )
        elif error_line.startswith("ValueError:"):
            guidance = (
                "\nRepair guidance: correct the invalid input or operand before conversion; do not "
                "wrap the already-invalid operation in another conversion."
            )
        return (
            f"Exact failing location: {matched_path} line {line_number}.\n"
            f"Current source line: {current_line}\n"
            f"Error: {error_line}{guidance}"
        )[:max_chars]
    return combined[-max_chars:]
TERMINAL = {"completed", "failed", "cancelled", "timed_out"}


def now() -> datetime:
    return datetime.now(UTC)


def chat_metrics(chat: ChatResult) -> dict[str, int]:
    metrics = {"model_duration_ms": chat.duration_ms}
    for key, value in {
        "prompt_tokens": chat.prompt_tokens,
        "completion_tokens": chat.completion_tokens,
        "model_load_ms": chat.load_duration_ms,
        "model_evaluation_ms": chat.evaluation_duration_ms,
    }.items():
        if value is not None:
            metrics[key] = value
    return metrics


def add_audit(
    session: Session,
    task: Task,
    run: TaskRun,
    event_type: str,
    payload: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            workspace_id=task.workspace_id,
            run_id=run.id,
            event_type=event_type,
            actor_type="agent",
            actor_id=task.created_by_user_id,
            payload=payload,
        )
    )


def add_step(
    session: Session,
    run: TaskRun,
    kind: str,
    title: str,
    detail: str,
    *,
    tool_name: str | None = None,
    input_data: dict[str, object] | None = None,
    output_data: dict[str, object] | None = None,
    duration_ms: int | None = None,
    status: str = "completed",
    error_category: str | None = None,
) -> TaskStep:
    sequence = (
        session.scalar(select(func.max(TaskStep.sequence)).where(TaskStep.run_id == run.id)) or 0
    ) + 1
    settings = get_settings()
    if sequence > settings.task_max_steps:
        raise AppError("STEP_LIMIT_EXCEEDED", "The agent reached its maximum step count.", 409)
    step = TaskStep(
        run_id=run.id,
        sequence=sequence,
        kind=kind,
        status=status,
        title=title,
        detail=detail[:500],
        tool_name=tool_name,
        input=input_data or {},
        output=output_data or {},
        duration_ms=duration_ms,
        error_category=error_category,
        completed_at=now(),
    )
    run.step_count = sequence
    run.version += 1
    session.add(step)
    session.commit()
    return step


def check_run(session: Session, task: Task, run: TaskRun) -> None:
    session.refresh(run)
    if run.cancel_requested:
        run.status = task.status = "cancelled"
        run.completed_at = task.updated_at = now()
        add_audit(session, task, run, "TASK_CANCELLED", {"step_count": run.step_count})
        session.commit()
        raise AppError("TASK_CANCELLED", "The task was cancelled.", 409)
    deadline = run.deadline_at
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    if now() >= deadline:
        run.status = task.status = "timed_out"
        run.completed_at = task.updated_at = now()
        add_audit(session, task, run, "TASK_TIMED_OUT", {"step_count": run.step_count})
        session.commit()
        raise AppError("TASK_TIMED_OUT", "The task exceeded its deadline.", 504)


def citation_metadata(hits: list[dict[str, Any]]) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    for hit in hits:
        citation: dict[str, object] = {
            "source_id": hit["source_id"],
            "document_id": hit["document_id"],
            "display_name": hit["display_name"],
            "page_start": hit["page_start"],
            "page_end": hit["page_end"],
            "score": hit["score"],
            "retrieval_mode": hit.get("retrieval_mode", "unknown"),
            "source_type": hit.get("source_type", "unknown"),
        }
        if hit.get("file_id"):
            citation["file_id"] = hit["file_id"]
        if hit.get("knowledge_base_id"):
            citation["knowledge_base_id"] = hit["knowledge_base_id"]
            citation["knowledge_base_name"] = hit.get("knowledge_base_name", "Knowledge base")
        citations.append(citation)
    return citations


def grounded_prompt(goal: str, evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return (
            "You are a concise local industrial assistant. Complete the requested task. "
            "Clearly state when no source evidence was provided.\n\nTASK:\n" + goal
        )
    blocks = "\n\n".join(
        f"[{hit['source_id']}] {hit['display_name']} page {hit['page_start']}\n{hit['text']}"
        for hit in evidence
    )
    return (
        "You are a cautious industrial document agent. Answer only from the supplied evidence. "
        "Cite material claims using the exact source IDs such as [S1]. "
        "If evidence is insufficient, say that human review is required. "
        "Provide a clear approval recommendation and safety caveats."
        f"\n\nTASK:\n{goal}\n\nEVIDENCE:\n{blocks}"
    )


async def execute_coding_workflow(
    session: Session,
    task: Task,
    run: TaskRun,
    provider: OllamaModelProvider,
    model_key: str,
    registry: ToolRegistry,
) -> None:
    settings = get_settings()
    if task.knowledge_base_ids and task.mode == "coding":
        raise AppError(
            "CODING_KNOWLEDGE_DENIED",
            "Coding mode accepts repository files only; deselect knowledge bases.",
            422,
        )
    stored_files = list(
        session.scalars(
            select(StoredFile).where(
                StoredFile.id.in_([uuid.UUID(value) for value in task.input_file_ids]),
                StoredFile.workspace_id == task.workspace_id,
                StoredFile.status != "deleted",
            )
        )
    )
    if len(stored_files) != len(task.input_file_ids):
        raise AppError("CODING_INPUT_REQUIRED", "Select an available repository input.", 422)
    materialized = materialize_repository(settings, task.workspace_id, run.id, stored_files)
    working_root = materialized.root
    try:
        original = snapshot_repository(working_root, settings.sandbox_max_repository_bytes)
        verification_command = resolve_verification_command(task.test_command, list(original))
        add_step(
            session,
            run,
            "repository",
            "Repository isolated",
            f"Copied {materialized.file_count} files into a run-scoped working copy.",
            tool_name="read_repository",
            input_data={"source_file_count": len(stored_files)},
            output_data={
                "repository_files": materialized.file_count,
                "repository_bytes": materialized.total_bytes,
                "source_files": materialized.source_files,
                "original_sha256": repository_digest(original),
            },
        )
        for source in materialized.source_files:
            add_audit(session, task, run, "REPOSITORY_INPUT_COPIED", source)
        session.commit()
        check_run(session, task, run)

        if verification_command != task.test_command:
            fallback_detail = (
                "No discoverable pytest files were present; executing the standalone Python "
                "program in the isolated sandbox."
                if verification_command == "run"
                else "No discoverable pytest files were present; using a read-only Python "
                "syntax check for this source-only task."
            )
            add_step(
                session,
                run,
                "verification",
                "Verification command resolved",
                fallback_detail,
                input_data={"requested_command": task.test_command},
                output_data={"effective_command": verification_command},
            )
            add_audit(
                session,
                task,
                run,
                "VERIFICATION_COMMAND_RESOLVED",
                {
                    "requested_command": task.test_command,
                    "effective_command": verification_command,
                    "reason": "no_discoverable_pytest_files",
                },
            )
            session.commit()

        context = ToolContext(
            task.workspace_id,
            session,
            settings,
            provider,
            repository_root=working_root,
            sandbox_client=SandboxClient(settings),
        )
        read_result = await registry.execute(
            run.agent_profile,
            "read_repository",
            {"max_chars": settings.sandbox_repository_context_chars},
            context,
        )
        add_step(
            session,
            run,
            "repository",
            "Repository read",
            read_result.summary,
            tool_name="read_repository",
            input_data={"context_limit": settings.sandbox_repository_context_chars},
            output_data={"file_count": read_result.data["file_count"]},
            duration_ms=read_result.duration_ms,
        )
        add_audit(session, task, run, "TOOL_ALLOWED", {"tool": "read_repository"})

        probe = await registry.execute(
            run.agent_profile, "run_python_tests", {"command": "network_probe"}, context
        )
        if probe.status != "completed" or "EGRESS_BLOCKED" not in str(probe.data["stdout"]):
            raise AppError(
                "SANDBOX_EGRESS_FAILURE", "Sandbox network isolation was not proven.", 500
            )
        add_step(
            session,
            run,
            "sandbox",
            "Sandbox boundary verified",
            "A controlled external request failed inside a no-network container.",
            tool_name="run_python_tests",
            output_data=probe.data,
            duration_ms=probe.duration_ms,
        )
        add_audit(
            session,
            task,
            run,
            "SANDBOX_EGRESS_BLOCKED",
            {"network_mode": "none", "container_id": probe.data["container_id"]},
        )
        check_run(session, task, run)

        baseline = await registry.execute(
            run.agent_profile,
            "run_python_tests",
            {"command": verification_command},
            context,
        )
        add_step(
            session,
            run,
            "sandbox",
            "Baseline verification executed",
            baseline.summary,
            tool_name="run_python_tests",
            output_data=baseline.data,
            duration_ms=baseline.duration_ms,
        )
        add_audit(
            session,
            task,
            run,
            "SANDBOX_EXECUTED",
            {
                "phase": "baseline",
                "command": verification_command,
                "exit_code": baseline.data["exit_code"],
            },
        )
        check_run(session, task, run)

        failure = (
            None
            if baseline.status == "completed"
            else _coding_failure_summary(
                baseline.data, original, settings.max_tool_output_chars
            )
        )
        attempts: list[dict[str, object]] = []
        all_changed: set[str] = set()
        final_test = baseline
        for attempt in range(1, settings.sandbox_max_attempts + 1):
            files = snapshot_repository(working_root, settings.sandbox_repository_context_chars)
            prompt = repository_prompt(task.goal, files, failure)
            chat = await provider.chat(
                ChatRequest(
                    model_key,
                    prompt,
                    settings.model_keep_alive,
                    seed=41 + attempt,
                    temperature=0.0 if attempt == 1 else 0.2,
                )
            )
            try:
                patch = extract_unified_diff(chat.content, settings.sandbox_max_patch_chars)
                applied = await registry.execute(
                    run.agent_profile, "apply_patch", {"patch": patch}, context
                )
            except AppError as exc:
                if not exc.code.startswith("PATCH_"):
                    raise
                run.retry_count += 1
                rejected_patch = patch[-settings.max_tool_output_chars :]
                current_failure = failure or "Verification failed."
                failure = (
                    "The previous patch was rejected by the deterministic patch validator: "
                    f"{exc.message} Return corrected line-range XML edits. Do not repeat the "
                    "rejected "
                    "proposal. Use line numbers from the freshly numbered current repository."
                    f"\n\nCURRENT VERIFICATION FAILURE STILL TO FIX:\n{current_failure}"
                    f"\n\nREJECTED PATCH:\n{rejected_patch}"
                )[: settings.max_tool_output_chars]
                add_step(
                    session,
                    run,
                    "patch",
                    f"Patch attempt {attempt} rejected safely",
                    (
                        f"{exc.message} A bounded correction attempt will follow."
                        if attempt < settings.sandbox_max_attempts
                        else f"{exc.message} The bounded correction budget is exhausted."
                    ),
                    tool_name="apply_patch",
                    input_data={"attempt": attempt},
                    output_data={"error_code": exc.code, **chat_metrics(chat)},
                )
                add_audit(
                    session,
                    task,
                    run,
                    "PATCH_REJECTED",
                    {"attempt": attempt, "error_code": exc.code},
                )
                session.commit()
                if attempt >= settings.sandbox_max_attempts:
                    break
                continue
            changed_files = [str(path) for path in applied.data["changed_files"]]
            all_changed.update(changed_files)
            add_step(
                session,
                run,
                "patch",
                f"Patch attempt {attempt} applied",
                applied.summary,
                tool_name="apply_patch",
                input_data={
                    "attempt": attempt,
                    "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
                },
                output_data={
                    **applied.data,
                    "changed_files": changed_files,
                    **chat_metrics(chat),
                },
                duration_ms=chat.duration_ms + applied.duration_ms,
            )
            add_audit(
                session,
                task,
                run,
                "PATCH_APPLIED",
                {"attempt": attempt, "changed_files": changed_files},
            )
            check_run(session, task, run)

            if verification_command != "compile":
                syntax_check = await registry.execute(
                    run.agent_profile,
                    "run_python_tests",
                    {"command": "compile"},
                    context,
                )
                if syntax_check.status != "completed":
                    restore_repository_files(working_root, files, changed_files)
                    run.retry_count += 1
                    failure = (
                        "The previous candidate was rolled back because it introduced a syntax "
                        "error at the wrong location. The last valid working copy was restored. "
                        "Address the unchanged current failure below.\n"
                        + (failure or "Verification failed.")
                    )[: settings.max_tool_output_chars]
                    add_step(
                        session,
                        run,
                        "patch",
                        f"Patch attempt {attempt} rolled back",
                        "The candidate failed read-only syntax validation; the last valid working "
                        "copy was restored.",
                        tool_name="run_python_tests",
                        input_data={"attempt": attempt, "command": "compile"},
                        output_data=syntax_check.data,
                        duration_ms=syntax_check.duration_ms,
                    )
                    add_audit(
                        session,
                        task,
                        run,
                        "PATCH_ROLLED_BACK",
                        {"attempt": attempt, "reason": "syntax_validation_failed"},
                    )
                    session.commit()
                    continue

            final_test = await registry.execute(
                run.agent_profile,
                "run_python_tests",
                {"command": verification_command},
                context,
            )
            attempts.append(
                {
                    "attempt": attempt,
                    "changed_files": changed_files,
                    "test": final_test.data,
                }
            )
            add_step(
                session,
                run,
                "sandbox",
                (
                    f"Verification attempt {attempt} "
                    f"{'passed' if final_test.status == 'completed' else 'failed'}"
                ),
                final_test.summary,
                tool_name="run_python_tests",
                input_data={"attempt": attempt, "command": verification_command},
                output_data=final_test.data,
                duration_ms=final_test.duration_ms,
            )
            add_audit(
                session,
                task,
                run,
                "SANDBOX_EXECUTED",
                {
                    "phase": "verification",
                    "attempt": attempt,
                    "exit_code": final_test.data["exit_code"],
                },
            )
            check_run(session, task, run)
            if final_test.status == "completed":
                break
            run.retry_count += 1
            current_files = snapshot_repository(
                working_root, settings.sandbox_repository_context_chars
            )
            failure = _coding_failure_summary(
                final_test.data, current_files, settings.max_tool_output_chars
            )
            session.commit()
        if final_test.status != "completed":
            raise AppError(
                "SANDBOX_TESTS_FAILED",
                "The bounded coding attempts did not pass the selected verification command.",
                422,
            )

        final = snapshot_repository(working_root, settings.sandbox_max_repository_bytes)
        final_patch = repository_diff(original, final)
        if not final_patch:
            raise AppError("PATCH_EMPTY", "The coding workflow produced no repository change.", 422)
        report: dict[str, object] = {
            "run_id": str(run.id),
            "model": model_key,
            "requested_test_command": task.test_command,
            "test_command": verification_command,
            "network_mode": "none",
            "egress_probe": probe.data,
            "baseline": baseline.data,
            "attempts": attempts,
            "original_sha256": repository_digest(original),
            "verified_sha256": repository_digest(final),
            "passed": True,
        }
        registry.authorize(run.agent_profile, "publish_code_artifacts")
        published = publish_code_artifacts(
            settings.data_root,
            task.workspace_id,
            run.id,
            working_root,
            final_patch,
            report,
        )
        for item in published:
            session.add(
                Artifact(
                    workspace_id=task.workspace_id,
                    run_id=run.id,
                    logical_name=item.logical_name,
                    revision=1,
                    display_name=item.display_name,
                    storage_key=item.storage_key,
                    media_type=item.media_type,
                    size_bytes=item.size_bytes,
                    sha256=item.sha256,
                    validation_status="valid",
                )
            )
        run.result_text = (
            "## Coding task verified\n\n"
            f"The isolated `{verification_command}` command passed after "
            f"{len(attempts)} patch attempt{'s' if len(attempts) != 1 else ''}.\n\n"
            f"- Changed files: {', '.join(sorted(all_changed))}\n"
            "- Sandbox network: disabled and actively verified\n"
            f"- Final repository SHA-256: `{report['verified_sha256']}`\n\n"
            "Download the patch, verified repository, and sandbox report for review."
        )
        add_step(
            session,
            run,
            "artifact",
            "Verified code artifacts published",
            "Published patch, verified repository, and sandbox execution report.",
            tool_name="publish_code_artifacts",
            output_data={
                "artifacts": [
                    {"logical_name": item.logical_name, "sha256": item.sha256} for item in published
                ]
            },
        )
        add_audit(
            session,
            task,
            run,
            "CODE_ARTIFACTS_PUBLISHED",
            {"artifact_count": len(published), "verified_sha256": report["verified_sha256"]},
        )
        session.commit()
    finally:
        shutil.rmtree(working_root.parent.parent, ignore_errors=True)


async def execute_run(run_id: uuid.UUID) -> None:
    async with _worker_lock:
        await _execute_claimed_run(run_id)


async def _execute_claimed_run(run_id: uuid.UUID) -> None:
    settings = get_settings()
    session = SessionLocal()
    task: Task | None = None
    run: TaskRun | None = None
    try:
        run = session.get(TaskRun, run_id)
        if run is None or run.status not in {"queued", "running"}:
            return
        task = session.get(Task, run.task_id)
        if task is None:
            return
        run.status = task.status = "running"
        run.started_at = run.started_at or now()
        run.deadline_at = run.started_at + timedelta(seconds=settings.task_timeout_seconds)
        task.updated_at = now()
        session.commit()
        check_run(session, task, run)

        input_filenames = list(
            session.scalars(
                select(StoredFile.display_name).where(
                    StoredFile.id.in_([uuid.UUID(value) for value in task.input_file_ids]),
                    StoredFile.workspace_id == task.workspace_id,
                    StoredFile.status != "deleted",
                )
            )
        )
        classification = classify_task(
            task.goal,
            bool(task.input_file_ids),
            bool(task.knowledge_base_ids),
            task.mode,
            input_filenames,
        )
        task.task_type = classification.task_type
        task.required_capabilities = classification.capabilities
        run.agent_profile = classification.agent_profile
        add_step(
            session,
            run,
            "classification",
            "Task classified",
            f"{classification.task_type} · {', '.join(classification.capabilities)}",
            output_data={
                "task_type": classification.task_type,
                "required_capabilities": classification.capabilities,
                "agent_profile": classification.agent_profile,
            },
        )
        add_audit(
            session,
            task,
            run,
            "TASK_CLASSIFIED",
            {"task_type": classification.task_type, "capabilities": classification.capabilities},
        )
        session.commit()
        check_run(session, task, run)

        provider = OllamaModelProvider(
            settings.ollama_base_url, context_tokens=settings.model_context_tokens
        )
        decision = await route_model(session, classification, provider)
        run.selected_model_id = decision.model.id
        run.route = decision.data
        add_step(
            session,
            run,
            "routing",
            "Model routed",
            f"Selected {decision.model.model_key} through deterministic capability routing.",
            output_data={
                "model_id": str(decision.model.id),
                "model_key": decision.model.model_key,
                "selection_reason": decision.data["selection_reason"],
            },
        )
        add_audit(
            session,
            task,
            run,
            "MODEL_SELECTED",
            {"model_id": str(decision.model.id), "model_key": decision.model.model_key},
        )
        session.commit()
        check_run(session, task, run)

        registry = ToolRegistry()
        if classification.task_type == "coding":
            await execute_coding_workflow(
                session,
                task,
                run,
                provider,
                decision.model.model_key,
                registry,
            )
            check_run(session, task, run)
            run.status = task.status = "completed"
            run.completed_at = task.updated_at = now()
            add_audit(
                session,
                task,
                run,
                "TASK_COMPLETED",
                {"step_count": run.step_count, "workflow": "coding"},
            )
            session.commit()
            add_step(
                session,
                run,
                "lifecycle",
                "Coding task completed",
                "Verified patch and sandbox evidence committed.",
                output_data={"status": "completed"},
            )
            return
        evidence: list[dict[str, Any]] = []
        citations: list[dict[str, object]] = []
        if task.input_file_ids:
            registry.authorize(run.agent_profile, "analyze_visual_pages")
            add_audit(
                session,
                task,
                run,
                "TOOL_ALLOWED",
                {"tool": "analyze_visual_pages"},
            )
            session.commit()
            multimodal = await asyncio.wait_for(
                enrich_multimodal_inputs(
                    session,
                    task.workspace_id,
                    task.input_file_ids,
                    task.goal,
                    provider,
                    settings,
                ),
                timeout=settings.task_evidence_timeout_seconds,
            )
            if multimodal.candidate_pages or multimodal.ocr_pages:
                detail = (
                    f"{multimodal.vision_pages} visual pages analyzed with "
                    f"{multimodal.vision_model}."
                    if multimodal.vision_model
                    else f"{multimodal.ocr_pages} pages processed with OCR fallback."
                )
                add_step(
                    session,
                    run,
                    "multimodal",
                    "Multimodal evidence normalized",
                    detail,
                    tool_name="analyze_visual_pages",
                    output_data={
                        "candidate_pages": multimodal.candidate_pages,
                        "vision_pages": multimodal.vision_pages,
                        "ocr_pages": multimodal.ocr_pages,
                        "vision_model": multimodal.vision_model,
                        "warnings": multimodal.warnings,
                        "prompt_tokens": multimodal.prompt_tokens,
                        "completion_tokens": multimodal.completion_tokens,
                    },
                    duration_ms=multimodal.duration_ms,
                )
                add_audit(
                    session,
                    task,
                    run,
                    "MULTIMODAL_EVIDENCE_NORMALIZED",
                    {
                        "vision_model": multimodal.vision_model,
                        "vision_pages": multimodal.vision_pages,
                        "ocr_pages": multimodal.ocr_pages,
                        "warnings": multimodal.warnings,
                    },
                )
                session.commit()
                check_run(session, task, run)
        if task.input_file_ids:
            registry.authorize(run.agent_profile, "read_file")
            add_audit(
                session,
                task,
                run,
                "TOOL_ALLOWED",
                {"tool": "read_file", "file_count": len(task.input_file_ids)},
            )
        if task.knowledge_base_ids:
            registry.authorize(run.agent_profile, "search_knowledge")
            add_audit(
                session,
                task,
                run,
                "TOOL_ALLOWED",
                {
                    "tool": "search_knowledge",
                    "knowledge_base_count": len(task.knowledge_base_ids),
                },
            )
        session.commit()
        try:
            retrieval = await asyncio.wait_for(
                gather_hybrid_evidence(
                    session,
                    task.workspace_id,
                    task.input_file_ids,
                    task.knowledge_base_ids,
                    task.goal,
                    provider,
                    settings,
                ),
                timeout=settings.task_evidence_timeout_seconds,
            )
        except TimeoutError as exc:
            raise AppError(
                "EVIDENCE_TIMEOUT",
                "Document retrieval exceeded its bounded time limit.",
                504,
                True,
            ) from exc
        evidence = retrieval.evidence
        citations = citation_metadata(evidence)
        run.citations = citations
        for item in retrieval.processed_files:
            add_audit(session, task, run, "FILE_ACCESSED", item)
        for item in retrieval.searched_knowledge_bases:
            add_audit(session, task, run, "RAG_SEARCHED", item)
        used_sources = [
            {
                key: citation[key]
                for key in (
                    "source_id",
                    "display_name",
                    "page_start",
                    "page_end",
                    "retrieval_mode",
                    "source_type",
                    "file_id",
                    "knowledge_base_id",
                    "knowledge_base_name",
                )
                if key in citation
            }
            for citation in citations
        ]
        if task.input_file_ids or task.knowledge_base_ids:
            add_step(
                session,
                run,
                "retrieval",
                "Hybrid evidence gathered",
                (
                    f"{len(retrieval.processed_files)} files and "
                    f"{len(retrieval.searched_knowledge_bases)} knowledge bases processed; "
                    f"{len(evidence)} grounded passages selected via {retrieval.mode}."
                ),
                tool_name="hybrid_retrieval",
                input_data={
                    "file_count": len(task.input_file_ids),
                    "knowledge_base_count": len(task.knowledge_base_ids),
                    "query_length": len(task.goal),
                },
                output_data={
                    "mode": retrieval.mode,
                    "candidate_chunks": retrieval.candidate_chunks,
                    "evidence_chars": retrieval.evidence_chars,
                    "processed_files": retrieval.processed_files,
                    "searched_knowledge_bases": retrieval.searched_knowledge_bases,
                    "used_sources": used_sources,
                },
                duration_ms=retrieval.duration_ms,
            )
            add_audit(
                session,
                task,
                run,
                "EVIDENCE_MERGED",
                {
                    "mode": retrieval.mode,
                    "source_count": len(used_sources),
                    "evidence_chars": retrieval.evidence_chars,
                },
            )
        session.commit()
        check_run(session, task, run)

        procurement = (
            compare_procurement(evidence)
            if classification.task_type == "procurement"
            else None
        )
        if procurement and not {"xlsx", "docx"}.issubset(task.requested_outputs):
            raise AppError(
                "PROCUREMENT_ARTIFACTS_REQUIRED",
                "Procurement tasks require validated XLSX and DOCX outputs.",
                422,
            )
        prompt = grounded_prompt(task.goal, evidence)
        if procurement:
            prompt += (
                "\n\nVALIDATED PROCUREMENT COMPARISON:\n"
                + procurement.model_dump_json(indent=2)
                + "\n\nProvide brief review notes only. Do not change the computed totals, "
                "compliance results, or recommended vendor."
            )
        started = time.perf_counter()
        result_text: str | None = None
        for attempt in range(settings.task_max_retries + 1):
            try:
                chat = await provider.chat(
                    ChatRequest(decision.model.model_key, prompt, settings.model_keep_alive)
                )
                result_text = chat.content
                break
            except AppError:
                if attempt >= settings.task_max_retries:
                    raise
                run.retry_count += 1
                session.commit()
        if result_text is None:
            raise AppError("MODEL_EMPTY_RESPONSE", "The model did not produce a result.", 502)
        if citations:
            source_line = "; ".join(
                f"[{item['source_id']}] {item['display_name']}, page {item['page_start']}"
                for item in citations
            )
            if "[S" not in result_text:
                result_text += f"\n\nSources: {source_line}"
        if procurement:
            # The model may surface review notes, but it cannot author the governed
            # procurement decision or weaken mandatory approval controls.
            result_text = comparison_markdown(procurement)
        run.result_text = result_text
        add_step(
            session,
            run,
            "model",
            "Grounded response generated",
            (
                "A deterministic validator composed the governed procurement result after "
                f"{decision.model.model_key} completed its bounded review."
                if procurement
                else f"{decision.model.model_key} produced a validated local response."
            ),
            input_data={"prompt_chars": len(prompt), "evidence_count": len(evidence)},
            output_data={
                "response_chars": len(result_text),
                "citation_count": len(citations),
                **chat_metrics(chat),
            },
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        check_run(session, task, run)

        if procurement and {"docx", "xlsx"} & set(task.requested_outputs):
            registry.authorize(run.agent_profile, "create_xlsx")
            registry.authorize(run.agent_profile, "create_docx")
            add_audit(
                session,
                task,
                run,
                "TOOL_ALLOWED",
                {"tools": ["create_xlsx", "create_docx"]},
            )
            started = time.perf_counter()
            organization_name = (
                session.scalar(
                    select(Organization.name)
                    .join(User, User.organization_id == Organization.id)
                    .where(User.id == task.created_by_user_id)
                )
                or "Organization"
            )
            published_items = await asyncio.wait_for(
                asyncio.to_thread(
                    create_procurement_artifacts,
                    settings.data_root,
                    task.workspace_id,
                    run.id,
                    task.goal,
                    procurement,
                    citations,
                    organization_name,
                ),
                timeout=settings.tool_timeout_seconds,
            )
            for procurement_artifact in published_items:
                session.add(
                    Artifact(
                        workspace_id=task.workspace_id,
                        run_id=run.id,
                        logical_name=procurement_artifact.logical_name,
                        revision=1,
                        display_name=procurement_artifact.display_name,
                        storage_key=procurement_artifact.storage_key,
                        media_type=procurement_artifact.media_type,
                        size_bytes=procurement_artifact.size_bytes,
                        sha256=procurement_artifact.sha256,
                        validation_status="valid",
                    )
                )
            add_step(
                session,
                run,
                "artifact",
                "Procurement artifacts published",
                "Validated XLSX comparison and DOCX recommendation were published atomically.",
                tool_name="create_xlsx",
                input_data={
                    "quotation_lines": len(procurement.lines),
                    "vendors": len(procurement.vendors),
                },
                output_data={
                    "artifacts": [
                        {
                            "logical_name": item.logical_name,
                            "sha256": item.sha256,
                        }
                        for item in published_items
                    ],
                    "recommended_vendor": procurement.recommended_vendor,
                },
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            add_audit(
                session,
                task,
                run,
                "PROCUREMENT_ARTIFACTS_PUBLISHED",
                {
                    "artifact_count": len(published_items),
                    "recommended_vendor": procurement.recommended_vendor,
                },
            )
            session.commit()
        elif "docx" in task.requested_outputs:
            registry.authorize(run.agent_profile, "create_docx")
            add_audit(session, task, run, "TOOL_ALLOWED", {"tool": "create_docx"})
            started = time.perf_counter()
            organization_name = (
                session.scalar(
                    select(Organization.name)
                    .join(User, User.organization_id == Organization.id)
                    .where(User.id == task.created_by_user_id)
                )
                or "Organization"
            )
            published = await asyncio.wait_for(
                asyncio.to_thread(
                    create_approval_docx,
                    settings.data_root,
                    task.workspace_id,
                    run.id,
                    task.goal,
                    result_text,
                    citations,
                    organization_name,
                ),
                timeout=settings.tool_timeout_seconds,
            )
            artifact = Artifact(
                workspace_id=task.workspace_id,
                run_id=run.id,
                logical_name="approval_recommendation",
                revision=1,
                display_name=published.display_name,
                storage_key=published.storage_key,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=published.size_bytes,
                sha256=published.sha256,
                validation_status="valid",
            )
            session.add(artifact)
            session.flush()
            add_step(
                session,
                run,
                "artifact",
                "Approval DOCX published",
                f"Validated immutable artifact {published.display_name}.",
                tool_name="create_docx",
                input_data={"citation_count": len(citations)},
                output_data={
                    "artifact_id": str(artifact.id),
                    "display_name": artifact.display_name,
                    "sha256": artifact.sha256,
                    "validation_status": artifact.validation_status,
                },
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            add_audit(
                session,
                task,
                run,
                "ARTIFACT_PUBLISHED",
                {"artifact_id": str(artifact.id), "sha256": artifact.sha256},
            )
            session.commit()
        check_run(session, task, run)

        run.status = task.status = "completed"
        run.completed_at = task.updated_at = now()
        add_audit(
            session,
            task,
            run,
            "TASK_COMPLETED",
            {
                "step_count": run.step_count,
                "workflow": classification.task_type,
                "requested_outputs": task.requested_outputs,
            },
        )
        session.commit()
        add_step(
            session,
            run,
            "lifecycle",
            "Task completed",
            "Result and validation evidence committed.",
            output_data={"status": "completed"},
        )
    except AppError as exc:
        if exc.code in {"TASK_CANCELLED", "TASK_TIMED_OUT"}:
            return
        session.rollback()
        if run and task:
            run = session.get(TaskRun, run.id)
            task = session.get(Task, task.id)
            if run and task and run.status not in TERMINAL:
                run.status = task.status = "failed"
                run.error_category = "dependency_unavailable" if exc.retryable else "validation"
                run.error_message = exc.message[:500]
                run.completed_at = task.updated_at = now()
                if "DENIED" in exc.code or "POLICY" in exc.code:
                    add_audit(
                        session,
                        task,
                        run,
                        "POLICY_DENIED",
                        {"error_code": exc.code, "category": run.error_category},
                    )
                add_audit(
                    session,
                    task,
                    run,
                    "TASK_FAILED",
                    {"error_code": exc.code, "category": run.error_category},
                )
                session.commit()
                with suppress(AppError):
                    add_step(
                        session,
                        run,
                        "error",
                        "Task failed safely",
                        exc.message,
                        status="failed",
                        error_category=run.error_category,
                    )
    except Exception:
        session.rollback()
        if run and task:
            run = session.get(TaskRun, run.id)
            task = session.get(Task, task.id)
            if run and task and run.status not in TERMINAL:
                run.status = task.status = "failed"
                run.error_category = "internal"
                run.error_message = "The local agent encountered an internal error."
                run.completed_at = task.updated_at = now()
                add_audit(session, task, run, "TASK_FAILED", {"category": "internal"})
                session.commit()
    finally:
        session.close()


async def recover_incomplete_runs() -> None:
    session = SessionLocal()
    try:
        runs = list(
            session.scalars(
                select(TaskRun)
                .where(TaskRun.status.in_(["queued", "running"]))
                .order_by(TaskRun.created_at)
            )
        )
        for run in runs:
            if run.status == "running":
                run.status = "queued"
                task = session.get(Task, run.task_id)
                if task:
                    task.status = "queued"
        session.commit()
    finally:
        session.close()


def notify_task_worker() -> None:
    """Wake the local worker after a durable run has been committed."""
    if _worker_event_loop and _worker_event_loop.is_running():
        _worker_event_loop.call_soon_threadsafe(_worker_wakeup.set)


def _next_queued_run_id() -> uuid.UUID | None:
    session = SessionLocal()
    try:
        return session.scalar(
            select(TaskRun.id)
            .where(TaskRun.status == "queued")
            .order_by(TaskRun.created_at, TaskRun.id)
            .limit(1)
        )
    finally:
        session.close()


async def task_worker_loop() -> None:
    """Continuously drain the durable FIFO queue with one local executor."""
    settings = get_settings()
    while not _worker_stop.is_set():
        run_id = _next_queued_run_id()
        if run_id is not None:
            await execute_run(run_id)
            continue
        _worker_wakeup.clear()
        with suppress(TimeoutError):
            await asyncio.wait_for(
                _worker_wakeup.wait(), timeout=settings.task_worker_poll_seconds
            )


async def start_task_worker() -> asyncio.Task[None]:
    global _worker_event_loop
    await recover_incomplete_runs()
    _worker_event_loop = asyncio.get_running_loop()
    _worker_stop.clear()
    _worker_wakeup.set()
    return asyncio.create_task(task_worker_loop(), name="sovereign-task-worker")


async def stop_task_worker(worker: asyncio.Task[None]) -> None:
    global _worker_event_loop
    _worker_stop.set()
    _worker_wakeup.set()
    try:
        await asyncio.wait_for(worker, timeout=5)
    except TimeoutError:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
    _worker_event_loop = None
