"""Assessment hardening: versions, drafts, adjudication, final scores, audit, research design tables.

Idempotent like the rest of the chain: a database built by ``create_all`` (fresh
install) already has the final shape and every step below is skipped. Existing
SQLite tables are rebuilt in batch mode because SQLite cannot drop or replace
constraints in place.

New tables are created from the current declarative definitions with
``checkfirst`` (the convention ``20260915_01`` already uses); the altered tables
are spelled out explicitly.
"""
import hashlib
import json

from alembic import op
import sqlalchemy as sa

revision = "20261018_09"
down_revision = "20261018_08"
branch_labels = None
depends_on = None

NEW_TABLES = ("assessment_form_reviewers", "assessment_answer_revisions", "assessment_events",
              "assessment_adjudications", "assessment_dataset_locks", "assessment_final_scores",
              "assessment_audit_log", "research_codes", "study_cohorts", "study_enrollments", "study_allocations")
LEGACY_WEIGHTS = {"medical_knowledge": 10, "key_information": 20, "differential_diagnosis": 25,
                  "evidence_integration": 15, "clinical_decision": 20, "evidence_based_medicine": 10}


def _cols(inspector, table):
    return {c["name"] for c in inspector.get_columns(table)}


def _index_names(inspector, table):
    return {i["name"] for i in inspector.get_indexes(table)}


def _unique_names(inspector, table):
    return {u["name"] for u in inspector.get_unique_constraints(table)}


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    from app.database import Base
    import app.assessment_models  # noqa: F401
    import app.models  # noqa: F401
    wanted = [Base.metadata.tables[n] for n in NEW_TABLES]
    Base.metadata.create_all(bind=bind, tables=wanted, checkfirst=True)

    # --- assessment_forms: (code) unique -> (code, version) unique; versioning + provenance columns
    cols = _cols(insp, "assessment_forms")
    if "content_sha256" not in cols:
        # 20261018_08 declared UNIQUE(code) unnamed, which SQLite batch mode cannot drop by
        # name; describe the table without it and let the rebuild omit the constraint.
        old = sa.Table("assessment_forms", sa.MetaData(),
                       sa.Column("id", sa.Integer, primary_key=True), sa.Column("code", sa.String(60), nullable=False),
                       sa.Column("version", sa.Integer, nullable=False), sa.Column("title", sa.String(200), nullable=False),
                       sa.Column("stages_json", sa.Text, nullable=False), sa.Column("key_json", sa.Text, nullable=False),
                       sa.Column("rubric_json", sa.Text, nullable=False),
                       sa.Column("review_status", sa.String(30), nullable=False),
                       sa.Column("created_at", sa.DateTime, nullable=False))
        with op.batch_alter_table("assessment_forms", copy_from=old, recreate="always") as b:
            b.add_column(sa.Column("author_user_id", sa.Integer, sa.ForeignKey("users.id", name="fk_author_user_id")))
            b.add_column(sa.Column("content_sha256", sa.String(64)))
            b.add_column(sa.Column("supersedes_form_id", sa.Integer, sa.ForeignKey("assessment_forms.id", name="fk_supersedes_form_id")))
            b.add_column(sa.Column("published_at", sa.DateTime))
            b.add_column(sa.Column("published_by_user_id", sa.Integer, sa.ForeignKey("users.id", name="fk_published_by_user_id")))
            b.create_unique_constraint("uq_assess_form_code_version", ["code", "version"])
        for row in bind.execute(sa.text("select id,title,stages_json,key_json,rubric_json from assessment_forms")):
            payload = json.dumps({"title": row.title, "stages": json.loads(row.stages_json),
                                  "answer_key": json.loads(row.key_json), "rubric": json.loads(row.rubric_json)},
                                 ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            bind.execute(sa.text("update assessment_forms set content_sha256=:h where id=:i"),
                         {"h": hashlib.sha256(payload.encode()).hexdigest(), "i": row.id})
        # Historic reviews were made against the content as it stood; bind them to it.
    if "form_content_sha256" not in _cols(insp, "assessment_form_reviews"):
        op.add_column("assessment_form_reviews", sa.Column("form_content_sha256", sa.String(64)))
        bind.execute(sa.text("update assessment_form_reviews set form_content_sha256="
                             "(select content_sha256 from assessment_forms f where f.id=assessment_form_reviews.form_id)"))

    # --- assessment_sittings: partial unique (live attempt) + lifecycle columns
    if "data_origin" not in _cols(insp, "assessment_sittings"):
        with op.batch_alter_table("assessment_sittings", recreate="always") as b:
            b.add_column(sa.Column("data_origin", sa.String(20), nullable=False, server_default="pilot_test"))
            b.add_column(sa.Column("attempt_no", sa.Integer, nullable=False, server_default="1"))
            b.add_column(sa.Column("retake_of_id", sa.Integer, sa.ForeignKey("assessment_sittings.id", name="fk_retake_of_id")))
            b.add_column(sa.Column("form_order", sa.String(1)))
            b.add_column(sa.Column("adjudicator_user_id", sa.Integer, sa.ForeignKey("users.id", name="fk_adjudicator_user_id")))
            b.add_column(sa.Column("blinding_risk", sa.String(40), nullable=False,
                                   server_default="UNVERIFIED_NO_COHORT_ROSTER"))
            b.add_column(sa.Column("started_at", sa.DateTime))
            b.add_column(sa.Column("last_saved_at", sa.DateTime))
            b.add_column(sa.Column("extended_until", sa.DateTime))
            b.add_column(sa.Column("closed_reason", sa.String(30)))
            b.add_column(sa.Column("voided_at", sa.DateTime))
            b.add_column(sa.Column("void_reason", sa.Text))
            b.add_column(sa.Column("allocation_id", sa.Integer, sa.ForeignKey("study_allocations.id", name="fk_allocation_id")))
            b.add_column(sa.Column("created_at", sa.DateTime))
            b.drop_constraint("uq_assess_student_timepoint", type_="unique")
        bind.execute(sa.text("update assessment_sittings set created_at=coalesce(window_start, current_timestamp)"))
    insp = sa.inspect(bind)
    if "uq_assess_live_student_timepoint" not in _index_names(insp, "assessment_sittings"):
        op.create_index("uq_assess_live_student_timepoint", "assessment_sittings", ["student_id", "timepoint"],
                        unique=True, sqlite_where=sa.text("status != 'voided'"))

    # --- assessment_answers
    if "answer_sha256" not in _cols(insp, "assessment_answers"):
        op.add_column("assessment_answers", sa.Column("answer_sha256", sa.String(64)))
        for row in bind.execute(sa.text("select id,answer_text from assessment_answers")):
            bind.execute(sa.text("update assessment_answers set answer_sha256=:h where id=:i"),
                         {"h": hashlib.sha256(row.answer_text.encode()).hexdigest(), "i": row.id})

    # --- assessment_reviews: partial unique (live review) + scoring provenance
    if "rater_slot" not in _cols(insp, "assessment_reviews"):
        with op.batch_alter_table("assessment_reviews", recreate="always") as b:
            b.add_column(sa.Column("rater_slot", sa.String(1)))
            b.add_column(sa.Column("rubric_version", sa.String(80)))
            b.add_column(sa.Column("weights_json", sa.Text))
            b.add_column(sa.Column("rationale", sa.Text))
            b.add_column(sa.Column("voided_at", sa.DateTime))
            b.add_column(sa.Column("voided_by_user_id", sa.Integer, sa.ForeignKey("users.id", name="fk_voided_by_user_id")))
            b.add_column(sa.Column("void_reason", sa.Text))
            b.drop_constraint("uq_assess_independent_rater", type_="unique")
        # Rows written before this revision used weights hard-coded in Python; say so.
        bind.execute(sa.text("update assessment_reviews set rater_slot=(select case when s.rater_a_id="
                             "assessment_reviews.rater_user_id then 'A' else 'B' end from assessment_sittings s "
                             "where s.id=assessment_reviews.sitting_id), rubric_version='LEGACY-HARDCODED-STUDY-WEIGHTS', "
                             "weights_json=:w"), {"w": json.dumps(LEGACY_WEIGHTS)})
    insp = sa.inspect(bind)
    if "uq_assess_live_rater" not in _index_names(insp, "assessment_reviews"):
        op.create_index("uq_assess_live_rater", "assessment_reviews", ["sitting_id", "rater_user_id"], unique=True,
                        sqlite_where=sa.text("voided_at IS NULL"))


def downgrade():
    bind = op.get_bind()
    voided = bind.execute(sa.text("select count(*) from assessment_sittings where status='voided'")).scalar()
    voided_reviews = bind.execute(sa.text("select count(*) from assessment_reviews where voided_at is not null")).scalar()
    versions = bind.execute(sa.text("select count(*) from assessment_forms where version>1")).scalar()
    if voided or voided_reviews or versions:
        raise RuntimeError("Cannot downgrade: voided attempts/reviews or form versions >1 exist and would violate the "
                           "older uniqueness rules. Export and resolve them first.")
    op.drop_index("uq_assess_live_rater", table_name="assessment_reviews")
    with op.batch_alter_table("assessment_reviews", recreate="always") as b:
        for name in ("void_reason", "voided_by_user_id", "voided_at", "rationale", "weights_json", "rubric_version", "rater_slot"):
            b.drop_column(name)
        b.create_unique_constraint("uq_assess_independent_rater", ["sitting_id", "rater_user_id"])
    with op.batch_alter_table("assessment_answers", recreate="always") as b:
        b.drop_column("answer_sha256")
    op.drop_index("uq_assess_live_student_timepoint", table_name="assessment_sittings")
    with op.batch_alter_table("assessment_sittings", recreate="always") as b:
        for name in ("created_at", "allocation_id", "void_reason", "voided_at", "closed_reason", "extended_until",
                     "last_saved_at", "started_at", "blinding_risk", "adjudicator_user_id", "form_order",
                     "retake_of_id", "attempt_no", "data_origin"):
            b.drop_column(name)
        b.create_unique_constraint("uq_assess_student_timepoint", ["student_id", "timepoint"])
    with op.batch_alter_table("assessment_form_reviews", recreate="always") as b:
        b.drop_column("form_content_sha256")
    with op.batch_alter_table("assessment_forms", recreate="always") as b:
        for name in ("published_by_user_id", "published_at", "supersedes_form_id", "content_sha256", "author_user_id"):
            b.drop_column(name)
        b.drop_constraint("uq_assess_form_code_version", type_="unique")
        b.create_unique_constraint("uq_assessment_forms_code", ["code"])
    for name in reversed(NEW_TABLES):
        op.drop_table(name)
