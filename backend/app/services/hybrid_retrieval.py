import math
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import KnowledgeBase, StoredFile
from app.documents.chunker import chunk_pages
from app.documents.types import NormalizedPage, TextChunk
from app.model_providers.base import EmbeddingResult
from app.services.document_extraction import ensure_document_extracted
from app.services.qdrant_store import QdrantStore


@dataclass(frozen=True, slots=True)
class HybridRetrievalResult:
    evidence: list[dict[str, Any]]
    mode: str
    processed_files: list[dict[str, Any]]
    searched_knowledge_bases: list[dict[str, Any]]
    candidate_chunks: int
    evidence_chars: int
    duration_ms: int


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str], model_key: str) -> EmbeddingResult: ...


class VectorSearch(Protocol):
    async def search(
        self, vector: list[float], kb_id: str, version: int, limit: int
    ) -> list[dict[str, Any]]: ...


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _terms(value: str) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9]+", value.casefold()) if len(item) > 2}


def _lexical_score(query_terms: set[str], chunk: TextChunk) -> float:
    if not query_terms:
        return 0.0
    terms = _terms(chunk.text)
    return len(query_terms & terms) / len(query_terms)


def _bounded_chunks(
    query: str,
    per_file: list[tuple[StoredFile, list[TextChunk]]],
    maximum: int,
) -> list[tuple[StoredFile, TextChunk]]:
    if not per_file:
        return []
    query_terms = _terms(query)
    quota = max(1, maximum // len(per_file))
    selected: list[tuple[float, StoredFile, TextChunk]] = []
    for stored, chunks in per_file:
        ranked = sorted(
            chunks,
            key=lambda item: (-_lexical_score(query_terms, item), item.ordinal),
        )
        selected.extend(
            (_lexical_score(query_terms, chunk), stored, chunk) for chunk in ranked[:quota]
        )
    selected.sort(key=lambda item: (-item[0], item[2].ordinal, str(item[1].id)))
    return [(stored, chunk) for _, stored, chunk in selected[:maximum]]


async def _embed_candidates(
    provider: EmbeddingProvider,
    settings: Settings,
    query_vector: list[float],
    candidates: list[tuple[StoredFile, TextChunk]],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for start in range(0, len(candidates), settings.task_embedding_batch_size):
        batch = candidates[start : start + settings.task_embedding_batch_size]
        embedded = await provider.embed(
            [chunk.text for _, chunk in batch], settings.embedding_model
        )
        for (stored, chunk), vector in zip(batch, embedded.vectors, strict=True):
            hits.append(
                {
                    "score": cosine_similarity(query_vector, vector),
                    "text": chunk.text,
                    "document_id": str(stored.id),
                    "file_id": str(stored.id),
                    "display_name": stored.display_name,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "retrieval_mode": "temporary_rag",
                    "source_type": "workspace_file",
                }
            )
    return hits


def _merge_and_bound(
    candidates: list[dict[str, Any]], maximum_hits: int, maximum_chars: int
) -> list[dict[str, Any]]:
    deduplicated: dict[tuple[str, int, int, str], dict[str, Any]] = {}
    for hit in candidates:
        text = str(hit.get("text", "")).strip()
        key = (
            str(hit.get("document_id", "")),
            int(hit.get("page_start", 1)),
            int(hit.get("page_end", 1)),
            text,
        )
        current = deduplicated.get(key)
        if current is None or float(hit.get("score", 0)) > float(current.get("score", 0)):
            deduplicated[key] = {**hit, "text": text}

    ranked = sorted(
        deduplicated.values(),
        key=lambda item: (-float(item.get("score", 0)), str(item.get("display_name", ""))),
    )
    selected: list[dict[str, Any]] = []
    per_document: Counter[str] = Counter()
    remaining = maximum_chars
    for hit in ranked:
        document_id = str(hit.get("document_id", ""))
        if per_document[document_id] >= 3 or remaining < 200:
            continue
        text = str(hit["text"])[:remaining]
        if not text:
            continue
        selected.append({**hit, "text": text})
        per_document[document_id] += 1
        remaining -= len(text)
        if len(selected) >= maximum_hits:
            break
    for index, hit in enumerate(selected, start=1):
        hit["source_id"] = f"S{index}"
    return selected


async def gather_hybrid_evidence(
    session: Session,
    workspace_id: uuid.UUID,
    file_ids: list[str],
    knowledge_base_ids: list[str],
    query: str,
    provider: EmbeddingProvider,
    settings: Settings,
    vector_store: VectorSearch | None = None,
) -> HybridRetrievalResult:
    started = time.perf_counter()
    extracted: list[tuple[StoredFile, list[NormalizedPage]]] = []
    for raw_file_id in file_ids:
        stored = session.get(StoredFile, uuid.UUID(raw_file_id))
        if stored is None or stored.workspace_id != workspace_id or stored.status == "deleted":
            raise AppError("TASK_FILE_NOT_FOUND", "A selected file is unavailable.", 404)
        _, pages = await ensure_document_extracted(session, stored, settings)
        extracted.append((stored, pages))

    total_file_chars = sum(len(page.text) for _, pages in extracted for page in pages)
    direct_mode = len(extracted) == 1 and total_file_chars <= settings.task_direct_read_chars
    raw_hits: list[dict[str, Any]] = []
    processed_files: list[dict[str, Any]] = []
    candidate_chunks = 0
    query_vector: list[float] | None = None

    if direct_mode:
        stored, pages = extracted[0]
        text = "\n\n".join(
            f"[Page {page.number}]\n{page.text}" for page in pages if page.text.strip()
        )
        raw_hits.append(
            {
                "score": 1.0,
                "text": text,
                "document_id": str(stored.id),
                "file_id": str(stored.id),
                "display_name": stored.display_name,
                "page_start": min((page.number for page in pages), default=1),
                "page_end": max((page.number for page in pages), default=1),
                "retrieval_mode": "direct_read",
                "source_type": "workspace_file",
            }
        )
        processed_files.append(
            {
                "file_id": str(stored.id),
                "display_name": stored.display_name,
                "page_count": len(pages),
                "chunk_count": 0,
                "mode": "direct_read",
            }
        )
    elif extracted:
        per_file: list[tuple[StoredFile, list[TextChunk]]] = []
        for stored, pages in extracted:
            chunks = chunk_pages(
                pages, settings.chunk_size_chars, settings.chunk_overlap_chars
            )
            candidate_chunks += len(chunks)
            per_file.append((stored, chunks))
            processed_files.append(
                {
                    "file_id": str(stored.id),
                    "display_name": stored.display_name,
                    "page_count": len(pages),
                    "chunk_count": len(chunks),
                    "mode": "temporary_rag",
                }
            )
        candidates = _bounded_chunks(
            query, per_file, settings.task_ephemeral_max_chunks
        )
        if candidates:
            query_embedding = await provider.embed([query], settings.embedding_model)
            query_vector = query_embedding.vectors[0]
            raw_hits.extend(
                await _embed_candidates(provider, settings, query_vector, candidates)
            )

    searched_bases: list[dict[str, Any]] = []
    store = vector_store or QdrantStore(settings.qdrant_url, settings.qdrant_collection)
    if knowledge_base_ids and query_vector is None:
        query_embedding = await provider.embed([query], settings.embedding_model)
        query_vector = query_embedding.vectors[0]
    for raw_kb_id in knowledge_base_ids:
        kb = session.get(KnowledgeBase, uuid.UUID(raw_kb_id))
        if (
            kb is None
            or kb.workspace_id != workspace_id
            or kb.active_index_version is None
            or kb.status != "ready"
        ):
            raise AppError(
                "TASK_KNOWLEDGE_NOT_READY",
                "A selected knowledge base is unavailable or not indexed.",
                409,
            )
        points = await store.search(
            query_vector or [], str(kb.id), kb.active_index_version, settings.task_kb_hits_per_base
        )
        searched_bases.append(
            {
                "knowledge_base_id": str(kb.id),
                "name": kb.name,
                "index_version": kb.active_index_version,
                "result_count": len(points),
            }
        )
        for point in points:
            payload = point.get("payload", {})
            raw_hits.append(
                {
                    "score": float(point.get("score", 0)),
                    "text": str(payload.get("text", "")),
                    "document_id": str(payload.get("document_id", "")),
                    "knowledge_base_id": str(kb.id),
                    "knowledge_base_name": kb.name,
                    "display_name": str(payload.get("display_name", "Document")),
                    "page_start": int(payload.get("page_start", 1)),
                    "page_end": int(payload.get("page_end", 1)),
                    "retrieval_mode": "knowledge_base_rag",
                    "source_type": "knowledge_base",
                }
            )

    evidence = _merge_and_bound(
        raw_hits, settings.task_evidence_max_hits, settings.task_evidence_max_chars
    )
    selected_counts = Counter(str(hit.get("file_id", "")) for hit in evidence)
    for item in processed_files:
        item["selected_hit_count"] = selected_counts[str(item["file_id"])]
    base_counts = Counter(str(hit.get("knowledge_base_id", "")) for hit in evidence)
    for item in searched_bases:
        item["selected_hit_count"] = base_counts[str(item["knowledge_base_id"])]

    modes = {str(hit.get("retrieval_mode")) for hit in evidence}
    mode = next(iter(modes)) if len(modes) == 1 else "hybrid"
    if not modes:
        mode = "no_evidence"
    return HybridRetrievalResult(
        evidence=evidence,
        mode=mode,
        processed_files=processed_files,
        searched_knowledge_bases=searched_bases,
        candidate_chunks=candidate_chunks,
        evidence_chars=sum(len(str(hit["text"])) for hit in evidence),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
