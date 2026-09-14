import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response as StarletteResponse

from app.api.routes import auth, health, inference, knowledge, models, security, tasks
from app.core.config import get_settings
from app.core.errors import AppError


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    from app.tasks.runtime import start_task_worker, stop_task_worker

    worker = await start_task_worker()
    try:
        yield
    finally:
        await stop_task_worker(worker)


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first SOVEREIGN AI application API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def enforce_origin_and_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[StarletteResponse]],
) -> StarletteResponse:
    origin = request.headers.get("origin")
    unsafe_origin = (
        request.method in {"POST", "PATCH", "PUT", "DELETE"}
        and origin
        and origin != settings.frontend_origin
    )
    if unsafe_origin:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "ORIGIN_DENIED",
                    "message": "The request origin is not allowed.",
                    "correlation_id": str(uuid.uuid4()),
                    "retryable": False,
                    "details": {},
                }
            },
        )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    correlation_id = str(uuid.uuid4())
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "correlation_id": correlation_id,
                "retryable": exc.retryable,
                "details": exc.details,
            }
        },
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(inference.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(security.router, prefix="/api/v1")
