import json
import uuid
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.db.models import Document, RegisteredModel, StoredFile, Workspace
from app.model_providers.base import ChatRequest, ChatResult, ProviderHealth
from app.services.document_extraction import load_normalized_pages
from app.services.multimodal import enrich_multimodal_inputs


class FakeVisionProvider:
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    async def health(self, model_key: str) -> ProviderHealth:
        return ProviderHealth(model_key == "gemma3:4b", 1)

    async def chat(self, request: ChatRequest) -> ChatResult:
        self.requests.append(request)
        return ChatResult("A pressure gauge is visible and reads 4 bar.", 2)


@pytest.mark.asyncio
async def test_image_ocr_and_vision_are_merged_into_normalized_page(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        workspace = Workspace(name="Vision")
        session.add(workspace)
        session.flush()
        image_key = f"workspaces/{workspace.id}/uploads/gauge.png"
        image_path = tmp_path / image_key
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (160, 80), "white").save(image_path)
        stored = StoredFile(
            workspace_id=workspace.id,
            display_name="gauge.png",
            storage_key=image_key,
            media_type="image/png",
            size_bytes=image_path.stat().st_size,
            sha256="1" * 64,
        )
        session.add(stored)
        session.flush()
        normalized_key = f"workspaces/{workspace.id}/extracted/{uuid.uuid4()}/pages.json"
        normalized_path = tmp_path / normalized_key
        normalized_path.parent.mkdir(parents=True)
        normalized_path.write_text(
            json.dumps(
                [
                    {
                        "number": 1,
                        "text": "GAUGE",
                        "extraction_method": "ocr",
                        "visual_context": None,
                    }
                ]
            ),
            encoding="utf-8",
        )
        document = Document(
            file_id=stored.id,
            page_count=1,
            extraction_status="completed",
            normalized_path=normalized_key,
        )
        model = RegisteredModel(
            name="Vision",
            provider="ollama",
            model_key="gemma3:4b",
            capabilities=["text", "vision"],
            priority=80,
        )
        session.add_all([document, model])
        session.commit()
        provider = FakeVisionProvider()

        result = await enrich_multimodal_inputs(
            session,
            workspace.id,
            [str(stored.id)],
            "Inspect the gauge.",
            provider,  # type: ignore[arg-type]
            Settings(data_root=tmp_path),
        )

        pages = load_normalized_pages(Settings(data_root=tmp_path), document)
        assert result.vision_pages == 1
        assert result.vision_model == "gemma3:4b"
        assert pages[0].extraction_method == "ocr+vision"
        assert "4 bar" in pages[0].text
        assert provider.requests[0].images
    Base.metadata.drop_all(engine)
    engine.dispose()
