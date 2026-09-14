from pathlib import Path

import pymupdf
import pytest

from app.core.errors import AppError
from app.documents.chunker import chunk_pages
from app.documents.parser import extract_pages
from app.documents.types import NormalizedPage
from app.services.file_storage import validate_filename


def test_rejects_unsafe_and_unknown_filenames() -> None:
    with pytest.raises(AppError):
        validate_filename("../secret.pdf")
    with pytest.raises(AppError):
        validate_filename("payload.exe")


def test_chunks_are_page_aware_and_bounded() -> None:
    chunks = chunk_pages([NormalizedPage(3, "word " * 400, "native")], 500, 80)
    assert len(chunks) > 1
    assert all(chunk.page_start == 3 and len(chunk.text) <= 500 for chunk in chunks)
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))


def test_extracts_text_pdf(tmp_path: Path) -> None:
    path = tmp_path / "manual.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72), "Pump isolation procedure: close valve V-14 and verify zero pressure."
    )
    document.save(path)
    document.close()
    pages, warnings = extract_pages(path, "application/pdf", 10, 20)
    assert "close valve V-14" in pages[0].text
    assert pages[0].extraction_method == "native"
    assert warnings == []
