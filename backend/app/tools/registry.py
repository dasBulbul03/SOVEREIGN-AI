import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import KnowledgeBase, StoredFile
from app.model_providers.ollama import OllamaModelProvider
from app.services.code_repository import apply_unified_diff, snapshot_repository
from app.services.document_extraction import ensure_document_extracted
from app.services.file_storage import resolve_storage_key
from app.services.qdrant_store import QdrantStore
from app.services.sandbox_client import SandboxClient


class ReadFileArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: uuid.UUID
    max_chars: int = Field(default=12_000, ge=500, le=50_000)


class SearchKnowledgeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledge_base_id: uuid.UUID
    query: str = Field(min_length=2, max_length=1_000)
    limit: int = Field(default=5, ge=1, le=10)


class ReadRepositoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_chars: int = Field(default=32_000, ge=1_000, le=100_000)


class SearchFilesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=50)


class ApplyPatchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patch: str = Field(min_length=10, max_length=500_000)


class RunPythonTestsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str = Field(pattern=r"^(pytest|unittest|compile|run|network_probe)$")


@dataclass(frozen=True, slots=True)
class ToolContext:
    workspace_id: uuid.UUID
    session: Session
    settings: Settings
    provider: OllamaModelProvider
    repository_root: Path | None = None
    sandbox_client: SandboxClient | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    status: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


class AgentTool(Protocol):
    name: str
    input_model: type[BaseModel]

    async def execute(self, context: ToolContext, arguments: BaseModel) -> ToolResult: ...


class ReadFileTool:
    name = "read_file"
    input_model: type[BaseModel] = ReadFileArgs

    async def execute(self, context: ToolContext, arguments: BaseModel) -> ToolResult:
        args = ReadFileArgs.model_validate(arguments)
        started = time.perf_counter()
        stored = context.session.get(StoredFile, args.file_id)
        if (
            stored is None
            or stored.workspace_id != context.workspace_id
            or stored.status == "deleted"
        ):
            raise AppError("TOOL_FILE_DENIED", "The requested file is unavailable.", 404)
        if stored.media_type.startswith("text/"):
            text = resolve_storage_key(context.settings.data_root, stored.storage_key).read_text(
                encoding="utf-8"
            )
        else:
            document, pages = await ensure_document_extracted(
                context.session, stored, context.settings
            )
            text = "\n\n".join(f"[Page {page.number}]\n{page.text}" for page in pages if page.text)
        bounded = text[: args.max_chars]
        return ToolResult(
            "completed",
            f"Read {stored.display_name} ({len(bounded)} characters).",
            {
                "text": bounded,
                "file_id": str(stored.id),
                "display_name": stored.display_name,
                "page_count": document.page_count
                if not stored.media_type.startswith("text/")
                else 1,
            },
            int((time.perf_counter() - started) * 1000),
        )


class SearchKnowledgeTool:
    name = "search_knowledge"
    input_model: type[BaseModel] = SearchKnowledgeArgs

    async def execute(self, context: ToolContext, arguments: BaseModel) -> ToolResult:
        args = SearchKnowledgeArgs.model_validate(arguments)
        started = time.perf_counter()
        kb = context.session.get(KnowledgeBase, args.knowledge_base_id)
        if kb is None or kb.workspace_id != context.workspace_id or kb.active_index_version is None:
            raise AppError("TOOL_KNOWLEDGE_DENIED", "The knowledge base is unavailable.", 404)
        embedding = await context.provider.embed([args.query], context.settings.embedding_model)
        points = await QdrantStore(
            context.settings.qdrant_url, context.settings.qdrant_collection
        ).search(embedding.vectors[0], str(kb.id), kb.active_index_version, args.limit)
        hits = []
        for index, point in enumerate(points, start=1):
            payload = point.get("payload", {})
            hits.append(
                {
                    "source_id": f"S{index}",
                    "score": float(point.get("score", 0)),
                    "text": str(payload.get("text", ""))[: context.settings.max_tool_output_chars],
                    "document_id": str(payload.get("document_id", "")),
                    "display_name": str(payload.get("display_name", "Document")),
                    "page_start": int(payload.get("page_start", 1)),
                    "page_end": int(payload.get("page_end", 1)),
                }
            )
        return ToolResult(
            "completed",
            f"Retrieved {len(hits)} cited knowledge matches.",
            {"hits": hits, "knowledge_base_id": str(kb.id)},
            int((time.perf_counter() - started) * 1000),
        )


def _repository_root(context: ToolContext) -> Path:
    if context.repository_root is None:
        raise AppError("REPOSITORY_CONTEXT_MISSING", "No coding repository is available.", 409)
    return context.repository_root


class ReadRepositoryTool:
    name = "read_repository"
    input_model: type[BaseModel] = ReadRepositoryArgs

    async def execute(self, context: ToolContext, arguments: BaseModel) -> ToolResult:
        args = ReadRepositoryArgs.model_validate(arguments)
        started = time.perf_counter()
        files = snapshot_repository(_repository_root(context), args.max_chars)
        return ToolResult(
            "completed",
            f"Read {len(files)} repository files within the context budget.",
            {"files": files, "file_count": len(files)},
            int((time.perf_counter() - started) * 1000),
        )


class SearchFilesTool:
    name = "search_files"
    input_model: type[BaseModel] = SearchFilesArgs

    async def execute(self, context: ToolContext, arguments: BaseModel) -> ToolResult:
        args = SearchFilesArgs.model_validate(arguments)
        started = time.perf_counter()
        matches: list[dict[str, object]] = []
        for path, content in snapshot_repository(
            _repository_root(context), context.settings.sandbox_repository_context_chars
        ).items():
            for line_number, line in enumerate(content.splitlines(), start=1):
                if args.query.casefold() in line.casefold():
                    matches.append({"path": path, "line": line_number, "text": line[:300]})
                    if len(matches) >= args.limit:
                        break
            if len(matches) >= args.limit:
                break
        return ToolResult(
            "completed",
            f"Found {len(matches)} bounded repository matches.",
            {"matches": matches},
            int((time.perf_counter() - started) * 1000),
        )


class ApplyPatchTool:
    name = "apply_patch"
    input_model: type[BaseModel] = ApplyPatchArgs

    async def execute(self, context: ToolContext, arguments: BaseModel) -> ToolResult:
        args = ApplyPatchArgs.model_validate(arguments)
        started = time.perf_counter()
        changed = apply_unified_diff(_repository_root(context), args.patch)
        return ToolResult(
            "completed",
            f"Applied a bounded patch to {len(changed)} files in the working copy.",
            {"changed_files": changed, "patch_chars": len(args.patch)},
            int((time.perf_counter() - started) * 1000),
        )


class RunPythonTestsTool:
    name = "run_python_tests"
    input_model: type[BaseModel] = RunPythonTestsArgs

    async def execute(self, context: ToolContext, arguments: BaseModel) -> ToolResult:
        args = RunPythonTestsArgs.model_validate(arguments)
        if context.sandbox_client is None:
            raise AppError("SANDBOX_CONTEXT_MISSING", "The sandbox runner is unavailable.", 409)
        result = await context.sandbox_client.run(_repository_root(context), args.command)
        data = result.public_data()
        return ToolResult(
            "completed" if result.passed else "failed",
            (
                f"Sandbox command {args.command} passed."
                if result.passed
                else f"Sandbox command {args.command} failed with exit code {result.exit_code}."
            ),
            data,
            result.duration_ms,
        )


class ToolRegistry:
    permissions = {
        "general_agent": {"read_file", "create_docx", "analyze_visual_pages"},
        "document_agent": {
            "read_file",
            "search_knowledge",
            "create_docx",
            "analyze_visual_pages",
        },
        "procurement_agent": {
            "read_file",
            "search_knowledge",
            "create_docx",
            "create_xlsx",
            "analyze_visual_pages",
        },
        "coding_agent": {
            "read_repository",
            "search_files",
            "apply_patch",
            "run_python_tests",
            "publish_code_artifacts",
        },
    }

    def __init__(self) -> None:
        self.tools: dict[str, AgentTool] = {
            "read_file": ReadFileTool(),
            "search_knowledge": SearchKnowledgeTool(),
            "read_repository": ReadRepositoryTool(),
            "search_files": SearchFilesTool(),
            "apply_patch": ApplyPatchTool(),
            "run_python_tests": RunPythonTestsTool(),
        }

    def authorize(self, profile: str, name: str) -> None:
        if name not in self.permissions.get(profile, set()):
            raise AppError("TOOL_POLICY_DENIED", f"{profile} may not use {name}.", 403)

    async def execute(
        self,
        profile: str,
        name: str,
        raw_arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        self.authorize(profile, name)
        tool = self.tools.get(name)
        if tool is None:
            raise AppError("TOOL_NOT_REGISTERED", f"Tool {name} is not registered.", 400)
        arguments = tool.input_model.model_validate(raw_arguments)
        timeout = (
            context.settings.sandbox_timeout_seconds + 10
            if name == "run_python_tests"
            else context.settings.tool_timeout_seconds
        )
        try:
            return await asyncio.wait_for(tool.execute(context, arguments), timeout=timeout)
        except TimeoutError as exc:
            raise AppError("TOOL_TIMEOUT", f"Tool {name} exceeded its time limit.", 504) from exc
