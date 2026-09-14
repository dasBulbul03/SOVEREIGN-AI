import base64
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import Settings
from app.core.errors import AppError


@dataclass(frozen=True, slots=True)
class SandboxResult:
    status: str
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    output_truncated: bool
    network_mode: str
    container_id: str

    @property
    def passed(self) -> bool:
        return self.status == "completed" and self.exit_code == 0 and not self.timed_out

    def public_data(self) -> dict[str, object]:
        return {
            "status": self.status,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
            "output_truncated": self.output_truncated,
            "network_mode": self.network_mode,
            "container_id": self.container_id[:12],
            "stdout_sha256": hashlib.sha256(self.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(self.stderr.encode()).hexdigest(),
        }


class SandboxClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, repository_root: Path, command: str) -> SandboxResult:
        files = []
        total = 0
        for path in sorted(repository_root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            content = path.read_bytes()
            total += len(content)
            if total > self.settings.sandbox_max_repository_bytes:
                raise AppError("SANDBOX_INPUT_LIMIT", "Sandbox input exceeds its byte limit.", 413)
            files.append(
                {
                    "path": path.relative_to(repository_root).as_posix(),
                    "content": base64.b64encode(content).decode("ascii"),
                }
            )
        payload = {
            "command": command,
            "files": files,
            "timeout_seconds": self.settings.sandbox_timeout_seconds,
            "memory_mb": self.settings.sandbox_memory_mb,
            "cpu_count": self.settings.sandbox_cpu_count,
            "pids_limit": self.settings.sandbox_pids_limit,
            "max_output_bytes": self.settings.sandbox_max_output_bytes,
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.sandbox_timeout_seconds + 15
            ) as client:
                response = await client.post(
                    f"{self.settings.sandbox_runner_url.rstrip('/')}/v1/run",
                    json=payload,
                    headers={"X-Sandbox-Token": self.settings.sandbox_runner_token},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                "SANDBOX_UNAVAILABLE",
                "The isolated code sandbox is unavailable.",
                503,
                True,
            ) from exc
        data = response.json()
        return SandboxResult(
            status=str(data["status"]),
            command=str(data["command"]),
            exit_code=data.get("exit_code"),
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
            duration_ms=int(data.get("duration_ms", (time.perf_counter() - started) * 1000)),
            timed_out=bool(data.get("timed_out", False)),
            output_truncated=bool(data.get("output_truncated", False)),
            network_mode=str(data.get("network_mode", "unknown")),
            container_id=str(data.get("container_id", "")),
        )
