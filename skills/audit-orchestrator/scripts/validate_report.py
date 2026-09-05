#!/usr/bin/env python3
"""Validate an audit report JSON against the marketplace's fixed schema.

Usage:
    python validate_report.py report.json
    python run_audit.py https://example.com | python validate_report.py -

Exit 0 if valid, 1 if problems are found (printed to stderr).
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from auditlib import report as report_mod  # noqa: E402


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: validate_report.py <report.json|->", file=sys.stderr)
        return 2
    src = argv[0]
    data = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    try:
        rpt = json.loads(data)
    except json.JSONDecodeError as e:
        print(f"INVALID: not valid JSON: {e}", file=sys.stderr)
        return 1

    errs = report_mod.validate(rpt)
    if errs:
        print("INVALID:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"VALID: {rpt.get('site')} — {rpt['summary']['total_findings']} finding(s), "
          f"schema OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
