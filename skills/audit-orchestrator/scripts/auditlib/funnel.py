"""Visibility funnel — the discoverability score reasoned as a pipeline, not a flat sum.

Appendix A/B: to be found and cited, a page must clear four gates *in order* — the crawler must
**reach** it, **read** it, **quote** a clear fact from it, and **trust** it. An early-gate failure
dominates: if the crawler is blocked, structured data is moot. This module scores each gate and
names the **bottleneck** (the weakest gate, where a fix unlocks the most downstream value) — a
mechanism-sound lens over the same findings, alongside the headline score. Pure function; attached
as ``report['funnel']``.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import scoring

# gate key, label, the finding categories that gate it, and the one-line mechanism.
GATES = [
    ("reach", "Reach", {"crawlability", "reachability", "indexability"},
     "Can a crawler get in and be allowed to index the page?"),
    ("read", "Read", {"js-render-gap", "extractability"},
     "Can a fetch-only machine actually read the content as text?"),
    ("quote", "Quote", {"structured-data", "entity-identity"},
     "Can it lift a clear, attributable fact to cite?"),
    ("trust", "Trust", {"freshness", "corroboration"},
     "Does the fact look current and agreed-upon enough to repeat?"),
]
_BANDS = [(90, "healthy"), (70, "warning"), (0, "critical")]


def build(report: Dict[str, Any]) -> Dict[str, Any]:
    findings = [f for f in report.get("findings", [])
                if f.get("dimension") == "discoverability" and f.get("kind") != "opportunity"]
    gates: List[Dict[str, Any]] = []
    for key, label, cats, mech in GATES:
        members = [f for f in findings if f.get("category") in cats]
        score = max(0.0, min(100.0, round(100 - sum(scoring.penalty_of(f) for f in members), 1)))
        gates.append({"key": key, "label": label, "mechanism": mech, "score": score,
                      "status": _status(score), "findings": len(members)})
    weakest = min(gates, key=lambda g: g["score"])
    # The pipeline is only as strong as its narrowest gate; downstream gates can't help until it's fixed.
    downstream = [g["label"] for g in gates
                  if [x[0] for x in GATES].index(g["key"]) > [g2["key"] for g2 in gates].index(weakest["key"])]
    note = (f"Bottleneck: **{weakest['label']}** ({weakest['score']:.0f}/100). "
            + (f"Fixing it is what unlocks {', '.join(downstream)} downstream."
               if weakest["score"] < 90 and downstream else
               "All gates are clearing well.")) if gates else ""
    return {"gates": gates, "weakest": weakest["key"], "weakest_label": weakest["label"],
            "weakest_score": weakest["score"], "note": note}


def _status(score: float) -> str:
    for cut, st in _BANDS:
        if score >= cut:
            return st
    return "critical"
