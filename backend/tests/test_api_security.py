from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.auth import hash_password
import pytest

from app.models import Case, CaseSession, CompetencyProfile, LearningEvidenceEvent, Score, Student, Teacher, TeacherScoreReview, User
from app.routes import teacher as teacher_routes
from app.routes.teacher import ReviewCreate
from app.services.serializers import dumps_json


def test_public_registration_and_student_case_redaction(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    db = TestingSession()
    db.add(Case(
        title="Test case", disease_category="test", difficulty="basic",
        learning_objectives=dumps_json(["reason"]), chief_complaint="fever", history="history",
        physical_exam="exam", lab_results="labs", imaging="imaging", standard_diagnosis="secret diagnosis",
        differential_diagnosis=dumps_json(["secret differential"]), treatment_plan="secret treatment",
        rubric=dumps_json({"secret": "rubric"}),
    ))
    db.commit()
    db.close()

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert client.post("/api/auth/register", json={"username": "learner", "password": "secret1", "role": "student"}).status_code == 200
            assert client.post("/api/auth/register", json={"username": "teacher", "password": "secret1", "role": "teacher"}).status_code == 422
            assert client.post("/api/auth/register", json={"username": "admin", "password": "secret1", "role": "admin"}).status_code == 422
            started = client.post("/api/sessions/start", json={"case_id": 1})
            assert started.status_code == 200
            response = client.get(f"/api/sessions/{started.json()['id']}")
            assert response.status_code == 200
            body = response.json()
            serialized = str(body)
            for hidden_value in ("standard_diagnosis", "differential_diagnosis", "treatment_plan", "rubric", "secret diagnosis", "secret treatment"):
                assert hidden_value not in serialized
            case_response = client.get("/api/cases/1")
            assert case_response.status_code == 200
            assert "standard_diagnosis" not in case_response.json()
    finally:
        app.dependency_overrides.clear()


def test_teacher_review_rolls_back_when_projection_fails(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'rollback.db'}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    db = TestingSession()
    try:
        student = Student(name="Learner", student_no="S001", class_name="Test", current_stage="stage_1_basic_recognition")
        db.add(student)
        db.flush()
        db.add(CompetencyProfile(student_id=student.id, medical_knowledge=60, key_information=60, differential_diagnosis=60, evidence_integration=60, clinical_decision=60, evidence_based_medicine=60, learning_engagement=60))
        case = Case(title="Case", disease_category="test", difficulty="basic", learning_objectives="[]", chief_complaint="x", history="x", physical_exam="x", lab_results="x", imaging="x", standard_diagnosis="x", differential_diagnosis="[]", treatment_plan="x", rubric="{}")
        db.add(case)
        db.flush()
        session = CaseSession(student_id=student.id, case_id=case.id, status="completed")
        db.add(session)
        db.flush()
        score = Score(session_id=session.id, total_score=70, medical_knowledge=70, key_information=70, differential_diagnosis=70, evidence_integration=70, clinical_decision=70, evidence_based_medicine=70, feedback="x", strengths="x", weaknesses="x", ai_score=70)
        db.add(score)
        updates = {key: {"before": 60, "after": 63, "module_score": 70} for key in ("medical_knowledge", "key_information", "differential_diagnosis", "evidence_integration", "clinical_decision", "evidence_based_medicine")}
        event = LearningEvidenceEvent(student_id=student.id, module_type="case", module_id=None, session_id=session.id, event_type="case_session_scored", source_table="case_sessions", source_id=session.id, score=70, competency_updates_json=dumps_json(updates), evidence_payload_json="{}")
        teacher = Teacher(name="Teacher", teacher_no="T001", department="Medicine")
        db.add_all([event, teacher])
        db.flush()
        reviewer = User(username="teacher", password_hash="hash", role="teacher", teacher_id=teacher.id)
        db.add(reviewer)
        db.commit()

        monkeypatch.setattr(teacher_routes, "reproject_competencies", lambda *_args: (_ for _ in ()).throw(RuntimeError("projection failed")))
        payload = ReviewCreate(evidence_event_id=event.id, confirmed_dimensions={key: 60 for key in updates}, comment="test rollback")
        with pytest.raises(RuntimeError, match="projection failed"):
            teacher_routes.create_score_review(payload, db, reviewer)
        db.expire_all()
        assert db.query(TeacherScoreReview).count() == 0
        assert db.get(Score, score.id).teacher_confirmed_score is None
    finally:
        db.close()


def test_teacher_review_reprojects_from_authoritative_score(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'review.db'}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    db = TestingSession()
    db.add(Case(
        title="Review case", disease_category="test", difficulty="basic",
        learning_objectives=dumps_json(["reason"]), chief_complaint="fever", history="history",
        physical_exam="exam", lab_results="labs", imaging="imaging", standard_diagnosis="SLE",
        differential_diagnosis=dumps_json(["infection"]), treatment_plan="monitor", rubric=dumps_json({}),
    ))
    teacher = Teacher(name="Teacher", teacher_no="T001", department="Medicine")
    db.add(teacher)
    db.flush()
    db.add(User(username="teacher", password_hash=hash_password("secret1"), role="teacher", teacher_id=teacher.id))
    db.commit()
    db.close()

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as student_client:
            assert student_client.post("/api/auth/register", json={"username": "learner", "password": "secret1", "role": "student"}).status_code == 200
            session_id = student_client.post("/api/sessions/start", json={"case_id": 1}).json()["id"]
            assert student_client.post(f"/api/sessions/{session_id}/answers", json={"step": "reasoning", "answer_text": "fever rash ANA"}).status_code == 200
            assert student_client.post(f"/api/sessions/{session_id}/submit").status_code == 200
            assert student_client.get("/api/teacher/reviewable-evidence").status_code == 403

            db = TestingSession()
            event = db.query(LearningEvidenceEvent).filter(LearningEvidenceEvent.source_id == session_id).one()
            student_id = event.student_id
            before = db.get(User, 2).student.competency_profile.medical_knowledge
            db.close()

            with TestClient(app) as teacher_client:
                assert teacher_client.post("/api/auth/login", json={"username": "teacher", "password": "secret1"}).status_code == 200
                reviewable = teacher_client.get("/api/teacher/reviewable-evidence")
                assert reviewable.status_code == 200
                assert reviewable.json()[0]["evidence_event_id"] == event.id
                rejected = teacher_client.post("/api/teacher/reviews", json={"evidence_event_id": event.id, "confirmed_dimensions": {"medical_knowledge": 101}, "comment": "invalid"})
                assert rejected.status_code == 422
                response = teacher_client.post("/api/teacher/reviews", json={
                    "evidence_event_id": event.id,
                    "confirmed_dimensions": {
                        "medical_knowledge": 0, "key_information": 0, "differential_diagnosis": 0,
                        "evidence_integration": 0, "clinical_decision": 0, "evidence_based_medicine": 0,
                    },
                    "comment": "Evidence was incomplete.",
                    "ai_score": 100,
                    "teacher_score": 100,
                })
                assert response.status_code == 200
                assert response.json()["teacher_score"] == 0
                assert response.json()["ai_score"] != 100

            result = student_client.get(f"/api/sessions/{session_id}/result")
            assert result.status_code == 200
            assert result.json()["score"]["teacher_confirmed_score"] == 0

            db = TestingSession()
            after = db.get(User, 2).student.competency_profile.medical_knowledge
            assert after < before
            db.close()
    finally:
        app.dependency_overrides.clear()
