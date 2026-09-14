"""Add organization-scoped durable task, trace, artifact, and audit records."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_0004"
down_revision: str | None = "20260912_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_workspaces_organization_id",
        "workspaces",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"])
    op.execute(
        """
        UPDATE workspaces
        SET organization_id = (
            SELECT id FROM organizations ORDER BY created_at ASC LIMIT 1
        )
        WHERE organization_id IS NULL AND EXISTS (SELECT 1 FROM organizations)
        """
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(40), nullable=False),
        sa.Column("required_capabilities", sa.JSON(), nullable=False),
        sa.Column("input_file_ids", sa.JSON(), nullable=False),
        sa.Column("knowledge_base_ids", sa.JSON(), nullable=False),
        sa.Column("requested_outputs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "created_by_user_id", "idempotency_key", name="uq_task_user_idempotency"
        ),
    )
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_workspace_created", "tasks", ["workspace_id", "created_at"])

    op.create_table(
        "task_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("selected_model_id", sa.Uuid(), nullable=True),
        sa.Column("agent_profile", sa.String(60), nullable=False),
        sa.Column("route", sa.JSON(), nullable=False),
        sa.Column("step_count", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("error_category", sa.String(60), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["selected_model_id"], ["models.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "attempt", name="uq_task_run_attempt"),
    )
    op.create_index("ix_task_runs_status_created", "task_runs", ["status", "created_at"])

    op.create_table(
        "task_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("detail", sa.String(500), nullable=False),
        sa.Column("tool_name", sa.String(80), nullable=True),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["task_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_task_step_sequence"),
    )
    op.create_index("ix_task_steps_run_created", "task_steps", ["run_id", "created_at"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("logical_name", sa.String(120), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("validation_status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["task_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint("run_id", "logical_name", "revision", name="uq_artifact_revision"),
    )
    op.create_index("ix_artifacts_workspace_created", "artifacts", ["workspace_id", "created_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["task_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_workspace_occurred", "audit_events", ["workspace_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_workspace_occurred", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_artifacts_workspace_created", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_task_steps_run_created", table_name="task_steps")
    op.drop_table("task_steps")
    op.drop_index("ix_task_runs_status_created", table_name="task_runs")
    op.drop_table("task_runs")
    op.drop_index("ix_tasks_workspace_created", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_workspaces_organization_id", table_name="workspaces")
    op.drop_constraint("fk_workspaces_organization_id", "workspaces", type_="foreignkey")
    op.drop_column("workspaces", "organization_id")
