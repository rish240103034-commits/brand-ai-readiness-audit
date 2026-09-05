#!/usr/bin/env python3
"""Standalone runner for crawl-render-audit.

Checks crawlability (robots.txt incl. AI-bot access, status, noindex, sitemap) and
JS-render gaps. Emits a schema-valid mini audit report so the skill is useful on its own;
the orchestrator calls the same analyze() to compose the full report. Read-only.
"""
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

from auditlib.runner import run_single_skill  # noqa: E402
from auditlib.checks import crawl_render       # noqa: E402


def main(argv=None) -> int:
    return run_single_skill(
        "crawl-render-audit", [crawl_render.analyze],
        description="Crawlability & JS-render-gap audit for one site.", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
