"""Register the memory-conscious local vision model for Day 5."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "20260914_0007"
down_revision: str | None = "20260913_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VISION_MODEL_ID = UUID("cc469c0e-c124-4d7c-848a-5eea5a982819")


def upgrade() -> None:
    models = sa.table(
        "models",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("model_key", sa.String()),
        sa.column("capabilities", sa.JSON()),
        sa.column("context_window", sa.Integer()),
        sa.column("quantization", sa.String()),
        sa.column("priority", sa.Integer()),
        sa.column("enabled", sa.Boolean()),
        sa.column("config", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    connection = op.get_bind()
    existing = connection.execute(
        sa.select(models.c.id, models.c.capabilities).where(
            models.c.provider == "ollama", models.c.model_key == "gemma3:4b"
        )
    ).first()
    if existing:
        capabilities = list(existing.capabilities or [])
        for capability in ("text", "vision"):
            if capability not in capabilities:
                capabilities.append(capability)
        connection.execute(
            models.update()
            .where(models.c.id == existing.id)
            .values(capabilities=capabilities, updated_at=datetime.now(UTC))
        )
        return
    now = datetime.now(UTC)
    op.bulk_insert(
        models,
        [
            {
                "id": VISION_MODEL_ID,
                "name": "Gemma 3 Vision 4B",
                "provider": "ollama",
                "model_key": "gemma3:4b",
                "capabilities": ["text", "vision"],
                "context_window": 32768,
                "quantization": "ollama-default",
                "priority": 80,
                "enabled": True,
                "config": {"profile": "m1-8gb", "role": "visual-preprocessor"},
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM models WHERE id = :id").bindparams(id=VISION_MODEL_ID))
