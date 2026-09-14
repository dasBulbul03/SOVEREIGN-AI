import uuid
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import ModelHealthRecord, RegisteredModel
from app.model_providers.base import ChatRequest
from app.model_providers.ollama import OllamaModelProvider
from app.schemas.common import ModelCreate, ModelHealth, ModelResponse


def _latest_health(model: RegisteredModel) -> ModelHealth | None:
    if not model.health_records:
        return None
    record = max(model.health_records, key=lambda item: item.observed_at)
    status = cast(
        Literal["ready", "unavailable", "unknown"],
        record.status if record.status in {"ready", "unavailable", "unknown"} else "unknown",
    )
    return ModelHealth(
        status=status,
        observed_at=record.observed_at,
        latency_ms=record.latency_ms,
        details=record.details,
    )


def to_response(model: RegisteredModel) -> ModelResponse:
    return ModelResponse(
        id=model.id,
        name=model.name,
        provider=model.provider,
        model_key=model.model_key,
        capabilities=model.capabilities,
        context_window=model.context_window,
        quantization=model.quantization,
        priority=model.priority,
        enabled=model.enabled,
        latest_health=_latest_health(model),
    )


def list_models(session: Session) -> list[ModelResponse]:
    statement = select(RegisteredModel).order_by(
        RegisteredModel.priority.desc(), RegisteredModel.name
    )
    return [to_response(model) for model in session.scalars(statement).unique().all()]


def register_model(session: Session, payload: ModelCreate) -> RegisteredModel:
    model = RegisteredModel(
        name=payload.name.strip(),
        provider="ollama",
        model_key=payload.model_key,
        capabilities=list(dict.fromkeys(payload.capabilities)),
        context_window=payload.context_window,
        quantization=payload.quantization,
        priority=payload.priority,
    )
    session.add(model)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "MODEL_ALREADY_REGISTERED", "This Ollama model is already registered.", 409
        ) from exc
    session.refresh(model)
    return model


def get_model(session: Session, model_id: uuid.UUID) -> RegisteredModel:
    model = session.get(RegisteredModel, model_id)
    if model is None:
        raise AppError("MODEL_NOT_FOUND", "The requested model is not available.", 404)
    if not model.enabled:
        raise AppError("MODEL_DISABLED", "The requested model is disabled.", 409)
    return model


def set_model_enabled(session: Session, model_id: uuid.UUID, enabled: bool) -> RegisteredModel:
    model = session.get(RegisteredModel, model_id)
    if model is None:
        raise AppError("MODEL_NOT_FOUND", "The requested model is not available.", 404)
    model.enabled = enabled
    model.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(model)
    return model


async def select_general_model(session: Session, provider: OllamaModelProvider) -> RegisteredModel:
    statement = (
        select(RegisteredModel)
        .where(RegisteredModel.enabled.is_(True))
        .order_by(RegisteredModel.priority.desc(), RegisteredModel.model_key)
    )
    models = session.scalars(statement).all()
    candidates = [
        item
        for item in models
        if "general" in item.capabilities and "vision" not in item.capabilities
    ]
    for model in candidates:
        if (await provider.health(model.model_key)).ready:
            return model
    raise AppError(
        "NO_GENERAL_MODEL",
        "No healthy local general model is available.",
        503,
        retryable=True,
    )


async def check_model_health(
    session: Session, model: RegisteredModel, provider: OllamaModelProvider
) -> ModelResponse:
    try:
        result = await provider.health(model.model_key)
        status = "ready" if result.ready else "unavailable"
        details = result.details
        latency_ms = result.latency_ms
    except AppError as exc:
        status = "unavailable"
        details = {"error_code": exc.code, "provider_reachable": False}
        latency_ms = None

    record = ModelHealthRecord(
        model_id=model.id,
        status=status,
        observed_at=datetime.now(UTC),
        latency_ms=latency_ms,
        details=details,
    )
    session.add(record)
    session.commit()
    session.refresh(model)
    return to_response(model)


async def run_inference(
    model: RegisteredModel,
    prompt: str,
    provider: OllamaModelProvider,
    keep_alive: str,
) -> tuple[str, int]:
    if "embedding" in model.capabilities and "text" not in model.capabilities:
        raise AppError("MODEL_NOT_GENERATIVE", "The selected model cannot generate text.", 422)
    result = await provider.chat(
        ChatRequest(model_key=model.model_key, prompt=prompt, keep_alive=keep_alive)
    )
    return result.content, result.duration_ms
