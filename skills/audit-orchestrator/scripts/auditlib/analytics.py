"""Analyst layer — turn a scored report into a full data-analytics view.

The orchestrator produces a *scored* report (findings + an AI Visibility Score). This module
adds the interpretation an analyst would write on top of that data, all derived deterministically
from fields already on the report (severity, confidence, impact, category, affected pages):

  * **pillars**       — six sub-scores (crawl/render, structured data, extractability, freshness,
                        corroboration, engagement) with a health status each, for a radar view.
  * **distribution**  — counts + shares by severity, confidence, dimension, and category.
  * **matrix**        — every finding placed on an impact × effort grid (quick-win / major-project /
                        fill-in / low-priority quadrants), with the score points each one is costing.
  * **projection**    — "what-if" scores: where the AI Visibility Score would land if the quick wins,
                        or everything, were fixed — and how far it is to the next grade.
  * **hotspots**      — the specific pages carrying the most weighted issues.
  * **roadmap**       — findings bucketed into Now / Next / Later.
  * **kpis** + **narrative** — a headline metric row and a short auto-written executive summary.

Everything here is a pure function of the report dict, so it is trivially testable offline and
adds no new dependencies. It reuses the score model in ``scoring`` for projections — one source
of truth for the number.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from . import scoring

# --- Pillars: how the finding categories roll up into named health areas ----------
# (key, human label, dimension, {categories that belong to it}). Order = display order.
PILLARS = [
    ("crawl_render", "Crawl & Render", "discoverability",
     {"crawlability", "indexability", "reachability", "js-render-gap"}),
    ("structured_data", "Structured Data", "discoverability",
     {"structured-data", "entity-identity"}),
    ("extractability", "Extractability", "discoverability", {"extractability"}),
    ("freshness", "Freshness", "discoverability", {"freshness"}),
    ("corroboration", "Corroboration", "discoverability", {"corroboration"}),
    ("engagement", "Engagement", "engagement",
     {"mobile", "conversion", "orientation", "performance", "readability"}),
]
_CATEGORY_TO_PILLAR = {cat: key for key, _, _, cats in PILLARS for cat in cats}

# Pillar health bands (score cutoff → status).
PILLAR_BANDS = [(90, "healthy"), (70, "warning"), (0, "critical")]

# --- Effort model: rough implementation cost per category, 1 (trivial) … 5 (architectural).
# Transparent, like the score weights — an analyst can defend every number.
EFFORT_BY_CATEGORY = {
    "indexability": 1,      # flip a noindex / fix a canonical tag
    "input": 1,
    "crawlability": 2,      # publish a sitemap, adjust robots
    "entity-identity": 2,   # add sameAs / Organization identity
    "extractability": 2,    # titles, meta, alt text, headings
    "freshness": 2,         # surface dates, refresh stale copy
    "conversion": 2,        # add a clear call-to-action
    "orientation": 2,       # breadcrumbs / clearer navigation
    "readability": 2,       # break up walls of text
    "structured-data": 3,   # author + template JSON-LD across pages
    "reachability": 3,      # infra / uptime fix
    "mobile": 3,            # responsive layout work
    "performance": 4,       # trim page weight, speed up responses
    "corroboration": 4,     # build off-site presence — depends on third parties
    "js-render-gap": 5,     # server-side render / prerender — architectural
}
DEFAULT_EFFORT = 3
EFFORT_LABELS = {1: "Low", 2: "Low", 3: "Medium", 4: "High", 5: "High"}
QUADRANTS = {
    "quick_win": "Quick win",          # high impact, low effort — do first
    "major_project": "Major project",  # high impact, high effort — plan for it
    "fill_in": "Fill-in",              # low impact, low effort — batch it
    "low_priority": "Low priority",    # low impact, high effort — defer
}
# A finding is "high impact" at impact >= this, and "low effort" at effort <= this.
IMPACT_HIGH = 3
EFFORT_LOW = 2

VERDICT_BANDS = [
    (90, "Excellent", "The site is highly ready to be found and cited by AI assistants."),
    (80, "Strong", "The site is in good shape, with a few refinements left to make."),
    (70, "Fair", "The foundations are there but meaningful gaps are holding it back."),
    (60, "Weak", "Several issues are actively limiting how the brand is found and read."),
    (0, "At risk", "Core problems make the brand hard for AI assistants to find or trust."),
]


def attach(report: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the analytics block and attach it to *report* as ``report['analytics']``.

    Safe on any scored report (including the single-finding fatal report). Returns *report*.
    """
    findings: List[Dict[str, Any]] = report.get("findings", [])
    dims = scoring.dimensions_present(report)
    current = report.get("score", {}).get("value", scoring.compute_scores(findings, dims)["value"])

    # Enrich each finding with effort + quadrant + the score points it is costing.
    enriched = [_enrich(f, findings, dims, current) for f in findings]

    matrix = _matrix(enriched)
    projection = _projection(report, findings, dims, current, matrix["quick_win_ids"])
    pillars = _pillars(findings)
    distribution = _distribution(findings)
    hotspots = _hotspots(enriched)
    roadmap = _roadmap(enriched, matrix["quick_win_ids"])
    kpis = _kpis(report, enriched, pillars, matrix, projection)
    narrative = _narrative(report, kpis, pillars, matrix, projection)

    report["analytics"] = {
        "generated_from": "scored report (deterministic, no extra data collected)",
        "kpis": kpis,
        "pillars": pillars,
        "distribution": distribution,
        "matrix": matrix["items"],
        "quadrant_counts": matrix["counts"],
        "quick_wins": matrix["quick_wins"],
        "projection": projection,
        "hotspots": hotspots,
        "roadmap": roadmap,
        "narrative": narrative,
    }
    return report


# --- per-finding enrichment -------------------------------------------------------

def _effort(finding: Dict[str, Any]) -> int:
    """Estimated implementation effort 1–5 for a finding (category-based, +1 if site-wide)."""
    base = EFFORT_BY_CATEGORY.get(finding.get("category", ""), DEFAULT_EFFORT)
    if len(finding.get("affected_pages") or []) >= 5:  # site-wide template work costs more
        base = min(5, base + 1)
    return base


def _quadrant(impact: int, effort: int) -> str:
    high_impact = impact >= IMPACT_HIGH
    low_effort = effort <= EFFORT_LOW
    if high_impact and low_effort:
        return "quick_win"
    if high_impact and not low_effort:
        return "major_project"
    if not high_impact and low_effort:
        return "fill_in"
    return "low_priority"


def _enrich(finding: Dict[str, Any], all_findings: List[Dict[str, Any]],
            dims: Set[str], current: int) -> Dict[str, Any]:
    """Return a compact analytics record for one finding."""
    impact = int(finding.get("impact", 3))
    effort = _effort(finding)
    fid = finding.get("id", "")
    # Points at stake = how much the overall score would rise if just this finding were fixed.
    without = [f for f in all_findings if f.get("id") != fid]
    points = max(0, scoring.compute_scores(without, dims)["value"] - current)
    return {
        "id": fid,
        "title": finding.get("title", ""),
        "severity": finding.get("severity", "medium"),
        "dimension": finding.get("dimension", ""),
        "category": finding.get("category", ""),
        "confidence": finding.get("confidence", "high"),
        "priority": finding.get("priority", 0),
        "impact": impact,
        "effort": effort,
        "effort_label": EFFORT_LABELS.get(effort, "Medium"),
        "quadrant": _quadrant(impact, effort),
        "points_at_stake": points,
        "affected_pages": finding.get("affected_pages") or [],
    }


# --- matrix (impact × effort) -----------------------------------------------------

def _matrix(enriched: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {q: 0 for q in QUADRANTS}
    for e in enriched:
        counts[e["quadrant"]] += 1
    quick = [e for e in enriched if e["quadrant"] == "quick_win"]
    quick.sort(key=lambda e: (-e["points_at_stake"], -e["impact"], e["effort"]))
    return {
        "items": enriched,
        "counts": counts,
        "quick_wins": quick,
        "quick_win_ids": {e["id"] for e in quick},
    }


# --- projection ("what-if") -------------------------------------------------------

def _projection(report: Dict[str, Any], findings: List[Dict[str, Any]], dims: Set[str],
                current: int, quick_win_ids: Set[str]) -> Dict[str, Any]:
    after_quick = scoring.compute_scores(
        [f for f in findings if f.get("id") not in quick_win_ids], dims)
    after_all = scoring.compute_scores([], dims)
    to_next = _to_next_grade(current)
    return {
        "current": current,
        "current_grade": scoring._grade(current),
        "after_quick_wins": after_quick["value"],
        "after_quick_wins_grade": after_quick["grade"],
        "quick_win_gain": max(0, after_quick["value"] - current),
        "after_all_fixed": after_all["value"],
        "after_all_grade": after_all["grade"],
        "headroom": max(0, after_all["value"] - current),
        "to_next_grade": to_next,  # {points, grade} or None if already A
        "quick_wins_reach_next_grade": (
            to_next is not None and after_quick["value"] >= to_next["at_least"]),
    }


def _to_next_grade(score: int):
    """Points needed to reach the next grade up, or None if already an A."""
    higher = [(cut, letter) for cut, letter in scoring.GRADE_BANDS if cut > score]
    if not higher:
        return None
    cutoff, letter = min(higher, key=lambda cl: cl[0])
    return {"grade": letter, "points": cutoff - score, "at_least": cutoff}


# --- pillars ----------------------------------------------------------------------

def _pillar_status(score: float) -> str:
    for cutoff, status in PILLAR_BANDS:
        if score >= cutoff:
            return status
    return "critical"


def _pillars(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for key, label, dimension, cats in PILLARS:
        members = [f for f in findings if f.get("category") in cats]
        score = 100.0
        for f in members:
            score -= scoring.penalty_of(f)
        score = max(0.0, min(100.0, round(score, 1)))
        out.append({
            "key": key,
            "label": label,
            "dimension": dimension,
            "score": score,
            "status": _pillar_status(score),
            "findings": len(members),
        })
    return out


# --- distribution -----------------------------------------------------------------

def _distribution(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(findings) or 1

    def tally(field: str, order=None) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        for f in findings:
            counts[f.get(field, "")] = counts.get(f.get(field, ""), 0) + 1
        keys = order or sorted(counts, key=lambda k: -counts[k])
        return [{"key": k, "count": counts[k], "pct": round(100 * counts[k] / total)}
                for k in keys if counts.get(k)]

    return {
        "by_severity": tally("severity", order=["critical", "high", "medium", "low", "info"]),
        "by_confidence": tally("confidence", order=["high", "medium", "low"]),
        "by_dimension": tally("dimension", order=["discoverability", "engagement"]),
        "by_category": tally("category"),
    }


# --- hotspots ---------------------------------------------------------------------

def _hotspots(enriched: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    """Rank affected pages by number of findings and total impact carried."""
    acc: Dict[str, Dict[str, Any]] = {}
    for e in enriched:
        for url in e["affected_pages"]:
            row = acc.setdefault(url, {"url": url, "findings": 0, "impact": 0,
                                       "top_severity_rank": 99})
            row["findings"] += 1
            row["impact"] += e["impact"]
            rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(e["severity"], 5)
            row["top_severity_rank"] = min(row["top_severity_rank"], rank)
    rows = sorted(acc.values(), key=lambda r: (-r["impact"], -r["findings"]))
    sev_of = {0: "critical", 1: "high", 2: "medium", 3: "low", 4: "info", 5: "info"}
    for r in rows:
        r["top_severity"] = sev_of.get(r.pop("top_severity_rank", 5), "info")
    return rows[:limit]


# --- roadmap ----------------------------------------------------------------------

def _roadmap(enriched: List[Dict[str, Any]], quick_win_ids: Set[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Bucket findings into Now / Next / Later (each finding lands in exactly one)."""
    now, nxt, later = [], [], []
    for e in sorted(enriched, key=lambda x: x["priority"]):
        ref = {"id": e["id"], "title": e["title"], "severity": e["severity"],
               "impact": e["impact"], "effort_label": e["effort_label"],
               "quadrant": e["quadrant"], "points_at_stake": e["points_at_stake"]}
        if e["severity"] in ("critical", "high") or e["id"] in quick_win_ids:
            now.append(ref)
        elif e["severity"] == "medium":
            nxt.append(ref)
        else:
            later.append(ref)
    return {"now": now, "next": nxt, "later": later}


# --- KPIs + narrative -------------------------------------------------------------

def _kpis(report: Dict[str, Any], enriched: List[Dict[str, Any]], pillars, matrix,
          projection) -> Dict[str, Any]:
    score = report.get("score", {})
    scored_pillars = [p for p in pillars if p["findings"] > 0] or pillars
    weakest = min(pillars, key=lambda p: p["score"])
    strongest = max(pillars, key=lambda p: p["score"])
    total_effort = sum(e["effort"] for e in enriched)
    crit_high = sum(1 for e in enriched if e["severity"] in ("critical", "high"))
    return {
        "ai_visibility_score": score.get("value", 0),
        "grade": score.get("grade", "F"),
        "discoverability": score.get("discoverability", 0),
        "engagement": score.get("engagement", 0),
        "total_findings": len(enriched),
        "critical_high": crit_high,
        "quick_wins": matrix["counts"]["quick_win"],
        "projected_score": projection["after_quick_wins"],
        "projected_gain": projection["quick_win_gain"],
        "potential_score": projection["after_all_fixed"],
        "pages_analyzed": report.get("pages_crawled", 0),
        "weakest_pillar": weakest["label"],
        "weakest_pillar_score": weakest["score"],
        "strongest_pillar": strongest["label"],
        "total_effort_points": total_effort,
        "effort_band": _effort_band(total_effort),
    }


def _effort_band(points: int) -> str:
    if points <= 4:
        return "Small"
    if points <= 12:
        return "Moderate"
    return "Substantial"


def _verdict(score: int):
    for cutoff, label, sentence in VERDICT_BANDS:
        if score >= cutoff:
            return label, sentence
    return VERDICT_BANDS[-1][1], VERDICT_BANDS[-1][2]


def _narrative(report, kpis, pillars, matrix, projection) -> List[str]:
    """A short, data-grounded executive summary — the paragraph an analyst would open with."""
    site = report.get("site", "the site")
    score = kpis["ai_visibility_score"]
    grade = kpis["grade"]
    label, sentence = _verdict(score)
    lines = [
        f"{site} scores {score}/100 (grade {grade} — {label}). {sentence}"
    ]

    if kpis["total_findings"] == 0:
        lines.append("No issues were found across the checks that ran — a clean result.")
        return lines

    crit_high = kpis["critical_high"]
    if crit_high:
        lines.append(
            f"{crit_high} finding(s) are critical or high severity and should be addressed first; "
            f"the weakest area is {kpis['weakest_pillar']} ({kpis['weakest_pillar_score']:.0f}/100).")
    else:
        lines.append(
            f"Nothing is critical or high severity; the biggest opportunity is "
            f"{kpis['weakest_pillar']} ({kpis['weakest_pillar_score']:.0f}/100).")

    qw = kpis["quick_wins"]
    if qw:
        reach = " — enough to move up a grade" if projection["quick_wins_reach_next_grade"] else ""
        lines.append(
            f"{qw} quick win(s) (high impact, low effort) would lift the score by about "
            f"{projection['quick_win_gain']} point(s) to ~{projection['after_quick_wins']}/100{reach}.")

    lines.append(
        f"Fixing every finding would raise the score to about {projection['after_all_fixed']}/100 "
        f"(+{projection['headroom']}); estimated effort overall is {kpis['effort_band'].lower()}.")

    disc, eng = kpis["discoverability"], kpis["engagement"]
    gap = abs(disc - eng)
    if gap >= 10:
        weaker = "discoverability" if disc < eng else "engagement"
        lines.append(f"Discoverability ({disc:.0f}) and engagement ({eng:.0f}) diverge by "
                     f"{gap:.0f} points; {weaker} is the side pulling the score down.")
    return lines
