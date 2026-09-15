"""Unified AI invocation audit trail."""

from alembic import op
import sqlalchemy as sa

revision = "20260915_05"
down_revision = "20260915_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "ai_invocations" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "ai_invocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("evidence_ref", sa.String(200), nullable=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("case_sessions.id"), nullable=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=True),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ai_invocations_task_type", "ai_invocations", ["task_type"])


def downgrade() -> None:
    op.drop_index("ix_ai_invocations_task_type", table_name="ai_invocations")
    op.drop_table("ai_invocations")
