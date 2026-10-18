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

Usage:
    python3 -I scripts/grant/audit_exam_leakage.py [--repo-root DIR] [--json] [--exposure]
                                                   [--extra-json FILE ...] [--fail-on HIGH|MEDIUM|LOW]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
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
    except MissingInput as exc:
        print(f"ERROR (fail closed): {exc}", file=sys.stderr)
        return 2
    findings = analyse(items, forms)
    sims = top_similarity(items, forms)
    exposure = exposure_model() if args.exposure else None
    if args.json:
        print(json.dumps({
            "items_scanned": len(items),
            "findings": [{"exam": f.exam, "severity": f.severity, "category": f.item.category, "source": f.item.source,
                          "title": f.item.title, "line": f.item.line, "answer_hits": f.answer_hits,
                          "context_hits": f.context_hits, "similarity": f.similarity} for f in findings],
            "top_similarity": sims, "exposure": exposure}, ensure_ascii=False, indent=2))
    else:
        print(render_text(findings, sims, items, forms))
        if exposure:
            print("\nExposure model:", json.dumps(exposure, ensure_ascii=False, indent=2))
    threshold = SEVERITY_ORDER[args.fail_on]
    return 1 if any(SEVERITY_ORDER[f.severity] >= threshold for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
