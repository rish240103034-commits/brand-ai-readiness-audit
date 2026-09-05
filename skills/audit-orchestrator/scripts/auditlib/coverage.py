"""Coverage matrix — what each audit area actually assessed, and how confidently.

A zero-findings area is not automatically "healthy": the check may not have run, or may not
have had enough signal to judge (e.g. freshness with no dates anywhere; corroboration, which
inspects on-page signals but performs no independent external verification). This module turns
the scored report plus a few crawl signals into an explicit per-area status so the report can
distinguish **verified healthy** from **not assessed** — a core Round-3 requirement.

Pure function of (report, signals); no network, fully testable offline.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Each area: key, label, the skills that feed it, and the finding categories it owns.
AREAS = [
    ("crawlability", "Crawlability", {"crawl-render-audit"},
     {"crawlability", "indexability", "reachability"}),
    ("rendering", "Rendering", {"crawl-render-audit"}, {"js-render-gap"}),
    ("structured_data", "Structured Data", {"structured-data-audit"}, {"structured-data"}),
    ("extractability", "Extractability", {"content-extractability-audit"}, {"extractability"}),
    ("entity_identity", "Entity Identity",
     {"structured-data-audit", "freshness-corroboration"}, {"entity-identity"}),
    ("freshness", "Freshness", {"freshness-corroboration"}, {"freshness"}),
    ("corroboration", "Corroboration", {"freshness-corroboration"}, {"corroboration"}),
    ("engagement", "Engagement", {"engagement-audit"},
     {"mobile", "conversion", "orientation", "performance", "readability", "accessibility"}),
]

STATUS = {
    "healthy": "verified healthy",
    "issues": "issues detected",
    "partial": "partial",
    "not_assessed": "not assessed",
    "opportunities": "opportunities available",
}


def build(report: Dict[str, Any], signals: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return the coverage block: a row per area plus a summary."""
    signals = signals or {}
    findings: List[Dict[str, Any]] = [f for f in report.get("findings", []) if f.get("kind") != "opportunity"]
    skills_run = set(report.get("skills_run", []))
    pages = int(report.get("pages_crawled", 0) or 0)
    date_pages = int(signals.get("date_signal_pages", 0) or 0)
    external_done = bool(signals.get("external_lookups", False))

    rows: List[Dict[str, Any]] = []
    for key, label, skills, cats in AREAS:
        area_findings = [f for f in findings if f.get("category") in cats]
        ran = bool(skills & skills_run)
        rows.append(_row(key, label, ran, area_findings, cats, pages, date_pages,
                         external_done, signals))

    # Proactive opportunities are a distinct, non-defect area (kept out of `findings`).
    opps = report.get("opportunities", [])
    rows.append({
        "key": "proactive", "label": "Proactive Opportunities",
        "status": "opportunities" if opps else "healthy",
        "status_label": "opportunities available" if opps else "none surfaced",
        "checks": "context-driven", "pages_assessed": pages,
        "findings": len(opps), "confidence": "medium",
        "note": ("Recommendations that raise AI-readiness beyond fixing defects."
                 if opps else "No context-justified opportunities beyond the findings above."),
    })

    assessed = sum(1 for r in rows if r["key"] != "proactive" and r["status"] != "not_assessed")
    not_assessed = sum(1 for r in rows if r["status"] == "not_assessed")
    return {
        "areas": rows,
        "summary": {
            "areas_total": len(AREAS),
            "areas_assessed": assessed,
            "areas_not_assessed": not_assessed,
            "pages_crawled": pages,
        },
    }


def _row(key, label, ran, area_findings, cats, pages, date_pages, external_done, signals):
    n = len(area_findings)
    checks = ", ".join(sorted(cats))
    conf = _confidence(area_findings, key)

    if not ran:
        return _mk(key, label, "not_assessed", checks, 0, n, "low",
                   "The skill covering this area was not run.")

    if pages == 0:
        return _mk(key, label, "not_assessed", checks, 0, n, "low",
                   "No readable pages were crawled, so nothing could be assessed.")

    # Freshness needs date signals to judge; without any, it is genuinely not assessable.
    if key == "freshness" and n == 0 and date_pages == 0:
        return _mk(key, label, "not_assessed", checks, 0, 0, "low",
                   "No publication, modified, or copyright dates were found on the sampled "
                   "pages, so recency could not be judged either way.")

    # Corroboration inspects on-page signals only — no independent external verification is
    # performed, so a clean result is 'partial', never 'verified healthy'.
    if key == "corroboration":
        if n:
            return _mk(key, label, "issues", checks, pages, n, conf,
                       "On-page corroboration signals (sameAs, external profiles) checked.")
        note = ("On-page corroboration signals present; independent external verification of "
                "claims is out of scope for this static audit.")
        if not external_done:
            note = "External corroboration lookups were disabled; " + note
        return _mk(key, label, "partial", checks, pages, 0, "medium", note)

    if key == "freshness" and n == 0:
        return _mk(key, label, "healthy", checks, date_pages or pages, 0, conf,
                   f"Date signals found on {date_pages} page(s); none looked stale.")

    if n:
        return _mk(key, label, "issues", checks, pages, n, conf,
                   f"{n} finding(s) detected across the sampled pages.")
    return _mk(key, label, "healthy", checks, pages, 0, conf,
               "Assessed across the sampled pages; no issues detected.")


def _mk(key, label, status, checks, pages_assessed, findings, confidence, note):
    return {"key": key, "label": label, "status": status,
            "status_label": STATUS.get(status, status), "checks": checks,
            "pages_assessed": pages_assessed, "findings": findings,
            "confidence": confidence, "note": note}


def _confidence(area_findings, key) -> str:
    """Area confidence = the lowest finding confidence, or a sensible default for a clean area."""
    order = {"high": 3, "medium": 2, "low": 1}
    if area_findings:
        lowest = min(area_findings, key=lambda f: order.get(f.get("confidence", "high"), 3))
        return lowest.get("confidence", "high")
    # Heuristic areas can't claim high confidence even when clean.
    return "medium" if key in ("rendering",) else "high"
