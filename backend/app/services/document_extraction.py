import asyncio
import json
import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import Document, StoredFile
from app.documents.parser import extract_pages
from app.documents.types import NormalizedPage
from app.services.file_storage import resolve_storage_key


def load_normalized_pages(settings: Settings, document: Document) -> list[NormalizedPage]:
    if not document.normalized_path:
        return []
    payload = json.loads(
        resolve_storage_key(settings.data_root, document.normalized_path).read_text(
            encoding="utf-8"
        )
    )
    return [
        NormalizedPage(
            number=int(page["number"]),
            text=str(page["text"]),
            extraction_method=str(page["extraction_method"]),
            visual_context=(
                str(page["visual_context"]) if page.get("visual_context") else None
            ),
        )
        for page in payload
    ]


async def ensure_document_extracted(
    session: Session, stored: StoredFile, settings: Settings
) -> tuple[Document, list[NormalizedPage]]:
    document = session.scalar(select(Document).where(Document.file_id == stored.id))
    if document and document.extraction_status == "completed" and document.normalized_path:
        return document, load_normalized_pages(settings, document)
    if document is None:
        document = Document(file_id=stored.id)
        session.add(document)
        session.flush()

    pages, warnings = await asyncio.to_thread(
        extract_pages,
        resolve_storage_key(settings.data_root, stored.storage_key),
        stored.media_type,
        settings.max_pdf_pages,
        settings.ocr_text_threshold,
        settings.max_image_pixels,
    )
    if not any(page.text.strip() for page in pages):
        if stored.media_type == "application/pdf" or stored.media_type.startswith("image/"):
            pages = [
                NormalizedPage(
                    page.number,
                    "[No OCR text detected on this page.]",
                    page.extraction_method,
                )
                for page in pages
            ]
            warnings.append("No OCR text was detected; local vision analysis may add context")
        else:
            raise AppError(
                "NO_EXTRACTABLE_TEXT",
                f"No text could be extracted from {stored.display_name}.",
                422,
            )

    normalized_key = save_normalized_pages(settings, stored, document, pages)

    document.page_count = len(pages)
    document.extraction_status = "completed"
    document.normalized_path = normalized_key
    document.warnings = warnings
    document.updated_at = datetime.now(UTC)
    session.commit()
    return document, pages


def save_normalized_pages(
    settings: Settings,
    stored: StoredFile,
    document: Document,
    pages: list[NormalizedPage],
) -> str:
    normalized_key = f"workspaces/{stored.workspace_id}/extracted/{document.id}/pages.json"
    normalized_path = resolve_storage_key(settings.data_root, normalized_key)
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = normalized_path.with_suffix(".json.tmp")
    try:
        temporary.write_text(
            json.dumps([page.to_dict() for page in pages], ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, normalized_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return normalized_key
