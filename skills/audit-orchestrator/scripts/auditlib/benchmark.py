"""Competitor benchmarking — turn an absolute score into a competitive position.

Given the primary site's report plus one or more competitors' reports (each produced by the same
marketplace), build a side-by-side comparison: overall score/grade, per-pillar scores, the
answer-readiness count, and the **citation gaps** — pillars where a competitor clearly beats you
(and, implicitly, what they expose that you don't). Pure function of already-produced reports.
Attached as ``report['benchmark']``.
"""
from __future__ import annotations

from typing import Any, Dict, List

_PILLARS = [("crawl_render", "Crawl & Render"), ("structured_data", "Structured Data"),
            ("extractability", "Extractability"), ("freshness", "Freshness"),
            ("corroboration", "Corroboration"), ("engagement", "Engagement")]
GAP = 15  # a competitor must lead by at least this many points for it to count as a gap


def build(primary: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    you = _cap(primary)
    comps = [_cap(c) for c in competitors if c]
    gaps: List[Dict[str, Any]] = []
    for key, label in _PILLARS:
        yours = you["pillars"].get(key, 100)
        leaders = [(c["site"], c["pillars"].get(key, 0)) for c in comps]
        if not leaders:
            break
        best_site, best = max(leaders, key=lambda x: x[1])
        if best - yours >= GAP:
            gaps.append({"pillar": label, "you": yours, "best": best, "leader": best_site})
    return {"you": you, "competitors": comps, "gaps": gaps,
            "note": (f"{len(gaps)} pillar(s) where a competitor leads by ≥{GAP} points."
                     if gaps else "No competitor leads you by a clear margin on any pillar.")}


def _cap(rpt: Dict[str, Any]) -> Dict[str, Any]:
    an = rpt.get("analytics", {}) or {}
    ar = rpt.get("answer_readiness", {}) or {}
    return {
        "site": rpt.get("site", ""),
        "score": rpt.get("score", {}).get("value", 0),
        "grade": rpt.get("score", {}).get("grade", "F"),
        "pillars": {p["key"]: p["score"] for p in an.get("pillars", [])},
        "answer_ready": ar.get("score"),
        "answer_total": ar.get("applicable"),
        "findings": rpt.get("summary", {}).get("total_findings", 0),
    }
