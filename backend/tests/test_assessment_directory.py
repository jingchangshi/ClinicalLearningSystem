"""The two list endpoints the UI needs so staff and forms are chosen by name, not id."""
from app.models import User
from tests.assessment_helpers import SECRET_KEY, build_world, login, stages


def _new_form(client, code):
    return client.post("/api/assessments/forms", json={"code": code, "title": "题本", "stages": stages(),
                                                       "answer_key": SECRET_KEY, "rubric": {}})


def test_staff_directory_is_admin_only_and_never_exposes_credentials(db_factory, client):
    w = build_world(db_factory)
    login(client, "plain_teacher")
    assert client.get("/api/assessments/admin/staff").status_code == 403
    login(client, w.student_users[0])
    assert client.get("/api/assessments/admin/staff").status_code == 403

    login(client, "admin_user")
    r = client.get("/api/assessments/admin/staff")
    assert r.status_code == 200
    rows = r.json()
    assert {row["display_name"] for row in rows} >= {"rev_one", "rev_two", "admin_user"}
    for row in rows:
        # Exactly the four picker fields; nothing that could leak a secret.
        assert set(row) == {"user_id", "display_name", "role", "teacher_no"}
        assert row["role"] in ("teacher", "admin")
    # A teacher has a teacher_no; an admin has no teacher record.
    teacher = next(row for row in rows if row["display_name"] == "rev_one")
    assert teacher["teacher_no"] == "rev_one" and teacher["role"] == "teacher"
    assert next(row for row in rows if row["display_name"] == "admin_user")["teacher_no"] is None
    # Students are not staff and must not appear.
    assert all(row["role"] != "student" for row in rows)
    assert not any("测试学生" in row["display_name"] for row in rows)

    db = db_factory()
    try:
        assert db.query(User).filter(User.role == "student").count() == 1
        # No credential column is ever serialised.
        assert "password" not in r.text and "hash" not in r.text
    finally:
        db.close()


def test_staff_directory_read_is_audited(db_factory, client):
    build_world(db_factory)
    login(client, "admin_user")
    client.get("/api/assessments/admin/staff")
    log = client.get("/api/assessments/admin/audit", params={"action": "staff.read"}).json()
    assert log and log[0]["action"] == "staff.read"


def test_my_forms_lists_only_the_authors_newest_version(db_factory, client):
    build_world(db_factory)
    # rev_one authors two codes; rev_two authors one.
    login(client, "rev_one")
    first = _new_form(client, "MINE-1").json()["id"]
    _new_form(client, "MINE-2")
    login(client, "rev_two")
    other = _new_form(client, "THEIRS-1").json()["id"]
    assert client.get("/api/assessments/forms/mine").json()[0]["code"] == "THEIRS-1"

    login(client, "rev_one")
    mine = client.get("/api/assessments/forms/mine").json()
    assert {row["code"] for row in mine} == {"MINE-1", "MINE-2"}
    assert other not in {row["id"] for row in mine}
    for row in mine:
        assert set(row) == {"id", "code", "version", "title", "review_status", "published_at"}
        assert row["version"] == 1 and row["published_at"] is None

    # A second version replaces the first in the listing; it does not duplicate the code.
    v2 = client.post(f"/api/assessments/forms/{first}/versions",
                     json={"title": "题本 v2", "stages": stages(), "answer_key": SECRET_KEY, "rubric": {}})
    assert v2.status_code == 200, v2.text
    mine = client.get("/api/assessments/forms/mine").json()
    rows = [row for row in mine if row["code"] == "MINE-1"]
    assert len(rows) == 1 and rows[0]["version"] == 2 and rows[0]["id"] == v2.json()["id"]


def test_my_forms_is_refused_for_students_and_anonymous(db_factory, client):
    w = build_world(db_factory)
    assert client.get("/api/assessments/forms/mine").status_code in (401, 403)
    login(client, w.student_users[0])
    assert client.get("/api/assessments/forms/mine").status_code == 403
