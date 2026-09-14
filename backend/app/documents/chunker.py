import re

from app.documents.types import NormalizedPage, TextChunk


def chunk_pages(pages: list[NormalizedPage], size: int, overlap: int) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    step = max(1, size - min(overlap, size - 1))
    for page in pages:
        clean = re.sub(r"[ \t]+", " ", page.text).strip()
        if not clean:
            continue
        start = 0
        while start < len(clean):
            end = min(start + size, len(clean))
            if end < len(clean):
                boundary = clean.rfind(" ", start + size // 2, end)
                if boundary > start:
                    end = boundary
            text = clean[start:end].strip()
            if text:
                chunks.append(TextChunk(len(chunks), page.number, page.number, text))
            if end >= len(clean):
                break
            start = max(start + 1, end - overlap)
            if start < end - step:
                start = end - step
    return chunks
