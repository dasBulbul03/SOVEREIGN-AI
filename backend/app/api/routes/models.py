from uuid import UUID

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DatabaseSession, OllamaProvider
from app.core.errors import AppError
from app.schemas.common import ModelCreate, ModelResponse, ModelStateUpdate
from app.services.model_registry import (
    check_model_health,
    get_model,
    list_models,
    register_model,
    set_model_enabled,
    to_response,
)

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelResponse])
def models(session: DatabaseSession, _: CurrentUser) -> list[ModelResponse]:
    return list_models(session)


@router.post("", response_model=ModelResponse, status_code=201)
async def create_model(
    payload: ModelCreate,
    session: DatabaseSession,
    provider: OllamaProvider,
    user: CurrentUser,
) -> ModelResponse:
    if user.role != "owner":
        raise AppError("OWNER_REQUIRED", "Only an organization owner can register models.", 403)
    model = register_model(session, payload)
    return await check_model_health(session, model, provider)


@router.patch("/{model_id}", response_model=ModelResponse)
def update_model_state(
    model_id: UUID,
    payload: ModelStateUpdate,
    session: DatabaseSession,
    user: CurrentUser,
) -> ModelResponse:
    if user.role != "owner":
        raise AppError("OWNER_REQUIRED", "Only an organization owner can manage models.", 403)
    return to_response(set_model_enabled(session, model_id, payload.enabled))


@router.post("/{model_id}/health-check", response_model=ModelResponse)
async def model_health(
    model_id: UUID, session: DatabaseSession, provider: OllamaProvider, _: CurrentUser
) -> ModelResponse:
    model = get_model(session, model_id)
    return await check_model_health(session, model, provider)
