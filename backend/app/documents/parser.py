# mypy: disable-error-code="no-untyped-call,var-annotated,arg-type"
from pathlib import Path

import pymupdf
import pytesseract  # type: ignore[import-untyped]
from PIL import Image

from app.core.errors import AppError
from app.documents.types import NormalizedPage


def extract_pages(
    path: Path,
    media_type: str,
    max_pages: int,
    ocr_threshold: int,
    max_image_pixels: int = 25_000_000,
) -> tuple[list[NormalizedPage], list[str]]:
    if media_type == "application/pdf":
        return _extract_pdf(path, max_pages, ocr_threshold, max_image_pixels)
    if media_type.startswith("image/"):
        try:
            with Image.open(path) as image:
                if image.width * image.height > max_image_pixels:
                    raise AppError(
                        "IMAGE_PIXEL_LIMIT",
                        f"Images are limited to {max_image_pixels:,} pixels.",
                        413,
                    )
                image.load()
                text = pytesseract.image_to_string(image).strip()
        except AppError:
            raise
        except Exception as exc:
            raise AppError("INVALID_IMAGE", "The uploaded image could not be opened.", 422) from exc
        return [NormalizedPage(1, text, "ocr")], ([] if text else ["OCR produced no text"])
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise AppError(
            "INVALID_TEXT_ENCODING", "Text documents must use UTF-8 encoding.", 422
        ) from exc
    return [NormalizedPage(1, text.strip(), "text")], (
        [] if text.strip() else ["Document is empty"]
    )


def _extract_pdf(
    path: Path, max_pages: int, ocr_threshold: int, max_image_pixels: int
) -> tuple[list[NormalizedPage], list[str]]:
    pages: list[NormalizedPage] = []
    warnings: list[str] = []
    try:
        document = pymupdf.open(path)
    except Exception as exc:
        raise AppError("INVALID_PDF", "The uploaded PDF could not be opened.", 422) from exc
    with document:
        if document.page_count > max_pages:
            raise AppError("PDF_PAGE_LIMIT", f"PDFs are limited to {max_pages} pages.", 413)
        for index, page in enumerate(document):
            text = page.get_text("text").strip()
            method = "native"
            if len(text) < ocr_threshold:
                rendered_pixels = int(page.rect.width * 1.5 * page.rect.height * 1.5)
                if rendered_pixels > max_image_pixels:
                    raise AppError(
                        "PDF_PIXEL_LIMIT",
                        "A rendered PDF page exceeds the configured pixel limit.",
                        413,
                    )
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                ocr_text = pytesseract.image_to_string(image).strip()
                if len(ocr_text) > len(text):
                    text, method = ocr_text, "ocr"
                if not text:
                    warnings.append(f"Page {index + 1} produced no text")
            pages.append(NormalizedPage(index + 1, text, method))
    return pages, warnings
