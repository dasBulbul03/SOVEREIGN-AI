import uuid
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.knowledge import ingest, list_files
from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    Document,
    DocumentChunk,
    IngestionJob,
    KnowledgeBase,
    KnowledgeBaseDocument,
    Organization,
    StoredFile,
    User,
    Workspace,
)
from app.model_providers.base import EmbeddingResult
from app.schemas.knowledge import IngestionRequest
from app.services import knowledge_ingestion


def _knowledge_fixture(session: Session) -> tuple[User, Workspace, StoredFile, KnowledgeBase]:
    organization = Organization(name="Test Org", slug=f"test-{uuid.uuid4()}")
    session.add(organization)
    session.flush()
    user = User(
        organization_id=organization.id,
        email=f"{uuid.uuid4()}@example.test",
        full_name="Test Owner",
        password_hash="unused",
    )
    workspace = Workspace(organization_id=organization.id, name="Test Workspace")
    session.add_all([user, workspace])
    session.flush()
    stored = StoredFile(
        workspace_id=workspace.id,
        display_name="manual.txt",
        storage_key=f"testing/{uuid.uuid4()}/manual.txt",
        media_type="text/plain",
        size_bytes=12,
        sha256="0" * 64,
    )
    knowledge_base = KnowledgeBase(
        workspace_id=workspace.id,
        name="Operations Library",
        status="ready",
        active_index_version=1,
    )
    session.add_all([stored, knowledge_base])
    session.commit()
    return user, workspace, stored, knowledge_base


def test_file_indexed_status_can_be_scoped_to_one_knowledge_base() -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            user, workspace, stored, first_base = _knowledge_fixture(session)
            other_base = KnowledgeBase(
                workspace_id=workspace.id,
                name="Other Library",
                status="ready",
                active_index_version=1,
            )
            document = Document(file_id=stored.id, extraction_status="completed")
            session.add_all([other_base, document])
            session.flush()
            session.add(
                KnowledgeBaseDocument(
                    knowledge_base_id=other_base.id,
                    document_id=document.id,
                    index_version=1,
                    status="indexed",
                )
            )
            session.commit()

            global_files = list_files(workspace.id, session, user)
            first_base_files = list_files(workspace.id, session, user, first_base.id)
            other_base_files = list_files(workspace.id, session, user, other_base.id)

            assert global_files[0].indexed is True
            assert first_base_files[0].indexed is False
            assert other_base_files[0].indexed is True
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_ingestion_retry_advances_past_failed_staged_version() -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            user, _, stored, knowledge_base = _knowledge_fixture(session)
            session.add(
                IngestionJob(
                    knowledge_base_id=knowledge_base.id,
                    requested_file_ids=[str(stored.id)],
                    index_version=2,
                    total_documents=1,
                    status="failed",
                    error_code="VECTOR_INDEX_FAILED",
                )
            )
            session.commit()

            tasks = BackgroundTasks()
            job = ingest(
                knowledge_base.id,
                IngestionRequest(file_ids=[stored.id]),
                tasks,
                session,
                user,
            )

            assert job.index_version == 3
            assert job.status == "queued"
            assert len(tasks.tasks) == 1
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


async def test_ingestion_extracts_embeds_indexes_and_activates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    indexed_points: list[dict[str, object]] = []

    class FakeProvider:
        def __init__(self, _base_url: str, *, context_tokens: int = 8_192) -> None:
            assert context_tokens == 8_192

        async def embed(self, texts: list[str], _model_key: str) -> EmbeddingResult:
            return EmbeddingResult([[float(len(text)), 1.0, 0.5] for text in texts], 1)

    class FakeVectorStore:
        def __init__(self, _base_url: str, _collection: str) -> None:
            pass

        async def ensure_collection(self, dimensions: int) -> None:
            assert dimensions == 3

        async def upsert(self, points: list[dict[str, object]]) -> None:
            indexed_points.extend(points)

    try:
        with testing_session() as session:
            _, workspace, stored, knowledge_base = _knowledge_fixture(session)
            stored.storage_key = f"workspaces/{workspace.id}/uploads/manual.txt"
            knowledge_base.status = "indexing"
            knowledge_base.active_index_version = None
            job = IngestionJob(
                knowledge_base_id=knowledge_base.id,
                requested_file_ids=[str(stored.id)],
                index_version=1,
                total_documents=1,
            )
            session.add(job)
            session.commit()
            job_id = job.id
            knowledge_base_id = knowledge_base.id

        source = tmp_path / stored.storage_key
        source.parent.mkdir(parents=True)
        source.write_text("Lock out the pump and verify zero pressure before maintenance.")
        settings = Settings(
            data_root=tmp_path,
            chunk_size_chars=500,
            chunk_overlap_chars=50,
        )
        monkeypatch.setattr(knowledge_ingestion, "SessionLocal", testing_session)
        monkeypatch.setattr(knowledge_ingestion, "get_settings", lambda: settings)
        monkeypatch.setattr(knowledge_ingestion, "OllamaModelProvider", FakeProvider)
        monkeypatch.setattr(knowledge_ingestion, "QdrantStore", FakeVectorStore)

        await knowledge_ingestion.run_ingestion(job_id)

        with testing_session() as session:
            completed = session.get(IngestionJob, job_id)
            activated = session.get(KnowledgeBase, knowledge_base_id)
            chunks = list(
                session.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.knowledge_base_id == knowledge_base_id
                    )
                )
            )
            assert completed is not None
            assert completed.status == "completed"
            assert completed.completed_documents == 1
            assert activated is not None
            assert activated.status == "ready"
            assert activated.active_index_version == 1
            assert len(chunks) == 1
            assert indexed_points[0]["payload"] == {
                "knowledge_base_id": str(knowledge_base_id),
                "document_id": str(chunks[0].document_id),
                "index_version": 1,
                "page_start": 1,
                "page_end": 1,
                "text": "Lock out the pump and verify zero pressure before maintenance.",
                "display_name": "manual.txt",
            }
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
