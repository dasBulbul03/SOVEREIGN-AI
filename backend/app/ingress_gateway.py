"""Fixed-upstream browser ingress for the network-isolated API service."""

import os

import httpx
from fastapi import FastAPI, HTTPException, Request, Response

UPSTREAM = os.environ.get("API_UPSTREAM_URL", "http://api-worker:8000").rstrip("/")
MAX_REQUEST_BYTES = 32 * 1024 * 1024
REQUEST_HEADERS = {
    "accept",
    "access-control-request-headers",
    "access-control-request-method",
    "content-type",
    "cookie",
    "idempotency-key",
    "origin",
}
RESPONSE_HEADERS = {
    "access-control-allow-credentials",
    "access-control-allow-headers",
    "access-control-allow-methods",
    "access-control-allow-origin",
    "content-type",
    "content-disposition",
    "set-cookie",
    "cache-control",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
    "content-security-policy",
    "vary",
}

app = FastAPI(
    title="SOVEREIGN AI Local API Ingress",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/gateway-health")
async def gateway_health() -> dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{UPSTREAM}/api/v1/health")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Internal API is unavailable") from exc
    return {"status": "ready", "upstream": "internal-api"}


@app.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy(path: str, request: Request) -> Response:
    content = await request.body()
    if len(content) > MAX_REQUEST_BYTES:
        raise HTTPException(413, "Request exceeds the ingress limit")
    request_headers = {
        name: value
        for name, value in request.headers.items()
        if name.casefold() in REQUEST_HEADERS
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(240, connect=5)) as client:
            upstream = await client.request(
                request.method,
                f"{UPSTREAM}/api/v1/{path}",
                params=request.query_params,
                content=content or None,
                headers=request_headers,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Internal API request failed") from exc
    response_headers = {
        name: value
        for name, value in upstream.headers.items()
        if name.casefold() in RESPONSE_HEADERS
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )
