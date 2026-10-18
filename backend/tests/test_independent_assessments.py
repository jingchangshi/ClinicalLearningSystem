"""Independent exam cannot leak into formative pathway or blind reviewers."""
from datetime import datetime, timedelta
from app.auth import hash_password
from app.models import Teacher, User, Score, CaseSession, LearningRecommendation
from app.assessment_models import AssessmentReview, AssessmentSitting
from tests.factories import make_student

STAGES=[{"title":f"阶段{i}","clinical_information":f"信息{i}","question":f"问题{i}"} for i in range(5)]
SCORES={"medical_knowledge":75,"key_information":80,"differential_diagnosis":85,"evidence_integration":70,"clinical_decision":80,"evidence_based_medicine":90}

def setup_users(db):
    st,_=make_student(db,username="exam_student")
    for name in ("reviewer_a","reviewer_b","admin_user"):
        role="admin" if name=="admin_user" else "teacher"
        teacher=Teacher(name=name,teacher_no=name,department="Rheumatology")
        db.add(teacher);db.flush()
        db.add(User(username=name,password_hash=hash_password("secret1"),role=role,teacher_id=teacher.id))
    db.commit()
    return st.id

def login(client,name):
    assert client.post("/api/auth/login",json={"username":name,"password":"secret1"}).status_code==200

def setup_sitting(client,student_id):
    login(client,"admin_user")
    form=client.post("/api/assessments/forms",json={"code":"ASSESS-A-TEST","title":"保密考核","stages":STAGES,
         "answer_key":{"diagnosis":"hidden"},"rubric":{"dimensions":list(SCORES)}})
    assert form.status_code==200,form.text
    form_id=form.json()["id"]
    assert client.post(f"/api/assessments/forms/{form_id}/approve").status_code==409
    for name in ("reviewer_a","reviewer_b"):
        login(client,name)
        assert client.post(f"/api/assessments/forms/{form_id}/review",
            json={"decision":"approve","comment":"真实审核接口测试，非实际医师签名"}).status_code==200
    login(client,"admin_user")
    assert client.post(f"/api/assessments/forms/{form_id}/approve").status_code==200
    from app.database import get_db
    sess=next(iter(client.app.dependency_overrides[get_db]()))
    rater_ids={u.username:u.id for u in sess.query(User).filter(User.username.in_(["reviewer_a","reviewer_b"])).all()}
    sess.close()
    from app.database import get_db
    sess=next(iter(client.app.dependency_overrides[get_db]()))
    rater_ids={u.username:u.id for u in sess.query(User).filter(User.username.in_(["reviewer_a","reviewer_b"])).all()}
    sess.close()
    now=datetime.utcnow()
    sit=client.post("/api/assessments/sittings",json={"student_id":student_id,"form_id":form_id,
         "cohort_code":"cohort1","study_group":"CLINPATH","timepoint":"T0",
         "window_start":(now-timedelta(minutes=1)).isoformat(),"window_end":(now+timedelta(hours=2)).isoformat(),
         "rater_a_id":rater_ids["reviewer_a"],"rater_b_id":rater_ids["reviewer_b"]})
    assert sit.status_code==200,sit.text
    return sit.json()["id"]

def test_independent_exam_stages_and_blind_double_review(db_factory,client):
    db=db_factory();student_id=setup_users(db);db.close()
    sitting_id=setup_sitting(client,student_id)
    login(client,"exam_student")
    assert client.get("/api/assessments/blind/queue").status_code==403
    for index in range(5):
        got=client.get(f"/api/assessments/my/{sitting_id}")
        assert got.status_code==200
        data=got.json();assert data["stage"]["index"]==index
        assert "answer_key" not in str(data) and "diagnosis" not in str(data)
        assert f"信息{index+1}" not in str(data)
        post=client.post(f"/api/assessments/my/{sitting_id}/answer",json={"answer_text":f"独立作答{index}"})
        assert post.status_code==200,post.text
    assert client.post(f"/api/assessments/my/{sitting_id}/submit").status_code==200
    assert client.get(f"/api/assessments/my/{sitting_id}").status_code==409
    db=db_factory()
    assert db.query(Score).count()==0
    assert db.query(CaseSession).count()==0
    assert db.query(LearningRecommendation).count()==0
    db.close()
    for reviewer in ("reviewer_a","reviewer_b"):
        login(client,reviewer)
        queue=client.get("/api/assessments/blind/queue")
        assert queue.status_code==200 and len(queue.json())==1
        code=queue.json()[0]["blind_code"]
        detail=client.get("/api/assessments/blind/"+code).json()
        assert "student_id" not in detail and "timepoint" not in detail and "study_group" not in detail
        assert "cohort_code" not in detail and "scores" not in detail
        result=client.post("/api/assessments/blind/"+code+"/review",json={"scores":SCORES})
        assert result.status_code==200,result.text
        assert client.post("/api/assessments/blind/"+code+"/review",json={"scores":SCORES}).status_code==409
        assert client.get("/api/assessments/admin/export").status_code==403
    db=db_factory();assert db.query(AssessmentReview).count()==2;db.close()
    login(client,"admin_user")
    exported=client.get("/api/assessments/admin/export")
    assert exported.status_code==200
    assert len(exported.json()["records"][0]["scores"])==2

def test_reject_unapproved_form(db_factory,client):
    db=db_factory();student_id=setup_users(db);db.close()
    login(client,"admin_user")
    form=client.post("/api/assessments/forms",json={"code":"PENDING","title":"待审核考核","stages":STAGES,"answer_key":{},"rubric":{}})
    assert form.status_code==200
    now=datetime.utcnow()
    sit=client.post("/api/assessments/sittings",json={"student_id":student_id,"form_id":form.json()["id"],
        "cohort_code":"B2","study_group":"CBL","timepoint":"T1",
        "window_start":now.isoformat(),"window_end":(now+timedelta(hours=1)).isoformat(),
        "rater_a_id":rater_ids["reviewer_a"],"rater_b_id":rater_ids["reviewer_b"]})
    assert sit.status_code==409

def test_cannot_split_one_batch_into_two_study_groups(db_factory,client):
    db=db_factory();first=setup_users(db)
    second,_=make_student(db,name="第二测试学生",username="student_two")
    second_id=second.id
    db.commit()
    raters={u.username:u.id for u in db.query(User).filter(User.username.in_(["reviewer_a","reviewer_b"])).all()}
    db.close()
    sid=setup_sitting(client,first)
    assert sid>0
    login(client,"admin_user")
    from app.database import get_db
    sess=next(iter(client.app.dependency_overrides[get_db]()))
    assignment=sess.query(AssessmentSitting).filter_by(id=sid).one()
    form_id=assignment.form_id
    sess.close()
    now=datetime.utcnow()
    response=client.post("/api/assessments/sittings",json={
        "student_id":second_id,"form_id":form_id,
        "cohort_code":"cohort1","study_group":"CBL","timepoint":"T0",
        "rater_a_id":raters["reviewer_a"],"rater_b_id":raters["reviewer_b"],
        "window_start":(now-timedelta(minutes=1)).isoformat(),
        "window_end":(now+timedelta(hours=2)).isoformat()
    })
    assert response.status_code==409,response.text
