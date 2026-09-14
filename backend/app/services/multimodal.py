# mypy: disable-error-code="no-untyped-call,no-any-return"
import asyncio
import base64
import io
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Document, RegisteredModel, StoredFile
from app.documents.types import NormalizedPage
from app.model_providers.base import ChatRequest
from app.model_providers.ollama import OllamaModelProvider
from app.services.document_extraction import ensure_document_extracted, save_normalized_pages
from app.services.file_storage import resolve_storage_key


@dataclass(frozen=True, slots=True)
class MultimodalResult:
    candidate_pages: int
    vision_pages: int
    ocr_pages: int
    vision_model: str | None
    warnings: list[str]
    duration_ms: int
    prompt_tokens: int
    completion_tokens: int


def _render_page(path: Path, media_type: str, page_number: int, dpi: int) -> bytes:
    if media_type.startswith("image/"):
        with Image.open(path) as image:
            image.thumbnail((2048, 2048))
            normalized = image.convert("RGB")
            output = io.BytesIO()
            normalized.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    with pymupdf.open(path) as document:
        page = document[page_number - 1]
        scale = dpi / 72
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("jpeg", jpg_quality=88)


async def _vision_model(
    session: Session, provider: OllamaModelProvider
) -> RegisteredModel | None:
    candidates = list(
        session.scalars(
            select(RegisteredModel)
            .where(RegisteredModel.enabled.is_(True))
            .order_by(RegisteredModel.priority.desc(), RegisteredModel.model_key)
        )
    )
    for candidate in candidates:
        if "vision" not in candidate.capabilities:
            continue
        health = await provider.health(candidate.model_key)
        if health.ready:
            return candidate
    return None


async def enrich_multimodal_inputs(
    session: Session,
    workspace_id: uuid.UUID,
    file_ids: list[str],
    goal: str,
    provider: OllamaModelProvider,
    settings: Settings,
) -> MultimodalResult:
    started = time.perf_counter()
    candidates: list[
        tuple[StoredFile, Document, list[NormalizedPage], NormalizedPage]
    ] = []
    ocr_pages = 0
    for raw_file_id in file_ids:
        stored = session.get(StoredFile, uuid.UUID(raw_file_id))
        if stored is None or stored.workspace_id != workspace_id or stored.status == "deleted":
            continue
        document, pages = await ensure_document_extracted(session, stored, settings)
        for page in pages:
            if page.extraction_method.startswith("ocr"):
                ocr_pages += 1
            visual_candidate = (
                stored.media_type.startswith("image/") or page.extraction_method == "ocr"
            )
            if visual_candidate and not page.visual_context:
                candidates.append((stored, document, pages, page))
    bounded = candidates[: settings.vision_max_pages_per_task]
    model = await _vision_model(session, provider) if bounded else None
    warnings: list[str] = []
    vision_pages = 0
    prompt_tokens = 0
    completion_tokens = 0
    if bounded and model is None:
        warnings.append(
            "No healthy registered vision model was available; OCR text was retained as the "
            "explicit fallback."
        )
    updated: dict[uuid.UUID, tuple[StoredFile, Document, list[NormalizedPage]]] = {}
    if model:
        for stored, document, pages, target in bounded:
            image = await asyncio.to_thread(
                _render_page,
                resolve_storage_key(settings.data_root, stored.storage_key),
                stored.media_type,
                target.number,
                settings.vision_render_dpi,
            )
            prompt = (
                "Describe only visible facts useful for the requested industrial task. "
                "Transcribe labels, table cells, quantities, defects, and safety indicators. "
                "Do not infer facts that are not visible. Keep the answer under 180 words.\n\n"
                f"Task: {goal}"
            )
            result = await provider.chat(
                ChatRequest(
                    model.model_key,
                    prompt,
                    settings.model_keep_alive,
                    temperature=0.0,
                    images=(base64.b64encode(image).decode("ascii"),),
                )
            )
            prompt_tokens += result.prompt_tokens or 0
            completion_tokens += result.completion_tokens or 0
            replacement = NormalizedPage(
                target.number,
                f"{target.text}\n\n[Visual analysis]\n{result.content}",
                f"{target.extraction_method}+vision",
                result.content,
            )
            pages[pages.index(target)] = replacement
            updated[stored.id] = (stored, document, pages)
            vision_pages += 1
        for stored, document, pages in updated.values():
            document.normalized_path = save_normalized_pages(
                settings, stored, document, pages
            )
            document.extractor_version = "day5-multimodal-v1"
        session.commit()
    if len(candidates) > len(bounded):
        warnings.append(
            f"Vision analysis was bounded to {settings.vision_max_pages_per_task} pages; "
            f"{len(candidates) - len(bounded)} additional pages used OCR only."
        )
    return MultimodalResult(
        candidate_pages=len(candidates),
        vision_pages=vision_pages,
        ocr_pages=ocr_pages,
        vision_model=model.model_key if model else None,
        warnings=warnings,
        duration_ms=int((time.perf_counter() - started) * 1000),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
