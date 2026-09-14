from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_settings
from app.artifacts.procurement import safe_spreadsheet_text
from app.core.config import Settings
from app.core.errors import AppError
from app.db.base import Base
from app.db.models import AuditEvent, Workspace
from app.db.session import get_db
from app.ingress_gateway import app as ingress_app
from app.main import app
from app.ollama_gateway import app as gateway_app
from app.tools.registry import ToolRegistry


@pytest.fixture
def security_client() -> Generator[tuple[httpx.ASGITransport, sessionmaker[Session]], None, None]:
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
    app.dependency_overrides[get_settings] = lambda: Settings(app_egress_enforced=True)
    try:
        yield httpx.ASGITransport(app=app), testing_session
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


async def signup(client: httpx.AsyncClient, suffix: str = "one") -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": f"Security {suffix}",
            "full_name": "Security Owner",
            "email": f"security-{suffix}@example.test",
            "password": "SecurityTestPassword!2026",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_security_headers_and_cross_origin_mutation_are_enforced(
    security_client: tuple[httpx.ASGITransport, sessionmaker[Session]],
) -> None:
    transport, _ = security_client
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/v1/health")
        denied = await client.post(
            "/api/v1/auth/signin",
            headers={"Origin": "https://untrusted.example"},
            json={"email": "nobody@example.test", "password": "not-a-real-password"},
        )

    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"
    assert health.headers["referrer-policy"] == "no-referrer"
    assert health.headers["cache-control"] == "no-store"
    assert "camera=()" in health.headers["permissions-policy"]
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ORIGIN_DENIED"


@pytest.mark.asyncio
async def test_blocked_egress_is_persisted_and_aggregated(
    security_client: tuple[httpx.ASGITransport, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport, testing_session = security_client

    async def blocked(*_: object, **__: object) -> httpx.Response:
        request = httpx.Request("GET", "https://example.com")
        raise httpx.ConnectError("network unreachable", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", blocked)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await signup(client)
        probe = await client.post("/api/v1/security/egress-test")
        monkeypatch.undo()
        status = await client.get("/api/v1/security/status")

    assert probe.status_code == 200
    assert probe.json()["status"] == "blocked"
    assert probe.json()["enforcement"] == "configured"
    assert status.status_code == 200
    assert status.json()["overall"] == "verified"
    assert status.json()["latest_egress_probe"]["status"] == "blocked"
    assert status.json()["metrics"]["prompt_tokens"] is None
    with testing_session() as session:
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "EGRESS_PROBE_COMPLETED")
        )
        assert event is not None
        assert event.payload["probe_version"] == "day6-v1"


@pytest.mark.asyncio
async def test_audit_events_are_organization_scoped_and_do_not_store_task_prompt(
    security_client: tuple[httpx.ASGITransport, sessionmaker[Session]],
) -> None:
    transport, testing_session = security_client
    secret_goal = "CONFIDENTIAL-PROMPT-VALUE must not enter audit payloads"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as first:
        await signup(first, "first")
        with testing_session() as session:
            workspace = session.scalar(select(Workspace).order_by(Workspace.created_at))
            assert workspace is not None
            workspace_id = workspace.id
        submitted = await first.post(
            "/api/v1/tasks",
            headers={"Idempotency-Key": "security-redaction-test"},
            json={"workspace_id": str(workspace_id), "goal": secret_goal},
        )
        assert submitted.status_code == 202
        events = await first.get("/api/v1/audit-events?limit=20")

    serialized = events.text
    assert secret_goal not in serialized
    assert "TASK_CREATED" in serialized


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-2+3", "@SUM(A1:A2)", "\tformula"])
def test_formula_leading_values_are_forced_to_safe_spreadsheet_text(value: str) -> None:
    escaped = safe_spreadsheet_text(value)
    assert escaped.startswith("'")
    assert escaped[1:] == value


def test_document_agent_cannot_obey_prompt_injection_for_code_tools() -> None:
    registry = ToolRegistry()
    with pytest.raises(AppError) as denied:
        registry.authorize("document_agent", "run_python_tests")
    assert denied.value.code == "TOOL_POLICY_DENIED"


@pytest.mark.asyncio
async def test_local_ollama_gateway_is_not_a_general_proxy() -> None:
    transport = httpx.ASGITransport(app=gateway_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        denied_path = await client.get("/api/pull")
        denied_method = await client.delete("/api/tags")

    assert denied_path.status_code == 403
    assert denied_method.status_code == 403


@pytest.mark.asyncio
async def test_api_ingress_preserves_browser_cors_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def upstream_request(*_: object, **__: object) -> httpx.Response:
        request = httpx.Request("GET", "http://api-worker:8000/api/v1/auth/me")
        return httpx.Response(
            200,
            json={"email": "owner@example.test"},
            headers={
                "Access-Control-Allow-Origin": "http://localhost:3000",
                "Access-Control-Allow-Credentials": "true",
                "Vary": "Origin",
            },
            request=request,
        )

    monkeypatch.setattr(httpx.AsyncClient, "request", upstream_request)
    transport = httpx.ASGITransport(app=ingress_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://ingress") as client:
        response = await client.get(
            "/api/v1/auth/me", headers={"Origin": "http://localhost:3000"}
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["vary"] == "Origin"


@pytest.mark.asyncio
async def test_api_ingress_forwards_cors_preflight_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forwarded_headers: dict[str, str] = {}
    original_send = httpx.AsyncClient.send

    async def intercept_upstream(
        client: httpx.AsyncClient,
        request: httpx.Request,
        *args: object,
        **kwargs: object,
    ) -> httpx.Response:
        if request.url.host == "api-worker":
            forwarded_headers.update(dict(request.headers))
            return httpx.Response(
                200,
                headers={
                    "Access-Control-Allow-Origin": "http://localhost:3000",
                    "Access-Control-Allow-Methods": "POST",
                    "Access-Control-Allow-Headers": "Content-Type",
                },
                request=request,
            )
        return await original_send(client, request, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx.AsyncClient, "send", intercept_upstream)
    transport = httpx.ASGITransport(app=ingress_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://ingress") as client:
        response = await client.options(
            "/api/v1/knowledge-bases/kb-id/ingestions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert forwarded_headers["access-control-request-method"] == "POST"
    assert forwarded_headers["access-control-request-headers"] == "content-type"
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
