import base64
import hmac
import io
import os
import re
import tarfile
import time
import uuid
from contextlib import suppress
from pathlib import PurePosixPath

import docker
import requests
from docker.errors import DockerException
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

app = FastAPI(title="SOVEREIGN AI Sandbox Controller", docs_url=None, redoc_url=None)
TOKEN = os.environ.get("SANDBOX_RUNNER_TOKEN", "sandbox-dev-token")
IMAGE = os.environ.get("SANDBOX_IMAGE", "sovereignforge-sandbox-python:day4")
MAX_FILES = 200
MAX_INPUT_BYTES = 10 * 1024 * 1024
COMMANDS = {
    "pytest": ["python", "-m", "pytest", "-q"],
    "unittest": ["python", "-m", "unittest", "discover", "-v"],
    "compile": [
        "python",
        "-c",
        (
            "from pathlib import Path\n"
            "paths=sorted(Path('.').rglob('*.py'))\n"
            "for path in paths:\n"
            " compile(path.read_text(encoding='utf-8'), str(path), 'exec')\n"
            "print(f'Syntax verified: {len(paths)} Python file(s)')"
        ),
    ],
    "run": [
        "python",
        "-c",
        (
            "from pathlib import Path\n"
            "import runpy\n"
            "paths=sorted(Path('/work').rglob('*.py'))\n"
            "assert len(paths) == 1, 'standalone execution requires exactly one Python file'\n"
            "runpy.run_path(str(paths[0]), run_name='__main__')"
        ),
    ],
    "network_probe": [
        "python",
        "-c",
        (
            "import urllib.request\n"
            "try:\n urllib.request.urlopen('https://example.com', timeout=3)\n"
            "except Exception as exc:\n"
            " print('EGRESS_BLOCKED:'+type(exc).__name__); raise SystemExit(0)\n"
            "print('EGRESS_AVAILABLE'); raise SystemExit(9)"
        ),
    ],
    "timeout_probe": ["python", "-c", "import time; time.sleep(30)"],
}


class InputFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=500)
    content: str

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or any(not part for part in path.parts):
            raise ValueError("unsafe path")
        if re.search(r"[\x00-\x1f]", value):
            raise ValueError("unsafe path")
        return value


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str
    files: list[InputFile] = Field(min_length=1, max_length=MAX_FILES)
    timeout_seconds: int = Field(ge=2, le=120)
    memory_mb: int = Field(ge=64, le=512)
    cpu_count: float = Field(ge=0.25, le=2)
    pids_limit: int = Field(ge=16, le=128)
    max_output_bytes: int = Field(ge=1_000, le=500_000)

    @field_validator("command")
    @classmethod
    def known_command(cls, value: str) -> str:
        if value not in COMMANDS:
            raise ValueError("command is not allowlisted")
        return value


def container_options(request: RunRequest, volume_name: str) -> dict[str, object]:
    return {
        "image": IMAGE,
        "command": COMMANDS[request.command],
        "working_dir": "/tmp" if request.command == "run" else "/work",
        "network_mode": "none",
        "network_disabled": True,
        "user": "65532:65532",
        "read_only": True,
        "mem_limit": f"{request.memory_mb}m",
        "nano_cpus": int(request.cpu_count * 1_000_000_000),
        "pids_limit": request.pids_limit,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "tmpfs": {"/tmp": "rw,noexec,nosuid,size=32m"},
        "volumes": {volume_name: {"bind": "/work", "mode": "ro"}},
        "environment": {
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": "/tmp",
            "SANDBOX_CWD": "/tmp" if request.command == "run" else "/work",
        },
        "labels": {"sovereign-ai.sandbox": "day4"},
        "detach": True,
        "stdin_open": False,
        "tty": False,
    }


def input_archive(files: list[InputFile]) -> bytes:
    stream = io.BytesIO()
    total = 0
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for item in files:
            try:
                content = base64.b64decode(item.content, validate=True)
            except ValueError as exc:
                raise HTTPException(422, "Invalid file encoding") from exc
            total += len(content)
            if total > MAX_INPUT_BYTES:
                raise HTTPException(413, "Sandbox input is too large")
            info = tarfile.TarInfo(item.path)
            info.size = len(content)
            info.mode = 0o444
            info.uid = info.gid = 65532
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
        ready = b"ready\n"
        info = tarfile.TarInfo(".sovereign-ready")
        info.size = len(ready)
        info.mode = 0o444
        info.uid = info.gid = 65532
        info.mtime = 0
        archive.addfile(info, io.BytesIO(ready))
    return stream.getvalue()


def bounded_output(content: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(content) > limit
    return content[:limit].decode("utf-8", errors="replace"), truncated


@app.get("/health")
def health() -> dict[str, str]:
    try:
        docker.from_env().ping()
        return {"status": "ready", "sandbox_image": IMAGE}
    except DockerException as exc:
        raise HTTPException(503, "Docker engine unavailable") from exc


@app.post("/v1/run")
def run(request: RunRequest, x_sandbox_token: str = Header(default="")) -> dict[str, object]:
    if not hmac.compare_digest(x_sandbox_token, TOKEN):
        raise HTTPException(401, "Unauthorized")
    client = docker.from_env()
    container = None
    materializer = None
    volume = None
    started = time.perf_counter()
    timed_out = False
    try:
        volume = client.volumes.create(
            name=f"sovereign-sandbox-{uuid.uuid4().hex}",
            labels={"sovereign-ai.sandbox": "day4"},
        )
        materializer = client.containers.create(
            image=IMAGE,
            entrypoint=["sleep"],
            command=["30"],
            network_mode="none",
            network_disabled=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            volumes={volume.name: {"bind": "/work", "mode": "rw"}},
            labels={"sovereign-ai.materializer": "day4"},
        )
        materializer.start()
        if not materializer.put_archive("/work", input_archive(request.files)):
            raise HTTPException(500, "Could not materialize sandbox input")
        materializer.remove(force=True)
        materializer = None

        options = container_options(request, volume.name)
        options["name"] = f"sovereign-sandbox-{uuid.uuid4().hex[:12]}"
        container = client.containers.create(**options)
        container.start()
        try:
            wait_result = container.wait(timeout=request.timeout_seconds)
            exit_code = int(wait_result.get("StatusCode", 1))
            status = "completed"
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            timed_out = True
            status = "timed_out"
            exit_code = None
            container.kill()
        stdout_raw = container.logs(stdout=True, stderr=False)
        stderr_raw = container.logs(stdout=False, stderr=True)
        stdout, stdout_truncated = bounded_output(stdout_raw, request.max_output_bytes)
        stderr, stderr_truncated = bounded_output(stderr_raw, request.max_output_bytes)
        return {
            "status": status,
            "command": request.command,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "timed_out": timed_out,
            "output_truncated": stdout_truncated or stderr_truncated,
            "network_mode": "none",
            "container_id": container.id,
        }
    except DockerException as exc:
        raise HTTPException(503, "Sandbox execution failed") from exc
    finally:
        if materializer is not None:
            with suppress(DockerException):
                materializer.remove(force=True)
        if container is not None:
            with suppress(DockerException):
                container.remove(force=True)
        if volume is not None:
            with suppress(DockerException):
                volume.remove(force=True)
