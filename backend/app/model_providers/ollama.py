import time
from typing import Any

import httpx

from app.core.errors import AppError
from app.model_providers.base import ChatRequest, ChatResult, EmbeddingResult, ProviderHealth


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int | float) else None


def _nanoseconds_to_ms(value: object) -> int | None:
    return int(value / 1_000_000) if isinstance(value, int | float) else None


class OllamaModelProvider:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 120.0,
        context_tokens: int = 8_192,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self._context_tokens = context_tokens

    async def _installed_models(self) -> tuple[list[str], int]:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                code="OLLAMA_UNAVAILABLE",
                message="The local Ollama service is unavailable.",
                status_code=503,
                retryable=True,
            ) from exc
        elapsed = int((time.perf_counter() - started) * 1000)
        payload = response.json()
        names = [str(item.get("name")) for item in payload.get("models", []) if item.get("name")]
        return names, elapsed

    async def health(self, model_key: str) -> ProviderHealth:
        names, elapsed = await self._installed_models()
        ready = model_key in names or any(name.split(":", 1)[0] == model_key for name in names)
        return ProviderHealth(
            ready=ready,
            latency_ms=elapsed,
            details={"installed": ready, "provider_reachable": True},
        )

    async def chat(self, request: ChatRequest) -> ChatResult:
        message: dict[str, Any] = {"role": "user", "content": request.prompt}
        if request.images:
            message["images"] = list(request.images)
        payload: dict[str, Any] = {
            "model": request.model_key,
            "stream": False,
            "keep_alive": request.keep_alive,
            "messages": [message],
            "options": {
                "temperature": request.temperature,
                "seed": request.seed,
                "num_ctx": self._context_tokens,
            },
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = (
                "MODEL_NOT_INSTALLED"
                if exc.response.status_code == 404
                else "OLLAMA_REQUEST_FAILED"
            )
            raise AppError(
                code=code,
                message="The configured local model could not process the request.",
                status_code=503,
                retryable=exc.response.status_code >= 500,
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                code="OLLAMA_UNAVAILABLE",
                message="The local Ollama service is unavailable.",
                status_code=503,
                retryable=True,
            ) from exc

        elapsed = int((time.perf_counter() - started) * 1000)
        response_data = response.json()
        content = str(response_data.get("message", {}).get("content", "")).strip()
        if not content:
            raise AppError(
                code="MODEL_EMPTY_RESPONSE",
                message="The local model returned an empty response.",
                status_code=502,
                retryable=True,
            )
        return ChatResult(
            content=content,
            duration_ms=elapsed,
            prompt_tokens=_optional_int(response_data.get("prompt_eval_count")),
            completion_tokens=_optional_int(response_data.get("eval_count")),
            load_duration_ms=_nanoseconds_to_ms(response_data.get("load_duration")),
            evaluation_duration_ms=_nanoseconds_to_ms(response_data.get("eval_duration")),
        )

    async def embed(self, texts: list[str], model_key: str) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=[], duration_ms=0)
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": model_key, "input": texts, "truncate": True, "keep_alive": "2m"},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise AppError(
                    code="MODEL_NOT_INSTALLED",
                    message=f"The configured local embedding model '{model_key}' is not installed.",
                    status_code=503,
                    retryable=False,
                    details={"model_key": model_key},
                ) from exc
            raise AppError(
                code="EMBEDDING_FAILED",
                message="The local embedding model could not process the text.",
                status_code=503,
                retryable=exc.response.status_code >= 500,
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                code="EMBEDDING_FAILED",
                message="The local embedding model could not process the text.",
                status_code=503,
                retryable=True,
            ) from exc
        vectors = response.json().get("embeddings", [])
        if len(vectors) != len(texts):
            raise AppError(
                code="EMBEDDING_COUNT_MISMATCH",
                message="Embedding output was incomplete.",
                status_code=502,
            )
        return EmbeddingResult(
            vectors=vectors, duration_ms=int((time.perf_counter() - started) * 1000)
        )
