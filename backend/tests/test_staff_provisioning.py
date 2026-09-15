"""No privileged credential may be seeded, and staff ops must be safe."""

import io

import pytest

from app import manage_users, seed_data
from app.auth import verify_password
from app.models import CompetencyProfile, Student, Teacher, TeacherScoreReview, User
from app.services.serializers import dumps_json


def _students(db, count: int = 2) -> list[Student]:
    rows = []
    for index in range(count):
        student = Student(
            name=f"学生{index + 1}",
            student_no=f"S{index + 1:06d}",
            class_name="测试班",
            current_stage="stage_1_basic_recognition",
        )
        db.add(student)
        db.flush()
        db.add(
            CompetencyProfile(
                student_id=student.id,
                medical_knowledge=60,
                key_information=60,
                differential_diagnosis=60,
                evidence_integration=60,
                clinical_decision=60,
                evidence_based_medicine=60,
                learning_engagement=60,
            )
        )
        rows.append(student)
    db.commit()
    return rows


def test_seed_never_creates_privileged_accounts(db_factory, monkeypatch):
    monkeypatch.delenv("SEED_DEMO_STUDENT_ACCOUNTS", raising=False)
    db = db_factory()
    _students(db)

    seed_data._seed_default_users(db)
    db.commit()

    roles = {user.role for user in db.query(User).all()}
    assert "teacher" not in roles
    assert "admin" not in roles
    usernames = {user.username for user in db.query(User).all()}
    assert usernames == {"student1", "student2"}
    # The teacher *record* is still seeded so course data can reference it.
    assert db.query(Teacher).count() == 1
    db.close()


def test_seed_demo_logins_can_be_disabled(db_factory, monkeypatch):
    monkeypatch.setenv("SEED_DEMO_STUDENT_ACCOUNTS", "false")
    db = db_factory()
    _students(db)

    seed_data._seed_default_users(db)
    db.commit()

    assert db.query(User).count() == 0
    assert db.query(Teacher).count() == 1
    db.close()


def test_seed_demo_password_is_overridable(db_factory, monkeypatch):
    monkeypatch.setenv("SEED_DEMO_STUDENT_PASSWORD", "demo-password-x")
    db = db_factory()
    _students(db, count=1)

    seed_data._seed_default_users(db)
    db.commit()
    user = db.query(User).filter(User.username == "student1").one()
    assert verify_password("demo-password-x", user.password_hash)
    db.close()


@pytest.fixture
def ops(db_factory, monkeypatch):
    """Point manage_users at the test database."""

    from sqlalchemy.orm import sessionmaker

    db = db_factory()
    engine = db.get_bind()
    db.close()
    testing_session = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(manage_users, "SessionLocal", testing_session)
    return testing_session


def _run(monkeypatch, argv: list[str], stdin: str = "", capsys=None) -> str:
    monkeypatch.setattr("sys.argv", ["manage_users", *argv])
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    manage_users.main()
    return capsys.readouterr().out if capsys else ""


def test_audit_accounts_flags_risky_leftovers(ops, monkeypatch, capsys):
    db = ops()
    students = _students(db, count=1)
    teacher = Teacher(name="T", teacher_no="T1", department="Med")
    db.add(teacher)
    db.flush()
    db.add(User(username="teacher", password_hash="x", role="teacher", teacher_id=teacher.id))
    db.add(User(username="admin", password_hash="x", role="admin"))
    db.add(User(username="audit_admin_1", password_hash="x", role="admin"))
    db.add(User(username="dup", password_hash="x", role="student", student_id=students[0].id))
    db.add(
        User(
            username=f"student{students[0].id}",
            password_hash="x",
            role="student",
            student_id=students[0].id,
        )
    )
    db.commit()
    db.close()

    output = _run(monkeypatch, ["audit-accounts"], capsys=capsys)
    assert "legacy-default-name" in output
    assert "unlinked-admin" in output
    assert "duplicate-student-login" in output
    # Account listing must never include password material.
    assert "password_hash" not in output
    assert "$2b$" not in output


def test_rotate_password_reads_stdin_and_never_prints_it(ops, monkeypatch, capsys):
    db = ops()
    db.add(User(username="teacher", password_hash="old-hash", role="teacher"))
    db.commit()
    db.close()

    output = _run(monkeypatch, ["rotate-password", "teacher"], stdin="new-secret-123\n", capsys=capsys)
    assert "new-secret-123" not in output
    assert "Rotated password for teacher" in output

    db = ops()
    user = db.query(User).filter(User.username == "teacher").one()
    assert verify_password("new-secret-123", user.password_hash)
    db.close()


def test_rotate_password_rejects_short_secrets(ops, monkeypatch):
    db = ops()
    db.add(User(username="teacher", password_hash="old-hash", role="teacher"))
    db.commit()
    db.close()
    with pytest.raises(SystemExit):
        _run(monkeypatch, ["rotate-password", "teacher"], stdin="short\n")


def test_delete_user_refuses_referenced_accounts(ops, monkeypatch):
    db = ops()
    user = User(username="reviewer", password_hash="x", role="teacher")
    db.add(user)
    db.flush()
    db.add(
        TeacherScoreReview(
            evidence_event_id=1,
            reviewer_user_id=user.id,
            comment="review",
            ai_score=1,
            teacher_score=1,
            agreement_delta=0,
            confirmed_dimensions_json=dumps_json({}),
        )
    )
    db.commit()
    db.close()

    with pytest.raises(SystemExit) as error:
        _run(monkeypatch, ["delete-user", "reviewer"])
    assert "Refusing to delete" in str(error.value)

    db = ops()
    assert db.query(User).filter(User.username == "reviewer").count() == 1
    db.close()


def test_delete_user_refuses_the_last_admin(ops, monkeypatch):
    db = ops()
    db.add(User(username="only-admin", password_hash="x", role="admin"))
    db.commit()
    db.close()
    with pytest.raises(SystemExit) as error:
        _run(monkeypatch, ["delete-user", "only-admin"])
    assert "last administrator" in str(error.value)


def test_delete_user_removes_unreferenced_admin(ops, monkeypatch, capsys):
    db = ops()
    db.add(User(username="keeper", password_hash="x", role="admin"))
    db.add(User(username="leftover", password_hash="x", role="admin"))
    db.commit()
    db.close()

    output = _run(monkeypatch, ["delete-user", "leftover"], capsys=capsys)
    assert "Deleted leftover" in output
    db = ops()
    assert db.query(User).filter(User.username == "leftover").count() == 0
    assert db.query(User).filter(User.username == "keeper").count() == 1
    db.close()
