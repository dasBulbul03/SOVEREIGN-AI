from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import AuditEvent, RegisteredModel, StoredFile, User, Workspace
from app.db.session import get_db
from app.main import app
from app.services.auth import verify_password

DEMO_EMAIL = "demo@sovereignforge.local"
DEMO_PASSWORD = "SovereignForgeDemo!2026"


@pytest.mark.asyncio
async def test_local_signup_session_signin_and_signout() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            signup = await client.post(
                "/api/v1/auth/signup",
                json={
                    "organization_name": "SOVEREIGN AI Demo",
                    "full_name": "Demo Administrator",
                    "email": DEMO_EMAIL,
                    "password": DEMO_PASSWORD,
                },
            )
            assert signup.status_code == 201
            assert signup.json()["organization"]["name"] == "SOVEREIGN AI Demo"
            assert "HttpOnly" in signup.headers["set-cookie"]

            current = await client.get("/api/v1/auth/me")
            assert current.status_code == 200
            assert current.json()["email"] == DEMO_EMAIL

            updated = await client.patch(
                "/api/v1/auth/me", json={"full_name": "Updated Administrator"}
            )
            assert updated.status_code == 200
            assert updated.json()["full_name"] == "Updated Administrator"
            sessions = await client.get("/api/v1/auth/sessions")
            assert sessions.status_code == 200
            assert len(sessions.json()) == 1
            assert sessions.json()[0]["current"] is True

            with testing_session() as session:
                user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
                assert user is not None
                assert user.password_hash != DEMO_PASSWORD
                assert verify_password(user.password_hash, DEMO_PASSWORD)
                workspace = session.scalar(
                    select(Workspace).where(Workspace.organization_id == user.organization_id)
                )
                assert workspace is not None
                assert workspace.name == "SOVEREIGN AI Demo Workspace"
                stored = StoredFile(
                    workspace_id=workspace.id,
                    display_name="temporary.txt",
                    storage_key=f"testing/{workspace.id}/temporary.txt",
                    media_type="text/plain",
                    size_bytes=12,
                    sha256="0" * 64,
                )
                session.add(stored)
                session.commit()
                file_id = stored.id
                workspace_id = workspace.id

            listed = await client.get(f"/api/v1/workspaces/{workspace_id}/files")
            assert [item["id"] for item in listed.json()] == [str(file_id)]
            removed = await client.delete(f"/api/v1/workspaces/{workspace_id}/files/{file_id}")
            assert removed.status_code == 204
            assert (await client.get(f"/api/v1/workspaces/{workspace_id}/files")).json() == []
            with testing_session() as session:
                retained = session.get(StoredFile, file_id)
                assert retained is not None
                assert retained.status == "deleted"
                audit = session.scalar(
                    select(AuditEvent).where(AuditEvent.event_type == "FILE_REMOVED")
                )
                assert audit is not None
                assert audit.actor_id == user.id

            signout = await client.post("/api/v1/auth/signout")
            assert signout.status_code == 204
            assert (await client.get("/api/v1/auth/me")).status_code == 401

            signin = await client.post(
                "/api/v1/auth/signin",
                json={
                    "email": DEMO_EMAIL.upper(),
                    "password": DEMO_PASSWORD,
                },
            )
            assert signin.status_code == 200
            assert (await client.get("/api/v1/auth/me")).status_code == 200
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_protected_api_requires_authentication() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/models")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


@pytest.mark.asyncio
async def test_only_owner_can_enable_and_disable_registered_models() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            signup = await client.post(
                "/api/v1/auth/signup",
                json={
                    "organization_name": "Model Operators",
                    "full_name": "Registry Owner",
                    "email": "registry-owner@example.test",
                    "password": "RegistryOwnerPassword!2026",
                },
            )
            assert signup.status_code == 201

            with testing_session() as session:
                model = RegisteredModel(
                    name="Registry Test Model",
                    provider="ollama",
                    model_key="registry-test:latest",
                    capabilities=["text", "reasoning", "general"],
                    priority=100,
                )
                session.add(model)
                session.commit()
                model_id = model.id

            disabled = await client.patch(f"/api/v1/models/{model_id}", json={"enabled": False})
            assert disabled.status_code == 200
            assert disabled.json()["enabled"] is False

            listed = await client.get("/api/v1/models")
            assert listed.status_code == 200
            assert listed.json()[0]["id"] == str(model_id)
            assert listed.json()[0]["enabled"] is False

            with testing_session() as session:
                user = session.scalar(
                    select(User).where(User.email == "registry-owner@example.test")
                )
                assert user is not None
                user.role = "member"
                session.commit()

            forbidden = await client.patch(f"/api/v1/models/{model_id}", json={"enabled": True})
            assert forbidden.status_code == 403

            with testing_session() as session:
                persisted = session.get(RegisteredModel, model_id)
                assert persisted is not None
                assert persisted.enabled is False
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
