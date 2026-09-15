#!/usr/bin/env python3
"""Rebuild the ClinPath demo teaching dataset for the course-application video.

Why this exists
---------------
The public database accumulated months of E2E / debugging traffic: one student
with 160 case sessions, 140 learning-evidence events on a single day, a student
named ``test``, and scores that repeat to one decimal place. None of that is a
teaching story, and none of it may be hand-edited row by row on the server.

What it does
------------
It rebuilds the *learning records* of the four demo students only:

1. take a timestamped SQLite backup (``scripts/backup_db.sh``);
2. audit the database and refuse to touch anything that is not recognisably the
   seeded demo cohort;
3. delete only the synthetic learning records of those four students;
4. reset their competency profiles to a declared baseline;
5. replay a fixed plan of learning activities **through the real route code**
   (knowledge quiz, skill steps, case answers, tutor turns, guideline PICO, SP
   interview), so every session / answer / tutor turn / score / evidence /
   recommendation / audit row is produced by the same code the product runs;
6. re-stamp the created rows onto the plan's dates — the dataset is explicitly
   synthetic, and a spread of dates is the whole point;
7. recompute pathway stage and AI enrichment.

What it will never do
---------------------
* No student outside the demo cohort is read for modification, and the script
  aborts if it finds one it cannot classify.
* No ``drop_all``, no ``seed_data --reset``, no re-created accounts, no password
  change, no touched catalog (cases, knowledge units, guidelines, SP cases).
* AI scores are real model calls with real provenance. If no provider is
  configured the script stops instead of writing rule output as if it were AI.

Usage
-----
    python scripts/prepare_presentation_data.py --dry-run     # default, no writes
    python scripts/prepare_presentation_data.py --apply
    python scripts/prepare_presentation_data.py --apply --skip-enrichment
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
DEFAULT_DB_PATH = BACKEND_DIR / "clinical_learning.db"
OPERATOR_ENV = Path.home() / ".config" / "clinpath" / "backend.env"

# The replayed plan issues more requests per minute than the public abuse limits
# allow, so the limits are widened before the app reads them at import time.
for _bucket in ("SUBMIT", "COACH", "SP_MESSAGE", "LOGIN", "REGISTER", "AI_PROBE"):
    os.environ.setdefault(f"RATE_LIMIT_{_bucket}_PER_HOUR", "10000")
os.environ.setdefault("CLINPATH_ENV", "production")


def _load_operator_env() -> None:
    """Read the operator's mode-600 backend env without ever printing values.

    ``CLINPATH_SKIP_OPERATOR_ENV=1`` keeps an automated run (CI, the test suite)
    from picking up a developer's real credentials.
    """

    if os.environ.get("CLINPATH_SKIP_OPERATOR_ENV") == "1" or not OPERATOR_ENV.exists():
        return
    for line in OPERATOR_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_operator_env()
sys.path.insert(0, str(BACKEND_DIR))


DEMO_CLASS_ONE = "临床医学2023级1班"
DEMO_CLASS_TWO = "临床医学2023级2班"


@dataclass(frozen=True)
class DemoStudent:
    student_no: str
    name: str
    class_name: str
    baseline: dict[str, float]
    # Written over ``student_no`` when the stored value is a registration
    # artifact (``REGS000004``); the linked login is never touched.
    display_student_no: str | None = None


@dataclass(frozen=True)
class Activity:
    """One learning event on the demo timeline."""

    student_no: str
    kind: str
    when: str
    catalog_id: int | None = None
    answers: dict[str, str] | None = None
    quiz_ratio: float = 0.0
    skill_complete: bool = True
    tutor_steps: tuple[tuple[str, str], ...] = ()
    pico: dict[str, str] | None = None
    sp_messages: tuple[str, ...] = ()
    sp_diagnosis: str = ""
    note: str = ""


# --- The demo cohort -------------------------------------------------------

DEMO_STUDENTS = (
    DemoStudent(
        student_no="202601001",
        name="李明",
        class_name=DEMO_CLASS_ONE,
        baseline={
            "medical_knowledge": 60,
            "key_information": 66,
            "differential_diagnosis": 50,
            "evidence_integration": 54,
            "clinical_decision": 52,
            "evidence_based_medicine": 45,
            "skill_operation": 60,
            "communication": 68,
            "humanistic_care": 70,
            "learning_engagement": 58,
        },
    ),
    DemoStudent(
        student_no="202601002",
        name="王佳",
        class_name=DEMO_CLASS_ONE,
        baseline={
            "medical_knowledge": 78,
            "key_information": 76,
            "differential_diagnosis": 72,
            "evidence_integration": 71,
            "clinical_decision": 58,
            "evidence_based_medicine": 55,
            "skill_operation": 78,
            "communication": 78,
            "humanistic_care": 80,
            "learning_engagement": 74,
        },
    ),
    DemoStudent(
        student_no="202601003",
        name="陈晨",
        class_name=DEMO_CLASS_TWO,
        baseline={
            "medical_knowledge": 82,
            "key_information": 80,
            "differential_diagnosis": 76,
            "evidence_integration": 74,
            "clinical_decision": 74,
            "evidence_based_medicine": 68,
            "skill_operation": 70,
            "communication": 72,
            "humanistic_care": 74,
            "learning_engagement": 66,
        },
    ),
    # The `test` account created by E2E registration traffic is the same demo
    # student; only the display profile is normalised, the login is untouched.
    DemoStudent(
        student_no="REGS000004",
        name="赵敏",
        class_name=DEMO_CLASS_TWO,
        baseline={
            "medical_knowledge": 61,
            "key_information": 60,
            "differential_diagnosis": 55,
            "evidence_integration": 52,
            "clinical_decision": 56,
            "evidence_based_medicine": 44,
            "skill_operation": 64,
            "communication": 66,
            "humanistic_care": 70,
            "learning_engagement": 56,
        },
        display_student_no="202601004",
    ),
)


# --- Answer sets of deliberately different quality -------------------------

ANSWERS_DEVELOPING = {
    "key_information": "患者发热、皮疹、关节痛，ANA阳性。",
    "initial_diagnosis": "考虑系统性红斑狼疮。",
    "differential_diagnosis": "需要排除感染。",
    "examination": "完善补体和抗dsDNA检查。",
    "treatment": "使用激素治疗。",
}

ANSWERS_SOLID = {
    "key_information": (
        "青年女性，反复发热伴面部红斑、关节痛和脱发；实验室提示ANA阳性、抗dsDNA阳性、"
        "补体C3下降、白细胞减少，尿蛋白2+提示肾脏受累。胸片和肾脏超声未见异常。"
    ),
    "initial_diagnosis": (
        "考虑活动性系统性红斑狼疮，合并狼疮性肾炎可能。依据是多系统受累（皮肤、关节、血液、肾脏）"
        "加上抗dsDNA阳性和补体下降。"
    ),
    "differential_diagnosis": (
        "需要排除感染（结核、病毒）、淋巴瘤、嗜血细胞综合征、成人Still病、"
        "混合性结缔组织病和药物性狼疮。"
    ),
    "examination": (
        "复查补体、抗dsDNA、24小时尿蛋白定量和肾功能，评估肾活检指征；"
        "加做抗磷脂抗体、Coombs试验和胸部CT。"
    ),
    "treatment": (
        "以羟氯喹为基础治疗，根据器官受累程度予激素联合免疫抑制剂；"
        "治疗前筛查HBV、HCV、结核和HIV，随访血常规、肝肾功能和感染指标。"
    ),
}

ANSWERS_STRONG = {
    "key_information": (
        "青年女性，病程3年，近5天高热伴面部蝶形红斑、光过敏、口腔溃疡、脱发、双腕压痛和双下肢水肿；"
        "实验室：ANA 1:640、抗dsDNA阳性、补体C3/C4下降、白细胞和血小板减少、尿蛋白2+；"
        "胸片与肾脏超声正常，无关节畸形。"
    ),
    "initial_diagnosis": (
        "活动性系统性红斑狼疮（SLEDAI高活动度），合并狼疮性肾炎。"
        "依据EULAR/ACR分类标准：ANA阳性为入围条件，叠加皮肤、关节、血液系统、肾脏和免疫学共5项以上；"
        "蛋白尿加低补体支持肾脏受累和疾病活动。"
    ),
    "differential_diagnosis": (
        "优先排除感染（结核、CMV/EBV、细菌性心内膜炎）与淋巴瘤；"
        "其次为成人Still病、混合性结缔组织病、药物性狼疮和嗜血细胞综合征。"
        "支持SLE的证据是多系统受累、抗dsDNA阳性和低补体；不支持感染的是PCT轻度升高但无感染灶，"
        "且免疫指标高度特异。"
    ),
    "examination": (
        "完善24小时尿蛋白定量、尿沉渣、肾功能和抗磷脂抗体，安排肾活检明确ISN/RPS分型；"
        "治疗前完成HBV/HCV/HIV/结核筛查、血常规、肝肾功能、血糖和骨密度评估，并做眼底和心电图基线。"
    ),
    "treatment": (
        "羟氯喹为基础治疗；按ISN/RPS分型和疾病活动度选择激素联合吗替麦考酚酯或环磷酰胺，"
        "重症肾病考虑诱导缓解方案。同时给予羟氯喹眼底监测、骨质疏松预防、疫苗和妊娠规划教育；"
        "每1-3个月随访补体、抗dsDNA、尿蛋白和肾功能，按EULAR 2023推荐和KDIGO狼疮肾炎指南调整方案。"
    ),
}

ANSWER_SETS = {
    "developing": ANSWERS_DEVELOPING,
    "solid": ANSWERS_SOLID,
    "strong": ANSWERS_STRONG,
}


# --- The timeline ----------------------------------------------------------
#
# 李明's line is the one the video follows: basics -> skill -> three case
# sessions that visibly improve -> guideline work -> a next task. The other
# three students carry different stages, weaknesses, modules and dates, so the
# class heatmap and the research export describe a class, not one test run.

ACTIVITIES: tuple[Activity, ...] = (
    Activity("202601001", "knowledge", "2026-08-24 19:20", catalog_id=1, quiz_ratio=0.7, note="李明补基础"),
    Activity("202601002", "knowledge", "2026-08-25 18:30", catalog_id=1, quiz_ratio=0.9, note="王佳基础较好"),
    Activity("202601001", "skill", "2026-08-27 20:05", catalog_id=1, note="李明关节查体"),
    Activity("202601003", "knowledge", "2026-08-27 17:00", catalog_id=3, quiz_ratio=0.95, note="陈晨治疗决策单元"),
    Activity(
        "202601001",
        "case",
        "2026-08-31 19:40",
        catalog_id=1,
        answers=ANSWER_SETS["developing"],
        tutor_steps=(("key_information", "患者有发热、皮疹和关节痛，ANA阳性，我认为要先排除感染。"),),
        note="李明第一次病例训练",
    ),
    Activity("202601002", "skill", "2026-09-01 19:10", catalog_id=2, note="王佳膝关节穿刺"),
    Activity("202601003", "guideline", "2026-09-02 19:30", catalog_id=2, pico={
        "clinical_question": "ANCA相关血管炎诱导缓解期，糖皮质激素联合利妥昔单抗是否优于环磷酰胺？",
        "pico": "P：ANCA相关血管炎诱导缓解期患者；I：利妥昔单抗联合糖皮质激素；C：环磷酰胺联合糖皮质激素；O：缓解率与复发率。",
        "answer": (
            "2021年ANCA相关血管炎管理建议将利妥昔单抗与环磷酰胺并列为诱导缓解方案，"
            "对复发或生育需求患者优先考虑利妥昔单抗；需同时评估感染风险和维持治疗方案。"
        ),
    }, note="陈晨指南循证训练"),
    Activity("202601001", "knowledge", "2026-09-03 20:10", catalog_id=2, quiz_ratio=0.85, note="李明鉴别诊断单元"),
    Activity("REGS000004", "knowledge", "2026-09-04 21:00", catalog_id=2, quiz_ratio=0.6, note="赵敏刚刚起步"),
    Activity("202601002", "case", "2026-09-05 20:15", catalog_id=1, answers=ANSWER_SETS["solid"], note="王佳SLE病例"),
    Activity(
        "202601001",
        "case",
        "2026-09-07 15:55",
        catalog_id=8,
        answers=ANSWER_SETS["solid"],
        tutor_steps=(
            ("key_information", "补体下降和白细胞减少提示疾病活动，我把它们和蛋白尿一起作为关键信息。"),
            ("differential_diagnosis", "我用「最可能—需排除—不能漏」排序：先排感染和淋巴瘤，再考虑Still病。"),
        ),
        note="李明第二次病例训练（有导师追问）",
    ),
    Activity(
        "202601002",
        "sp",
        "2026-09-08 20:00",
        catalog_id=1,
        sp_messages=(
            "您好，我是今天接诊的医生。请问您这次主要是哪里不舒服？",
            "发热大概持续多久了？最高到多少度？",
            "除了发热，关节痛和皮疹是什么时候开始的？有没有口腔溃疡或者脱发？",
        ),
        sp_diagnosis="考虑活动性系统性红斑狼疮，需评估肾脏受累并排除感染。",
        note="王佳SP问诊",
    ),
    Activity(
        "202601003",
        "knowledge",
        "2026-09-09 18:40",
        catalog_id=1,
        quiz_ratio=1.0,
        note="陈晨巩固基础知识",
    ),
    Activity(
        "202601001",
        "case",
        "2026-09-10 14:21",
        catalog_id=10,
        answers=ANSWER_SETS["strong"],
        tutor_steps=(
            ("key_information", "我把蛋白尿和低补体放在最优先，因为它们同时提示肾脏受累和疾病活动。"),
            ("treatment", "我引用EULAR 2023和KDIGO说明肾活检分型决定诱导方案，并把感染筛查放在用药前。"),
        ),
        note="李明第三次病例训练（能力提升）",
    ),
    Activity(
        "REGS000004",
        "case",
        "2026-09-11 19:15",
        catalog_id=1,
        answers=ANSWER_SETS["developing"],
        tutor_steps=(("key_information", "我先想到发热和皮疹，但还没想清楚怎么排除感染。"),),
        note="赵敏第一次病例训练",
    ),
    Activity(
        "202601001",
        "guideline",
        "2026-09-12 16:30",
        catalog_id=1,
        pico={
            "clinical_question": "活动性狼疮肾炎患者，在激素基础上加用吗替麦考酚酯是否优于环磷酰胺？",
            "pico": "P：活动性狼疮肾炎患者；I：吗替麦考酚酯；C：环磷酰胺；O：完全缓解率与不良事件。",
            "answer": (
                "2023年EULAR推荐提示吗替麦考酚酯与低剂量环磷酰胺在诱导缓解中疗效相近，"
                "但吗替麦考酚酯在生育保护和感染风险方面更有优势，需按ISN/RPS分型个体化选择。"
            ),
        },
        note="李明循证学习",
    ),
)


# ---------------------------------------------------------------------------
# Pre-change audit
# ---------------------------------------------------------------------------


def audit(db) -> dict:
    from app.models import (
        CaseSession,
        LearningEvidenceEvent,
        LearningRecommendation,
        Student,
        TutorTurn,
        User,
    )

    # After the first run the stored student number is the normalised one.
    known = set()
    for entry in DEMO_STUDENTS:
        known.add(entry.student_no)
        if entry.display_student_no:
            known.add(entry.display_student_no)
    students = db.query(Student).all()
    unrecognised = [student for student in students if student.student_no not in known]
    return {
        "students": [
            {
                "id": student.id,
                "name": student.name,
                "student_no": student.student_no,
                "class_name": student.class_name,
                "current_stage": student.current_stage,
                "case_sessions": db.query(CaseSession)
                .filter(CaseSession.student_id == student.id)
                .count(),
                "evidence_events": db.query(LearningEvidenceEvent)
                .filter(LearningEvidenceEvent.student_id == student.id)
                .count(),
                "in_demo_cohort": student.student_no in known,
            }
            for student in students
        ],
        "users": db.query(User).count(),
        "tutor_turns": db.query(TutorTurn).count(),
        "recommendations": db.query(LearningRecommendation).count(),
        "unrecognised_students": [student.student_no for student in unrecognised],
    }


def _print_audit(report: dict) -> None:
    print("== 数据库审计 ==")
    for row in report["students"]:
        marker = "演示学生" if row["in_demo_cohort"] else "!! 非演示学生 !!"
        print(
            f'  [{marker}] id={row["id"]} {row["name"]} ({row["student_no"]}) '
            f'{row["class_name"]} {row["current_stage"]} '
            f'病例训练={row["case_sessions"]} 学习证据={row["evidence_events"]}'
        )
    print(
        f'  账号总数={report["users"]} 导师对话轮次={report["tutor_turns"]} '
        f'推荐记录={report["recommendations"]}'
    )
    if report["unrecognised_students"]:
        print(f'  !! 非演示学生：{", ".join(report["unrecognised_students"])}')


def plan_summary() -> str:
    lines = ["== 即将生成的演示数据集 =="]
    for entry in DEMO_STUDENTS:
        activities = [activity for activity in ACTIVITIES if activity.student_no == entry.student_no]
        modules = sorted({activity.kind for activity in activities})
        dates = sorted({activity.when[:10] for activity in activities})
        lines.append(
            f"  {entry.name}（{entry.student_no}，{entry.class_name}）："
            f"{len(activities)} 次训练，模块 {'/'.join(modules) or '无'}，"
            f"日期 {dates[0] if dates else '-'} 至 {dates[-1] if dates else '-'}"
        )
    all_dates = sorted({activity.when[:10] for activity in ACTIVITIES})
    all_modules = sorted({activity.kind for activity in ACTIVITIES})
    lines.append(
        f"  合计 {len(ACTIVITIES)} 次训练，{len(all_modules)} 个模块（{'/'.join(all_modules)}），"
        f"{len(all_dates)} 个不同日期（{all_dates[0]} ~ {all_dates[-1]}）"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

REPLAYED_TABLES = (
    "case_sessions",
    "student_answers",
    "tutor_turns",
    "scores",
    "knowledge_progress",
    "skill_sessions",
    "guideline_learning_sessions",
    "sp_sessions",
    "learning_evidence_events",
    "learning_recommendations",
)


def _models():
    """Imported lazily so ``--help`` works without a configured database."""

    from app import models

    return models


def _snapshot_max_ids(db) -> dict[str, int]:
    snapshot = {}
    for name in REPLAYED_TABLES:
        model = getattr(_models(), _model_name(name))
        row = db.query(model).order_by(model.id.desc()).first()
        snapshot[name] = row.id if row else 0
    return snapshot


def _model_name(table: str) -> str:
    names = {
        "case_sessions": "CaseSession",
        "student_answers": "StudentAnswer",
        "tutor_turns": "TutorTurn",
        "scores": "Score",
        "knowledge_progress": "KnowledgeProgress",
        "skill_sessions": "SkillSession",
        "guideline_learning_sessions": "GuidelineLearningSession",
        "sp_sessions": "SPSession",
        "learning_evidence_events": "LearningEvidenceEvent",
        "learning_recommendations": "LearningRecommendation",
    }
    return names[table]


def _fresh(db, table: str, snapshot: dict[str, int]) -> list:
    """Rows of one table that an activity created since the snapshot."""

    model = getattr(_models(), _model_name(table))
    return db.query(model).filter(model.id > snapshot[table]).all()


def _restamp(db, snapshot: dict[str, int], when: datetime) -> None:
    """Move the rows an activity just created onto the plan's timestamp."""

    for session in _fresh(db, "case_sessions", snapshot):
        session.started_at = when - timedelta(minutes=25)
        if session.completed_at:
            session.completed_at = when
    for index, answer in enumerate(
        sorted(_fresh(db, "student_answers", snapshot), key=lambda row: row.id)
    ):
        answer.created_at = when - timedelta(minutes=22 - index)
        answer.updated_at = answer.created_at
    for index, turn in enumerate(sorted(_fresh(db, "tutor_turns", snapshot), key=lambda row: row.id)):
        turn.created_at = when - timedelta(minutes=18 - index)
    for score in _fresh(db, "scores", snapshot):
        score.created_at = when
    for progress in _fresh(db, "knowledge_progress", snapshot):
        progress.updated_at = when
    for skill in _fresh(db, "skill_sessions", snapshot):
        skill.created_at = when - timedelta(minutes=15)
        if skill.completed_at:
            skill.completed_at = when
    for guideline in _fresh(db, "guideline_learning_sessions", snapshot):
        guideline.created_at = when
    for sp_session in _fresh(db, "sp_sessions", snapshot):
        sp_session.started_at = when - timedelta(minutes=20)
        if sp_session.completed_at:
            sp_session.completed_at = when
    for event in _fresh(db, "learning_evidence_events", snapshot):
        event.created_at = when
    for recommendation in _fresh(db, "learning_recommendations", snapshot):
        recommendation.created_at = when
    db.commit()


def _quiz_answers(db, unit_id: int, ratio: float) -> list[str]:
    from app.models import KnowledgeUnit
    from app.services.serializers import loads_json

    unit = db.get(KnowledgeUnit, unit_id)
    items = loads_json(unit.quiz_items, [])
    answers = []
    for index, item in enumerate(items):
        keywords = [str(keyword) for keyword in item.get("answer_keywords", [])]
        full = (index + 1) / max(1, len(items)) <= ratio
        if full or ratio >= 0.9:
            answers.append("；".join(keywords))
        elif ratio > 0:
            answers.append(keywords[0] if keywords else "")
        else:
            answers.append("")
    return answers


def _skill_steps(db, skill_id: int, complete: bool) -> list[str]:
    from app.models import ClinicalSkill
    from app.services.serializers import loads_json

    skill = db.get(ClinicalSkill, skill_id)
    steps = [str(step) for step in loads_json(skill.steps, [])]
    return steps if complete else steps[: max(1, len(steps) // 2)]


def _demo_user(db, student):
    from app.models import User

    user = db.query(User).filter(User.role == "student", User.student_id == student.id).first()
    if user is None:
        raise SystemExit(
            f"学生 {student.name}（{student.student_no}）没有关联的学生登录账号，脚本不会创建账号。"
        )
    return user


def _run_activity(db, activity: Activity, student) -> tuple[bool, bool]:
    """Replay one activity through the real route functions.

    Returns ``(used_provider, degraded)`` for the run's provenance summary.
    """

    from app.routes.guidelines import PicoSubmitRequest, submit_pico
    from app.routes.knowledge import QuizSubmitRequest, submit_quiz
    from app.routes.sessions import save_answer, start_session, submit_session, tutor_turn
    from app.routes.skills import (
        SkillSessionStartRequest,
        SkillSessionSubmitRequest,
        start_skill_session,
        submit_skill_session,
    )
    from app.routes.sp import (
        SPMessageRequest,
        SPSessionStartRequest,
        SPSubmitRequest,
        send_sp_message,
        start_sp_session,
        submit_sp_session,
    )
    from app.schemas import AnswerCreate, SessionStartRequest, TutorRequest

    user = _demo_user(db, student)
    when = datetime.strptime(activity.when, "%Y-%m-%d %H:%M")
    snapshot = _snapshot_max_ids(db)
    degraded = False

    if activity.kind == "knowledge":
        submit_quiz(
            activity.catalog_id,
            QuizSubmitRequest(
                student_id=student.id,
                answers=_quiz_answers(db, activity.catalog_id, activity.quiz_ratio),
            ),
            db=db,
            user=user,
        )
    elif activity.kind == "skill":
        created = start_skill_session(
            activity.catalog_id,
            SkillSessionStartRequest(student_id=student.id),
            db=db,
            user=user,
        )
        submit_skill_session(
            created["id"],
            SkillSessionSubmitRequest(
                submitted_steps=_skill_steps(db, activity.catalog_id, activity.skill_complete)
            ),
            db=db,
            user=user,
        )
    elif activity.kind == "case":
        created = start_session(
            SessionStartRequest(student_id=student.id, case_id=activity.catalog_id),
            db=db,
            user=user,
        )
        session_id = created["session_id"]
        for step, text in (activity.answers or {}).items():
            save_answer(session_id, AnswerCreate(step=step, answer_text=text), db=db, user=user)
        for step, reply in activity.tutor_steps:
            tutor_turn(session_id, TutorRequest(step=step, message=None), db=db, user=user)
            if reply:
                tutor_turn(session_id, TutorRequest(step=step, message=reply), db=db, user=user)
        response = submit_session(session_id, db=db, user=user)
        degraded = bool(response["summary"]["degraded"])
    elif activity.kind == "guideline":
        submit_pico(
            activity.catalog_id,
            PicoSubmitRequest(student_id=student.id, **(activity.pico or {})),
            db=db,
            user=user,
        )
    elif activity.kind == "sp":
        created = start_sp_session(
            SPSessionStartRequest(student_id=student.id, sp_case_id=activity.catalog_id),
            db=db,
            user=user,
        )
        for message in activity.sp_messages:
            send_sp_message(created["session_id"], SPMessageRequest(message=message), db=db, user=user)
        submit_sp_session(
            created["session_id"],
            SPSubmitRequest(diagnosis_summary=activity.sp_diagnosis),
            db=db,
            user=user,
        )
    else:  # pragma: no cover - ACTIVITIES is a literal tuple
        raise SystemExit(f"未知的学习活动类型：{activity.kind}")

    _restamp(db, snapshot, when)
    print(f"    ok {activity.when} {student.name} {activity.kind} #{activity.catalog_id} {activity.note}")
    return activity.kind in {"case", "guideline", "sp"} or bool(activity.tutor_steps), degraded


def _purge_demo_records(db, student_ids: list[int]) -> dict[str, int]:
    """Remove only the learning records of the demo cohort."""

    from app.models import (
        AIEnrichment,
        AIMessage,
        AIInvocation,
        CaseSession,
        GuidelineLearningSession,
        KnowledgeProgress,
        LearningEvidenceEvent,
        LearningRecommendation,
        Score,
        SPSession,
        SkillSession,
        StudentAnswer,
        TeacherScoreReview,
        TutorTurn,
    )

    session_ids = [
        session_id
        for (session_id,) in db.query(CaseSession.id)
        .filter(CaseSession.student_id.in_(student_ids))
        .all()
    ]
    evidence_ids = [
        event_id
        for (event_id,) in db.query(LearningEvidenceEvent.id)
        .filter(LearningEvidenceEvent.student_id.in_(student_ids))
        .all()
    ]

    counts: dict[str, int] = {}
    if session_ids:
        counts["tutor_turns"] = (
            db.query(TutorTurn)
            .filter(TutorTurn.session_id.in_(session_ids))
            .delete(synchronize_session=False)
        )
        counts["student_answers"] = (
            db.query(StudentAnswer)
            .filter(StudentAnswer.session_id.in_(session_ids))
            .delete(synchronize_session=False)
        )
        counts["ai_messages"] = (
            db.query(AIMessage)
            .filter(AIMessage.session_id.in_(session_ids))
            .delete(synchronize_session=False)
        )
        counts["scores"] = (
            db.query(Score).filter(Score.session_id.in_(session_ids)).delete(synchronize_session=False)
        )
    if evidence_ids:
        counts["teacher_score_reviews"] = (
            db.query(TeacherScoreReview)
            .filter(TeacherScoreReview.evidence_event_id.in_(evidence_ids))
            .delete(synchronize_session=False)
        )
    counts["case_sessions"] = (
        db.query(CaseSession)
        .filter(CaseSession.student_id.in_(student_ids))
        .delete(synchronize_session=False)
    )
    counts["learning_evidence_events"] = (
        db.query(LearningEvidenceEvent)
        .filter(LearningEvidenceEvent.student_id.in_(student_ids))
        .delete(synchronize_session=False)
    )
    counts["learning_recommendations"] = (
        db.query(LearningRecommendation)
        .filter(LearningRecommendation.student_id.in_(student_ids))
        .delete(synchronize_session=False)
    )
    counts["knowledge_progress"] = (
        db.query(KnowledgeProgress)
        .filter(KnowledgeProgress.student_id.in_(student_ids))
        .delete(synchronize_session=False)
    )
    counts["skill_sessions"] = (
        db.query(SkillSession)
        .filter(SkillSession.student_id.in_(student_ids))
        .delete(synchronize_session=False)
    )
    counts["guideline_sessions"] = (
        db.query(GuidelineLearningSession)
        .filter(GuidelineLearningSession.student_id.in_(student_ids))
        .delete(synchronize_session=False)
    )
    counts["sp_sessions"] = (
        db.query(SPSession).filter(SPSession.student_id.in_(student_ids)).delete(synchronize_session=False)
    )
    counts["ai_enrichments"] = (
        db.query(AIEnrichment)
        .filter(AIEnrichment.student_id.in_(student_ids))
        .delete(synchronize_session=False)
    )
    # Audit rows of the records that just disappeared; the replay writes its own.
    audit_query = db.query(AIInvocation).filter(AIInvocation.student_id.in_(student_ids))
    if session_ids:
        audit_query = db.query(AIInvocation).filter(
            AIInvocation.student_id.in_(student_ids) | AIInvocation.session_id.in_(session_ids)
        )
    counts["ai_invocations"] = audit_query.delete(synchronize_session=False)
    db.commit()
    return counts


def _resolve_students(db) -> dict:
    from app.models import Student

    students = {}
    for entry in DEMO_STUDENTS:
        candidates = {entry.student_no}
        if entry.display_student_no:
            candidates.add(entry.display_student_no)
        student = db.query(Student).filter(Student.student_no.in_(candidates)).first()
        if student is None:
            raise SystemExit(f"缺少演示学生 {entry.name}（{entry.student_no}），脚本不会创建账号。")
        students[entry.student_no] = student
    return students


CATALOG_TABLE = {
    "knowledge": "KnowledgeUnit",
    "skill": "ClinicalSkill",
    "case": "Case",
    "guideline": "GuidelineDocument",
    "sp": "SPCase",
}


def preflight(db, students: dict) -> None:
    """Everything the plan needs must exist *before* anything is deleted.

    A missing catalog row half-way through the replay would leave the demo
    dataset partially rebuilt, so this runs first and aborts the whole run.
    """

    problems: list[str] = []
    for entry in DEMO_STUDENTS:
        student = students[entry.student_no]
        try:
            _demo_user(db, student)
        except SystemExit as error:
            problems.append(str(error))
    for activity in ACTIVITIES:
        model = getattr(_models(), CATALOG_TABLE[activity.kind])
        if db.get(model, activity.catalog_id) is None:
            problems.append(
                f"{activity.when} {activity.kind} 引用的目录记录 #{activity.catalog_id} 不存在"
            )
    if problems:
        raise SystemExit("拒绝执行，前置检查未通过：\n  - " + "\n  - ".join(problems))


def apply(db_factory, *, skip_enrichment: bool = False) -> dict:
    from app.models import Case, LearningRecommendation
    from app.services import ai_enrichment
    from app.services.recommendation_service import choose_recommendation, determine_pathway_stage
    from app.services.serializers import serialize_case_summary, serialize_profile

    db = db_factory()
    try:
        report = audit(db)
        if report["unrecognised_students"]:
            raise SystemExit(
                "拒绝执行：数据库中存在脚本无法识别为非演示数据的学生账号 "
                f'({", ".join(report["unrecognised_students"])})。请先确认演示/真实数据边界。'
            )

        students = _resolve_students(db)
        preflight(db, students)
        student_ids = [student.id for student in students.values()]

        print("== 清理旧的合成学习记录 ==")
        for name, count in _purge_demo_records(db, student_ids).items():
            print(f"    -{count:>5}  {name}")

        # Normalise identity and reset the learner model to a declared baseline so
        # the replay produces an explainable starting point.
        for entry in DEMO_STUDENTS:
            student = students[entry.student_no]
            student.name = entry.name
            student.class_name = entry.class_name
            if entry.display_student_no:
                student.student_no = entry.display_student_no
            profile = student.competency_profile
            for key, value in entry.baseline.items():
                setattr(profile, key, float(value))
            profile.updated_at = datetime.utcnow()
            student.current_stage = determine_pathway_stage(entry.baseline)
            print(
                f"    规范化 {entry.name}（{student.student_no}）：{entry.class_name} · "
                f"{student.current_stage}"
            )
        db.commit()

        print("== 重放学习活动（真实路由代码） ==")
        # Enrichment is regenerated deliberately at the end instead of firing a
        # background model call after every event.
        previous_enrichment = os.environ.get("CLINPATH_AI_ENRICHMENT")
        os.environ["CLINPATH_AI_ENRICHMENT"] = "off"
        provider_activities: list[str] = []
        degraded_activities: list[str] = []
        try:
            for activity in ACTIVITIES:
                used_provider, degraded = _run_activity(db, activity, students[activity.student_no])
                if used_provider:
                    provider_activities.append(f"{activity.when} {activity.kind}")
                if degraded:
                    degraded_activities.append(f"{activity.when} {activity.kind}")
        finally:
            if previous_enrichment is None:
                os.environ.pop("CLINPATH_AI_ENRICHMENT", None)
            else:
                os.environ["CLINPATH_AI_ENRICHMENT"] = previous_enrichment

        print("== 重算能力画像 / 阶段 / 推荐 ==")
        cases = [serialize_case_summary(case) for case in db.query(Case).all()]
        stages = {}
        for entry in DEMO_STUDENTS:
            student = students[entry.student_no]
            db.refresh(student)
            profile = serialize_profile(student.competency_profile)
            student.current_stage = determine_pathway_stage(profile)
            stages[entry.name] = student.current_stage
            recommendation = choose_recommendation(profile, [], cases)
            db.add(
                LearningRecommendation(
                    student_id=student.id,
                    recommended_case_id=recommendation["case"]["id"],
                    recommendation_reason=recommendation["reason"],
                    pathway_stage=recommendation["pathway_stage"],
                )
            )
            print(f"    {entry.name} -> {student.current_stage}")
        db.commit()

        if not skip_enrichment:
            from app.routes.teacher import build_teacher_insight_text

            print("== 生成 AI 推荐说明（真实模型调用） ==")
            for entry in DEMO_STUDENTS:
                student = students[entry.student_no]
                ok = ai_enrichment.regenerate_pathway(db, student.id)
                print(f"    {entry.name} 推荐说明：{'已生成' if ok else '跳过（模型不可用）'}")
            insight = ai_enrichment.regenerate_teacher_insight(db, build_teacher_insight_text)
            print(f"    班级洞察：{'已生成' if insight else '跳过（模型不可用）'}")

        return {
            "audit": report,
            "final": audit(db),
            "activities": len(ACTIVITIES),
            "provider_activities": provider_activities,
            "degraded_activities": degraded_activities,
            "stages": stages,
        }
    finally:
        db.close()


def _backup() -> None:
    print("== 备份数据库 ==")
    subprocess.run(["bash", str(REPO_ROOT / "scripts" / "backup_db.sh")], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只打印计划，不写数据库（默认）")
    mode.add_argument("--apply", action="store_true", help="备份后重建演示数据集")
    parser.add_argument("--skip-enrichment", action="store_true", help="跳过最后的 AI 说明生成")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite 数据库路径")
    args = parser.parse_args(argv)

    # The app resolves ``sqlite:///./clinical_learning.db`` against its working
    # directory, so an absolute URL is set here instead of relying on where the
    # operator happened to run the script from.
    db_path = Path(args.db).resolve()
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ.setdefault("CLINPATH_DB_PATH", str(db_path))
    print(f"数据库：{db_path}")

    from app.core.llm_config import LLM_CONFIGURED, LLM_MODEL, LLM_PROVIDER
    from app.database import SessionLocal

    print(plan_summary())
    db = SessionLocal()
    try:
        _print_audit(audit(db))
    finally:
        db.close()

    if not args.apply:
        print("\n== DRY RUN ==")
        print("未写入任何数据。确认无误后使用 --apply 执行。")
        return 0

    provider = f"{LLM_PROVIDER}/{LLM_MODEL}" if LLM_CONFIGURED else "未配置"
    print(f"\nAI 配置：{provider}")
    if not LLM_CONFIGURED:
        print("拒绝执行：演示数据集需要真实的 AI 评分来源。请配置 LLM_API_KEY 后重试。")
        return 2

    _backup()
    outcome = apply(SessionLocal, skip_enrichment=args.skip_enrichment)
    print(f'\n== 完成 == 重放 {outcome["activities"]} 次学习活动')
    if outcome["degraded_activities"]:
        print(f'!! 降级评分的活动：{", ".join(outcome["degraded_activities"])}')
    print(f'   真实 AI 参与的活动：{len(outcome["provider_activities"])} 次')
    _print_audit(outcome["final"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
