"""Finding model, severity handling, and audit-report assembly against the fixed schema.

The report shape matches (and extends) the contest's required schema:
  site, audited_at, summary{counts by severity}, findings[]
Each finding carries: id, title, severity, evidence, suggested_action{summary, priority}.
Extra fields (category, dimension, confidence, details) are additive and allowed.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

SEVERITIES = ["critical", "high", "medium", "low", "info"]
_SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}

# Discoverability vs engagement — the two halves of the Round-2 problem.
DIMENSIONS = {"discoverability", "engagement"}


@dataclass
class Finding:
    title: str
    severity: str
    evidence: str
    suggested_action_summary: str
    suggested_action_priority: str
    category: str = "general"          # e.g. crawlability, structured-data
    dimension: str = "discoverability"  # discoverability | engagement
    confidence: str = "high"           # high | medium | low
    affected_pages: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    id: str = ""                        # assigned by the report builder
    # --- richer evidence model (all optional; empty falls back gracefully) ---------
    why: str = ""                       # SPECIFIC reason this finding hurts (per-check)
    how_to_fix: str = ""               # concrete, mechanism-sound remediation steps
    scope: str = ""                    # e.g. "8 of 12 pages (67%)"
    measurements: Dict[str, Any] = field(default_factory=dict)  # observed numbers
    expected_impact: str = ""          # what fixing it is expected to improve
    kind: str = "defect"               # defect | opportunity (proactive)

    def normalized_severity(self) -> str:
        s = (self.severity or "").lower()
        return s if s in _SEV_RANK else "medium"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "title": self.title,
            "severity": self.normalized_severity(),
            "dimension": self.dimension,
            "category": self.category,
            "confidence": self.confidence,
            "kind": self.kind,
            "evidence": self.evidence,
            "affected_pages": self.affected_pages[:10],
            "suggested_action": {
                "summary": self.suggested_action_summary,
                "priority": (self.suggested_action_priority or "medium").lower(),
            },
            "details": self.details,
        }
        # Emit the richer fields only when populated, so the schema floor stays clean.
        if self.why:
            d["why"] = self.why
        if self.how_to_fix:
            d["how_to_fix"] = self.how_to_fix
        if self.scope:
            d["scope"] = self.scope
        if self.measurements:
            d["measurements"] = self.measurements
        if self.expected_impact:
            d["expected_impact"] = self.expected_impact
        return d


def build_report(
    site: str,
    findings: List[Finding],
    pages_crawled: int = 0,
    notes: Optional[List[str]] = None,
    started_at: Optional[str] = None,
) -> Dict[str, Any]:
    # Deterministic ordering: severity, then dimension, then title.
    ordered = sorted(
        findings,
        key=lambda f: (_SEV_RANK.get(f.normalized_severity(), 99), f.dimension, f.title.lower()),
    )
    for i, f in enumerate(ordered, start=1):
        f.id = f"F-{i:03d}"

    counts = {s: 0 for s in SEVERITIES}
    dim_counts = {"discoverability": 0, "engagement": 0}
    for f in ordered:
        counts[f.normalized_severity()] += 1
        if f.dimension in dim_counts:
            dim_counts[f.dimension] += 1

    # Always include the four standard severity counts (0 if none) so the counts-by-severity
    # summary matches the handout's floor shape exactly; `info` only when it actually occurs.
    summary: Dict[str, Any] = {"total_findings": len(ordered)}
    for s in ("critical", "high", "medium", "low"):
        summary[s] = counts[s]
    if counts["info"]:
        summary["info"] = counts["info"]
    summary["by_dimension"] = dim_counts

    return {
        "site": site,
        "audited_at": _now_iso(),
        "started_at": started_at or _now_iso(),
        "auditor": "brand-ai-readiness-audit/2.5",
        "pages_crawled": pages_crawled,
        "summary": summary,
        "findings": [f.to_dict() for f in ordered],
        "notes": notes or [],
    }


def scope_str(n: int, total: int) -> str:
    """A consistent 'N of M pages (P%)' scope string for finding evidence."""
    total = total or 0
    if total <= 0:
        return f"{n} page(s)"
    return f"{n} of {total} page(s) ({round(100 * n / total)}%)"


def merge(*groups: List[Finding]) -> List[Finding]:
    out: List[Finding] = []
    for g in groups:
        out.extend(g or [])
    return out


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def dumps(report: Dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)


# --- minimal self-validation (used by scripts/validate) ---------------------------
REQUIRED_FINDING_KEYS = {"id", "title", "severity", "evidence", "suggested_action"}
REQUIRED_ACTION_KEYS = {"summary", "priority"}


def validate(report: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    for key in ("site", "audited_at", "summary", "findings"):
        if key not in report:
            errs.append(f"missing top-level key: {key}")
    if "summary" in report and "total_findings" not in report["summary"]:
        errs.append("summary.total_findings missing")
    for i, f in enumerate(report.get("findings", [])):
        missing = REQUIRED_FINDING_KEYS - set(f)
        if missing:
            errs.append(f"finding[{i}] missing keys: {sorted(missing)}")
        act = f.get("suggested_action", {})
        amiss = REQUIRED_ACTION_KEYS - set(act if isinstance(act, dict) else {})
        if amiss:
            errs.append(f"finding[{i}].suggested_action missing: {sorted(amiss)}")
        if f.get("severity") not in SEVERITIES:
            errs.append(f"finding[{i}] invalid severity: {f.get('severity')}")
    return errs
