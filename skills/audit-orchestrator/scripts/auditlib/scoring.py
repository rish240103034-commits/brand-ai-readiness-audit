"""AI Visibility Score, letter grade, and impact-based prioritization.

Turns a finished report into a single 0–100 "AI Visibility Score" with an A–F grade and
per-dimension sub-scores, and enriches each finding with an ``impact`` (1–5), a plain-English
``why`` it hurts, and a ``priority`` rank — then re-orders findings most-actionable first.

The model is deterministic and transparent: every dimension starts at 100 and loses points
per finding, weighted by severity and confidence. No magic — the weights live here.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Points removed from a dimension's 100 per finding, before the confidence factor.
SEVERITY_PENALTY = {"critical": 35, "high": 18, "medium": 8, "low": 3, "info": 1}
# Heuristic checks shouldn't dock as hard as directly-observed ones.
CONFIDENCE_FACTOR = {"high": 1.0, "medium": 0.75, "low": 0.5}
# Impact on a 1–5 scale for prioritization.
SEVERITY_IMPACT = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
# Overall score weighting across the two halves of the problem.
DIMENSION_WEIGHT = {"discoverability": 0.6, "engagement": 0.4}

# Why each finding category hurts — one plain sentence, keyed by category then dimension.
WHY_BY_CATEGORY = {
    "crawlability": "If the crawler can't fetch the page, no AI assistant can ever cite it.",
    "indexability": "A noindexed page can be read but is deliberately kept out of results and answers.",
    "reachability": "A page that fails to load is dropped, and repeated failures can deprioritize the whole host.",
    "js-render-gap": "Fetch-only AI retrievers don't run JavaScript, so client-rendered facts are invisible to them.",
    "structured-data": "Without machine-readable markup, assistants must guess facts from prose and often get them wrong.",
    "entity-identity": "With no stable, disambiguated identity, assistants can't confidently attribute facts to the brand.",
    "extractability": "A fact locked in an image or missing its text anchor can't be extracted or quoted.",
    "freshness": "Content that looks abandoned is trusted and surfaced less often.",
    "corroboration": "A claim made in only one place is fragile; assistants trust facts echoed across independent sources.",
    "mobile": "A non-responsive page drives mobile visitors away before they read anything.",
    "conversion": "With no clear next step, visitors who arrive leave without acting.",
    "orientation": "Disoriented visitors who can't tell where they are or where to go bounce.",
    "performance": "Slow, heavy pages lose visitors before the content renders.",
    "readability": "Unscannable walls of text get skimmed and abandoned.",
    "input": "The target could not be validated, so nothing could be audited.",
}
WHY_BY_DIMENSION = {
    "discoverability": "This weakens how reliably the brand is found and cited by AI assistants.",
    "engagement": "This makes visitors who do arrive more likely to leave without engaging.",
}

GRADE_BANDS = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]


def _grade(score: float) -> str:
    """Map a 0–100 score to an A–F letter grade."""
    for cutoff, letter in GRADE_BANDS:
        if score >= cutoff:
            return letter
    return "F"


def _why(finding: Dict[str, Any]) -> str:
    """Return the plain-English reason a finding hurts (category first, else dimension)."""
    cat = finding.get("category", "")
    if cat in WHY_BY_CATEGORY:
        return WHY_BY_CATEGORY[cat]
    return WHY_BY_DIMENSION.get(finding.get("dimension", "discoverability"),
                               WHY_BY_DIMENSION["discoverability"])


def _dimension_score(findings: List[Dict[str, Any]], dimension: str) -> float:
    """Score one dimension: start at 100 and subtract weighted penalties."""
    score = 100.0
    for f in findings:
        if f.get("dimension") != dimension:
            continue
        sev = f.get("severity", "medium")
        conf = f.get("confidence", "high")
        score -= SEVERITY_PENALTY.get(sev, 8) * CONFIDENCE_FACTOR.get(conf, 1.0)
    return max(0.0, min(100.0, round(score, 1)))


def score_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich *report* in place with per-finding impact/why/priority and an overall score.

    Adds ``report['score'] = {value, grade, discoverability, engagement, headline}`` and,
    to each finding, ``impact`` (1–5), ``why`` (plain-English), and ``priority`` (1 = act
    first). Findings are re-sorted most-actionable-first and re-numbered ``F-001`` upward.
    """
    findings: List[Dict[str, Any]] = report.get("findings", [])

    # Per-finding enrichment.
    for f in findings:
        sev = f.get("severity", "medium")
        conf = f.get("confidence", "high")
        impact = SEVERITY_IMPACT.get(sev, 3)
        if conf == "low" and impact > 1:
            impact -= 1  # temper low-confidence heuristics
        f["impact"] = impact
        f["why"] = _why(f)
        f["_priority_score"] = SEVERITY_PENALTY.get(sev, 8) * CONFIDENCE_FACTOR.get(conf, 1.0)

    # Re-order most-actionable first and renumber ids, keeping them stable/deterministic.
    findings.sort(key=lambda f: (-f["_priority_score"], f.get("dimension", ""), f.get("title", "").lower()))
    for i, f in enumerate(findings, start=1):
        f["priority"] = i
        f["id"] = f"F-{i:03d}"
        f.pop("_priority_score", None)

    # Dimension + overall scores. Only weight dimensions that were actually assessed.
    dims_present = {f.get("dimension") for f in findings} | _dims_from_skills(report)
    disc = _dimension_score(findings, "discoverability")
    eng = _dimension_score(findings, "engagement")
    weights = {d: w for d, w in DIMENSION_WEIGHT.items() if d in dims_present} or DIMENSION_WEIGHT
    total_w = sum(weights.values())
    parts = {"discoverability": disc, "engagement": eng}
    overall = round(sum(parts[d] * w for d, w in weights.items()) / total_w)

    report["score"] = {
        "value": overall,
        "grade": _grade(overall),
        "discoverability": disc,
        "engagement": eng,
        "headline": f"AI Visibility Score {overall}/100 ({_grade(overall)})",
    }
    return report


def _dims_from_skills(report: Dict[str, Any]) -> set:
    """Infer which dimensions were assessed from the skills that ran (best-effort)."""
    ran = report.get("skills_run", [])
    dims = set()
    for sid in ran:
        dims.add("engagement" if "engagement" in sid else "discoverability")
    return dims
