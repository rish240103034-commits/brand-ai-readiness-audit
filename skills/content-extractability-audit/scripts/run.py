#!/usr/bin/env python3
"""Standalone runner for content-extractability-audit (text vs non-text facts). Read-only."""
from __future__ import annotations

import os
import sys


def _find_auditlib() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        cand = os.path.join(d, "skills", "audit-orchestrator", "scripts")
        if os.path.isdir(os.path.join(cand, "auditlib")):
            return cand
        d = os.path.dirname(d)
    raise ImportError("auditlib not found; run this within the marketplace tree.")


sys.path.insert(0, _find_auditlib())

from auditlib.runner import run_single_skill    # noqa: E402
from auditlib.checks import extractability        # noqa: E402


def main(argv=None) -> int:
    return run_single_skill(
        "content-extractability-audit", [extractability.analyze],
        description="Content-extractability audit for one site.", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
