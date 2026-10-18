"""A batch enrolled before any training has students with no CompetencyProfile.

The 49-student study enrolls a whole seven-student batch before D2/D3 training, so a
``Student`` without a ``CompetencyProfile`` row is a normal state, not an error. The
teacher surfaces used to raise AttributeError on it (500 on /api/teacher/dashboard and
the student learning-profile route). These tests pin the fixed behaviour: the page
renders, the learner is marked as having no profile yet, and no weakness is invented
for them.
"""
from app.models import CompetencyProfile, Student
from tests.factories import make_case, make_catalog, make_student
from tests.test_presentation_surfaces import _login


def _student_without_profile(db, name="待训练学生") -> int:
    """A student who has not trained yet: the factory profile is removed."""
    student, _ = make_student(db, name=name)
    db.query(CompetencyProfile).filter_by(student_id=student.id).delete()
    db.flush()
    return student.id


def test_dashboard_renders_a_student_who_has_not_trained_yet(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student_id = _student_without_profile(db)
    db.commit()
    db.close()

    _login(client, db_factory, username="teacher1", role="teacher")
    r = client.get("/api/teacher/dashboard")
    assert r.status_code == 200, r.text
    payload = r.json()
    row = next(item for item in payload["students"] if item["id"] == student_id)
    assert row["has_profile"] is False
    assert row["recent_score"] is None
    # No measured weakness is claimed for a learner with no evidence at all.
    assert row["weakest_ability"] == "尚无训练数据"
    assert row["recommended_training"] == "完成首次病例训练后生成建议"
    # The class-level aggregates stay honest too: nobody has a profile, so they are zero.
    assert payload["student_count"] == 1
    assert payload["class_competency"]["medical_knowledge"] == 0


def test_a_profileless_student_still_gets_a_learning_profile_page(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student_id = _student_without_profile(db)
    db.commit()
    db.close()

    _login(client, db_factory, username="teacher1", role="teacher")
    r = client.get(f"/api/teacher/students/{student_id}/learning-profile")
    assert r.status_code == 200, r.text
    assert r.json()["competency"]["has_profile"] is False


def test_a_trained_student_is_unchanged_by_the_guard(db_factory, client):
    """The guard must not alter the normal path: a real profile still reports its weakest dimension."""
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="已训练学生")
    profile = db.query(CompetencyProfile).filter_by(student_id=student.id).one()
    profile.differential_diagnosis = 30  # the clear weak point
    db.commit()
    student_id = student.id
    db.close()

    _login(client, db_factory, username="teacher1", role="teacher")
    payload = client.get("/api/teacher/dashboard").json()
    row = next(item for item in payload["students"] if item["id"] == student_id)
    assert row["has_profile"] is True
    assert row["weakest_ability"] == "鉴别诊断"
    assert row["recommended_training"] == "发热皮疹鉴别诊断训练"
    assert payload["class_competency"]["differential_diagnosis"] == 30


def test_serialize_profile_marks_absence_and_keeps_the_same_keys():
    from app.services.serializers import ALL_COMPETENCIES, serialize_profile
    empty = serialize_profile(None)
    assert empty["has_profile"] is False and empty["updated_at"] is None
    assert all(empty[key] == 0 for key in ALL_COMPETENCIES)
    assert empty["learning_engagement"] == 0
    assert {row["dimension"] for row in empty["chart_data"]}  # chart shapes stay renderable
    assert len(empty["expanded_chart_data"]) == len(ALL_COMPETENCIES)
