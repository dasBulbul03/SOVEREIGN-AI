import re
from dataclasses import dataclass
from pathlib import PurePath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.file_types import is_source_code_filename
from app.db.models import RegisteredModel
from app.model_providers.ollama import OllamaModelProvider


@dataclass(frozen=True, slots=True)
class Classification:
    task_type: str
    capabilities: list[str]
    agent_profile: str
    reasons: list[str]


@dataclass(frozen=True, slots=True)
class RouteDecision:
    model: RegisteredModel
    data: dict[str, object]


def classify_task(
    goal: str,
    has_files: bool,
    has_knowledge: bool,
    requested_mode: str = "auto",
    filenames: list[str] | tuple[str, ...] = (),
) -> Classification:
    normalized = goal.casefold()
    source_suffixes = sorted(
        {PurePath(name.casefold()).suffix for name in filenames if is_source_code_filename(name)}
    )
    coding_terms = (
        "api endpoint",
        "backend",
        "bug",
        "build error",
        "code",
        "coding",
        "compile",
        "compiler",
        "database migration",
        "debug",
        "frontend",
        "function",
        "implement",
        "javascript",
        "python",
        "react component",
        "refactor",
        "repository",
        "source file",
        "test",
        "tests",
        "typescript",
    )
    coding = bool(source_suffixes) or any(
        re.search(rf"\b{re.escape(term)}\b", normalized) for term in coding_terms
    )
    spreadsheet = requested_mode == "procurement" or any(
        word in normalized
        for word in ("spreadsheet", "quotation", "procurement", "vendor", "compare bids")
    )
    document = has_files or any(word in normalized for word in ("document", "pdf", "inspection"))
    rag = has_knowledge or any(
        word in normalized for word in ("policy", "sop", "manual", "knowledge")
    )
    if requested_mode == "coding":
        return Classification("coding", ["text", "coding"], "coding_agent", ["coding intent"])
    if requested_mode == "procurement":
        return Classification(
            "procurement", ["text", "reasoning"], "procurement_agent", ["procurement intent"]
        )
    if requested_mode == "document":
        return Classification(
            "document_analysis", ["text", "reasoning"], "document_agent", ["document intent"]
        )
    if coding:
        reason = (
            f"source files supplied: {', '.join(source_suffixes)}"
            if source_suffixes
            else "coding intent"
        )
        return Classification("coding", ["text", "coding"], "coding_agent", [reason])
    if spreadsheet:
        return Classification(
            "procurement", ["text", "reasoning"], "procurement_agent", ["procurement intent"]
        )
    if rag:
        return Classification(
            "rag", ["text", "reasoning"], "document_agent", ["knowledge base supplied"]
        )
    if document:
        return Classification(
            "document_analysis", ["text", "reasoning"], "document_agent", ["files supplied"]
        )
    return Classification("general", ["text", "reasoning"], "general_agent", ["default route"])


async def route_model(
    session: Session, classification: Classification, provider: OllamaModelProvider
) -> RouteDecision:
    candidates = list(
        session.scalars(
            select(RegisteredModel)
            .where(RegisteredModel.enabled.is_(True))
            .order_by(RegisteredModel.priority.desc(), RegisteredModel.model_key)
        )
    )
    evaluated: list[dict[str, object]] = []
    selected: RegisteredModel | None = None
    for candidate in candidates:
        missing = sorted(set(classification.capabilities) - set(candidate.capabilities))
        reserved_for_vision = (
            "vision" in candidate.capabilities
            and "vision" not in classification.capabilities
            and "coding" not in classification.capabilities
        )
        record: dict[str, object] = {
            "model_id": str(candidate.id),
            "model_key": candidate.model_key,
            "priority": candidate.priority,
            "missing_capabilities": missing,
            "eligible": False,
        }
        if reserved_for_vision:
            record["exclusion_reason"] = "reserved for visual preprocessing"
        elif not missing:
            health = await provider.health(candidate.model_key)
            record["health"] = "ready" if health.ready else "unavailable"
            record["latency_ms"] = health.latency_ms
            record["eligible"] = health.ready
            if health.ready and selected is None:
                selected = candidate
        evaluated.append(record)
    if selected is None:
        raise AppError(
            "NO_CAPABLE_MODEL", "No healthy local model covers the task capabilities.", 503, True
        )
    return RouteDecision(
        selected,
        {
            "task_type": classification.task_type,
            "required_capabilities": classification.capabilities,
            "classification_reasons": classification.reasons,
            "candidates": evaluated,
            "selected_model_id": str(selected.id),
            "selected_model_key": selected.model_key,
            "selection_reason": "highest-priority healthy model covering every capability",
        },
    )
