from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = 400
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)
