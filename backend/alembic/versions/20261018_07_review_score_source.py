"""Record which score a teacher review was compared against.

Historic rows are ambiguous: ``TeacherScoreReview.ai_score`` was written from
``Score.ai_score`` when a model produced a score, and from ``Score.total_score``
when the evaluation had fallen back to rules. A review of a rule-fallback score
therefore *looks* like a review of an AI score, and any agreement statistic
computed from ``ai_score`` mixes two different producers.

This migration adds ``baseline_score`` and ``baseline_source`` so a row says
what it compared against. It does not rewrite history: existing rows keep their
``ai_score`` value and are labelled ``legacy_ambiguous``, because there is no
reliable way to reconstruct the producer after the fact.

Backfill rule for ``baseline_score`` (the number the delta was computed from):
``ai_score`` is always non-null on these rows, so ``baseline_score = ai_score``
and ``agreement_delta`` stays exactly what it was.
"""

from alembic import op
import sqlalchemy as sa

revision = "20261018_07"
down_revision = "20260915_06"
branch_labels = None
depends_on = None

SOURCE_ENUM_NOTE = (
    "ai | rule_fallback | legacy_ambiguous "
    "(ai = a model produced the compared score; rule_fallback = the rule engine did; "
    "legacy_ambiguous = written before this column existed, producer unknown)"
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("teacher_score_reviews")}

    # SQLite cannot relax a NOT NULL in place, so the ai_score change uses a
    # batch rebuild. Historic values are preserved verbatim; only the
    # constraint changes.
    needs_ai_nullable = False
    for column in inspector.get_columns("teacher_score_reviews"):
        if column["name"] == "ai_score" and not column["nullable"]:
            needs_ai_nullable = True

    if needs_ai_nullable or "baseline_score" not in columns or "baseline_source" not in columns:
        with op.batch_alter_table("teacher_score_reviews") as batch:
            if needs_ai_nullable:
                batch.alter_column(
                    "ai_score", existing_type=sa.Float(), nullable=True
                )
            if "baseline_score" not in columns:
                batch.add_column(sa.Column("baseline_score", sa.Float(), nullable=True))
            if "baseline_source" not in columns:
                batch.add_column(
                    sa.Column(
                        "baseline_source",
                        sa.String(30),
                        nullable=False,
                        server_default="legacy_ambiguous",
                    )
                )

    # Existing rows: the compared number was whatever ``ai_score`` held.
    bind.execute(
        sa.text(
            "UPDATE teacher_score_reviews "
            "SET baseline_score = ai_score "
            "WHERE baseline_score IS NULL"
        )
    )
    # Every pre-existing row is ambiguous by construction; make that explicit
    # rather than guessing a producer from the score's shape.
    bind.execute(
        sa.text(
            "UPDATE teacher_score_reviews "
            "SET baseline_source = 'legacy_ambiguous' "
            "WHERE baseline_source IS NULL OR baseline_source = ''"
        )
    )


def downgrade() -> None:
    # A null ai_score cannot survive the old NOT NULL constraint. Backfill it
    # from the honest baseline before narrowing the column again, so the
    # downgrade never loses the number a review was actually about.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE teacher_score_reviews SET ai_score = baseline_score "
            "WHERE ai_score IS NULL AND baseline_score IS NOT NULL"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE teacher_score_reviews SET ai_score = teacher_score "
            "WHERE ai_score IS NULL"
        )
    )
    with op.batch_alter_table("teacher_score_reviews") as batch:
        batch.alter_column("ai_score", existing_type=sa.Float(), nullable=False)
        batch.drop_column("baseline_source")
        batch.drop_column("baseline_score")
