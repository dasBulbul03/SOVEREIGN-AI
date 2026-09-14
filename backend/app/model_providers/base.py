from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ChatRequest:
    model_key: str
    prompt: str
    keep_alive: str
    seed: int = 42
    temperature: float = 0.2
    images: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    duration_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    load_duration_ms: int | None = None
    evaluation_duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    ready: bool
    latency_ms: int
    details: dict[str, Any] = field(default_factory=dict)


class ModelProvider(Protocol):
    async def chat(self, request: ChatRequest) -> ChatResult: ...

    async def health(self, model_key: str) -> ProviderHealth: ...

    async def embed(self, texts: list[str], model_key: str) -> EmbeddingResult: ...
