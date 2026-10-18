"""Independent assessment tables separated from formative CaseSession/Score."""
from alembic import op
import sqlalchemy as sa
revision="20261018_08"
down_revision="20261018_07"
branch_labels=None
depends_on=None

def upgrade():
    # Idempotent like the rest of the chain: a database built by ``create_all`` (fresh
    # install, or ``seed_data`` before ``upgrade``) already has these tables.
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    _create_missing(existing)


def _create_missing(existing):
    _create(existing,"assessment_forms",
        sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("code",sa.String(60),nullable=False,unique=True),
        sa.Column("version",sa.Integer,nullable=False),
        sa.Column("title",sa.String(200),nullable=False),
        sa.Column("stages_json",sa.Text,nullable=False),
        sa.Column("key_json",sa.Text,nullable=False),
        sa.Column("rubric_json",sa.Text,nullable=False),
        sa.Column("review_status",sa.String(30),nullable=False),
        sa.Column("created_at",sa.DateTime,nullable=False))
    _create(existing,"assessment_form_reviews",
        sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("form_id",sa.Integer,sa.ForeignKey("assessment_forms.id"),nullable=False),
        sa.Column("teacher_user_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False),
        sa.Column("decision",sa.String(20),nullable=False),
        sa.Column("comment",sa.Text,nullable=False),
        sa.Column("reviewed_at",sa.DateTime,nullable=False),
        sa.UniqueConstraint("form_id","teacher_user_id",name="uq_assess_form_teacher"))
    _create(existing,"assessment_sittings",
        sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("student_id",sa.Integer,sa.ForeignKey("students.id"),nullable=False),
        sa.Column("form_id",sa.Integer,sa.ForeignKey("assessment_forms.id"),nullable=False),
        sa.Column("cohort_code",sa.String(70),nullable=False),
        sa.Column("study_group",sa.String(20),nullable=False),
        sa.Column("timepoint",sa.String(5),nullable=False),
        sa.Column("rater_a_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False),
        sa.Column("rater_b_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False),
        sa.Column("blind_code",sa.String(64),nullable=False,unique=True),
        sa.Column("window_start",sa.DateTime,nullable=False),
        sa.Column("window_end",sa.DateTime,nullable=False),
        sa.Column("status",sa.String(20),nullable=False),
        sa.Column("stage_index",sa.Integer,nullable=False),
        sa.Column("submitted_at",sa.DateTime),
        sa.UniqueConstraint("student_id","timepoint",name="uq_assess_student_timepoint"))
    _create(existing,"assessment_answers",
        sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("sitting_id",sa.Integer,sa.ForeignKey("assessment_sittings.id"),nullable=False),
        sa.Column("stage_index",sa.Integer,nullable=False),
        sa.Column("answer_text",sa.Text,nullable=False),
        sa.Column("submitted_at",sa.DateTime,nullable=False),
        sa.UniqueConstraint("sitting_id","stage_index",name="uq_assess_answer_stage"))
    _create(existing,"assessment_reviews",
        sa.Column("id",sa.Integer,primary_key=True),
        sa.Column("sitting_id",sa.Integer,sa.ForeignKey("assessment_sittings.id"),nullable=False),
        sa.Column("rater_user_id",sa.Integer,sa.ForeignKey("users.id"),nullable=False),
        sa.Column("scores_json",sa.Text,nullable=False),
        sa.Column("total_score",sa.Float,nullable=False),
        sa.Column("reviewed_at",sa.DateTime,nullable=False),
        sa.UniqueConstraint("sitting_id","rater_user_id",name="uq_assess_independent_rater"))

def _create(existing,name,*items):
    if name not in existing:
        op.create_table(name,*items)

def downgrade():
    op.drop_table("assessment_reviews")
    op.drop_table("assessment_answers")
    op.drop_table("assessment_sittings")
    op.drop_table("assessment_form_reviews")
    op.drop_table("assessment_forms")
