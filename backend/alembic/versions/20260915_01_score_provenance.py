"""Add immutable scoring provenance and teacher confirmation fields."""

from alembic import op
import sqlalchemy as sa

revision = "20260915_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New installations receive the full declarative schema. Existing installs
    # retain their data and receive only the provenance columns below.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "scores" not in inspector.get_table_names():
        from app.database import Base
        import app.models  # noqa: F401
        Base.metadata.create_all(bind=bind)
        return
    with op.batch_alter_table("scores") as batch:
        batch.add_column(sa.Column("evaluation_mode", sa.String(30), nullable=False, server_default="rule_fallback"))
        batch.add_column(sa.Column("provider", sa.String(50), nullable=True))
        batch.add_column(sa.Column("model", sa.String(100), nullable=True))
        batch.add_column(sa.Column("prompt_version", sa.String(50), nullable=False, server_default="case-evaluation-v1"))
        batch.add_column(sa.Column("rubric_version", sa.String(50), nullable=False, server_default="case-rubric-v1"))
        batch.add_column(sa.Column("evaluator_version", sa.String(50), nullable=False, server_default="hybrid-v1"))
        batch.add_column(sa.Column("rule_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("ai_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("evaluation_detail_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("teacher_confirmed_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("teacher_override_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scores") as batch:
        for name in ("teacher_override_reason", "teacher_confirmed_score", "evaluation_detail_json", "degraded", "ai_score", "rule_score", "evaluator_version", "rubric_version", "prompt_version", "model", "provider", "evaluation_mode"):
            batch.drop_column(name)
