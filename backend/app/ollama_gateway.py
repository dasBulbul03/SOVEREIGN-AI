"""Fixed-purpose bridge from the isolated application network to native Ollama.

The gateway deliberately is not a general HTTP proxy. It exposes only the three
Ollama operations used by this application and always forwards to one configured
local upstream.
"""

import os
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, Response

UPSTREAM = os.environ.get("OLLAMA_UPSTREAM_URL", "http://host.docker.internal:11434").rstrip("/")
ALLOWED: dict[tuple[str, str], Literal["GET", "POST"]] = {
    ("GET", "/api/tags"): "GET",
    ("POST", "/api/chat"): "POST",
    ("POST", "/api/embed"): "POST",
}
MAX_REQUEST_BYTES = 32 * 1024 * 1024

app = FastAPI(
    title="SOVEREIGN AI Local Ollama Gateway",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{UPSTREAM}/api/tags")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Local Ollama is unavailable") from exc
    return {"status": "ready", "upstream": "native-local-ollama"}


@app.api_route("/api/{operation}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(operation: str, request: Request) -> Response:
    path = f"/api/{operation}"
    method = request.method.upper()
    if (method, path) not in ALLOWED:
        raise HTTPException(403, "Operation is not allowed by the local inference gateway")
    content = await request.body()
    if len(content) > MAX_REQUEST_BYTES:
        raise HTTPException(413, "Inference request exceeds the gateway limit")
    headers: dict[str, Any] = {"Content-Type": "application/json"} if content else {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=5)) as client:
            upstream = await client.request(
                method,
                f"{UPSTREAM}{path}",
                content=content or None,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Local Ollama request failed") from exc
    response_headers = {}
    if content_type := upstream.headers.get("content-type"):
        response_headers["Content-Type"] = content_type
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )
