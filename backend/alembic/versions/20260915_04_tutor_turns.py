"""Persist step-level Socratic tutor conversations."""

from alembic import op
import sqlalchemy as sa

revision = "20260915_04"
down_revision = "20260915_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tutor_turns" in inspector.get_table_names():
        return
    op.create_table(
        "tutor_turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("case_sessions.id"), nullable=False),
        sa.Column("step", sa.String(100), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("tutor_state_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("session_id", "step", "turn_index", name="uq_tutor_turns_session_step_index"),
    )


def downgrade() -> None:
    op.drop_table("tutor_turns")
