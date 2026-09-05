"""Coverage matrix — what each audit area assessed, which named checks passed/failed, and how
confidently.

A zero-findings area is not automatically "healthy". This module drives every area from an
explicit **check registry**: each named check resolves to PASS, FAIL, NOT_VERIFIED (browser- or
render-dependent, which this static audit does not execute), or PARTIAL (e.g. corroboration's
independent external verification, which is out of scope). An area is:

  * ``issues``       — one or more findings,
  * ``partial``      — clean, but some checks are NOT_VERIFIED / PARTIAL (e.g. Rendering, whose
                       rendered-DOM parity is never executed; Corroboration's external check),
  * ``healthy``      — every check resolved PASS,
  * ``not_assessed`` — the skill did not run, nothing crawled, or there was no signal to judge
                       (e.g. Freshness with no dates anywhere).

Pure function of (report, signals); no network, fully testable offline.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

PASS, FAIL, NOT_VERIFIED, PARTIAL = "pass", "fail", "not_verified", "partial"

# area key, label, contributing skills, finding categories owned by the area.
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

# Named checks per area: (id, label, title-keywords that mean this check FAILED, kind).
# kind: "static" (pass unless a finding matches), "browser" (NOT_VERIFIED — we don't run a
# browser), "external" (PARTIAL — no independent external verification is performed).
_REG: Dict[str, List] = {
    "crawlability": [
        ("robots_ai", "AI crawler access (robots.txt)", ["retrieval crawlers are blocked", "disallows all crawlers"], "static"),
        ("robots_pages", "Key pages crawlable", ["disallowed by robots"], "static"),
        ("reachability", "Pages return 2xx", ["server errors"], "static"),
        ("sitemap", "XML sitemap present", ["no xml sitemap"], "static"),
        ("canonical", "Canonical consistency", ["canonical tags point"], "static"),
        ("internal_links", "Internal links resolve", ["broken internal links"], "static"),
        ("nofollow", "Internal links followable", ["marked rel=nofollow"], "static"),
    ],
    "rendering": [
        ("ssr_content", "Primary content in static HTML", ["require client-side javascript", "thin server-rendered"], "static"),
        ("noscript_notice", "No 'enable JavaScript' wall", ["tell users to enable javascript"], "static"),
        ("rendered_dom", "Rendered-DOM parity", [], "browser"),
    ],
    "structured_data": [
        ("present", "Structured data present", ["no structured data anywhere"], "static"),
        ("valid", "Structured data parses", ["invalid json-ld"], "static"),
        ("complete", "Recommended properties present", ["missing recommended properties", "properties present but empty"], "static"),
        ("product", "Product schema on product pages", ["product-like pages missing"], "static"),
        ("article", "Article schema on articles", ["article/blog pages missing"], "static"),
    ],
    "extractability": [
        ("title", "Every page has a <title>", ["missing a <title>"], "static"),
        ("title_quality", "Titles are a useful length", ["title tags outside"], "static"),
        ("meta_desc", "Meta descriptions present", ["missing a meta description"], "static"),
        ("h1", "One clear H1 per page", ["missing an h1", "multiple h1"], "static"),
        ("hierarchy", "Heading hierarchy ordered", ["hierarchy skips"], "static"),
        ("alt", "Images have alt text", ["images lack alt", "embedded in images"], "static"),
        ("lang", "Language declared", ["language is not declared"], "static"),
    ],
    "entity_identity": [
        ("homepage_identity", "Homepage identity schema", ["lacks organization"], "static"),
        ("name_consistency", "Consistent brand identity", ["inconsistent brand name", "identity signals disagree", "conflicting organization"], "static"),
    ],
    "freshness": [
        ("dated", "Content is dated", ["without a visible date"], "static"),
        ("current", "Content looks current", ["stale copyright", "more than two years old"], "static"),
    ],
    "corroboration": [
        ("sameas", "sameAs corroboration links", ["no sameas"], "static"),
        ("external_presence", "Links to external profiles", ["no links to external"], "static"),
        ("external_verification", "Independent external verification", [], "external"),
    ],
    "engagement": [
        ("mobile", "Responsive viewport", ["viewport"], "static"),
        ("cta", "Clear call-to-action", ["call-to-action"], "static"),
        ("navigation", "Semantic navigation & onward links", ["navigation region", "dead-end"], "static"),
        ("performance", "Reasonable weight & response", ["heavy pages", "slow server", "render-blocking"], "static"),
        ("readability", "Scannable content", ["subheadings", "wall"], "static"),
        ("orientation", "Orientation / breadcrumbs", ["breadcrumbs"], "static"),
        ("accessibility", "Accessibility basics", ["label", "iframe", "non-descriptive"], "static"),
        ("barriers", "No login/interstitial barriers", ["login or registration", "interstitial"], "static"),
    ],
}

STATUS = {
    "healthy": "verified healthy", "issues": "issues detected", "partial": "partial",
    "not_assessed": "not assessed", "opportunities": "opportunities available",
}


def build(report: Dict[str, Any], signals: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    signals = signals or {}
    findings = [f for f in report.get("findings", []) if f.get("kind") != "opportunity"]
    skills_run = set(report.get("skills_run", []))
    pages = int(report.get("pages_crawled", 0) or 0)
    date_pages = int(signals.get("date_signal_pages", 0) or 0)
    external_done = bool(signals.get("external_lookups", False))
    external_verified = signals.get("external_verified")  # None=not performed, True/False if --verify-external

    rows: List[Dict[str, Any]] = []
    for key, label, skills, cats in AREAS:
        area_findings = [f for f in findings if f.get("category") in cats]
        ran = bool(skills & skills_run)
        rows.append(_row(key, label, ran, area_findings, cats, pages, date_pages,
                         external_done, external_verified))

    opps = report.get("opportunities", [])
    rows.append({
        "key": "proactive", "label": "Proactive Opportunities",
        "status": "opportunities" if opps else "healthy",
        "status_label": "opportunities available" if opps else "none surfaced",
        "checks": [], "checks_total": 0, "passed": 0, "failed": 0, "not_verified": 0, "partial_checks": 0,
        "pages_assessed": pages, "findings": len(opps), "confidence": "medium",
        "note": ("Context-justified recommendations beyond fixing defects."
                 if opps else "No context-justified opportunities beyond the findings above."),
    })

    real = [r for r in rows if r["key"] != "proactive"]
    return {
        "areas": rows,
        "summary": {
            "areas_total": len(AREAS),
            "areas_fully_assessed": sum(1 for r in real if r["status"] in ("healthy", "issues")),
            "areas_partial": sum(1 for r in real if r["status"] == "partial"),
            "areas_not_assessed": sum(1 for r in real if r["status"] == "not_assessed"),
            "areas_assessed": sum(1 for r in real if r["status"] != "not_assessed"),
            "pages_crawled": pages,
        },
    }


def _row(key, label, ran, area_findings, cats, pages, date_pages, external_done, external_verified=None):
    not_assessed_note = None
    if not ran:
        not_assessed_note = "The skill covering this area was not run."
    elif pages == 0:
        not_assessed_note = "No readable pages were crawled, so nothing could be assessed."
    elif key == "freshness" and not area_findings and date_pages == 0:
        not_assessed_note = ("No publication, modified, or copyright dates were found on the "
                             "sampled pages, so recency could not be judged either way.")

    checks = _checks_for(key, area_findings, assessable=(not_assessed_note is None),
                         external_verified=external_verified)
    passed = sum(1 for c in checks if c["state"] == PASS)
    failed = sum(1 for c in checks if c["state"] == FAIL)
    nver = sum(1 for c in checks if c["state"] == NOT_VERIFIED)
    part = sum(1 for c in checks if c["state"] == PARTIAL)

    if not_assessed_note is not None:
        status, note = "not_assessed", not_assessed_note
    elif area_findings:
        status = "issues"
        note = f"{failed} check(s) failed across the sampled pages."
    elif nver or part:
        status = "partial"
        bits = []
        if nver:
            bits.append(f"{nver} check(s) require rendered/browser validation (not executed)")
        if part:
            bits.append(f"{part} check(s) only partially verifiable (no external verification)")
        note = "; ".join(bits) + "."
    else:
        status, note = "healthy", "All checks passed across the sampled pages."

    if key == "corroboration" and not external_done:
        for c in checks:
            if c["id"] == "external_verification":
                c["note"] = "External corroboration lookups were disabled for this run."

    pages_assessed = 0 if not_assessed_note else (date_pages or pages if key == "freshness" else pages)
    confidence = _confidence(area_findings, nver or part)
    return {"key": key, "label": label, "status": status, "status_label": STATUS.get(status, status),
            "checks": checks, "checks_total": len(checks), "passed": passed, "failed": failed,
            "not_verified": nver, "partial_checks": part, "pages_assessed": pages_assessed,
            "findings": len(area_findings), "confidence": confidence, "note": note}


def _checks_for(key, area_findings, assessable, external_verified=None) -> List[Dict[str, Any]]:
    titles = [f.get("title", "").lower() for f in area_findings]
    out = []
    for cid, label, keywords, kind in _REG.get(key, []):
        if not assessable:
            state, note = NOT_VERIFIED, "Area not assessed."
        elif any(any(k in t for t in titles) for k in keywords) if keywords else False:
            state, note = FAIL, "A finding was detected for this check."
        elif kind == "browser":
            state, note = NOT_VERIFIED, "Requires executing the page in a browser; this audit is static."
        elif kind == "external":
            # PARTIAL by default (on-page signals only); real state when --verify-external is used.
            if external_verified is True:
                state, note = PASS, "Verified against an independent external source (Wikidata / declared profiles)."
            elif external_verified is False:
                state, note = FAIL, "External verification ran but found no corroborating source."
            else:
                state, note = PARTIAL, "On-page signals only; run --verify-external for independent verification."
        else:
            state, note = PASS, "No issue detected across the sampled pages."
        out.append({"id": cid, "label": label, "state": state, "note": note})
    return out


def _confidence(area_findings, has_unverified) -> str:
    order = {"high": 3, "medium": 2, "low": 1}
    if area_findings:
        lowest = min(area_findings, key=lambda f: order.get(f.get("confidence", "high"), 3))
        return lowest.get("confidence", "high")
    return "medium" if has_unverified else "high"
