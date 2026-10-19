#!/usr/bin/env python3
"""Read-only leakage audit: does anything a student can reach teach or reveal CASE-A01 / CASE-A02?

Scans, without importing the application or touching any database:
  * seeded student-accessible content in ``backend/app/seed_data.py`` (cases, SP cases,
    knowledge units, guidelines, skills) via ``ast`` (string literals only),
  * other string literals in ``backend/app`` services/routes/core (recommendation and
    tutor texts, display labels, ...) excluding the independent-assessment code itself,
  * frontend source text outside the assessment pages,
  * the training case cards (``A01_training_*.md``) that become student-visible once imported,
  * optional JSON exports of the live case catalogue (``--extra-json``), e.g. a de-identified
    export of ``/api/cases`` / SP / knowledge / guideline lists from the deployed database.

For each exam form it reports (a) keyword hits split into *answer terms* (the hidden
diagnosis / key finding) and *context terms*, and (b) 4-gram Jaccard similarity of every
case-like item against the exam stage text.  It also prints the cross-cohort exposure model
for the 7 x 7 batch design (``--exposure``).

Severity: HIGH   = the item contains an answer term AND at least two distinct keywords overall,
                   or its similarity to an exam form is >= 0.25 (it substantially teaches or copies the exam);
          MEDIUM = the item contains an answer term;
          LOW    = only context terms (incidental, e.g. an SLE card noting "no dry eyes").
Exit status: 0 normally; 1 when a finding at or above ``--fail-on`` exists; 2 when a required
input is missing (fail closed - a missing file never counts as "no leakage").

Leakage is *not one thing*, and a single static scan cannot cover it.  ``--channels`` prints the
five channels this file keeps apart, each with its own method and its own coverage status:

  T  student-visible training-library overlap  (INSPECTED here, static text)
  G  public GitHub history exposure            (only with ``--history``: the local remote refs)
  P  actual cases in the production database   (NOT INSPECTED unless ``--extra-json`` is given)
  W  within-cohort verbal spread               (MODELED ONLY - arithmetic, never observed)
  C  cross-cohort spread across the 7 batches  (MODELED ONLY - arithmetic, never observed)

A clean static scan is therefore **not** evidence that the official exam carries no leakage
risk.  The script prints that restriction itself (``--channels``), so a passing run cannot be
quoted as "no leakage".

Usage:
    python3 -I scripts/grant/audit_exam_leakage.py [--repo-root DIR] [--json] [--exposure]
                                                   [--channels] [--history]
                                                   [--extra-json FILE ...] [--fail-on HIGH|MEDIUM|LOW]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
CASE_REL = Path("docs/teaching_grant_2026/workpackages/A_cases")
PAYLOADS = {"CASE-A01": CASE_REL / "A01_assessment_payload_DRAFT.json",
            "CASE-A02": CASE_REL / "A02_assessment_payload_DRAFT.json"}

# answer terms: hidden diagnosis / decisive finding; context terms: supporting vocabulary.
KEYWORDS = {
    "CASE-A02": {
        "answer": ["干燥综合征", "Sjögren", "Sjogren", "唇腺", "Schirmer", "唾液流率", "眼表染色"],
        "context": ["口干", "眼干", "干眼", "腮腺", "抗SSA", "抗SSB", "SSA/Ro", "ESSDAI", "龋齿", "干燥症状", "泪液"],
    },
    "CASE-A01": {
        "answer": ["未分化", "undifferentiated", "病程不足6周", "病程<6周", "病程 <6 周"],
        "context": ["2010 ACR/EULAR", "非对称", "抗CCP阴性", "抗 CCP 阴性", "RF弱阳性", "RF 弱阳性", "低滴度", "入口条件"],
    },
}
SIMILARITY_FLAG = 0.25
SERVICE_DIRS = ("services", "routes", "core", "llm")
EXCLUDED_BACKEND = ("assessment", "assessment_models.py", "routes/assessments.py", "seed_data.py", "__pycache__")
FRONTEND_DIRS = ("app", "lib", "components")
FRONTEND_EXCLUDE = ("assessments", "assessment-forms", "assessment-admin", "node_modules", ".next", "tests")
SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


@dataclass
class Item:
    category: str            # case | sp | knowledge | guideline | skill | service_text | frontend | training_card | extra
    source: str              # file (and function) it came from
    title: str
    text: str
    line: int | None = None


@dataclass
class Finding:
    exam: str
    item: Item
    answer_hits: list[str] = field(default_factory=list)
    context_hits: list[str] = field(default_factory=list)
    similarity: float = 0.0
    severity: str = "LOW"


class MissingInput(Exception):
    pass


# ---------------------------------------------------------------------------- collection
def _cjk(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text))


def _strings_in(node: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def collect_seed_items(seed_path: Path) -> list[Item]:
    if not seed_path.is_file():
        raise MissingInput(f"seed data not found: {seed_path}")
    tree = ast.parse(seed_path.read_text(encoding="utf-8"))
    category_by_func = {"_case_payloads": "case", "_sp_case_payloads": "sp", "_knowledge_payloads": "knowledge",
                        "_guideline_payloads": "guideline", "_skill_payloads": "skill"}
    items: list[Item] = []
    for func in [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in category_by_func]:
        for node in ast.walk(func):
            if not isinstance(node, ast.Dict):
                continue
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            if "title" not in keys:
                continue
            title = ""
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "title" and isinstance(v, ast.Constant):
                    title = str(v.value)
            items.append(Item(category_by_func[func.name], f"{seed_path.name}:{func.name}", title,
                              "\n".join(_strings_in(node)), node.lineno))
    if not items:
        raise MissingInput(f"no seeded items could be extracted from {seed_path}")
    return items


def collect_service_strings(app_dir: Path) -> list[Item]:
    items: list[Item] = []
    if not app_dir.is_dir():
        raise MissingInput(f"backend app dir not found: {app_dir}")
    for sub in SERVICE_DIRS:
        for path in sorted((app_dir / sub).rglob("*.py")) if (app_dir / sub).is_dir() else []:
            rel = path.relative_to(app_dir).as_posix()
            if any(part in rel for part in EXCLUDED_BACKEND):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and _cjk(node.value) and len(node.value) >= 6:
                    items.append(Item("service_text", f"backend/app/{rel}", node.value[:30], node.value, node.lineno))
    return items


def collect_frontend(frontend_dir: Path) -> list[Item]:
    items: list[Item] = []
    if not frontend_dir.is_dir():
        return items  # frontend is optional for the audit; backend seed is the required input
    for sub in FRONTEND_DIRS:
        base = frontend_dir / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in {".ts", ".tsx", ".js", ".json", ".md"} or not path.is_file():
                continue
            rel = path.relative_to(frontend_dir).as_posix()
            if any(part in rel.split("/") or part in rel for part in FRONTEND_EXCLUDE):
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                if _cjk(line) and len(line.strip()) >= 6:
                    items.append(Item("frontend", f"frontend/{rel}", line.strip()[:30], line.strip(), lineno))
    return items


def collect_training_cards(case_dir: Path) -> list[Item]:
    cards = sorted(case_dir.glob("A01_training_*.md"))
    if not cards:
        raise MissingInput(f"no training cards found in {case_dir}")
    return [Item("training_card", c.name, c.stem, c.read_text(encoding="utf-8")) for c in cards]


def collect_extra(paths: list[Path]) -> list[Item]:
    items: list[Item] = []
    for path in paths:
        if not path.is_file():
            raise MissingInput(f"extra json not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        records = data if isinstance(data, list) else data.get("items", [])
        for rec in records:
            if isinstance(rec, dict):
                items.append(Item("extra", path.name, str(rec.get("title", ""))[:60],
                                  "\n".join(str(v) for v in rec.values())))
    return items


def load_exam_forms(root: Path) -> dict[str, str]:
    forms: dict[str, str] = {}
    for code, rel in PAYLOADS.items():
        path = root / rel
        if not path.is_file():
            raise MissingInput(f"exam payload not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        forms[code] = "\n".join(s["clinical_information"] for s in payload["stages"])
    return forms


# ---------------------------------------------------------------------------- analysis
def _ngrams(text: str, n: int = 4) -> set[str]:
    compact = re.sub(r"\s+", "", text)
    return {compact[i:i + n] for i in range(len(compact) - n + 1)}


def jaccard(a: str, b: str) -> float:
    ga, gb = _ngrams(a), _ngrams(b)
    return len(ga & gb) / len(ga | gb) if ga and gb else 0.0


def containment(item_text: str, exam_text: str) -> float:
    """Share of the *exam* 4-grams that also occur in the item (how much of the exam it reproduces)."""
    ge, gi = _ngrams(exam_text), _ngrams(item_text)
    return len(ge & gi) / len(ge) if ge else 0.0


def analyse(items: list[Item], forms: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    for exam, exam_text in forms.items():
        words = KEYWORDS[exam]
        for item in items:
            answer = sorted({w for w in words["answer"] if w.lower() in item.text.lower()})
            context = sorted({w for w in words["context"] if w.lower() in item.text.lower()})
            sim = 0.0
            if item.category in {"case", "sp", "training_card", "extra"}:
                sim = max(jaccard(item.text, exam_text), containment(item.text, exam_text))
            if not answer and not context and sim < SIMILARITY_FLAG:
                continue
            if sim >= SIMILARITY_FLAG or (answer and len(answer) + len(context) >= 2):
                severity = "HIGH"
            elif answer:
                severity = "MEDIUM"
            else:
                severity = "LOW"
            findings.append(Finding(exam, item, answer, context, round(sim, 3), severity))
    findings.sort(key=lambda f: (-SEVERITY_ORDER[f.severity], f.exam, f.item.source))
    return findings


def top_similarity(items: list[Item], forms: dict[str, str], k: int = 3) -> dict[str, list[tuple[float, str]]]:
    out: dict[str, list[tuple[float, str]]] = {}
    for exam, exam_text in forms.items():
        scored = [(round(max(jaccard(i.text, exam_text), containment(i.text, exam_text)), 3), f"{i.category}:{i.title or i.source}")
                  for i in items if i.category in {"case", "sp", "training_card", "extra"}]
        out[exam] = sorted(scored, reverse=True)[:k]
    return out


def exposure_model(batches: int = 7, per_batch: int = 7, x_size: int | None = None) -> dict:
    """Cross-cohort exposure for the X (A01->A02) / Y (A02->A01) crossover with one form pair.

    A student sits one form at D1 and the other at D6.  Everything below counts people who
    have *already sat the student's D6 form* before that student does, i.e. potential informants.
    """
    x = x_size if x_size is not None else (per_batch + 1) // 2     # 4 X / 3 Y for 7 students
    y = per_batch - x
    rows = []
    for b in range(1, batches + 1):
        prior = per_batch * (b - 1)                               # earlier cohorts: sat BOTH forms
        rows.append({
            "batch": b,
            "prior_students_who_sat_both_forms": prior,
            "within_batch_informants_for_X_at_D6": y,            # Y students sat A02 at D1; X sits A02 at D6
            "within_batch_informants_for_Y_at_D6": x,
            "informants_for_X_at_D6_total": y + prior,
            "informants_for_Y_at_D6_total": x + prior,
            "informants_at_D1_total": prior,                       # D1 informants are only earlier cohorts
        })
    total = batches * per_batch
    return {
        "design": f"{batches} batches x {per_batch} students, one X/Y form pair, split {x}/{y} per batch",
        "students": total,
        "students_with_any_within_batch_informant_at_D6": total if (x > 0 and y > 0) else 0,
        "students_with_prior_cohort_informants_at_D1": per_batch * (batches - 1),
        "share_with_prior_cohort_informants_at_D1": round((batches - 1) / batches, 3),
        "per_batch": rows,
    }


# ------------------------------------------------------------------- the five leakage channels
# A static scan answers one question.  The official exam's leakage risk is the union of five, and
# four of them are outside this file's reach.  Keeping them apart in one report is the point: it
# stops "the scan is clean" from being read as "the exam is safe".
CHANNEL_META = {
    "T": {"name": "学生可见训练库重叠 / student-visible training-library overlap",
          "question": "训练病例、种子内容、导师文案是否教到了考核题的推理或答案？",
          "method": "静态扫描（seed_data、服务文案、前端文案、训练病例卡）"},
    "G": {"name": "公开 GitHub 历史暴露 / public GitHub history exposure",
          "question": "考核题本、答案键、锚点是否已在公开远端可读？",
          "method": "只读列出本地远端跟踪引用中的考核相关路径（--history）；不联网、不改写历史"},
    "P": {"name": "生产数据库实际病例 / cases in the current production database",
          "question": "线上实际病例/SP/知识/指南目录里有没有与考核题同病的材料？",
          "method": "生产库脱敏导出（--extra-json）；未提供即为未核查"},
    "W": {"name": "同批学生口头传播 / within-cohort verbal spread",
          "question": "同一批内 D1 与 D6 之间，同学之间会不会交流题本内容？",
          "method": "按设计计算知情人数（exposure_model）；无法观测，只能建模与登记事件"},
    "C": {"name": "跨轮转批次传播 / cross-cohort spread",
          "question": "后一批学生能否从往届同学处获知题本？",
          "method": "按设计计算往届知情人数（exposure_model）；无法观测，只能建模与登记事件"},
}
CHANNELS = ("T", "G", "P", "W", "C")
STATUS_ZH = {"INSPECTED": "已核查（本脚本范围内）", "PARTIAL": "部分核查（有已知盲区）",
             "NOT_INSPECTED": "未核查", "MODELED_ONLY": "仅建模，无法观测"}

# Paths that make a public-history hit a real exposure (the form cards, their payloads, the
# anchor tables and the sample answers).
HISTORY_EXAM_PATTERNS = ("A01_assessment", "A02_assessment", "assessment_payload", "sample_answers",
                         "ANCHOR_CONSISTENCY", "CASE_REVIEW_FORM_A0", "DIFFICULTY_MATCH",
                         "B02_sample_answers")


def collect_public_history(root: Path) -> dict:
    """Read-only: which exam-bearing paths are already readable in the local remote refs?

    Deliberately does **not** run ``git fetch``: the audit must not touch the network or the
    remote.  Consequence, reported with the result: the refs are as fresh as the last fetch, so
    the remote may carry more than this listing shows.
    """
    try:
        proc = subprocess.run(["git", "-C", str(root), "for-each-ref",
                               "--format=%(refname) %(objectname)", "refs/remotes", "refs/heads"],
                              capture_output=True, text=True)
    except OSError as exc:
        raise MissingInput(f"cannot read public history: git unavailable ({exc})") from exc
    if proc.returncode != 0:
        raise MissingInput(f"cannot read public history: {proc.stderr.strip()}")
    refs = [line.split() for line in proc.stdout.splitlines() if line.strip()]
    if not refs:
        raise MissingInput("cannot read public history: no refs found")
    exposed: dict[str, list[str]] = {}
    inspected = []
    for ref, sha in refs:
        listed = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref],
                                capture_output=True, text=True)
        if listed.returncode != 0:
            raise MissingInput(f"cannot list {ref}: {listed.stderr.strip()}")
        inspected.append({"ref": ref, "sha": sha})
        for path in listed.stdout.splitlines():
            # a script that names the patterns (a validator, a builder) is not exam material
            if path.startswith("scripts/") or path.endswith(".py"):
                continue
            if any(pattern in path for pattern in HISTORY_EXAM_PATTERNS):
                exposed.setdefault(path, []).append(ref)
    return {
        "refs_inspected": inspected,
        "exposed_paths": [{"path": p, "refs": sorted(r)} for p, r in sorted(exposed.items())],
        "limits": ["本地远端跟踪引用，可能落后于远端（未执行 git fetch）",
                   "无法看到已被克隆/缓存/复刻的副本",
                   "已推送内容不会因删除文件或改写历史而撤销；本审计不改写历史"],
    }


def channel_matrix(items: list[Item], history: dict | None, production: dict | None,
                   exposure: dict) -> list[dict]:
    """The five channels, each with its own status and evidence.  Never a single verdict."""
    categories = sorted({i.category for i in items})
    rows = []
    for code in CHANNELS:
        meta = CHANNEL_META[code]
        row = {"channel": code, "name": meta["name"], "question": meta["question"],
               "method": meta["method"], "status": None, "evidence": {}, "limits": []}
        if code == "T":
            row["status"] = "PARTIAL"
            row["evidence"] = {"items_scanned": len(items), "categories": categories}
            row["limits"] = ["静态关键词与 4-gram 相似度看不懂“换了说法、同一推理链”的重叠",
                             "未扫描运行期由 API 返回的内容",
                             "覆盖范围限于本次列出的静态来源"]
        elif code == "G":
            if history is None:
                row["status"] = "NOT_INSPECTED"
                row["limits"] = ["本次未执行 --history，公开历史暴露状态未核查",
                                 "静态扫描不包含远端历史；既往暴露不会因删除文件而消失"]
            else:
                row["status"] = "PARTIAL"
                row["evidence"] = {"refs": len(history["refs_inspected"]),
                                   "exposed_paths": history["exposed_paths"]}
                row["limits"] = history["limits"]
        elif code == "P":
            if production is None:
                row["status"] = "NOT_INSPECTED"
                row["limits"] = ["生产实际病例目录未核查（需要生产库的脱敏目录导出，见 --extra-json）",
                                 "种子数据不等于线上目录"]
            else:
                row["status"] = "PARTIAL"
                row["evidence"] = production
                row["limits"] = ["只覆盖导出文件中的字段，导出本身的完整性由导出方负责"]
        elif code == "W":
            row["status"] = "MODELED_ONLY"
            row["evidence"] = {
                "students_with_any_within_batch_informant_at_D6":
                    exposure["students_with_any_within_batch_informant_at_D6"],
                "students": exposure["students"]}
            row["limits"] = ["学生之间的交流无法由任何工具观测；只能靠统一监考、保密声明与泄漏事件登记",
                             "批内暴露是 X/Y 交叉设计的固有性质，不是偶发泄漏"]
        else:
            row["status"] = "MODELED_ONLY"
            row["evidence"] = {
                "students_with_prior_cohort_informants_at_D1":
                    exposure["students_with_prior_cohort_informants_at_D1"],
                "share_with_prior_cohort_informants_at_D1":
                    exposure["share_with_prior_cohort_informants_at_D1"],
                "last_batch_prior_informants":
                    exposure["per_batch"][-1]["prior_students_who_sat_both_forms"]}
            row["limits"] = ["7 批共用一对题本，往届知情人数随批次线性增加",
                             "方向未知：既可能抬高 T0，也可能抬高 T1，不能假定相互抵消"]
        rows.append(row)
    return rows


def forbidden_claims(rows: list[dict]) -> list[str]:
    """What a passing static scan may *not* be written up as."""
    unclosed = [r["channel"] for r in rows if r["status"] in {"NOT_INSPECTED", "MODELED_ONLY"}]
    claims = ["不得写成“正式考试无泄漏风险”“已确认无泄漏”或等价的表述",
              "静态扫描只能支持“本次扫描范围内未发现与考核题高度相似或直接暴露答案的静态文本”"]
    if unclosed:
        claims.append(f"渠道 {'/'.join(unclosed)} 尚未核查或无法观测，结论中必须逐项列出")
    if any(r["channel"] == "P" and r["status"] == "NOT_INSPECTED" for r in rows):
        claims.append("生产实际病例目录仍未核查：不得暗示线上病例库已经检查过")
    return claims


def render_channels(rows: list[dict], forbidden: list[str]) -> str:
    out = ["Leakage channels (five separate risks - a clean static scan covers channel T only):"]
    for row in rows:
        out.append(f"  [{row['channel']}] {STATUS_ZH[row['status']]}  {row['name']}")
        out.append(f"       question : {row['question']}")
        out.append(f"       method   : {row['method']}")
        if row["evidence"]:
            out.append(f"       evidence : {json.dumps(row['evidence'], ensure_ascii=False)}")
        for limit in row["limits"]:
            out.append(f"       limit    : {limit}")
    out.append("")
    out.append("Wording restriction (this scan cannot support more):")
    out += [f"  - {claim}" for claim in forbidden]
    return "\n".join(out)


# ---------------------------------------------------------------------------- reporting
def render_text(findings: list[Finding], sims: dict, items: list[Item], forms: dict[str, str]) -> str:
    lines = [f"Scanned {len(items)} items against {len(forms)} exam forms (categories: "
             + ", ".join(sorted({i.category for i in items})) + ")", ""]
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_ORDER}
    lines.append(f"Findings: HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}")
    for f in findings:
        loc = f"{f.item.source}" + (f":{f.item.line}" if f.item.line else "")
        lines.append(f"[{f.severity}] {f.exam} <- {f.item.category} '{f.item.title}' ({loc}) "
                     f"answer={f.answer_hits} context={f.context_hits} sim={f.similarity}")
    lines.append("")
    lines.append("Highest similarity of case-like items to each exam form (4-gram, max of Jaccard/containment):")
    for exam, rows in sims.items():
        lines.append(f"  {exam}: " + "; ".join(f"{s} {name}" for s, name in rows))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--extra-json", action="append", type=Path, default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--exposure", action="store_true", help="print the 7x7 cross-cohort exposure model")
    parser.add_argument("--channels", action="store_true",
                        help="print the five leakage channels with their coverage status and the "
                             "wording a clean scan does NOT support")
    parser.add_argument("--history", action="store_true",
                        help="read-only scan of the local remote refs for already-public exam material")
    parser.add_argument("--fail-on", choices=list(SEVERITY_ORDER), default="HIGH")
    args = parser.parse_args(argv)
    root: Path = args.repo_root
    try:
        forms = load_exam_forms(root)
        items = (collect_seed_items(root / "backend/app/seed_data.py")
                 + collect_service_strings(root / "backend/app")
                 + collect_frontend(root / "frontend")
                 + collect_training_cards(root / CASE_REL)
                 + collect_extra(args.extra_json))
        history = collect_public_history(root) if args.history else None
    except MissingInput as exc:
        print(f"ERROR (fail closed): {exc}", file=sys.stderr)
        return 2
    findings = analyse(items, forms)
    sims = top_similarity(items, forms)
    exposure = exposure_model()
    production = ({"extra_json_files": [str(p) for p in args.extra_json],
                   "items_from_production_export": sum(1 for i in items if i.category == "extra")}
                  if args.extra_json else None)
    channels = channel_matrix(items, history, production, exposure)
    forbidden = forbidden_claims(channels)
    if args.json:
        print(json.dumps({
            "items_scanned": len(items),
            "findings": [{"exam": f.exam, "severity": f.severity, "category": f.item.category, "source": f.item.source,
                          "title": f.item.title, "line": f.item.line, "answer_hits": f.answer_hits,
                          "context_hits": f.context_hits, "similarity": f.similarity} for f in findings],
            "top_similarity": sims, "exposure": exposure,
            "channels": channels, "forbidden_claims": forbidden,
            "static_scan": {"scope": "student-visible static text (channel T)",
                            "counts": {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_ORDER},
                            "supported_claim": "本次扫描范围内未发现与考核题高度相似或直接暴露答案的静态文本",
                            "not_supported_claim": "正式考试无泄漏风险"},
        }, ensure_ascii=False, indent=2))
    else:
        print(render_text(findings, sims, items, forms))
        if args.exposure:
            print("\nExposure model:", json.dumps(exposure, ensure_ascii=False, indent=2))
        if args.channels:
            print()
            print(render_channels(channels, forbidden))
    threshold = SEVERITY_ORDER[args.fail_on]
    return 1 if any(SEVERITY_ORDER[f.severity] >= threshold for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
