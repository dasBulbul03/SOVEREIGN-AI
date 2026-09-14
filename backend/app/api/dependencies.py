from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db
from app.model_providers.ollama import OllamaModelProvider

DatabaseSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_ollama_provider(settings: AppSettings) -> OllamaModelProvider:
    return OllamaModelProvider(
        settings.ollama_base_url, context_tokens=settings.model_context_tokens
    )


OllamaProvider = Annotated[OllamaModelProvider, Depends(get_ollama_provider)]


def get_current_user(request: Request, session: DatabaseSession, settings: AppSettings) -> User:
    from app.services.auth import user_for_token

    return user_for_token(session, request.cookies.get(settings.auth_cookie_name))


CurrentUser = Annotated[User, Depends(get_current_user)]
