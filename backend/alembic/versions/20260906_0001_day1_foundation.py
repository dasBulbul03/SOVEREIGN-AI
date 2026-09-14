"""Create Day 1 foundation tables and model registry seed."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "20260906_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model_key", sa.String(length=160), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("quantization", sa.String(length=40), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model_key", name="uq_models_provider_key"),
    )
    op.create_table(
        "model_health",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_health_model_observed", "model_health", ["model_id", "observed_at"])

    now = datetime.now(UTC)
    models_table = sa.table(
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
    op.bulk_insert(
        models_table,
        [
            {
                "id": UUID("7b35d238-5350-4b39-b12a-c93d796c5231"),
                "name": "General 1.7B",
                "provider": "ollama",
                "model_key": "qwen3:1.7b",
                "capabilities": ["text", "reasoning", "general"],
                "context_window": 32768,
                "quantization": "ollama-default",
                "priority": 100,
                "enabled": True,
                "config": {"profile": "m1-8gb"},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": UUID("205b2a0f-ec4f-41e0-af9e-18d23394fd68"),
                "name": "Coder 1.5B",
                "provider": "ollama",
                "model_key": "qwen2.5-coder:1.5b",
                "capabilities": ["text", "coding"],
                "context_window": 32768,
                "quantization": "ollama-default",
                "priority": 90,
                "enabled": True,
                "config": {"profile": "m1-8gb"},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": UUID("d424a49d-738c-4e1d-98ca-d7fe88285a53"),
                "name": "Nomic Embed Text",
                "provider": "ollama",
                "model_key": "nomic-embed-text",
                "capabilities": ["embedding"],
                "context_window": 2048,
                "quantization": "ollama-default",
                "priority": 100,
                "enabled": True,
                "config": {"profile": "m1-8gb"},
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_model_health_model_observed", table_name="model_health")
    op.drop_table("model_health")
    op.drop_table("models")
    op.drop_table("workspaces")
