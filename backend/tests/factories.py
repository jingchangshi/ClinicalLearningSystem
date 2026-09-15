"""Seed helpers so each test can build exactly the rows it needs."""

from app.auth import hash_password
from app.models import (
    Case,
    ClinicalSkill,
    CompetencyProfile,
    GuidelineDocument,
    KnowledgeUnit,
    SPCase,
    Student,
    User,
)
from app.services.serializers import dumps_json

ANSWER_TEXTS = {
    "key_information": "发热、皮疹、ANA阳性、蛋白尿，需评估器官受累。",
    "initial_diagnosis": "考虑系统性红斑狼疮，依据症状、抗体与器官受累。",
    "differential_diagnosis": "需排除感染、AOSD、HLH、淋巴瘤与其他结缔组织病。",
    "examination": "补充补体、抗dsDNA、尿蛋白定量与肺功能评估活动度。",
    "treatment": "激素联合免疫抑制剂，治疗前感染筛查，随访监测不良反应。",
}


def make_case(db, title: str = "SLE基础病例", diagnosis: str = "系统性红斑狼疮") -> Case:
    case = Case(
        title=title,
        disease_category="SLE",
        difficulty="基础",
        learning_objectives=dumps_json(["关键信息提取", "鉴别诊断"]),
        chief_complaint="发热伴皮疹",
        history="反复发热、面部皮疹、关节痛。",
        physical_exam="面部蝶形红斑。",
        lab_results="ANA阳性，补体降低，蛋白尿。",
        imaging="胸部CT未见明显异常。",
        standard_diagnosis=diagnosis,
        differential_diagnosis=dumps_json(["感染", "淋巴瘤"]),
        treatment_plan="激素联合免疫抑制剂，感染筛查后随访。",
        rubric=dumps_json({"medical_knowledge": "诊断依据"}),
    )
    db.add(case)
    db.flush()
    return case


def make_student(db, name: str = "测试学生", username: str | None = None) -> tuple[Student, User | None]:
    student = Student(
        name=name,
        student_no=f"T{db.query(Student).count() + 1:06d}",
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
    user = None
    if username:
        user = User(
            username=username,
            password_hash=hash_password("secret1"),
            role="student",
            student_id=student.id,
        )
        db.add(user)
    db.flush()
    return student, user


def make_catalog(db) -> None:
    """The minimum other modules the adaptive pathway reads from."""

    db.add(
        KnowledgeUnit(
            title="SLE核心知识",
            category="基础",
            level="基础",
            learning_objectives=dumps_json(["识别核心表现"]),
            content="内容",
            key_points=dumps_json(["要点"]),
            quiz_items=dumps_json([]),
            related_case_ids=dumps_json([]),
        )
    )
    db.add(
        ClinicalSkill(
            title="关节查体",
            category="查体",
            difficulty="基础",
            indication="关节痛",
            contraindication="无",
            steps=dumps_json([]),
            common_errors=dumps_json([]),
            scoring_rubric=dumps_json({}),
        )
    )
    db.add(
        GuidelineDocument(
            title="EULAR SLE 推荐",
            organization="EULAR",
            year=2023,
            disease_category="SLE",
            source_type="指南",
            summary="摘要",
            recommendations=dumps_json([]),
            pico_examples=dumps_json([]),
        )
    )
    db.add(
        SPCase(
            title="SLE问诊",
            disease_category="SLE",
            difficulty="基础",
            patient_profile=dumps_json({"name": "王女士"}),
            opening_statement="医生，我最近总发热。",
            hidden_history=dumps_json({"发热": "反复发热两周"}),
            emotional_style="焦虑",
            expected_tasks=dumps_json(["问诊"]),
            scoring_rubric=dumps_json({}),
        )
    )
    db.flush()
