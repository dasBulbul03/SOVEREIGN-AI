import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, UploadFile
from sqlalchemy import func, select

from app.api.dependencies import AppSettings, CurrentUser, DatabaseSession, OllamaProvider
from app.core.errors import AppError
from app.db.models import (
    AuditEvent,
    Document,
    IngestionJob,
    KnowledgeBase,
    KnowledgeBaseDocument,
    StoredFile,
    Workspace,
)
from app.schemas.knowledge import (
    Citation,
    FileResponse,
    IngestionRequest,
    IngestionResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
    WorkspaceCreate,
    WorkspaceResponse,
)
from app.services.file_storage import store_upload
from app.services.knowledge_ingestion import run_ingestion
from app.services.qdrant_store import QdrantStore
from app.tasks.service import owned_workspace

router = APIRouter(tags=["knowledge"])


def owned_knowledge_base(
    session: DatabaseSession, kb_id: uuid.UUID, user: CurrentUser
) -> KnowledgeBase:
    kb = session.scalar(
        select(KnowledgeBase)
        .join(Workspace, Workspace.id == KnowledgeBase.workspace_id)
        .where(KnowledgeBase.id == kb_id, Workspace.organization_id == user.organization_id)
    )
    if kb is None:
        raise AppError("KNOWLEDGE_BASE_NOT_FOUND", "Knowledge base not found.", 404)
    return kb


@router.get("/workspaces", response_model=list[WorkspaceResponse])
def list_workspaces(session: DatabaseSession, user: CurrentUser) -> list[Workspace]:
    return list(
        session.scalars(
            select(Workspace)
            .where(Workspace.organization_id == user.organization_id)
            .order_by(Workspace.created_at)
        )
    )


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
def create_workspace(
    payload: WorkspaceCreate, session: DatabaseSession, user: CurrentUser
) -> Workspace:
    workspace = Workspace(name=payload.name.strip(), organization_id=user.organization_id)
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


@router.get("/workspaces/{workspace_id}/files", response_model=list[FileResponse])
def list_files(
    workspace_id: uuid.UUID,
    session: DatabaseSession,
    user: CurrentUser,
    knowledge_base_id: uuid.UUID | None = None,
) -> list[FileResponse]:
    owned_workspace(session, workspace_id, user)
    knowledge_base = None
    if knowledge_base_id is not None:
        knowledge_base = owned_knowledge_base(session, knowledge_base_id, user)
        if knowledge_base.workspace_id != workspace_id:
            raise AppError(
                "KNOWLEDGE_BASE_NOT_FOUND",
                "Knowledge base not found in this workspace.",
                404,
            )
    files = list(
        session.scalars(
            select(StoredFile)
            .where(StoredFile.workspace_id == workspace_id, StoredFile.status != "deleted")
            .order_by(StoredFile.created_at.desc())
        )
    )
    indexed_statement = (
        select(Document.file_id)
        .join(KnowledgeBaseDocument, KnowledgeBaseDocument.document_id == Document.id)
        .join(KnowledgeBase, KnowledgeBase.id == KnowledgeBaseDocument.knowledge_base_id)
        .where(
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBaseDocument.status == "indexed",
            KnowledgeBaseDocument.index_version == KnowledgeBase.active_index_version,
        )
    )
    if knowledge_base is not None:
        indexed_statement = indexed_statement.where(KnowledgeBase.id == knowledge_base.id)
    indexed_file_ids = set(session.scalars(indexed_statement))
    return [
        FileResponse.model_validate(item).model_copy(
            update={"indexed": item.id in indexed_file_ids}
        )
        for item in files
    ]


@router.post("/workspaces/{workspace_id}/files", response_model=FileResponse, status_code=201)
async def upload_file(
    workspace_id: uuid.UUID,
    session: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
) -> StoredFile:
    owned_workspace(session, workspace_id, user)
    uploaded = await store_upload(file, settings.data_root, workspace_id, settings.max_upload_bytes)
    record = StoredFile(
        workspace_id=workspace_id,
        display_name=uploaded.display_name,
        storage_key=uploaded.storage_key,
        media_type=uploaded.media_type,
        size_bytes=uploaded.size_bytes,
        sha256=uploaded.sha256,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.delete("/workspaces/{workspace_id}/files/{file_id}", status_code=204)
def remove_file(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> None:
    owned_workspace(session, workspace_id, user)
    record = session.scalar(
        select(StoredFile).where(
            StoredFile.id == file_id,
            StoredFile.workspace_id == workspace_id,
            StoredFile.status != "deleted",
        )
    )
    if record is None:
        raise AppError("FILE_NOT_FOUND", "File not found.", 404)
    record.status = "deleted"
    session.add(
        AuditEvent(
            workspace_id=workspace_id,
            event_type="FILE_REMOVED",
            actor_type="user",
            actor_id=user.id,
            payload={"file_id": str(record.id), "display_name": record.display_name},
        )
    )
    session.commit()


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(
    session: DatabaseSession, user: CurrentUser, workspace_id: uuid.UUID | None = None
) -> list[KnowledgeBase]:
    statement = (
        select(KnowledgeBase)
        .join(Workspace, Workspace.id == KnowledgeBase.workspace_id)
        .where(Workspace.organization_id == user.organization_id)
        .order_by(KnowledgeBase.created_at)
    )
    if workspace_id:
        statement = statement.where(KnowledgeBase.workspace_id == workspace_id)
    return list(session.scalars(statement))


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse, status_code=201)
def create_knowledge_base(
    payload: KnowledgeBaseCreate, session: DatabaseSession, user: CurrentUser
) -> KnowledgeBase:
    owned_workspace(session, payload.workspace_id, user)
    kb = KnowledgeBase(workspace_id=payload.workspace_id, name=payload.name.strip())
    session.add(kb)
    session.commit()
    session.refresh(kb)
    return kb


@router.post(
    "/knowledge-bases/{kb_id}/ingestions", response_model=IngestionResponse, status_code=202
)
def ingest(
    kb_id: uuid.UUID,
    payload: IngestionRequest,
    tasks: BackgroundTasks,
    session: DatabaseSession,
    user: CurrentUser,
) -> IngestionJob:
    kb = owned_knowledge_base(session, kb_id, user)
    if kb.status == "indexing":
        raise AppError(
            "INGESTION_IN_PROGRESS", "This knowledge base is already indexing.", 409, True
        )
    files = list(session.scalars(select(StoredFile).where(StoredFile.id.in_(payload.file_ids))))
    if len(files) != len(set(payload.file_ids)) or any(
        item.workspace_id != kb.workspace_id or item.status == "deleted" for item in files
    ):
        raise AppError("FILE_NOT_FOUND", "Every file must belong to this workspace.", 404)
    # Failed staged versions deliberately remain available for diagnosis. Always advance
    # past every attempted version so a retry cannot collide with their immutable rows.
    latest_attempt = session.scalar(
        select(func.max(IngestionJob.index_version)).where(
            IngestionJob.knowledge_base_id == kb.id
        )
    )
    version = max(kb.active_index_version or 0, latest_attempt or 0) + 1
    job = IngestionJob(
        knowledge_base_id=kb.id,
        requested_file_ids=[str(item) for item in payload.file_ids],
        index_version=version,
        total_documents=len(payload.file_ids),
    )
    kb.status = "indexing"
    session.add(job)
    session.commit()
    session.refresh(job)
    tasks.add_task(run_ingestion, job.id)
    return job


@router.get("/ingestions/{job_id}", response_model=IngestionResponse)
def ingestion_status(
    job_id: uuid.UUID, session: DatabaseSession, user: CurrentUser
) -> IngestionJob:
    job = session.scalar(
        select(IngestionJob)
        .join(KnowledgeBase, KnowledgeBase.id == IngestionJob.knowledge_base_id)
        .join(Workspace, Workspace.id == KnowledgeBase.workspace_id)
        .where(IngestionJob.id == job_id, Workspace.organization_id == user.organization_id)
    )
    if job is None:
        raise AppError("INGESTION_NOT_FOUND", "Ingestion job not found.", 404)
    return job


@router.post("/knowledge-bases/{kb_id}/search", response_model=SearchResponse)
async def search(
    kb_id: uuid.UUID,
    payload: SearchRequest,
    session: DatabaseSession,
    settings: AppSettings,
    provider: OllamaProvider,
    user: CurrentUser,
) -> SearchResponse:
    kb = owned_knowledge_base(session, kb_id, user)
    if kb.active_index_version is None:
        raise AppError(
            "KNOWLEDGE_BASE_NOT_READY", "Index this knowledge base before searching it.", 409
        )
    embedding = await provider.embed([payload.query], settings.embedding_model)
    points = await QdrantStore(settings.qdrant_url, settings.qdrant_collection).search(
        embedding.vectors[0], str(kb.id), kb.active_index_version, payload.limit
    )
    hits = [
        SearchHit(
            score=float(point.get("score", 0)),
            text=str(point.get("payload", {}).get("text", "")),
            citation=Citation(
                document_id=point.get("payload", {}).get("document_id"),
                display_name=point.get("payload", {}).get("display_name", "Document"),
                page_start=point.get("payload", {}).get("page_start", 1),
                page_end=point.get("payload", {}).get("page_end", 1),
            ),
        )
        for point in points
    ]
    return SearchResponse(
        knowledge_base_id=kb.id,
        index_version=kb.active_index_version,
        query=payload.query,
        hits=hits,
    )
