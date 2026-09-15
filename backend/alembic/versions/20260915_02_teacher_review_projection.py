"""Add teacher-review provenance and database score idempotency."""

from alembic import op
import sqlalchemy as sa

revision = "20260915_02"
down_revision = "20260915_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    review_columns = {column["name"] for column in inspector.get_columns("teacher_score_reviews")}
    if "reviewer_user_id" not in review_columns:
        with op.batch_alter_table("teacher_score_reviews") as batch:
            batch.add_column(sa.Column("reviewer_user_id", sa.Integer(), nullable=True))
            batch.add_column(sa.Column("confirmed_dimensions_json", sa.Text(), nullable=False, server_default="{}"))
            batch.add_column(sa.Column("projector_version", sa.String(50), nullable=False, server_default="v1"))
            batch.create_foreign_key("fk_teacher_score_reviews_reviewer_user", "users", ["reviewer_user_id"], ["id"])
        # Historic reviews predate reviewer identity; keep them auditable while
        # allowing the new endpoint to require an authenticated reviewer.
        with op.batch_alter_table("scores") as batch:
            batch.create_unique_constraint("uq_scores_session_id", ["session_id"])


def downgrade() -> None:
    with op.batch_alter_table("scores") as batch:
        batch.drop_constraint("uq_scores_session_id", type_="unique")
    with op.batch_alter_table("teacher_score_reviews") as batch:
        batch.drop_column("projector_version")
        batch.drop_column("confirmed_dimensions_json")
        batch.drop_column("reviewer_user_id")
