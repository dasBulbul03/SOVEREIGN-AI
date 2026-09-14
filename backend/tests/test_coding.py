import uuid
import zipfile
from pathlib import Path

import pytest

from app.artifacts.code import publish_code_artifacts
from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import StoredFile, Workspace
from app.services.code_repository import (
    apply_unified_diff,
    materialize_repository,
    repository_diff,
    repository_prompt,
    resolve_verification_command,
    restore_repository_files,
    snapshot_repository,
)
from app.tasks.runtime import _coding_failure_summary


def test_repository_prompt_only_lists_source_code_as_implementation_targets() -> None:
    prompt = repository_prompt(
        "Fix the implementation.",
        {
            "monitor.py": "VALUE = 1\n",
            "readings.csv": "value\n1\n",
            "README.md": "# Fixture\n",
            "test_monitor.py": "def test_value():\n    assert True\n",
        },
    )

    targets = prompt.split("IMPLEMENTATION TARGETS:\n", 1)[1].split(
        "\n\nIMMUTABLE", 1
    )[0]
    assert targets == "monitor.py"


def stored_archive(tmp_path: Path, workspace: Workspace, members: dict[str, str]) -> StoredFile:
    relative = Path("workspaces") / str(workspace.id) / "uploads" / "repository.zip"
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return StoredFile(
        workspace_id=workspace.id,
        display_name="repository.zip",
        storage_key=relative.as_posix(),
        media_type="application/zip",
        size_bytes=path.stat().st_size,
        sha256="1" * 64,
    )


@pytest.mark.parametrize(
    ("requested", "paths", "expected"),
    [
        ("pytest", ["test.py"], "run"),
        ("pytest", ["src/app.py", "test_app.py"], "pytest"),
        ("pytest", ["src/app.py", "app_test.py"], "pytest"),
        ("pytest", ["src/app.py", "src/helper.py"], "compile"),
        ("unittest", ["app.py"], "unittest"),
        ("compile", ["app.py"], "compile"),
    ],
)
def test_resolve_verification_command(
    requested: str, paths: list[str], expected: str
) -> None:
    assert resolve_verification_command(requested, paths) == expected


def test_repository_materialization_patch_and_artifacts(tmp_path: Path) -> None:
    workspace = Workspace(id=uuid.uuid4(), name="Coding")
    stored = stored_archive(
        tmp_path,
        workspace,
        {
            "src/calculator.py": "def add(left, right):\n    return left - right\n",
            "readings.csv": "timestamp,value\n2026-09-12T10:00:00Z,90.0\n",
            "test_calculator.py": (
                "from src.calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
            ),
        },
    )
    settings = Settings(data_root=tmp_path)
    run_id = uuid.uuid4()

    materialized = materialize_repository(settings, workspace.id, run_id, [stored])
    before = snapshot_repository(materialized.root, 100_000)
    changed = apply_unified_diff(
        materialized.root,
        "--- a/src/calculator.py\n"
        "+++ b/src/calculator.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def add(left, right):\n"
        "-    return left - right\n"
        "+    return left + right\n\nPatch complete.",
    )
    after = snapshot_repository(materialized.root, 100_000)
    patch = repository_diff(before, after)
    artifacts = publish_code_artifacts(
        tmp_path,
        workspace.id,
        run_id,
        materialized.root,
        patch,
        {"passed": True, "network_mode": "none"},
    )

    assert changed == ["src/calculator.py"]
    assert "return left + right" in after["src/calculator.py"]
    assert "90.0" in after["readings.csv"]
    assert "**" not in patch
    assert {item.logical_name for item in artifacts} == {
        "code_patch",
        "verified_repository",
        "sandbox_report",
    }
    assert all((tmp_path / item.storage_key).is_file() for item in artifacts)
    repository_zip = next(item for item in artifacts if item.logical_name == "verified_repository")
    with zipfile.ZipFile(tmp_path / repository_zip.storage_key) as archive:
        assert "return left + right" in archive.read("src/calculator.py").decode()
        assert "90.0" in archive.read("readings.csv").decode()


def test_patch_accepts_wrong_hunk_position_only_with_unique_exact_context(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "calculator.py"
    target.write_text("def add(left, right):\n    return left - right\n", encoding="utf-8")

    changed = apply_unified_diff(
        root,
        "--- a/calculator.py\n"
        "+++ b/calculator.py\n"
        "@@ -9,2 +9,2 @@\n"
        " def add(left, right):\n"
        "-    return left - right\n"
        "+    return left + right\n",
    )

    assert changed == ["calculator.py"]
    assert target.read_text(encoding="utf-8").endswith("return left + right\n")


def test_patch_normalizes_single_misclassified_context_line(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "calculator.py"
    target.write_text(
        "def add(left: int, right: int) -> int:\n"
        '    """Return the sum of two integers."""\n'
        "    return left - right\n",
        encoding="utf-8",
    )

    changed = apply_unified_diff(
        root,
        "--- a/calculator.py\n"
        "+++ b/calculator.py\n"
        "@@ -1,4 +1,4 @@\n"
        " def add(left: int, right: int) -> int:\n"
        '-    """Return the sum of two integers."""\n'
        '+    """Return the sum of two integers."""\n'
        "     return left + right\n",
    )

    assert changed == ["calculator.py"]
    assert target.read_text(encoding="utf-8").endswith("return left + right\n")


def test_patch_rejects_ambiguous_context_when_hunk_position_is_wrong(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "app.py"
    target.write_text("value = 1\nvalue = 1\n", encoding="utf-8")

    with pytest.raises(AppError) as denied:
        apply_unified_diff(
            root,
            "--- a/app.py\n+++ b/app.py\n@@ -9 +9 @@\n-value = 1\n+value = 2\n",
        )

    assert denied.value.code == "PATCH_CONTEXT_MISMATCH"
    assert target.read_text(encoding="utf-8") == "value = 1\nvalue = 1\n"


def test_patch_rejects_noop_content(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(AppError) as denied:
        apply_unified_diff(
            root,
            "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-value = 1\n+value = 1\n",
        )

    assert denied.value.code == "PATCH_EMPTY"
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_patch_applies_exact_search_replace_blocks_atomically(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "app.py"
    target.write_text("tax = '0.18'\nprint(tax)\n", encoding="utf-8")

    changed = apply_unified_diff(
        root,
        "<<<<<<< SEARCH app.py\n"
        "tax = '0.18'\n"
        "=======\n"
        "tax = 0.18\n"
        ">>>>>>> REPLACE\n",
    )

    assert changed == ["app.py"]
    assert target.read_text(encoding="utf-8") == "tax = 0.18\nprint(tax)\n"


def test_patch_rejects_non_unique_search_replace_text(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "app.py"
    target.write_text("value = 1\nvalue = 1\n", encoding="utf-8")

    with pytest.raises(AppError) as denied:
        apply_unified_diff(
            root,
            "<<<<<<< SEARCH app.py\n"
            "value = 1\n"
            "=======\n"
            "value = 2\n"
            ">>>>>>> REPLACE\n",
        )

    assert denied.value.code == "PATCH_CONTEXT_MISMATCH"
    assert target.read_text(encoding="utf-8") == "value = 1\nvalue = 1\n"


def test_patch_applies_non_overlapping_line_range_edits(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "app.py"
    target.write_text("tax = '0.18'\namount = 10\nprint(amount)\n", encoding="utf-8")

    changed = apply_unified_diff(
        root,
        '<edit path="app.py" start="1" end="1">\n'
        "tax = 0.18\n"
        "</edit>\n"
        '<edit path="app.py" start="3" end="3">\n'
        "print(amount * (1 + tax))\n"
        "</edit>\n",
    )

    assert changed == ["app.py"]
    assert target.read_text(encoding="utf-8") == (
        "tax = 0.18\namount = 10\nprint(amount * (1 + tax))\n"
    )


def test_patch_rejects_overlapping_line_range_edits_atomically(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "app.py"
    original = "one\ntwo\nthree\n"
    target.write_text(original, encoding="utf-8")

    with pytest.raises(AppError) as denied:
        apply_unified_diff(
            root,
            '<edit path="app.py" start="1" end="2">\nchanged\n</edit>\n'
            '<edit path="app.py" start="2" end="3">\nchanged again\n</edit>\n',
        )

    assert denied.value.code == "PATCH_CONTEXT_MISMATCH"
    assert target.read_text(encoding="utf-8") == original


def test_patch_preserves_base_indent_for_line_range_edit(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "app.py"
    target.write_text("def total():\n    return '1'\n", encoding="utf-8")

    apply_unified_diff(
        root,
        '<edit path="app.py" start="2" end="2">\nreturn 1\n</edit>\n',
    )

    assert target.read_text(encoding="utf-8") == "def total():\n    return 1\n"


def test_restore_repository_files_reverts_failed_candidate(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    before = snapshot_repository(root, 1_000)
    target.write_text("broken syntax (\n", encoding="utf-8")

    restore_repository_files(root, before, ["app.py"])

    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_coding_failure_summary_selects_last_repository_frame() -> None:
    summary = _coding_failure_summary(
        {
            "stdout": "",
            "stderr": (
                '  File "bigtest.py", line 85, in create_order\n'
                '  File "bigtest.py", line 62, in total\n'
                "    return amount + amount * TAX_RATE\n"
                "TypeError: unsupported operand types\n"
            ),
        },
        {"bigtest.py": "\n" * 61 + "    return amount + amount * TAX_RATE\n"},
        1_000,
    )

    assert "bigtest.py line 62" in summary
    assert "Current source line:     return amount" in summary
    assert "TypeError: unsupported operand types" in summary
    assert "normalize the incompatible value types" in summary


def test_coding_failure_summary_adds_json_guidance() -> None:
    summary = _coding_failure_summary(
        {
            "stderr": (
                '  File "app.py", line 3, in save\n'
                "    json.dump(order, handle)\n"
                "TypeError: Object of type datetime is not JSON serializable\n"
            )
        },
        {"app.py": "import json\norder = {}\njson.dump(order, handle)\n"},
        1_000,
    )

    assert "safe JSON default serializer" in summary


def test_coding_failure_summary_adds_conversion_guidance() -> None:
    summary = _coding_failure_summary(
        {
            "stderr": (
                '  File "app.py", line 2, in total\n'
                "    return float(amount * rate)\n"
                "ValueError: could not convert string to float: ''\n"
            )
        },
        {"app.py": "rate = '0.18'\nreturn float(amount * rate)\n"},
        1_000,
    )

    assert "before conversion" in summary
    assert "already-invalid operation" in summary


@pytest.mark.parametrize("unsafe", ["../escape.py", "/absolute.py", "src/../../escape.py"])
def test_repository_archive_rejects_path_escape(tmp_path: Path, unsafe: str) -> None:
    workspace = Workspace(id=uuid.uuid4(), name="Unsafe")
    stored = stored_archive(tmp_path, workspace, {unsafe: "print('unsafe')\n"})

    with pytest.raises(AppError) as denied:
        materialize_repository(Settings(data_root=tmp_path), workspace.id, uuid.uuid4(), [stored])

    assert denied.value.code == "REPOSITORY_PATH_DENIED"


def test_repository_archive_rejects_symlink(tmp_path: Path) -> None:
    workspace = Workspace(id=uuid.uuid4(), name="Symlink")
    relative = Path("workspaces") / str(workspace.id) / "uploads" / "repository.zip"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    info = zipfile.ZipInfo("link.py")
    info.create_system = 3
    info.external_attr = 0o120777 << 16
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, "../../secret")
    stored = StoredFile(
        workspace_id=workspace.id,
        display_name="repository.zip",
        storage_key=relative.as_posix(),
        media_type="application/zip",
        size_bytes=path.stat().st_size,
        sha256="2" * 64,
    )

    with pytest.raises(AppError) as denied:
        materialize_repository(Settings(data_root=tmp_path), workspace.id, uuid.uuid4(), [stored])

    assert denied.value.code == "REPOSITORY_SYMLINK_DENIED"


def test_repository_archive_enforces_expanded_size(tmp_path: Path) -> None:
    workspace = Workspace(id=uuid.uuid4(), name="Bomb")
    stored = stored_archive(tmp_path, workspace, {"large.py": "x" * 2_000})
    settings = Settings(data_root=tmp_path, sandbox_max_repository_bytes=1_024)

    with pytest.raises(AppError) as denied:
        materialize_repository(settings, workspace.id, uuid.uuid4(), [stored])

    assert denied.value.code == "REPOSITORY_SIZE_LIMIT"


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        (
            "--- a/app.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-print('safe')\n",
            "PATCH_DELETE_DENIED",
        ),
        (
            "--- a/app.py\n+++ b/../escape.py\n@@ -1 +1 @@\n-print('safe')\n+print('bad')\n",
            "REPOSITORY_PATH_DENIED",
        ),
        (
            "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-print('wrong')\n+print('bad')\n",
            "PATCH_CONTEXT_MISMATCH",
        ),
        (
            "--- a/test_app.py\n+++ b/test_app.py\n@@ -1 +1 @@\n-assert True\n+assert False\n",
            "PATCH_VERIFICATION_DENIED",
        ),
    ],
)
def test_patch_rejects_destructive_or_invalid_changes(
    tmp_path: Path, patch: str, code: str
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('safe')\n", encoding="utf-8")
    (root / "test_app.py").write_text("assert True\n", encoding="utf-8")

    with pytest.raises(AppError) as denied:
        apply_unified_diff(root, patch)

    assert denied.value.code == code
    assert (root / "app.py").read_text(encoding="utf-8") == "print('safe')\n"
    assert (root / "test_app.py").read_text(encoding="utf-8") == "assert True\n"
