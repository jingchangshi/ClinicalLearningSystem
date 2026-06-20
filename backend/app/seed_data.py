import argparse

from app.database import Base, SessionLocal, engine
from app.models import Case, CompetencyProfile, LearningRecommendation, Student
from app.services.recommendation_service import determine_pathway_stage
from app.services.serializers import dumps_json, serialize_case_summary, serialize_profile


def init_db(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(Student).first():
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
