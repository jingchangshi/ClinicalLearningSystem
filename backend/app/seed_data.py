import argparse

from sqlalchemy import inspect, text

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import (
    Case,
    ClinicalSkill,
    CompetencyProfile,
    GuidelineDocument,
    KnowledgeProgress,
    KnowledgeUnit,
    LearningRecommendation,
    SPCase,
    Student,
    Teacher,
    User,
)
from app.services.recommendation_service import determine_pathway_stage
from app.services.serializers import dumps_json, serialize_case_summary, serialize_profile


def init_db(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _ensure_compatible_schema()

    db = SessionLocal()
    try:
        if db.query(Student).first():
            _seed_learning_modules(db)
            _seed_default_users(db)
            db.commit()
            return

        students = [
            Student(
                name="李明",
                student_no="202601001",
                class_name="临床医学2023级1班",
                current_stage="stage_1_basic_recognition",
            ),
            Student(
                name="王佳",
                student_no="202601002",
                class_name="临床医学2023级1班",
                current_stage="stage_2_differential_reasoning",
            ),
            Student(
                name="陈晨",
                student_no="202601003",
                class_name="临床医学2023级2班",
                current_stage="stage_3_clinical_decision",
            ),
        ]
        db.add_all(students)
        db.flush()

        profiles = [
            CompetencyProfile(
                student_id=students[0].id,
                medical_knowledge=58,
                key_information=62,
                differential_diagnosis=55,
                evidence_integration=60,
                clinical_decision=57,
                evidence_based_medicine=48,
                learning_engagement=66,
            ),
            CompetencyProfile(
                student_id=students[1].id,
                medical_knowledge=72,
                key_information=70,
                differential_diagnosis=58,
                evidence_integration=64,
                clinical_decision=63,
                evidence_based_medicine=52,
                learning_engagement=74,
            ),
            CompetencyProfile(
                student_id=students[2].id,
                medical_knowledge=78,
                key_information=76,
                differential_diagnosis=72,
                evidence_integration=68,
                clinical_decision=59,
                evidence_based_medicine=61,
                learning_engagement=70,
            ),
        ]
        db.add_all(profiles)

        cases = [_make_case(item) for item in _case_payloads()]
        db.add_all(cases)
        db.flush()

        summaries = [serialize_case_summary(case) for case in cases]
        for student, profile in zip(students, profiles):
            profile_dict = serialize_profile(profile)
            stage = determine_pathway_stage(profile_dict)
            student.current_stage = stage
            recommended = _initial_case_for_stage(stage, summaries)
            db.add(
                LearningRecommendation(
                    student_id=student.id,
                    recommended_case_id=recommended["id"],
                    recommendation_reason=f"根据当前能力画像，建议优先完成“{recommended['title']}”。",
                    pathway_stage=stage,
                )
            )
        _seed_learning_modules(db)
        _seed_default_users(db)
        db.commit()
    finally:
        db.close()


def _make_case(payload: dict) -> Case:
    return Case(
        title=payload["title"],
        disease_category=payload["disease_category"],
        difficulty=payload["difficulty"],
        learning_objectives=dumps_json(payload["learning_objectives"]),
        chief_complaint=payload["chief_complaint"],
        history=payload["history"],
        physical_exam=payload["physical_exam"],
        lab_results=payload["lab_results"],
        imaging=payload["imaging"],
        standard_diagnosis=payload["standard_diagnosis"],
        differential_diagnosis=dumps_json(payload["differential_diagnosis"]),
        treatment_plan=payload["treatment_plan"],
        rubric=dumps_json(payload["rubric"]),
    )


def _initial_case_for_stage(stage: str, cases: list[dict]) -> dict:
    preferences = {
        "stage_1_basic_recognition": "SLE基础病例",
        "stage_2_differential_reasoning": "SLE与感染鉴别病例",
        "stage_3_clinical_decision": "ANCA相关血管炎病例",
        "stage_4_evidence_based_learning": "皮肌炎/抗合成酶综合征病例",
    }
    title = preferences.get(stage, "SLE基础病例")
    return next(case for case in cases if title in case["title"])


def _seed_learning_modules(db) -> None:
    if not db.query(KnowledgeUnit).first():
        knowledge_units = [_make_knowledge_unit(item) for item in _knowledge_payloads()]
        db.add_all(knowledge_units)
        db.flush()
        students = db.query(Student).all()
        for student in students:
            for unit in knowledge_units:
                db.add(
                    KnowledgeProgress(
                        student_id=student.id,
                        knowledge_unit_id=unit.id,
                        status="not_started",
                        quiz_score=0,
                        mastery_score=0,
                    )
                )

    if not db.query(ClinicalSkill).first():
        db.add_all([_make_skill(item) for item in _skill_payloads()])

    if not db.query(GuidelineDocument).first():
        db.add_all([_make_guideline(item) for item in _guideline_payloads()])

    if not db.query(SPCase).first():
        db.add_all([_make_sp_case(item) for item in _sp_case_payloads()])


def _seed_default_users(db) -> None:
    teacher = db.query(Teacher).filter(Teacher.teacher_no == "T2026001").first()
    if not teacher:
        teacher = Teacher(name="张老师", teacher_no="T2026001", department="风湿免疫科")
        db.add(teacher)
        db.flush()

    for student in db.query(Student).all():
        username = f"student{student.id}"
        if not db.query(User).filter(User.username == username).first():
            db.add(
                User(
                    username=username,
                    password_hash=hash_password("student123"),
                    role="student",
                    student_id=student.id,
                )
            )

    if not db.query(User).filter(User.username == "teacher").first():
        db.add(
            User(
                username="teacher",
                password_hash=hash_password("teacher123"),
                role="teacher",
                teacher_id=teacher.id,
            )
        )
    if not db.query(User).filter(User.username == "admin").first():
        db.add(
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
            )
        )


def _make_knowledge_unit(payload: dict) -> KnowledgeUnit:
    return KnowledgeUnit(
        title=payload["title"],
        category=payload["category"],
        level=payload["level"],
        learning_objectives=dumps_json(payload["learning_objectives"]),
        content=payload["content"],
        key_points=dumps_json(payload["key_points"]),
        quiz_items=dumps_json(payload["quiz_items"]),
        related_case_ids=dumps_json(payload["related_case_ids"]),
    )


def _make_skill(payload: dict) -> ClinicalSkill:
    return ClinicalSkill(
        title=payload["title"],
        category=payload["category"],
        difficulty=payload["difficulty"],
        indication=payload["indication"],
        contraindication=payload["contraindication"],
        steps=dumps_json(payload["steps"]),
        common_errors=dumps_json(payload["common_errors"]),
        scoring_rubric=dumps_json(payload["scoring_rubric"]),
    )


def _make_guideline(payload: dict) -> GuidelineDocument:
    return GuidelineDocument(
        title=payload["title"],
        organization=payload["organization"],
        year=payload["year"],
        disease_category=payload["disease_category"],
        source_type=payload["source_type"],
        summary=payload["summary"],
        recommendations=dumps_json(payload["recommendations"]),
        pico_examples=dumps_json(payload["pico_examples"]),
    )


def _make_sp_case(payload: dict) -> SPCase:
    return SPCase(
        title=payload["title"],
        disease_category=payload["disease_category"],
        difficulty=payload["difficulty"],
        patient_profile=dumps_json(payload["patient_profile"]),
        opening_statement=payload["opening_statement"],
        hidden_history=dumps_json(payload["hidden_history"]),
        emotional_style=payload["emotional_style"],
        expected_tasks=dumps_json(payload["expected_tasks"]),
        scoring_rubric=dumps_json(payload["scoring_rubric"]),
    )


def _ensure_compatible_schema() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "competency_profiles" not in table_names:
        return
    existing_columns = {column["name"] for column in inspector.get_columns("competency_profiles")}
    required_columns = {
        "skill_operation": "FLOAT DEFAULT 75 NOT NULL",
        "communication": "FLOAT DEFAULT 75 NOT NULL",
        "humanistic_care": "FLOAT DEFAULT 75 NOT NULL",
    }
    missing = [(name, ddl) for name, ddl in required_columns.items() if name not in existing_columns]
    if not missing:
        return
    with engine.begin() as connection:
        for name, ddl in missing:
            connection.execute(text(f"ALTER TABLE competency_profiles ADD COLUMN {name} {ddl}"))


def _knowledge_payloads() -> list[dict]:
    return [
        {
            "title": "SLE核心诊断线索",
            "category": "风湿免疫基础",
            "level": "基础",
            "learning_objectives": ["识别SLE常见临床表现", "理解自身抗体和补体的诊断意义"],
            "content": "系统性红斑狼疮常表现为发热、皮疹、关节痛、血细胞减少、蛋白尿等多系统受累。ANA敏感性高，抗dsDNA与疾病活动度和肾脏受累相关，补体下降提示免疫复合物活动。",
            "key_points": ["多系统受累", "ANA筛查意义", "抗dsDNA与补体变化", "狼疮肾炎风险"],
            "quiz_items": [
                {
                    "question": "SLE患者出现蛋白尿时应重点评估哪类器官受累？",
                    "answer_keywords": ["肾", "狼疮肾炎", "肾脏"],
                },
                {
                    "question": "哪些免疫学指标支持SLE活动？",
                    "answer_keywords": ["抗dsDNA", "补体", "ANA"],
                },
            ],
            "related_case_ids": [1, 2],
        },
        {
            "title": "发热皮疹的鉴别诊断",
            "category": "症状群鉴别",
            "level": "进阶",
            "learning_objectives": ["区分SLE活动、感染、AOSD和HLH", "建立高危鉴别诊断优先级"],
            "content": "发热和皮疹可见于感染、SLE活动、成人Still病、HLH、淋巴瘤和药物反应。鉴别时需结合热型、皮疹特点、血培养、铁蛋白、血细胞变化、器官受累和免疫指标。",
            "key_points": ["感染排除", "AOSD热型", "HLH高铁蛋白", "淋巴瘤警示信号"],
            "quiz_items": [
                {
                    "question": "发热皮疹并铁蛋白显著升高时应考虑哪些诊断？",
                    "answer_keywords": ["成人Still", "AOSD", "HLH"],
                },
                {
                    "question": "免疫抑制治疗前为什么要排除感染？",
                    "answer_keywords": ["感染", "免疫抑制", "风险"],
                },
            ],
            "related_case_ids": [2, 3],
        },
        {
            "title": "免疫抑制治疗安全监测",
            "category": "治疗决策",
            "level": "中等",
            "learning_objectives": ["掌握激素和免疫抑制剂常见风险", "制定感染筛查和随访监测计划"],
            "content": "风湿免疫病治疗常需糖皮质激素、羟氯喹、环磷酰胺、吗替麦考酚酯或生物制剂。治疗前需评估感染、肝肾功能、妊娠风险和疫苗状态，治疗中需监测血常规、肝肾功能、感染和器官活动度。",
            "key_points": ["感染筛查", "肝肾功能监测", "血常规监测", "随访疾病活动度"],
            "quiz_items": [
                {
                    "question": "开始免疫抑制剂前应筛查哪些风险？",
                    "answer_keywords": ["感染", "肝", "肾", "妊娠"],
                },
                {
                    "question": "治疗随访中至少应监测哪些项目？",
                    "answer_keywords": ["血常规", "肝肾功能", "感染", "活动度"],
                },
            ],
            "related_case_ids": [2, 4, 5],
        },
    ]


def _skill_payloads() -> list[dict]:
    return [
        {
            "title": "炎性关节查体",
            "category": "体格检查",
            "difficulty": "基础",
            "indication": "关节痛、晨僵、疑似炎性关节炎或结缔组织病关节受累。",
            "contraindication": "局部严重疼痛、开放伤口或患者无法配合时需调整检查方式。",
            "steps": ["手卫生并解释检查", "视诊关节肿胀和畸形", "触诊压痛和皮温", "评估主动和被动活动度", "记录受累关节分布"],
            "common_errors": ["未比较双侧", "只问疼痛不查肿胀", "遗漏功能受限评估"],
            "scoring_rubric": {
                "preparation": "能说明目的并保护隐私。",
                "sequence": "按视诊、触诊、活动度顺序完成。",
                "safety": "动作轻柔，避免诱发明显疼痛。",
                "documentation": "能记录关节分布和阳性体征。",
            },
        },
        {
            "title": "膝关节穿刺模拟",
            "category": "操作技能",
            "difficulty": "进阶",
            "indication": "关节腔积液需要明确感染、晶体性关节炎或炎症性质。",
            "contraindication": "穿刺部位感染、严重凝血异常或患者拒绝。",
            "steps": ["核对适应证和禁忌证", "取得知情同意", "无菌铺巾和消毒", "定位穿刺点", "抽取关节液并送检", "压迫止血并告知注意事项"],
            "common_errors": ["未评估凝血风险", "无菌观念不足", "未送检细胞计数和培养"],
            "scoring_rubric": {
                "indication": "能说明穿刺目的。",
                "asepsis": "严格无菌操作。",
                "specimen": "能安排常规、生化、培养和晶体检查。",
                "aftercare": "能说明术后观察和并发症警示。",
            },
        },
    ]


def _guideline_payloads() -> list[dict]:
    return [
        {
            "title": "SLE管理建议摘要",
            "organization": "EULAR",
            "year": 2023,
            "disease_category": "系统性红斑狼疮",
            "source_type": "指南摘要",
            "summary": "SLE治疗强调疾病活动度、器官受累和药物风险分层，推荐基础使用羟氯喹并尽量减少长期激素暴露。",
            "recommendations": [
                {"text": "无禁忌时推荐羟氯喹作为基础治疗。", "grade": "强推荐"},
                {"text": "根据器官受累选择糖皮质激素和免疫抑制剂。", "grade": "专家共识"},
            ],
            "pico_examples": [
                {
                    "p": "活动性SLE患者",
                    "i": "羟氯喹联合低剂量激素",
                    "c": "单用激素",
                    "o": "复发率和药物不良反应",
                }
            ],
        },
        {
            "title": "ANCA相关血管炎诱导缓解治疗摘要",
            "organization": "ACR/VF",
            "year": 2021,
            "disease_category": "ANCA相关血管炎",
            "source_type": "指南摘要",
            "summary": "重症ANCA相关血管炎诱导缓解治疗需结合糖皮质激素、利妥昔单抗或环磷酰胺，并同步评估感染风险。",
            "recommendations": [
                {"text": "重症活动期可使用利妥昔单抗或环磷酰胺诱导缓解。", "grade": "有条件推荐"},
                {"text": "治疗前需排除感染并评估肾脏和肺部受累。", "grade": "专家共识"},
            ],
            "pico_examples": [
                {
                    "p": "肺肾受累ANCA相关血管炎患者",
                    "i": "利妥昔单抗",
                    "c": "环磷酰胺",
                    "o": "缓解率、复发率和感染风险",
                }
            ],
        },
    ]


def _sp_case_payloads() -> list[dict]:
    return [
        {
            "title": "发热皮疹青年女性问诊",
            "disease_category": "系统性红斑狼疮",
            "difficulty": "基础",
            "patient_profile": {"age": 21, "gender": "女", "occupation": "大学生"},
            "opening_statement": "医生，我最近总是低烧，脸上起红斑，手指关节也疼。",
            "hidden_history": {
                "duration": "大概一个月，最近一周更明显。",
                "fever": "多是低热，最高大概38度。",
                "pain": "双手小关节疼，早上会僵一会儿。",
                "associated": "最近掉头发，还有口腔溃疡。",
            },
            "emotional_style": "焦虑但愿意配合",
            "expected_tasks": ["问清发热和皮疹特点", "询问关节、肾脏和血液系统线索", "表达共情", "总结初步诊断和检查计划"],
            "scoring_rubric": {
                "history_taking": "覆盖主诉、现病史、系统回顾和危险信号。",
                "communication": "语言清晰，能回应患者焦虑。",
                "reasoning": "能提出SLE及必要鉴别诊断。",
                "humanistic_care": "体现隐私保护和共情。",
            },
        },
        {
            "title": "咳血尿色加深中年男性问诊",
            "disease_category": "ANCA相关血管炎",
            "difficulty": "进阶",
            "patient_profile": {"age": 52, "gender": "男", "occupation": "司机"},
            "opening_statement": "我最近咳嗽有血丝，小便颜色也很深，人很乏力。",
            "hidden_history": {
                "duration": "两周左右，越来越明显。",
                "fever": "偶尔低热，没有寒战。",
                "pain": "没有明显胸痛，但鼻子经常堵和出血。",
                "associated": "尿量变少，腿有点肿。",
            },
            "emotional_style": "担心病情严重，需要解释",
            "expected_tasks": ["识别肺肾综合征", "询问鼻窦和肾脏受累", "评估感染和肿瘤鉴别", "说明紧急检查必要性"],
            "scoring_rubric": {
                "history_taking": "覆盖咯血、尿色、鼻窦、肾脏和全身症状。",
                "communication": "解释病情紧急性但避免恐吓。",
                "reasoning": "能考虑ANCA相关血管炎和感染鉴别。",
                "humanistic_care": "关注患者工作和就医顾虑。",
            },
        },
    ]


def _case_payloads() -> list[dict]:
    common_rubric = {
        "medical_knowledge": "能识别疾病核心诊断标准和器官受累特点。",
        "key_information": "能提取关键阳性、关键阴性和异常检查。",
        "differential_diagnosis": "能覆盖感染、肿瘤、HLH、AOSD、其他结缔组织病等。",
        "evidence_integration": "能解释支持证据、反对证据和证据权重。",
        "clinical_decision": "能制定治疗、筛查、监测和随访计划。",
        "evidence_based_medicine": "能结合指南、推荐级别或文献证据。",
    }
    return [
        {
            "title": "SLE基础病例",
            "disease_category": "系统性红斑狼疮",
            "difficulty": "基础",
            "learning_objectives": ["识别SLE核心表现", "理解分类标准", "制定初始评估计划"],
            "chief_complaint": "女性，21岁，反复发热、面部红斑、关节痛1个月。",
            "history": "近1个月低热，日晒后面颊红斑加重，双手小关节疼痛晨僵，伴脱发和口腔溃疡。",
            "physical_exam": "蝶形红斑，双腕轻压痛，无明显关节畸形，双下肢轻度水肿。",
            "lab_results": "ANA 1:640阳性，抗dsDNA阳性，补体C3下降，尿蛋白2+，白细胞3.0x10^9/L。",
            "imaging": "胸片未见明显异常，肾脏超声大小形态正常。",
            "standard_diagnosis": "系统性红斑狼疮，疑似狼疮肾炎。",
            "differential_diagnosis": ["病毒感染", "类风湿关节炎", "混合性结缔组织病", "药物性狼疮"],
            "treatment_plan": "完善尿蛋白定量、肾功能和肾活检评估；给予羟氯喹，必要时糖皮质激素，评估免疫抑制剂适应证。",
            "rubric": common_rubric,
        },
        {
            "title": "SLE与感染鉴别病例",
            "disease_category": "系统性红斑狼疮/感染鉴别",
            "difficulty": "进阶",
            "learning_objectives": ["区分狼疮活动与感染", "评估免疫抑制风险", "制定安全处理策略"],
            "chief_complaint": "女性，28岁，SLE病史3年，高热、咳嗽、皮疹加重5天。",
            "history": "长期泼尼松和吗替麦考酚酯治疗，近5天体温39.5摄氏度，咳黄痰，面部红斑加重。",
            "physical_exam": "肺部散在湿啰音，面部红斑，口腔溃疡，心率112次/分。",
            "lab_results": "CRP明显升高，PCT升高，补体下降，抗dsDNA升高，淋巴细胞减少。",
            "imaging": "胸部CT示右下肺斑片状浸润影。",
            "standard_diagnosis": "SLE活动合并社区获得性肺炎，需动态鉴别感染与狼疮活动。",
            "differential_diagnosis": ["细菌感染", "机会性感染", "狼疮肺炎", "成人Still病", "HLH"],
            "treatment_plan": "先行感染评估和经验性抗感染，暂停或调整免疫抑制剂；根据培养、炎症指标和狼疮活动指标调整激素。",
            "rubric": common_rubric,
        },
        {
            "title": "成人Still病病例",
            "disease_category": "成人Still病",
            "difficulty": "中等",
            "learning_objectives": ["识别发热皮疹关节痛症状群", "排除感染和肿瘤", "理解铁蛋白意义"],
            "chief_complaint": "男性，26岁，间断高热、咽痛、皮疹和关节痛3周。",
            "history": "每日傍晚高热，热退后皮疹消退，抗生素治疗效果差，伴膝踝关节痛。",
            "physical_exam": "躯干淡红色斑丘疹，咽部充血，肝脾轻度肿大。",
            "lab_results": "白细胞18x10^9/L，中性粒细胞增多，铁蛋白显著升高，ANA阴性，血培养阴性。",
            "imaging": "腹部超声提示轻度肝脾肿大，胸部CT未见明确感染灶。",
            "standard_diagnosis": "成人Still病。",
            "differential_diagnosis": ["感染性疾病", "淋巴瘤", "HLH", "SLE", "药物热"],
            "treatment_plan": "排除感染和肿瘤后给予NSAIDs或糖皮质激素，重症或复发考虑IL-1/IL-6通路生物制剂。",
            "rubric": common_rubric,
        },
        {
            "title": "ANCA相关血管炎病例",
            "disease_category": "ANCA相关血管炎",
            "difficulty": "进阶",
            "learning_objectives": ["识别肺肾综合征", "安排ANCA和组织活检", "制定诱导缓解治疗"],
            "chief_complaint": "男性，52岁，咳血、乏力、尿色加深2周。",
            "history": "近2周鼻塞血涕、咳血丝痰，尿量减少，体重下降。",
            "physical_exam": "贫血貌，双肺散在湿啰音，下肢轻度水肿。",
            "lab_results": "肌酐升高，尿红细胞管型，PR3-ANCA阳性，ESR和CRP升高。",
            "imaging": "胸部CT多发结节和磨玻璃影，部分空洞形成。",
            "standard_diagnosis": "ANCA相关血管炎，倾向肉芽肿性多血管炎，肺肾受累。",
            "differential_diagnosis": ["肺结核", "肺部真菌感染", "抗GBM病", "SLE肾炎", "恶性肿瘤"],
            "treatment_plan": "完善肾活检和感染筛查；重症给予糖皮质激素联合利妥昔单抗或环磷酰胺诱导缓解，监测感染和肾功能。",
            "rubric": common_rubric,
        },
        {
            "title": "皮肌炎/抗合成酶综合征病例",
            "disease_category": "炎性肌病",
            "difficulty": "高阶",
            "learning_objectives": ["识别肌炎皮疹和肺间质病变", "理解肌炎抗体谱", "制定多学科治疗计划"],
            "chief_complaint": "女性，45岁，四肢近端无力、技工手和气促2个月。",
            "history": "上楼困难，双手粗糙皲裂，咳嗽气促进行性加重，伴低热。",
            "physical_exam": "Gottron丘疹，技工手，双肺底Velcro啰音，近端肌力4级。",
            "lab_results": "CK升高，抗Jo-1抗体阳性，ANA阳性，炎症指标升高。",
            "imaging": "胸部HRCT示双下肺网格影和磨玻璃影，符合间质性肺病。",
            "standard_diagnosis": "抗合成酶综合征，皮肌炎伴间质性肺病。",
            "differential_diagnosis": ["特发性肺纤维化", "系统性硬化症", "MCTD", "药物性肌病", "感染性肌炎"],
            "treatment_plan": "评估肺功能和肌炎活动；糖皮质激素联合免疫抑制剂，必要时利妥昔单抗或钙调神经磷酸酶抑制剂，监测感染和肺功能。",
            "rubric": common_rubric,
        },
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables.")
    args = parser.parse_args()
    init_db(reset=args.reset)
