#!/usr/bin/env python3
"""Round-4 demo companion: a READ-ONLY terminal viewer for an audit report.

It renders a report JSON that the frozen v2.7.0 marketplace engine has already produced
(`run_audit.py ... --out report.json`). It performs NO crawling, NO scoring, and NO
detection of its own — it only formats the engine's output for a clean live drill-down.
Because it reads the engine's canonical JSON, it can never disagree with the engine.

This file is NOT part of the marketplace (not referenced by marketplace.json) and does not
alter the audited engine in any way.

Usage:
    python round4/view_report.py report.json                 # prioritized summary
    python round4/view_report.py report.json --finding F-001 # drill into one finding
    python round4/view_report.py report.json --top 5         # top N by priority
    python round4/view_report.py report.json --severity high,critical
"""
from __future__ import annotations

import argparse
import json
import sys

# This companion (unlike the frozen engine) is free to guarantee UTF-8 stdout, so it prints
# reports containing non-ASCII evidence safely even on a cp1252 Windows console.
try:  # pragma: no cover - platform dependent
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
BAR = "─" * 72


def load(path: str) -> dict:
    """Load a report JSON (always UTF-8, so it is Windows-safe)."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _header(rpt: dict) -> None:
    score = rpt.get("score", {})
    s = rpt.get("summary", {})
    print(BAR)
    print(f"  {rpt.get('site', '?')}   —   {score.get('headline', 'AI Visibility Score n/a')}")
    print(BAR)
    print(f"  discoverability {score.get('discoverability', '?')}/100   "
          f"engagement {score.get('engagement', '?')}/100   "
          f"pages crawled: {rpt.get('pages_crawled', '?')}")
    print(f"  findings: {s.get('total_findings', 0)}  "
          f"(critical {s.get('critical', 0)}, high {s.get('high', 0)}, "
          f"medium {s.get('medium', 0)}, low {s.get('low', 0)})")
    rel = rpt.get("reliability")
    if isinstance(rel, dict) and rel.get("provisional"):
        print(f"  ⚠ score is PROVISIONAL: {rel.get('reason', 'thin crawl')}")
    print(BAR)


def _finding_line(f: dict) -> str:
    return (f"[P{f.get('priority', '?')}] {f.get('severity', '?').upper():<8} "
            f"{f.get('category', ''):<16} {f.get('title', '')}")


def _drill(f: dict) -> None:
    """Print the full signal→evidence→severity→fix→priority chain for one finding."""
    print()
    print(_finding_line(f))
    print(f"    id            : {f.get('id')}   dimension: {f.get('dimension')}   "
          f"confidence: {f.get('confidence')}   impact: {f.get('impact', '?')}/5")
    print(f"    evidence      : {f.get('evidence', '')}")
    if f.get("scope"):
        print(f"    scope         : {f.get('scope')}")
    if f.get("why"):
        print(f"    why it hurts  : {f.get('why')}")
    act = f.get("suggested_action", {})
    fix = f.get("how_to_fix") or act.get("summary", "")
    print(f"    suggested fix : {fix}")
    print(f"    fix priority  : {act.get('priority', '?')}")
    if f.get("expected_impact"):
        print(f"    expected gain : {f.get('expected_impact')}")
    if f.get("measurements"):
        print(f"    measurements  : {json.dumps(f.get('measurements'), ensure_ascii=False)}")
    pages = f.get("affected_pages") or []
    if pages:
        print(f"    affected pages: {len(pages)} — e.g. {pages[0]}")


def _filter(findings, severities):
    if not severities:
        return findings
    want = {s.strip().lower() for s in severities.split(",")}
    return [f for f in findings if f.get("severity", "").lower() in want]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read-only terminal viewer for an audit report JSON.")
    ap.add_argument("report", nargs="?", default="report.json", help="Path to the report JSON")
    ap.add_argument("--finding", help="Drill into a single finding id, e.g. F-001")
    ap.add_argument("--top", type=int, default=None, help="Show only the top N findings by priority")
    ap.add_argument("--severity", help="Comma-separated severities to include (e.g. high,critical)")
    args = ap.parse_args(argv)

    try:
        rpt = load(args.report)
    except FileNotFoundError:
        print(f"error: report not found: {args.report}\n"
              f"Run the engine first, e.g.:\n"
              f"  python skills/audit-orchestrator/scripts/run_audit.py sqlite.org --out {args.report}",
              file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"error: {args.report} is not valid JSON: {e}", file=sys.stderr)
        return 2

    findings = rpt.get("findings", [])

    if args.finding:
        match = next((f for f in findings if f.get("id") == args.finding), None)
        if not match:
            print(f"error: no finding with id {args.finding}", file=sys.stderr)
            return 2
        _header(rpt)
        _drill(match)
        return 0

    _header(rpt)
    shown = _filter(findings, args.severity)
    shown = sorted(shown, key=lambda f: f.get("priority", 999))
    if args.top:
        shown = shown[: args.top]
    print(f"\n  Prioritized findings (most-actionable first): showing {len(shown)} of {len(findings)}\n")
    for f in shown:
        print("  " + _finding_line(f))
        print(f"        └ {f.get('evidence', '')[:100]}")
    print(f"\n  Drill in with:  python round4/view_report.py {args.report} --finding F-001")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
