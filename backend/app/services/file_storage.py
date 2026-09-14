import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import AppError
from app.core.file_types import SOURCE_CODE_SUFFIXES

ALLOWED_TYPES = {
    **{suffix: "text/plain" for suffix in SOURCE_CODE_SUFFIXES},
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".zip": "application/zip",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".jsx": "text/jsx",
    ".ts": "text/typescript",
    ".tsx": "text/tsx",
    ".json": "application/json",
    ".toml": "application/toml",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".cfg": "text/plain",
    ".ini": "text/plain",
    ".ipynb": "application/json",
    ".xml": "application/xml",
}


@dataclass(frozen=True, slots=True)
class StoredUpload:
    display_name: str
    storage_key: str
    media_type: str
    size_bytes: int
    sha256: str


def validate_filename(name: str | None) -> tuple[str, str]:
    if (
        not name
        or len(name) > 255
        or name != Path(name).name
        or ".." in name
        or re.search(r"[\x00-\x1f]", name)
    ):
        raise AppError("INVALID_FILENAME", "The filename is not safe.", 422)
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_TYPES:
        raise AppError(
            "UNSUPPORTED_FILE_TYPE",
            "Use a supported document, image, source-code file, or ZIP repository.",
            415,
        )
    return name, suffix


async def store_upload(
    upload: UploadFile, root: Path, workspace_id: uuid.UUID, max_bytes: int
) -> StoredUpload:
    name, suffix = validate_filename(upload.filename)
    file_id = uuid.uuid4()
    relative = Path("workspaces") / str(workspace_id) / "uploads" / f"{file_id}{suffix}"
    target = (root / relative).resolve()
    resolved_root = root.resolve()
    if resolved_root not in target.parents:
        raise AppError("INVALID_STORAGE_PATH", "The storage target is invalid.", 400)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".upload")
    digest, size, first = hashlib.sha256(), 0, b""
    try:
        with temporary.open("xb") as output:
            while chunk := await upload.read(1024 * 1024):
                if not first:
                    first = chunk[:8]
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(
                        "UPLOAD_TOO_LARGE",
                        f"Files are limited to {max_bytes // (1024 * 1024)} MB.",
                        413,
                    )
                digest.update(chunk)
                output.write(chunk)
        if suffix == ".pdf" and not first.startswith(b"%PDF-"):
            raise AppError("INVALID_PDF", "The file does not have a valid PDF signature.", 422)
        if suffix == ".png" and not first.startswith(b"\x89PNG\r\n\x1a\n"):
            raise AppError("INVALID_IMAGE", "The file does not have a valid PNG signature.", 422)
        if suffix in {".jpg", ".jpeg"} and not first.startswith(b"\xff\xd8\xff"):
            raise AppError("INVALID_IMAGE", "The file does not have a valid JPEG signature.", 422)
        if suffix == ".zip" and not first.startswith(b"PK"):
            raise AppError("INVALID_ARCHIVE", "The file does not have a valid ZIP signature.", 422)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    media_type = ALLOWED_TYPES[suffix]
    return StoredUpload(name, relative.as_posix(), media_type, size, digest.hexdigest())


def resolve_storage_key(root: Path, storage_key: str) -> Path:
    path, resolved_root = (root / storage_key).resolve(), root.resolve()
    if resolved_root not in path.parents:
        raise AppError("INVALID_STORAGE_PATH", "The stored path is invalid.", 500)
    return path
