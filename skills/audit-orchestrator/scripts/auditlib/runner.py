"""Shared CLI runner for standalone skills.

Every non-entrypoint skill's `scripts/run.py` delegates here so that argument parsing,
input validation, error handling, logging, and exit codes are implemented once and behave
identically. A standalone skill must never crash the process: on any failure it still emits
a schema-valid (possibly fatal) report and returns a documented exit code.

Exit codes (shared with the orchestrator):
    0  audit completed (findings may be present)
    1  audit completed only partially (one or more checks errored)
    2  bad input (invalid URL, blocked target) — nothing was audited
"""
from __future__ import annotations

import argparse
import logging
from typing import Callable, List, Sequence

from . import http
from . import report as report_mod
from .context import AuditContext
from .logutil import configure_logging

LOG = logging.getLogger("audit.runner")

AnalyzeFn = Callable[[AuditContext], List[report_mod.Finding]]


def build_arg_parser(description: str, with_external: bool = False) -> argparse.ArgumentParser:
    """Return the argument parser shared by every standalone skill runner."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("url", help="Website URL or domain to audit")
    ap.add_argument("--max-pages", type=int, default=None, help="Max pages to sample")
    ap.add_argument("--timeout", type=int, default=None, help="Per-request timeout (seconds)")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose (DEBUG) logging")
    ap.add_argument("--quiet", "-q", action="store_true", help="Only errors")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate inputs and print the plan without making network calls")
    if with_external:
        ap.add_argument("--no-external", action="store_true",
                        help="Disable off-site corroboration lookups")
    return ap


def run_single_skill(skill_label: str, analyze_fns: Sequence[AnalyzeFn],
                     description: str, argv: Sequence[str] = None,
                     with_external: bool = False) -> int:
    """Parse args, build a shared context, run one skill's checks, and print a report.

    Args:
        skill_label: human-readable id used in the report note (e.g. "crawl-render-audit").
        analyze_fns: one or more ``analyze(ctx) -> [Finding]`` callables for this skill.
        description: CLI help text.
        argv: argument vector (defaults to ``sys.argv[1:]``).
        with_external: whether to expose the ``--no-external`` flag.

    Returns:
        A process exit code (0 ok, 1 partial, 2 bad input).
    """
    from .config import CONFIG

    ap = build_arg_parser(description, with_external=with_external)
    args = ap.parse_args(argv)
    configure_logging(verbose=args.verbose, quiet=args.quiet)

    cfg = CONFIG.derive(
        max_pages=args.max_pages,
        timeout=args.timeout,
    )
    external = not getattr(args, "no_external", False)

    valid, target, reason = http.validate_target(args.url, cfg)
    if not valid:
        LOG.error("invalid target %r: %s", args.url, reason)
        rpt = report_mod.build_report(
            site=args.url, findings=[_bad_input_finding(reason)], pages_crawled=0,
            notes=[f"bad input: {reason}"])
        print(report_mod.dumps(rpt))
        return 2

    if args.dry_run:
        _print_dry_run(target, cfg, [skill_label], external)
        return 0

    partial = False
    try:
        ctx = AuditContext.build(target, cfg=cfg, external_lookups=external)
    except Exception as e:  # never crash a standalone skill
        LOG.error("crawl failed: %s", e)
        rpt = report_mod.build_report(site=http.host_of(target),
                                      findings=[_fatal_finding(f"crawl failed: {e}")],
                                      pages_crawled=0, notes=[str(e)])
        print(report_mod.dumps(rpt))
        return 2

    if not ctx.pages:
        rpt = report_mod.build_report(site=http.host_of(target),
                                      findings=[_fatal_finding("homepage not readable")],
                                      pages_crawled=0, notes=ctx.notes)
        print(report_mod.dumps(rpt))
        return 2

    findings: List[report_mod.Finding] = []
    for fn in analyze_fns:
        try:
            findings.extend(fn(ctx) or [])
        except Exception as e:
            partial = True
            LOG.warning("check in %s errored: %s", skill_label, e)
            ctx.notes.append(f"check in {skill_label} errored and was skipped: {e}")

    rpt = report_mod.build_report(
        site=http.host_of(target), findings=findings, pages_crawled=len(ctx.pages),
        notes=ctx.notes + [f"Partial report: {skill_label} only."])
    print(report_mod.dumps(rpt))
    return 1 if partial else 0


def _print_dry_run(target: str, cfg, skills: List[str], external: bool) -> None:
    """Print the crawl/analysis plan without touching the network."""
    print("DRY RUN — no network calls will be made")
    print(f"  target       : {target}")
    print(f"  host         : {http.host_of(target)}")
    print(f"  max_pages    : {cfg.max_pages}")
    print(f"  timeout      : {cfg.timeout}s  (retries: {cfg.max_retries}, backoff: {cfg.backoff_base}s)")
    print(f"  user_agent   : {cfg.user_agent}")
    print(f"  external     : {external}")
    print(f"  skills       : {', '.join(skills)}")


def _fatal_finding(message: str) -> report_mod.Finding:
    """Finding used when the site could not be audited at all."""
    return report_mod.Finding(
        title="Site could not be audited", severity="critical",
        dimension="discoverability", category="reachability", evidence=message,
        suggested_action_summary=("Ensure the URL is correct and publicly reachable (DNS, TLS, "
                                  "and a 2xx homepage); a site a crawler cannot load cannot be "
                                  "found or cited at all."),
        suggested_action_priority="critical")


def _bad_input_finding(reason: str) -> report_mod.Finding:
    """Finding used when the supplied target failed validation."""
    return report_mod.Finding(
        title="Invalid audit target", severity="critical",
        dimension="discoverability", category="input", evidence=reason,
        suggested_action_summary="Provide a public http(s) URL or domain (not localhost or a private address).",
        suggested_action_priority="critical")
