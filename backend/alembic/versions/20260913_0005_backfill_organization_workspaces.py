"""Backfill a default workspace for organizations created before Day 3."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_0005"
down_revision: str | None = "20260913_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    organizations = sa.table(
        "organizations",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
    )
    workspaces = sa.table(
        "workspaces",
        sa.column("id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    connection = op.get_bind()
    missing = connection.execute(
        sa.select(organizations.c.id, organizations.c.name).where(
            ~sa.exists(sa.select(1).where(workspaces.c.organization_id == organizations.c.id))
        )
    ).all()
    timestamp = datetime.now(UTC)
    if missing:
        op.bulk_insert(
            workspaces,
            [
                {
                    "id": uuid.uuid4(),
                    "organization_id": organization_id,
                    "name": f"{organization_name} Workspace",
                    "status": "active",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
                for organization_id, organization_name in missing
            ],
        )


def downgrade() -> None:
    # Keep user-visible workspaces: a data backfill cannot be distinguished safely
    # from records subsequently used or renamed by an operator.
    pass
