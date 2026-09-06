"""Citation-readiness score.

Discoverability answers "can an AI *find* the brand?"  Citation readiness
answers the harder question judges care about: "when an AI has found the brand,
will it *quote and attribute* it — or paraphrase a competitor instead?"

It is a deterministic 0-100 composite of five signals, each derived from data
already in the report (the claim inventory, the hallucination scan, the
knowledge graph, the answer-readiness scorecard). No new crawling; no live
search. When the opt-in external verifier ran, its corroboration lifts the
corroboration component — otherwise that component is capped and the ``limits``
field says so, so the number is never overstated.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .scoring import _grade

# component -> weight (sums to 1.0)
_WEIGHTS = {
    "machine_quotability": 0.30,
    "extractability": 0.20,
    "corroboration": 0.25,
    "stability": 0.15,
    "attribution": 0.10,
}


def build(report: Dict[str, Any]) -> Dict[str, Any]:
    """Compute citation readiness from an already-assembled report. Never raises."""
    claims = (report.get("claims") or {}).get("claims", [])
    csum = (report.get("claims") or {}).get("summary", {})
    consistency = report.get("consistency") or {}
    kg = (report.get("knowledge_graph") or {}).get("summary", {})
    ext = report.get("external_verification")

    comps: List[Dict[str, Any]] = []

    # 1. Machine quotability — share of facts an AI can lift verbatim from schema.
    mq = csum.get("machine_readable_pct", 0)
    comps.append(_c("machine_quotability", "Machine-quotable facts", mq,
                    f"{csum.get('machine_readable_pct', 0)}% of extracted claims are in structured data."))

    # 2. Extractability — share of facts present as readable text (not locked away).
    total = csum.get("total", 0) or 0
    in_text = sum(1 for c in claims if c.get("in_visible_text"))
    ex = round(in_text / total * 100) if total else 0
    comps.append(_c("extractability", "Facts readable as text", ex,
                    f"{in_text}/{total} claims appear in visible page text."))

    # 3. Corroboration — do independent sources agree? External verify lifts the cap.
    limits = None
    if ext and ext.get("verified"):
        cor = 100
        cdetail = "Corroborated off-site (opt-in external verification confirmed identity links)."
    else:
        offsite = sum(1 for c in claims if c.get("off_site"))
        if offsite >= 2:
            cor, cdetail = 65, f"{offsite} declared off-site identity links, but not externally verified."
        elif offsite == 1:
            cor, cdetail = 50, "One declared off-site identity link, not externally verified."
        else:
            cor, cdetail = 30, "No off-site identity links found to corroborate the brand."
        limits = ("Corroboration is capped without live verification. Re-run with "
                  "--verify-external to confirm identity links (Wikidata + declared profiles).")
    comps.append(_c("corroboration", "Independent corroboration", cor, cdetail))

    # 4. Stability — a self-contradicting site is un-citable; each conflict cuts hard.
    conflicts = len(consistency.get("conflicts", []))
    stab = max(0, 100 - 30 * conflicts)
    comps.append(_c("stability", "Fact stability (no self-contradiction)", stab,
                    "No contradictory facts detected." if not conflicts
                    else f"{conflicts} self-contradiction(s) make facts risky to cite."))

    # 5. Attribution — is there a citable entity (Org schema) + canonical identity?
    attr = 0
    if kg.get("has_identity") or kg.get("nodes", 0) > 0:
        attr += 60
    if any(c.get("type") in ("identity_link", "social_profile") for c in claims):
        attr += 40
    attr = min(100, attr)
    comps.append(_c("attribution", "Citable entity identity", attr,
                    "Organization entity + identity links present." if attr >= 90
                    else "Weak or missing canonical entity for an AI to attribute a quote to."))

    score = round(sum(c["value"] * _WEIGHTS[c["key"]] for c in comps))
    out = {
        "score": score,
        "grade": _grade(score),
        "headline": f"Citation Readiness {score}/100 ({_grade(score)})",
        "components": comps,
        "weakest": min(comps, key=lambda c: c["value"])["key"] if comps else None,
        "method": ("Weighted composite of machine-quotability, extractability, corroboration, "
                   "stability and attribution. Deterministic; derived from the claim inventory."),
    }
    if limits:
        out["limits"] = limits
    return out


def _c(key, label, value, detail):
    return {"key": key, "label": label, "value": int(round(value)),
            "weight": _WEIGHTS[key], "detail": detail}
