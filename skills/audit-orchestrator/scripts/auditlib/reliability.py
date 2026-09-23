"""Crawl-reliability / confidence guard.

A score computed from a single readable page looks identical to one from a full sample — but it is
not the same thing. When a site rate-limits, blocks, or times out the crawler (common on
bot-protected retail sites), the audit still emits a confident-looking number from almost no
evidence. This guard inspects *how much the crawl actually saw* — pages read vs. fetches that timed
out or were blocked — and, when the evidence is too thin, marks the report **provisional** so the
score is not mistaken for a full assessment. Deterministic; never raises; changes no finding.
"""
from __future__ import annotations

from typing import Any, Dict

THIN_PAGES = 2   # ≤ this many readable pages ⇒ too little evidence to trust the headline score


def assess(pages_readable: int, http_failures: int = 0, requests_made: int = 0) -> Dict[str, Any]:
    """Return a reliability block describing how much the crawl actually analyzed."""
    provisional = pages_readable <= THIN_PAGES
    if not provisional:
        reason = ""
    elif http_failures:
        reason = (f"Only {pages_readable} page(s) were readable; {http_failures} fetch(es) timed out "
                  "or were blocked. The site most likely rate-limited or blocked the crawler, so most "
                  "of it could not be analyzed — treat the score as provisional.")
    else:
        reason = (f"Only {pages_readable} page(s) were available to analyze, so the score is based on "
                  "limited evidence — treat it as provisional.")
    return {
        "pages_readable": pages_readable,
        "http_failures": http_failures,
        "requests_made": requests_made,
        "confidence": "low" if provisional else "ok",
        "provisional": provisional,
        "reason": reason,
    }


def apply(report: Dict[str, Any], block: Dict[str, Any]) -> Dict[str, Any]:
    """Attach the reliability block; when provisional, flag the score and prepend a prominent note."""
    report["reliability"] = block
    if block.get("provisional"):
        sc = report.get("score")
        if isinstance(sc, dict):
            sc["provisional"] = True
            sc["confidence"] = "low"
            head = sc.get("headline", "")
            if head and not head.startswith("Provisional"):
                sc["headline"] = "Provisional — " + head
        report.setdefault("notes", []).insert(0, "LOW CONFIDENCE: " + block["reason"])
    return block
