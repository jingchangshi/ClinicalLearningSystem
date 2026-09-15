"""Make one logical answer per (session, step) and track its revision time.

Historic rows could contain several answers for the same step. The newest
non-empty answer per (session_id, step) is kept; nothing is dropped silently
without first collapsing the duplicates onto that row.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260915_03"
down_revision = "20260915_02"
branch_labels = None
depends_on = None

DEDUPE_SQL = """
DELETE FROM student_answers
WHERE id NOT IN (
    SELECT COALESCE(
        MAX(CASE WHEN TRIM(answer_text) <> '' THEN id END),
        MAX(id)
    )
    FROM student_answers
    GROUP BY session_id, step
)
"""


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("student_answers")}

    before = bind.execute(sa.text("SELECT COUNT(*) FROM student_answers")).scalar() or 0
    duplicates = (
        bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM ("
                "  SELECT session_id, step FROM student_answers"
                "  GROUP BY session_id, step HAVING COUNT(*) > 1)"
            )
        ).scalar()
        or 0
    )
    if duplicates:
        bind.execute(sa.text(DEDUPE_SQL))
        after = bind.execute(sa.text("SELECT COUNT(*) FROM student_answers")).scalar() or 0
        print(f"[migration] collapsed {before - after} duplicate answer row(s) across {duplicates} (session, step) group(s)")

    if "updated_at" not in columns:
        with op.batch_alter_table("student_answers") as batch:
            batch.add_column(
                sa.Column(
                    "updated_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                )
            )
        bind.execute(sa.text("UPDATE student_answers SET updated_at = created_at"))

    unique_names = {constraint["name"] for constraint in inspector.get_unique_constraints("student_answers")}
    if "uq_student_answers_session_step" not in unique_names:
        with op.batch_alter_table("student_answers") as batch:
            batch.create_unique_constraint(
                "uq_student_answers_session_step", ["session_id", "step"]
            )


def downgrade() -> None:
    with op.batch_alter_table("student_answers") as batch:
        batch.drop_constraint("uq_student_answers_session_step", type_="unique")
        batch.drop_column("updated_at")
