"""The demo-data tool must be repeatable, bounded, and refuse unsafe input.

It rewrites the *learning records* of the seeded demo cohort, so the two things
that matter are: running it twice leaves the same, complete dataset, and it
aborts instead of improvising when the database does not look like the demo.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

from app.models import (
    Case,
    CaseSession,
    ClinicalSkill,
    CompetencyProfile,
    GuidelineDocument,
    KnowledgeUnit,
    LearningEvidenceEvent,
    SPCase,
    Student,
    User,
)
from app.services.serializers import dumps_json

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "prepare_presentation_data.py"


@pytest.fixture
def presentation_module():
    """Import the script without letting it read the developer's real env file."""

    os.environ["CLINPATH_SKIP_OPERATOR_ENV"] = "1"
    spec = importlib.util.spec_from_file_location("prepare_presentation_data", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # ``from __future__ import annotations`` makes dataclass field types strings,
    # and dataclasses looks the module up again while resolving them.
    sys.modules["prepare_presentation_data"] = module
    spec.loader.exec_module(module)
    return module


def _catalog_row(db, model, **kwargs):
    row = model(**kwargs)
    db.add(row)
    db.flush()
    return row


def _seed_catalog(db, presentation_module) -> None:
    """Create exactly the catalog ids the plan references."""

    for index in range(10):
        _catalog_row(
            db,
            Case,
            title=f"演示病例{index + 1}",
            disease_category="系统性红斑狼疮",
            difficulty="基础",
            learning_objectives=dumps_json(["关键信息提取"]),
            chief_complaint="发热伴皮疹",
            history="反复发热、面部皮疹、关节痛。",
            physical_exam="面部蝶形红斑。",
            lab_results="ANA阳性，补体降低，蛋白尿。",
            imaging="胸片未见异常。",
            standard_diagnosis="系统性红斑狼疮",
            differential_diagnosis=dumps_json(["感染"]),
            treatment_plan="激素联合免疫抑制剂。",
            rubric=dumps_json({"medical_knowledge": "诊断依据"}),
        )
    for index in range(3):
        _catalog_row(
            db,
            KnowledgeUnit,
            title=f"知识单元{index + 1}",
            category="基础",
            level="基础",
            learning_objectives=dumps_json(["识别核心表现"]),
            content="内容",
            key_points=dumps_json(["要点"]),
            quiz_items=dumps_json(
                [{"question": "Q", "answer_keywords": ["感染", "免疫抑制", "风险"]}]
            ),
            related_case_ids=dumps_json([]),
        )
    for index in range(2):
        _catalog_row(
            db,
            ClinicalSkill,
            title=f"技能{index + 1}",
            category="查体",
            difficulty="基础",
            indication="关节痛",
            contraindication="无",
            steps=dumps_json(["手卫生并解释检查", "视诊关节肿胀和畸形", "触诊压痛和皮温"]),
            common_errors=dumps_json(["未比较双侧"]),
            scoring_rubric=dumps_json({}),
        )
    for index in range(2):
        _catalog_row(
            db,
            GuidelineDocument,
            title=f"指南{index + 1}",
            organization="EULAR",
            year=2023,
            disease_category="SLE",
            source_type="指南",
            summary="摘要",
            recommendations=dumps_json([]),
            pico_examples=dumps_json([]),
        )
    _catalog_row(
        db,
        SPCase,
        title="SP病例",
        disease_category="SLE",
        difficulty="基础",
        patient_profile=dumps_json({"name": "王女士"}),
        opening_statement="医生，我最近总发热。",
        hidden_history=dumps_json({"duration": "一个月"}),
        emotional_style="焦虑",
        expected_tasks=dumps_json(["问诊"]),
        scoring_rubric=dumps_json({}),
    )
    db.commit()


def _seed_demo_cohort(db, presentation_module) -> None:
    for entry in presentation_module.DEMO_STUDENTS:
        student = Student(
            name=entry.name,
            student_no=entry.student_no,
            class_name=entry.class_name,
            current_stage="stage_1_basic_recognition",
        )
        db.add(student)
        db.flush()
        db.add(
            CompetencyProfile(
                student_id=student.id,
                **{key: float(value) for key, value in entry.baseline.items()},
            )
        )
        db.add(
            User(
                username=f"user{student.id}",
                password_hash="x",
                role="student",
                student_id=student.id,
            )
        )
    db.commit()


def _counts(db) -> dict[str, int]:
    from app.models import GuidelineLearningSession, KnowledgeProgress, Score, SkillSession, SPSession, StudentAnswer, TutorTurn

    return {
        "case_sessions": db.query(CaseSession).count(),
        "answers": db.query(StudentAnswer).count(),
        "tutor_turns": db.query(TutorTurn).count(),
        "scores": db.query(Score).count(),
        "knowledge_progress": db.query(KnowledgeProgress).count(),
        "skill_sessions": db.query(SkillSession).count(),
        "guideline_sessions": db.query(GuidelineLearningSession).count(),
        "sp_sessions": db.query(SPSession).count(),
        "evidence": db.query(LearningEvidenceEvent).count(),
    }


def test_dry_run_plan_is_deterministic(presentation_module):
    first = presentation_module.plan_summary()
    second = presentation_module.plan_summary()

    assert first == second
    assert "李明" in first and "赵敏" in first
    # The plan itself must cover the diversity the demo depends on.
    kinds = {activity.kind for activity in presentation_module.ACTIVITIES}
    assert kinds == {"knowledge", "skill", "case", "guideline", "sp"}
    dates = {activity.when[:10] for activity in presentation_module.ACTIVITIES}
    assert len(dates) >= 3
    assert len({activity.student_no for activity in presentation_module.ACTIVITIES}) >= 3


def test_apply_is_idempotent_and_builds_a_connected_dataset(db_factory, presentation_module, monkeypatch):
    """Running twice must not duplicate, and the second run must not abort."""

    # No provider is configured in the test suite, so scoring takes the honest
    # rule fallback; that is enough to prove the graph is rebuilt consistently.
    plan = presentation_module.ACTIVITIES[:12]
    assert {activity.kind for activity in plan} == {"knowledge", "skill", "case", "guideline", "sp"}
    monkeypatch.setattr(presentation_module, "ACTIVITIES", plan)

    db = db_factory()
    _seed_catalog(db, presentation_module)
    _seed_demo_cohort(db, presentation_module)
    db.close()

    first = presentation_module.apply(db_factory, skip_enrichment=True)
    assert first["activities"] == len(plan)
    db = db_factory()
    first_counts = _counts(db)
    db.close()

    second = presentation_module.apply(db_factory, skip_enrichment=True)
    assert second["activities"] == len(plan)
    db = db_factory()
    second_counts = _counts(db)
    db.close()

    assert first_counts == second_counts, "re-running must rebuild, not accumulate"
    assert second_counts["case_sessions"] >= 3
    assert second_counts["tutor_turns"] >= 4
    assert second_counts["evidence"] == len(plan)

    # Every record still points at a student and a date the plan declared.
    db = db_factory()
    try:
        assert db.query(Student).filter(Student.name == "test").count() == 0
        assert db.query(Student).filter(Student.name == "赵敏").count() == 1
        dates = {str(row.created_at)[:10] for row in db.query(LearningEvidenceEvent).all()}
        assert len(dates) >= 2
    finally:
        db.close()


def test_apply_refuses_a_database_it_cannot_classify(db_factory, presentation_module):
    db = db_factory()
    _seed_catalog(db, presentation_module)
    _seed_demo_cohort(db, presentation_module)
    stranger = Student(
        name="真实学生",
        student_no="202699999",
        class_name="真实班级",
        current_stage="stage_1_basic_recognition",
    )
    db.add(stranger)
    db.commit()
    db.close()

    with pytest.raises(SystemExit) as error:
        presentation_module.apply(db_factory, skip_enrichment=True)

    assert "202699999" in str(error.value)


def test_preflight_blocks_a_missing_catalog_row(db_factory, presentation_module):
    db = db_factory()
    _seed_catalog(db, presentation_module)
    _seed_demo_cohort(db, presentation_module)
    # The demo plan references case #10.
    db.query(Case).filter(Case.id == 10).delete()
    db.commit()
    db.close()

    with pytest.raises(SystemExit) as error:
        presentation_module.apply(db_factory, skip_enrichment=True)

    assert "前置检查未通过" in str(error.value)
