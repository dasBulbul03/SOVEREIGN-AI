import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.db.models import AuthSession, Organization, User, Workspace
from app.schemas.auth import AuthUserResponse, OrganizationResponse, SessionResponse, SignupRequest

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def organization_slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "organization"
    return f"{base}-{secrets.token_hex(3)}"


def create_account(session: Session, data: SignupRequest) -> User:
    organization = Organization(
        name=data.organization_name,
        slug=organization_slug(data.organization_name),
    )
    session.add(organization)
    session.flush()
    user = User(
        organization_id=organization.id,
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role="owner",
    )
    session.add_all(
        [user, Workspace(organization_id=organization.id, name=f"{organization.name} Workspace")]
    )
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise AppError(
            "account_exists", "An account with this email already exists.", 409
        ) from error
    session.refresh(user)
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    user = session.scalar(
        select(User).options(joinedload(User.organization)).where(User.email == email.casefold())
    )
    if user is None or not user.is_active or not verify_password(user.password_hash, password):
        raise AppError("invalid_credentials", "Email or password is incorrect.", 401)
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        session.commit()
    return user


def create_auth_session(session: Session, user: User, lifetime_hours: int) -> str:
    token = secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=datetime.now(UTC) + timedelta(hours=lifetime_hours),
        )
    )
    session.commit()
    return token


def user_for_token(session: Session, token: str | None) -> User:
    if not token:
        raise AppError("authentication_required", "Sign in to continue.", 401)
    auth_session = session.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user).joinedload(User.organization))
        .where(AuthSession.token_hash == token_digest(token))
    )
    now = datetime.now(UTC)
    if auth_session is None:
        raise AppError("authentication_required", "Sign in to continue.", 401)
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now or not auth_session.user.is_active:
        session.delete(auth_session)
        session.commit()
        raise AppError("session_expired", "Your session expired. Sign in again.", 401)
    auth_session.last_used_at = now
    session.commit()
    return auth_session.user


def revoke_session(session: Session, token: str | None) -> None:
    if not token:
        return
    auth_session = session.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(token))
    )
    if auth_session is not None:
        session.delete(auth_session)
        session.commit()


def update_profile(session: Session, user: User, full_name: str) -> User:
    user.full_name = full_name
    user.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(user)
    return user


def list_user_sessions(
    session: Session, user: User, current_token: str | None
) -> list[SessionResponse]:
    current_digest = token_digest(current_token) if current_token else None
    records = list(
        session.scalars(
            select(AuthSession)
            .where(AuthSession.user_id == user.id)
            .order_by(AuthSession.last_used_at.desc())
        )
    )
    return [
        SessionResponse(
            id=record.id,
            current=record.token_hash == current_digest,
            created_at=record.created_at,
            last_used_at=record.last_used_at,
            expires_at=record.expires_at,
        )
        for record in records
    ]


def revoke_user_session(session: Session, user: User, session_id: uuid.UUID) -> None:
    record = session.scalar(
        select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user.id)
    )
    if record is None:
        raise AppError("SESSION_NOT_FOUND", "Session not found.", 404)
    session.delete(record)
    session.commit()


def auth_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organization=OrganizationResponse(
            id=user.organization.id,
            name=user.organization.name,
            slug=user.organization.slug,
        ),
    )
