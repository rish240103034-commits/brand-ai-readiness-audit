"""AI answer simulation.

Given the extracted claim inventory, simulate — deterministically, offline —
what an answer engine would do when a user asks a common question about the
brand: could it answer, what would it base the answer on, and crucially *would
it cite this site* or paraphrase without attribution?

This is not a call to any model. It is a transparent projection: an answer
engine can only state a fact it can extract, and it prefers to cite facts that
are machine-readable and non-contradictory. We apply exactly that rule to the
claims we found, so every row is explainable from the report itself.
"""
from __future__ import annotations

from typing import Any, Dict, List

# question template -> claim types that would answer it
_QUESTIONS = [
    ("Who is {brand} and what do they do?", ["brand_name", "offering"]),
    ("When was {brand} founded?", ["founding_year"]),
    ("Where is {brand} based / headquartered?", ["location"]),
    ("What does {brand} sell or offer?", ["offering"]),
    ("How do I contact {brand}?", ["contact"]),
    ("How much do {brand}'s products/services cost?", ["price_signal"]),
    ("Is {brand} a legitimate, established company?",
     ["identity_link", "social_profile", "founding_year", "brand_name"]),
]


def build(report: Dict[str, Any], ctx=None) -> List[Dict[str, Any]]:
    """Return one simulated answer per common question. Never raises."""
    claims = (report.get("claims") or {}).get("claims", [])
    if not claims:
        return []
    brand = claims[0].get("subject") or "the brand"
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for c in claims:
        by_type.setdefault(c["type"], []).append(c)

    rows = []
    for template, types in _QUESTIONS:
        support = [c for t in types for c in by_type.get(t, [])]
        rows.append(_simulate(template.format(brand=brand), support))
    return rows


def _simulate(question: str, support: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not support:
        return {
            "question": question,
            "answerable": "no",
            "basis": "none",
            "would_cite": False,
            "confidence": "low",
            "supporting_claims": [],
            "gap": "No claim about this was found on the site — the AI would guess or omit the brand.",
        }
    contradicted = [c for c in support if c["status"] == "contradicted"]
    structured = [c for c in support if c["in_structured_data"]]
    textual = [c for c in support if c["in_visible_text"]]

    if contradicted:
        answerable, basis, cite = "risky", "conflicting", False
        gap = "The site contradicts itself here; an AI may state the wrong value or refuse to cite."
    elif structured and textual:
        answerable, basis, cite = "yes", "structured", True
        gap = ""
    elif structured:
        answerable, basis, cite = "yes", "structured", True
        gap = "Fact is in schema but thin in the readable copy — fine for machines, weak for humans."
    elif textual:
        answerable, basis, cite = "yes", "text", False
        gap = "Fact is readable but not machine-marked — an AI may paraphrase without citing the site."
    else:  # off-site / unverified only
        answerable, basis, cite = "partial", "off-site", False
        gap = "Only inferable from off-site links; the site itself doesn't state it clearly."

    conf = "high" if any(c["confidence"] == "high" for c in support) else \
           "medium" if any(c["confidence"] == "medium" for c in support) else "low"
    return {
        "question": question,
        "answerable": answerable,
        "basis": basis,
        "would_cite": cite,
        "confidence": conf,
        "supporting_claims": [c["id"] for c in support][:5],
        "gap": gap,
    }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll-up used by the report `scores`/narrative layer."""
    total = len(rows) or 1
    answered = sum(1 for r in rows if r["answerable"] in ("yes", "partial"))
    cited = sum(1 for r in rows if r["would_cite"])
    return {
        "questions": len(rows),
        "answerable_pct": round(answered / total * 100),
        "citable_pct": round(cited / total * 100),
    }
