"""Cached AI enrichment text (explanation wording only, never a decision input)."""

from alembic import op
import sqlalchemy as sa

revision = "20260915_06"
down_revision = "20260915_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "ai_enrichments" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "ai_enrichments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("cache_key", sa.String(100), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("source_fingerprint", sa.String(120), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("kind", "cache_key", name="uq_ai_enrichments_kind_key"),
    )
    op.create_index("ix_ai_enrichments_kind", "ai_enrichments", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_ai_enrichments_kind", table_name="ai_enrichments")
    op.drop_table("ai_enrichments")
