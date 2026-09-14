import difflib
import hashlib
import os
import re
import stat
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.core.errors import AppError
from app.core.file_types import REPOSITORY_SUPPORT_SUFFIXES, SOURCE_CODE_SUFFIXES
from app.db.models import StoredFile
from app.services.file_storage import resolve_storage_key

CODE_SUFFIXES = REPOSITORY_SUPPORT_SUFFIXES
IGNORED_PARTS = {
    ".git",
    ".idea",
    ".next",
    ".venv",
    "__MACOSX",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "venv",
}
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def is_verification_path(path: str) -> bool:
    """Return true for files that must remain immutable during repair attempts."""
    pure = PurePosixPath(path)
    name = pure.name.casefold()
    parts = {part.casefold() for part in pure.parts}
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.jsx", ".test.ts", ".test.tsx"))
        or name in {"pytest.ini", "tox.ini", "conftest.py"}
    )


def resolve_verification_command(requested: str, paths: list[str]) -> str:
    """Resolve a useful bounded fallback when pytest has no discoverable tests."""
    if requested != "pytest":
        return requested
    has_pytest_file = any(
        PurePosixPath(path).name.casefold().startswith("test_")
        or PurePosixPath(path).name.casefold().endswith("_test.py")
        for path in paths
    )
    if has_pytest_file:
        return "pytest"
    python_sources = [path for path in paths if PurePosixPath(path).suffix.casefold() == ".py"]
    return "run" if len(python_sources) == 1 else "compile"


@dataclass(frozen=True, slots=True)
class RepositoryMaterialization:
    root: Path
    file_count: int
    total_bytes: int
    source_files: list[dict[str, object]]


def _safe_relative(raw: str) -> PurePosixPath:
    normalized = raw.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise AppError("REPOSITORY_PATH_DENIED", "A repository path is unsafe.", 422)
    if any(part in IGNORED_PARTS for part in path.parts):
        raise AppError(
            "REPOSITORY_PATH_DENIED", "Generated/dependency folders are not accepted.", 422
        )
    if path.suffix.casefold() not in CODE_SUFFIXES:
        raise AppError(
            "REPOSITORY_FILE_UNSUPPORTED", "The repository contains an unsupported file type.", 415
        )
    return path


def _contained(root: Path, relative: PurePosixPath) -> Path:
    target = (root / Path(*relative.parts)).resolve()
    if root.resolve() not in target.parents:
        raise AppError("REPOSITORY_PATH_DENIED", "A repository path escaped its working copy.", 422)
    return target


def _write_new_file(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as output:
            output.write(content)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def materialize_repository(
    settings: Settings,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    stored_files: list[StoredFile],
) -> RepositoryMaterialization:
    if not stored_files:
        raise AppError("CODING_INPUT_REQUIRED", "Select a ZIP repository or source files.", 422)
    root = (
        settings.data_root
        / "workspaces"
        / str(workspace_id)
        / "runs"
        / str(run_id)
        / "working"
        / "repository"
    ).resolve()
    data_root = settings.data_root.resolve()
    if data_root not in root.parents:
        raise AppError("REPOSITORY_PATH_DENIED", "The repository destination is invalid.", 500)
    root.mkdir(parents=True, exist_ok=False)
    count = 0
    total = 0
    sources: list[dict[str, object]] = []
    for stored in stored_files:
        source = resolve_storage_key(settings.data_root, stored.storage_key)
        if source.suffix.casefold() == ".zip":
            try:
                archive = zipfile.ZipFile(source)
            except zipfile.BadZipFile as exc:
                raise AppError(
                    "REPOSITORY_ARCHIVE_INVALID", "The repository ZIP is invalid.", 422
                ) from exc
            with archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    mode = member.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise AppError(
                            "REPOSITORY_SYMLINK_DENIED", "Repository symlinks are not allowed.", 422
                        )
                    relative = _safe_relative(member.filename)
                    count += 1
                    total += member.file_size
                    if count > settings.sandbox_max_files:
                        raise AppError(
                            "REPOSITORY_FILE_LIMIT", "The repository has too many files.", 413
                        )
                    if total > settings.sandbox_max_repository_bytes:
                        raise AppError(
                            "REPOSITORY_SIZE_LIMIT", "The expanded repository is too large.", 413
                        )
                    content = archive.read(member)
                    try:
                        content.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise AppError(
                            "REPOSITORY_ENCODING_INVALID",
                            "Repository source files must use UTF-8 encoding.",
                            422,
                        ) from exc
                    target = _contained(root, relative)
                    if target.exists():
                        raise AppError(
                            "REPOSITORY_DUPLICATE_PATH",
                            "The repository contains duplicate file paths.",
                            422,
                        )
                    _write_new_file(target, content)
        else:
            relative = _safe_relative(stored.display_name)
            content = source.read_bytes()
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise AppError(
                    "REPOSITORY_ENCODING_INVALID",
                    "Repository source files must use UTF-8 encoding.",
                    422,
                ) from exc
            count += 1
            total += len(content)
            if count > settings.sandbox_max_files or total > settings.sandbox_max_repository_bytes:
                raise AppError(
                    "REPOSITORY_SIZE_LIMIT", "The repository exceeds sandbox limits.", 413
                )
            target = _contained(root, relative)
            if target.exists():
                raise AppError(
                    "REPOSITORY_DUPLICATE_PATH",
                    "Selected source files have duplicate names.",
                    422,
                )
            _write_new_file(target, content)
        sources.append(
            {
                "file_id": str(stored.id),
                "display_name": stored.display_name,
                "sha256": stored.sha256,
            }
        )
    if count == 0:
        raise AppError(
            "REPOSITORY_EMPTY", "The repository contains no supported source files.", 422
        )
    return RepositoryMaterialization(root, count, total, sources)


def snapshot_repository(root: Path, max_chars: int) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    remaining = max_chars
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        if remaining <= 0:
            break
        snapshot[relative] = text[:remaining]
        remaining -= len(snapshot[relative])
    return snapshot


def repository_prompt(
    goal: str,
    files: dict[str, str],
    previous_failure: str | None = None,
) -> str:
    content = "\n\n".join(
        f"FILE: {path}\n" + "\n".join(
            f"{number:04d}|{line}" for number, line in enumerate(text.splitlines(), start=1)
        )
        for path, text in files.items()
    )
    immutable = sorted(path for path in files if is_verification_path(path))
    implementation = sorted(
        path
        for path in files
        if not is_verification_path(path)
        and PurePosixPath(path).suffix.casefold() in SOURCE_CODE_SUFFIXES
    )
    retry = (
        "\n\nCURRENT VERIFICATION FAILURE — HIGHEST PRIORITY:\n"
        "Fix the exact current failure below. The numbered repository is the current truth; do "
        "not repeat an edit that is already present.\n"
        f"{previous_failure}"
        if previous_failure
        else ""
    )
    return (
        "You are a precise coding agent operating on an isolated working copy. "
        "Return only line-range XML edits; do not return a unified diff, Markdown fences, or "
        "explanations. Use one or more blocks in this exact format:\n"
        '<edit path="path/to/file.py" start="7" end="7">\n'
        "replacement code without line-number prefixes\n"
        "</edit>\n"
        "Start and end are inclusive line numbers from the numbered current repository below. "
        "Use the smallest non-overlapping ranges that solve the task. "
        "Fix the implementation, never the verification contract. Do not delete or rename files, "
        "add dependencies, modify any immutable verification file, or include explanations outside "
        "the edit blocks. Make the smallest implementation change that solves the task."
        f"\n\nIMPLEMENTATION TARGETS:\n{', '.join(implementation) or 'none'}"
        f"\n\nIMMUTABLE VERIFICATION FILES:\n{', '.join(immutable) or 'none'}"
        f"{retry}\n\nTASK:\n{goal}\n\nNUMBERED CURRENT REPOSITORY:\n{content}"
    )


def restore_repository_files(root: Path, snapshot: dict[str, str], paths: list[str]) -> None:
    for relative in paths:
        if relative not in snapshot:
            raise AppError(
                "PATCH_ROLLBACK_UNAVAILABLE",
                "A failed patch created a file that cannot be rolled back safely.",
                422,
            )
        target = _contained(root, PurePosixPath(relative))
        _write_new_file(target, snapshot[relative].encode())


def extract_unified_diff(response: str, max_chars: int) -> str:
    edit_start = response.find('<edit path="')
    if edit_start >= 0:
        last_end = response.rfind("</edit>")
        if last_end < edit_start:
            raise AppError("PATCH_FORMAT_INVALID", "A line-range edit is incomplete.", 422)
        proposal = response[edit_start : last_end + len("</edit>")].strip() + "\n"
        if len(proposal) > max_chars:
            raise AppError(
                "PATCH_SIZE_LIMIT", "The proposed patch exceeds the configured limit.", 413
            )
        return proposal
    search_start = response.find("<<<<<<< SEARCH ")
    if search_start >= 0:
        last_end = response.rfind(">>>>>>> REPLACE")
        if last_end < search_start:
            raise AppError("PATCH_FORMAT_INVALID", "A SEARCH/REPLACE block is incomplete.", 422)
        proposal = response[search_start : last_end + len(">>>>>>> REPLACE")].strip() + "\n"
        if len(proposal) > max_chars:
            raise AppError(
                "PATCH_SIZE_LIMIT", "The proposed patch exceeds the configured limit.", 413
            )
        return proposal
    fenced = re.search(r"```(?:diff|patch)?\s*\n([\s\S]*?)```", response, re.IGNORECASE)
    candidate = fenced.group(1) if fenced else response
    start = candidate.find("--- ")
    if start < 0:
        raise AppError(
            "PATCH_FORMAT_INVALID", "The coding model did not return a unified diff.", 422
        )
    patch = candidate[start:].strip() + "\n"
    if len(patch) > max_chars:
        raise AppError("PATCH_SIZE_LIMIT", "The proposed patch exceeds the configured limit.", 413)
    return patch


SEARCH_REPLACE_BLOCK = re.compile(
    r"^<<<<<<< SEARCH (?P<path>[^\n]+)\n"
    r"(?P<search>[\s\S]*?)\n=======\n"
    r"(?P<replacement>[\s\S]*?)\n>>>>>>> REPLACE$",
    re.MULTILINE,
)

LINE_RANGE_EDIT = re.compile(
    r'^<edit path="(?P<path>[^"\n]+)" start="(?P<start>\d+)" end="(?P<end>\d+)">\n'
    r"(?P<replacement>[\s\S]*?)\n</edit>$",
    re.MULTILINE,
)


def _apply_line_range_edits(root: Path, proposal: str) -> list[str]:
    matches = list(LINE_RANGE_EDIT.finditer(proposal.strip()))
    if not matches or LINE_RANGE_EDIT.sub("", proposal.strip()).strip():
        raise AppError("PATCH_FORMAT_INVALID", "A line-range edit is malformed.", 422)

    by_path: dict[str, tuple[Path, list[str], list[tuple[int, int, list[str]]]]] = {}
    for match in matches:
        relative = _safe_relative(match.group("path")).as_posix()
        if is_verification_path(relative):
            raise AppError(
                "PATCH_VERIFICATION_DENIED",
                "Verification files are immutable; patch the implementation instead.",
                403,
            )
        target = _contained(root, PurePosixPath(relative))
        if target.is_symlink() or not target.is_file():
            raise AppError("PATCH_TARGET_DENIED", "A patch target is unavailable.", 422)
        current = by_path.get(relative)
        if current is None:
            lines = target.read_text(encoding="utf-8").splitlines()
            edits: list[tuple[int, int, list[str]]] = []
        else:
            _, lines, edits = current
        start = int(match.group("start"))
        end = int(match.group("end"))
        if start < 1 or end < start or end > len(lines):
            raise AppError("PATCH_CONTEXT_MISMATCH", "An edit line range is out of bounds.", 422)
        replacement = match.group("replacement").splitlines()
        original_indent = lines[start - 1][: len(lines[start - 1]) - len(lines[start - 1].lstrip())]
        if original_indent and replacement and replacement[0] == replacement[0].lstrip():
            replacement = [
                original_indent + line if line else line
                for line in replacement
            ]
        edits.append((start - 1, end, replacement))
        by_path[relative] = (target, lines, edits)

    changed: list[str] = []
    staged: list[tuple[str, Path, str]] = []
    for relative, (target, lines, edits) in by_path.items():
        ordered = sorted(edits, reverse=True)
        for index, (start, end, replacement) in enumerate(ordered):
            if index and end > ordered[index - 1][0]:
                raise AppError("PATCH_CONTEXT_MISMATCH", "Edit line ranges overlap.", 422)
            lines[start:end] = replacement
        updated = "\n".join(lines) + "\n"
        if updated != target.read_text(encoding="utf-8"):
            staged.append((relative, target, updated))
    for relative, target, updated in staged:
        _write_new_file(target, updated.encode())
        changed.append(relative)
    if not changed:
        raise AppError("PATCH_EMPTY", "The proposed patch contains no content changes.", 422)
    return changed


def _apply_search_replace(root: Path, proposal: str) -> list[str]:
    matches = list(SEARCH_REPLACE_BLOCK.finditer(proposal.strip()))
    if not matches:
        raise AppError("PATCH_FORMAT_INVALID", "A SEARCH/REPLACE block is malformed.", 422)
    residue = SEARCH_REPLACE_BLOCK.sub("", proposal.strip()).strip()
    if residue:
        raise AppError("PATCH_FORMAT_INVALID", "Only SEARCH/REPLACE blocks are allowed.", 422)

    staged: dict[str, tuple[Path, str]] = {}
    for match in matches:
        relative = _safe_relative(match.group("path").strip()).as_posix()
        if is_verification_path(relative):
            raise AppError(
                "PATCH_VERIFICATION_DENIED",
                "Verification files are immutable; patch the implementation instead.",
                403,
            )
        target = _contained(root, PurePosixPath(relative))
        if target.is_symlink() or not target.is_file():
            raise AppError("PATCH_TARGET_DENIED", "A patch target is unavailable.", 422)
        current = staged.get(relative, (target, target.read_text(encoding="utf-8")))[1]
        search = match.group("search")
        replacement = match.group("replacement")
        if not search:
            raise AppError("PATCH_FORMAT_INVALID", "A SEARCH section may not be empty.", 422)
        if current.count(search) != 1:
            raise AppError(
                "PATCH_CONTEXT_MISMATCH",
                "SEARCH text does not uniquely match the current file.",
                422,
            )
        staged[relative] = (target, current.replace(search, replacement, 1))

    changed: list[str] = []
    for relative, (target, updated) in staged.items():
        if updated == target.read_text(encoding="utf-8"):
            continue
        _write_new_file(target, updated.encode())
        changed.append(relative)
    if not changed:
        raise AppError("PATCH_EMPTY", "The proposed patch contains no content changes.", 422)
    return changed


def _header_path(line: str, prefix: str) -> str:
    raw = line[len(prefix) :].split("\t", 1)[0].strip()
    if raw == "/dev/null":
        return raw
    if raw.startswith(("a/", "b/")):
        raw = raw[2:]
    return _safe_relative(raw).as_posix()


def apply_unified_diff(root: Path, patch: str) -> list[str]:
    if patch.lstrip().startswith('<edit path="'):
        return _apply_line_range_edits(root, patch)
    if patch.lstrip().startswith("<<<<<<< SEARCH "):
        return _apply_search_replace(root, patch)
    lines = patch.splitlines()
    for line in lines:
        if not line.startswith("+++ "):
            continue
        proposed = _header_path(line, "+++ ")
        if proposed != "/dev/null" and is_verification_path(proposed):
            raise AppError(
                "PATCH_VERIFICATION_DENIED",
                "Verification files are immutable; patch the implementation instead.",
                403,
            )
    index = 0
    changed: list[str] = []
    while index < len(lines):
        if not lines[index].startswith("--- "):
            index += 1
            continue
        old_path = _header_path(lines[index], "--- ")
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            raise AppError("PATCH_FORMAT_INVALID", "A patch file header is incomplete.", 422)
        new_path = _header_path(lines[index], "+++ ")
        index += 1
        if new_path == "/dev/null":
            raise AppError("PATCH_DELETE_DENIED", "Coding tasks may not delete files.", 403)
        if old_path != "/dev/null" and old_path != new_path:
            raise AppError("PATCH_RENAME_DENIED", "Coding tasks may not rename files.", 403)
        target = _contained(root, PurePosixPath(new_path))
        if target.is_symlink() or (old_path != "/dev/null" and not target.is_file()):
            raise AppError("PATCH_TARGET_DENIED", "A patch target is unavailable.", 422)
        source = [] if old_path == "/dev/null" else target.read_text(encoding="utf-8").splitlines()
        output: list[str] = []
        cursor = 0
        saw_hunk = False
        while index < len(lines) and not lines[index].startswith("--- "):
            header = HUNK_HEADER.match(lines[index])
            if not header:
                index += 1
                continue
            saw_hunk = True
            old_start = int(header.group(1)) - 1
            hunk_end = index + 1
            old_values: list[str] = []
            desired_values: list[str] = []
            removed_values: list[str] = []
            added_values: list[str] = []
            while hunk_end < len(lines) and not lines[hunk_end].startswith(("@@ ", "--- ")):
                candidate = lines[hunk_end]
                if candidate == "\\ No newline at end of file":
                    hunk_end += 1
                    continue
                if not candidate or candidate[0] not in {" ", "+", "-"}:
                    break
                if candidate[0] in {" ", "-"}:
                    old_values.append(candidate[1:])
                if candidate[0] in {" ", "+"}:
                    desired_values.append(candidate[1:])
                if candidate[0] == "-":
                    removed_values.append(candidate[1:])
                elif candidate[0] == "+":
                    added_values.append(candidate[1:])
                hunk_end += 1
            predicted_matches = (
                old_start >= cursor
                and old_start + len(old_values) <= len(source)
                and source[old_start : old_start + len(old_values)] == old_values
            )
            if not predicted_matches:
                candidates = [
                    position
                    for position in range(cursor, len(source) - len(old_values) + 1)
                    if source[position : position + len(old_values)] == old_values
                ]
                if not candidates and removed_values == added_values and removed_values:
                    normalized = [
                        position
                        for position in range(cursor, len(source) - len(desired_values) + 1)
                        if sum(
                            left != right
                            for left, right in zip(
                                source[position : position + len(desired_values)],
                                desired_values,
                                strict=True,
                            )
                        )
                        == 1
                        and len(desired_values) >= 3
                    ]
                    if len(normalized) == 1:
                        old_start = normalized[0]
                        output.extend(source[cursor:old_start])
                        output.extend(desired_values)
                        cursor = old_start + len(desired_values)
                        index = hunk_end
                        continue
                if len(candidates) != 1:
                    raise AppError(
                        "PATCH_CONTEXT_MISMATCH",
                        "Patch context does not uniquely match the file.",
                        422,
                    )
                old_start = candidates[0]
            output.extend(source[cursor:old_start])
            cursor = old_start
            index += 1
            while index < len(lines) and not lines[index].startswith(("@@ ", "--- ")):
                patch_line = lines[index]
                if patch_line == "\\ No newline at end of file":
                    index += 1
                    continue
                if not patch_line or patch_line[0] not in {" ", "+", "-"}:
                    break
                marker, value = patch_line[0], patch_line[1:]
                if marker in {" ", "-"}:
                    if cursor >= len(source) or source[cursor] != value:
                        raise AppError(
                            "PATCH_CONTEXT_MISMATCH", "Patch context does not match the file.", 422
                        )
                    if marker == " ":
                        output.append(source[cursor])
                    cursor += 1
                else:
                    output.append(value)
                index += 1
        if not saw_hunk:
            raise AppError("PATCH_FORMAT_INVALID", "A patch contains no change hunks.", 422)
        output.extend(source[cursor:])
        updated = "\n".join(output) + "\n"
        existing = "" if old_path == "/dev/null" else target.read_text(encoding="utf-8")
        if updated != existing:
            _write_new_file(target, updated.encode())
            changed.append(new_path)
    if not changed:
        raise AppError("PATCH_EMPTY", "The proposed patch contains no content changes.", 422)
    return changed


def repository_diff(before: dict[str, str], after: dict[str, str]) -> str:
    chunks: list[str] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) == after.get(path):
            continue
        chunks.extend(
            difflib.unified_diff(
                before.get(path, "").splitlines(keepends=True),
                after.get(path, "").splitlines(keepends=True),
                fromfile=f"a/{path}" if path in before else "/dev/null",
                tofile=f"b/{path}",
            )
        )
    return "".join(chunks)


def repository_digest(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, content in sorted(files.items()):
        digest.update(path.encode())
        digest.update(b"\0")
        digest.update(content.encode())
        digest.update(b"\0")
    return digest.hexdigest()
