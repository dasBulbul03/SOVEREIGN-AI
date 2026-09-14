import hashlib
import json
import os
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import AppError


@dataclass(frozen=True, slots=True)
class PublishedCodeArtifact:
    logical_name: str
    display_name: str
    storage_key: str
    media_type: str
    size_bytes: int
    sha256: str


def _publish_bytes(
    data_root: Path,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    logical_name: str,
    display_name: str,
    media_type: str,
    content: bytes,
) -> PublishedCodeArtifact:
    artifact_id = uuid.uuid4()
    storage_key = f"workspaces/{workspace_id}/artifacts/{artifact_id}/{display_name}"
    destination = (data_root / storage_key).resolve()
    if data_root.resolve() not in destination.parents:
        raise AppError("ARTIFACT_PATH_INVALID", "Artifact destination is invalid.", 500)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with temporary.open("xb") as output:
            output.write(content)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return PublishedCodeArtifact(
        logical_name,
        display_name,
        storage_key,
        media_type,
        len(content),
        hashlib.sha256(content).hexdigest(),
    )


def publish_code_artifacts(
    data_root: Path,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    repository_root: Path,
    patch: str,
    report: dict[str, object],
) -> list[PublishedCodeArtifact]:
    short = str(run_id)[:8]
    patch_artifact = _publish_bytes(
        data_root,
        workspace_id,
        run_id,
        "code_patch",
        f"verified-changes-{short}.patch",
        "text/x-diff",
        patch.encode(),
    )
    report_content = json.dumps(report, indent=2, sort_keys=True).encode()
    report_artifact = _publish_bytes(
        data_root,
        workspace_id,
        run_id,
        "sandbox_report",
        f"sandbox-report-{short}.json",
        "application/json",
        report_content,
    )
    archive_path = repository_root.parent / f"verified-repository-{short}.zip.tmp"
    try:
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(repository_root.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    archive.write(path, path.relative_to(repository_root).as_posix())
        repository_content = archive_path.read_bytes()
    finally:
        archive_path.unlink(missing_ok=True)
    repository_artifact = _publish_bytes(
        data_root,
        workspace_id,
        run_id,
        "verified_repository",
        f"verified-repository-{short}.zip",
        "application/zip",
        repository_content,
    )
    return [patch_artifact, repository_artifact, report_artifact]
