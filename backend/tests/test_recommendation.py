"""Candidate selection must be structural: renaming a case cannot change planning."""

from app.services.catalog_tags import item_tags
from app.services.recommendation_service import (
    apply_constraints,
    choose_recommendation,
    generate_candidates,
    readiness_rank,
    rank_candidates,
)


def _case(case_id: int, title: str, difficulty: str, objectives: list[str]) -> dict:
    return {
        "id": case_id,
        "title": title,
        "disease_category": "SLE",
        "difficulty": difficulty,
        "chief_complaint": "发热伴皮疹",
        "learning_objectives": objectives,
    }


def _profile(weak: str, score: float = 55) -> dict:
    profile = {
        "medical_knowledge": 80,
        "key_information": 80,
        "differential_diagnosis": 80,
        "evidence_integration": 80,
        "clinical_decision": 80,
        "evidence_based_medicine": 80,
    }
    profile[weak] = score
    return profile


WEAK_DIFFERENTIAL = _profile("differential_diagnosis")
WEAK_KNOWLEDGE = _profile("medical_knowledge", 52)

BASIC = _case(1, "病例甲", "基础", ["关键信息提取"])
ADVANCED_DIFFERENTIAL = _case(2, "病例乙", "进阶", ["鉴别诊断与排除逻辑"])
ADVANCED_TREATMENT = _case(3, "病例丙", "进阶", ["治疗方案与监测"])


def test_tags_are_derived_from_structured_fields():
    tags = item_tags("case", ADVANCED_DIFFERENTIAL)
    assert "differential_diagnosis" in tags["abilities"]
    assert tags["difficulty"] == "进阶"
    assert tags["difficulty_rank"] == 2
    assert tags["disease_category"] == "SLE"
    assert tags["prerequisites"] == {"medical_knowledge": 55}


def test_differential_weakness_prefers_a_differential_case():
    picked = choose_recommendation(WEAK_DIFFERENTIAL, [WEAK_DIFFERENTIAL], [BASIC, ADVANCED_DIFFERENTIAL, ADVANCED_TREATMENT])
    assert picked["case"]["id"] == ADVANCED_DIFFERENTIAL["id"]


def test_knowledge_weakness_prefers_basic_material():
    picked = choose_recommendation(WEAK_KNOWLEDGE, [WEAK_KNOWLEDGE], [ADVANCED_TREATMENT, BASIC])
    assert picked["case"]["id"] == BASIC["id"]


def test_renaming_a_case_does_not_change_the_choice():
    renamed = [
        {**ADVANCED_DIFFERENTIAL, "title": "ZZZ 未命名病例"},
        {**ADVANCED_TREATMENT, "title": "AAA 另一个病例"},
        BASIC,
    ]
    original = choose_recommendation(WEAK_DIFFERENTIAL, [WEAK_DIFFERENTIAL], [BASIC, ADVANCED_DIFFERENTIAL, ADVANCED_TREATMENT])
    after = choose_recommendation(WEAK_DIFFERENTIAL, [WEAK_DIFFERENTIAL], renamed)
    assert original["case"]["id"] == after["case"]["id"] == ADVANCED_DIFFERENTIAL["id"]


def test_no_matching_case_still_returns_something_deterministic():
    unrelated = [_case(9, "无关病例", "基础", ["医患沟通"])]
    first = choose_recommendation(WEAK_DIFFERENTIAL, [WEAK_DIFFERENTIAL], unrelated)
    second = choose_recommendation(WEAK_DIFFERENTIAL, [WEAK_DIFFERENTIAL], unrelated)
    assert first["case"]["id"] == second["case"]["id"] == 9


def _activity() -> dict:
    return {
        "cases": [BASIC, ADVANCED_DIFFERENTIAL, ADVANCED_TREATMENT],
        "knowledge_units": [
            {"id": 11, "title": "SLE核心知识", "level": "基础", "category": "基础",
             "learning_objectives": ["识别核心表现"], "key_points": ["诊断标准"]},
            {"id": 12, "title": "发热皮疹鉴别", "level": "进阶", "category": "症状群",
             "learning_objectives": ["鉴别诊断与排除"], "key_points": ["感染鉴别"]},
            {"id": 13, "title": "SLE诊断标准进展", "level": "高阶", "category": "诊断",
             "learning_objectives": ["疾病识别与分类标准"], "key_points": ["ACR/EULAR 标准"]},
        ],
        "clinical_skills": [
            {"id": 21, "title": "关节查体", "difficulty": "基础", "category": "查体",
             "indication": "关节痛评估", "common_errors": ["顺序错误"]},
        ],
        "guidelines": [
            {"id": 31, "title": "EULAR SLE 推荐", "disease_category": "SLE", "source_type": "指南",
             "summary": "治疗推荐与证据等级", "recommendations": [{"text": "激素联合免疫抑制剂", "grade": "A"}]},
        ],
        "sp_cases": [
            {"id": 41, "title": "SLE问诊", "difficulty": "基础", "disease_category": "SLE",
             "expected_tasks": ["问诊", "沟通与共情"], "opening_statement": "医生我发热"},
        ],
    }


def test_candidate_generator_uses_item_tags_not_titles():
    candidates = generate_candidates(["differential_diagnosis"], _activity())
    types = {candidate["type"] for candidate in candidates}
    # Only items whose own content targets differential reasoning qualify.
    assert types == {"case", "knowledge_unit"}
    assert all(candidate["matched_ability"] == "differential_diagnosis" for candidate in candidates)

    # The SP case is offered for the ability its tasks actually target.
    sp_candidates = generate_candidates(["key_information"], _activity())
    assert "sp_case" in {candidate["type"] for candidate in sp_candidates}

    # A renamed case still qualifies, because the tags come from its objectives.
    renamed = _activity()
    renamed["cases"] = [{**ADVANCED_DIFFERENTIAL, "title": "ZZZ"}]
    renamed_candidates = generate_candidates(["differential_diagnosis"], renamed)
    assert any(candidate["id"] == ADVANCED_DIFFERENTIAL["id"] for candidate in renamed_candidates)


def test_constraint_filter_blocks_advanced_material_for_a_weak_learner():
    candidates = generate_candidates(["differential_diagnosis"], _activity())
    weak = _profile("differential_diagnosis", 40)
    strong = _profile("differential_diagnosis", 85)
    weak_allowed = apply_constraints(candidates, weak)
    strong_allowed = apply_constraints(candidates, strong)
    assert all(candidate["tags"]["difficulty_rank"] < 3 for candidate in weak_allowed)
    assert any(candidate["tags"]["difficulty_rank"] >= 2 for candidate in strong_allowed)


def test_ranker_returns_a_shortlist_with_module_diversity():
    weak = _profile("differential_diagnosis", 45)
    ranked = rank_candidates(
        generate_candidates(["differential_diagnosis"], _activity()), weak, ["differential_diagnosis"]
    )
    assert 1 <= len(ranked) <= 3
    assert len({task["type"] for task in ranked}) == len(ranked)
    for task in ranked:
        assert task["target_abilities"]
        assert task["source_evidence"]
        assert task["difficulty_label"]
        assert task["priority"] >= 84


def test_ranker_prefers_material_matching_the_learners_readiness():
    activity = _activity()

    def pipeline(score: float) -> list[dict]:
        profile = _profile("medical_knowledge", score)
        candidates = generate_candidates(["medical_knowledge"], activity)
        return rank_candidates(apply_constraints(candidates, profile), profile, ["medical_knowledge"])

    # 45 is a foundational band: the advanced unit must be filtered out.
    assert readiness_rank(45) == 1
    foundational = pipeline(45)
    assert foundational[0]["difficulty_label"] == "基础"
    assert all(task["difficulty_label"] != "高阶" for task in foundational)

    # A confident learner is pushed to the harder unit instead of repeating basics.
    assert readiness_rank(88) == 3
    advanced = pipeline(88)
    assert all(task["difficulty_label"] != "基础" for task in advanced)
