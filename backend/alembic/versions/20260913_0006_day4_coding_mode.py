"""Add explicit coding mode and test-command selection to tasks."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_0006"
down_revision: str | None = "20260913_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("mode", sa.String(24), nullable=False, server_default="auto"))
    op.add_column(
        "tasks", sa.Column("test_command", sa.String(24), nullable=False, server_default="pytest")
    )


def downgrade() -> None:
    op.drop_column("tasks", "test_command")
    op.drop_column("tasks", "mode")
