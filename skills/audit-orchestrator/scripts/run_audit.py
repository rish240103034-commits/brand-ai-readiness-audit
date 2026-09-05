#!/usr/bin/env python3
"""Entrypoint runner for the brand-ai-readiness-audit marketplace.

Crawls a small, robots-respecting, SSRF-safe sample of a website, runs every selected check
(discoverability + engagement), composes the findings into one audit report against the fixed
schema, and prints it as JSON (or HTML).

Usage:
    python run_audit.py https://example.com [--max-pages 12] [--no-external]
        [--profile strict|balanced|lenient] [--crawl-scope host|domain]
        [--skills crawl-render,structured-data] [--format json|html|md] [--out FILE]
        [--csv FILE] [--dry-run] [--verbose|--quiet]

Read-only and recommend-only. Exit codes: 0 completed, 1 partial (a check errored),
2 bad input / unauditable.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from auditlib import http, report as report_mod            # noqa: E402
from auditlib.config import make_config, VALID_PROFILES     # noqa: E402
from auditlib.context import AuditContext                   # noqa: E402
from auditlib.logutil import configure_logging, get_logger  # noqa: E402
from auditlib.registry import discover_skills, select_skills  # noqa: E402
from auditlib.scoring import score_report                   # noqa: E402
from auditlib import analytics as analytics_mod             # noqa: E402
from auditlib import coverage as coverage_mod               # noqa: E402
from auditlib import pages as pages_mod                     # noqa: E402
from auditlib import proactive as proactive_mod             # noqa: E402
from auditlib import exports as exports_mod                 # noqa: E402
from auditlib import render as render_mod                   # noqa: E402
from auditlib.checks import freshness as _freshness         # noqa: E402

LOG = get_logger("orchestrator")

EXIT_OK, EXIT_PARTIAL, EXIT_BADINPUT = 0, 1, 2


def run(url: str, cfg, external: bool = True, only_skills=None):
    """Crawl once, run the selected skills, and return (report_dict, exit_code)."""
    started = report_mod._now_iso()
    t0 = time.time()

    skills = select_skills(discover_skills(), only_skills)
    if not skills:
        LOG.error("no skills selected/available")
        return _fatal_report(http.host_of(url), "no skills available", started), EXIT_BADINPUT

    fetcher = http.Fetcher(cfg=cfg)
    try:
        ctx = AuditContext.build(url, cfg=cfg, external_lookups=external, fetcher=fetcher)
    except Exception as e:  # pragma: no cover - defensive
        return _fatal_report(http.host_of(url), f"crawl failed: {e}", started), EXIT_BADINPUT

    if not ctx.pages:
        home = ctx.responses[0] if ctx.responses else None
        reason = (home.error or f"status {home.status}") if home else "no response"
        return _fatal_report(http.host_of(url), f"homepage not readable ({reason})", started), EXIT_BADINPUT

    all_findings, notes, partial = _run_skills_concurrently(skills, ctx, cfg)

    notes.append(f"Crawled {len(ctx.pages)} page(s) in {int((time.time()-t0)*1000)} ms; "
                 f"{fetcher.request_count} HTTP request(s). Static, read-only analysis.")
    notes.extend(ctx.notes)

    rpt = report_mod.build_report(
        site=http.host_of(url), findings=all_findings, pages_crawled=len(ctx.pages),
        notes=notes, started_at=started)
    rpt["profile"] = cfg.profile
    rpt["skills_run"] = [s.id for s in skills]
    score_report(rpt)          # attach AI Visibility Score + grade
    rpt["opportunities"] = proactive_mod.build(ctx)  # context-justified, non-defect recommendations
    # Coverage matrix: what each area actually assessed (healthy vs not-assessed vs partial).
    signals = {"date_signal_pages": _freshness.count_date_signal_pages(ctx.pages),
               "external_lookups": external}
    rpt["coverage"] = coverage_mod.build(rpt, signals)
    rpt["pages"] = pages_mod.build(ctx, rpt)  # per-page detail for the page explorer
    analytics_mod.attach(rpt)  # attach the analyst layer (pillars, matrix, projection, …)

    errs = report_mod.validate(rpt)
    if errs:
        rpt["notes"].append("SCHEMA WARNINGS: " + "; ".join(errs))
    return rpt, (EXIT_PARTIAL if partial else EXIT_OK)


def _run_skills_concurrently(skills, ctx, cfg):
    """Run each skill's checks in a thread pool under a global timeout.

    Checks are I/O-light (pages are already crawled), so threads add safety and speed without
    extra host load. Returns (findings, notes, partial). A skill that errors or exceeds the
    global ``analysis_timeout`` is skipped and marks the report partial rather than hanging.
    """
    import concurrent.futures as cf

    def _run_one(skill):
        out = []
        for fn in skill.analyze_fns:
            out.extend(fn(ctx) or [])
        return out

    findings, notes, partial = [], [], False
    deadline = cfg.analysis_timeout
    with cf.ThreadPoolExecutor(max_workers=min(cfg.max_workers, max(1, len(skills)))) as ex:
        future_to_skill = {ex.submit(_run_one, s): s for s in skills}
        try:
            for fut in cf.as_completed(future_to_skill, timeout=deadline):
                skill = future_to_skill[fut]
                try:
                    findings.extend(fut.result() or [])
                except Exception as e:
                    partial = True
                    notes.append(f"check in '{skill.id}' errored and was skipped: {e}")
                    LOG.warning("check in %s errored: %s", skill.id, e)
        except cf.TimeoutError:
            unfinished = [s.id for f, s in future_to_skill.items() if not f.done()]
            partial = True
            notes.append(f"analysis timed out after {deadline}s; skipped: {', '.join(unfinished)}")
            LOG.error("analysis timeout; unfinished skills: %s", unfinished)
    return findings, notes, partial


def _fatal_report(site: str, message: str, started: str) -> dict:
    """Build a schema-valid report describing why the site could not be audited."""
    f = report_mod.Finding(
        title="Site could not be audited", severity="critical", dimension="discoverability",
        category="reachability", evidence=message,
        suggested_action_summary=("Ensure the URL is correct and publicly reachable (DNS, TLS, and a 2xx "
                                  "homepage). A site a crawler cannot load cannot be found or cited at all."),
        suggested_action_priority="critical")
    rpt = report_mod.build_report(site=site, findings=[f], pages_crawled=0,
                                  notes=[message], started_at=started)
    score_report(rpt)
    analytics_mod.attach(rpt)
    return rpt


def build_parser() -> argparse.ArgumentParser:
    """Construct the orchestrator CLI parser."""
    ap = argparse.ArgumentParser(description="Audit a website for AI-discoverability and on-site-engagement problems.")
    ap.add_argument("url", help="Website URL or domain to audit")
    ap.add_argument("--max-pages", type=int, default=None, help="Max pages to sample (default 12)")
    ap.add_argument("--no-external", action="store_true", help="Disable off-site corroboration lookups")
    ap.add_argument("--timeout", type=int, default=None, help="Per-request timeout seconds")
    ap.add_argument("--profile", choices=VALID_PROFILES, default="balanced", help="Scoring/threshold profile")
    ap.add_argument("--crawl-scope", choices=["host", "domain"], default=None,
                    help="'host' (default) audits only the given host; 'domain' spans all subdomains")
    ap.add_argument("--skills", default=None, help="Comma-separated skill ids to run (default: all)")
    ap.add_argument("--format", choices=["json", "html", "md"], default="json",
                    help="Output format: json (canonical), html (dashboard), md (Markdown brief)")
    ap.add_argument("--out", help="Write the report to this file instead of stdout")
    ap.add_argument("--csv", dest="csv_out", metavar="FILE",
                    help="Also write findings as CSV to this file (analyst spreadsheet export)")
    ap.add_argument("--compare-previous", action="store_true",
                    help="Record this score and show the delta vs the last run for this domain")
    ap.add_argument("--history-db", default=None, help="Path to the SQLite history file")
    ap.add_argument("--allow-private", action="store_true", help="Allow localhost/private targets (testing only)")
    ap.add_argument("--dry-run", action="store_true", help="Validate inputs and print the plan; no network calls")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose (DEBUG) logging")
    ap.add_argument("--quiet", "-q", action="store_true", help="Only errors")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose, quiet=args.quiet)

    cfg = make_config(args.profile).derive(
        max_pages=args.max_pages, timeout=args.timeout, allow_private_hosts=args.allow_private or None,
        crawl_scope=args.crawl_scope)

    valid, target, reason = http.validate_target(args.url, cfg)
    if not valid:
        LOG.error("invalid target %r: %s", args.url, reason)
        return EXIT_BADINPUT

    only = [s.strip() for s in args.skills.split(",")] if args.skills else None

    if args.dry_run:
        _print_dry_run(target, cfg, only, not args.no_external)
        return EXIT_OK

    try:
        rpt, code = run(target, cfg, external=not args.no_external, only_skills=only)
    except KeyboardInterrupt:
        LOG.error("interrupted")
        return 130

    if args.compare_previous:
        from auditlib import history
        db = args.history_db or history.DEFAULT_DB
        history.record_and_compare(rpt, db_path=db, compare=True)
        cmp = rpt.get("comparison", {})
        if cmp.get("delta") is not None:
            LOG.info("score delta vs previous (%s): %+d", cmp.get("previous_at"), cmp["delta"])

    if args.format == "html":
        out = render_mod.render_html(rpt)
    elif args.format == "md":
        out = exports_mod.render_markdown(rpt)
    else:
        out = report_mod.dumps(rpt)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        LOG.info("wrote %s (%d findings, score %s %s)", args.out, rpt["summary"]["total_findings"],
                 rpt.get("score", {}).get("value"), rpt.get("score", {}).get("grade"))
    else:
        print(out)

    if args.csv_out:
        with open(args.csv_out, "w", encoding="utf-8", newline="") as fh:
            fh.write(exports_mod.findings_csv(rpt))
        LOG.info("wrote %s (%d finding row(s))", args.csv_out, rpt["summary"]["total_findings"])
    return code


def _print_dry_run(target, cfg, only, external) -> None:
    """Print the crawl/analysis plan without making any network calls."""
    from auditlib.registry import discover_skills, select_skills
    skills = select_skills(discover_skills(), only)
    print("DRY RUN — no network calls will be made")
    print(f"  target    : {target}")
    print(f"  host      : {http.host_of(target)}")
    print(f"  profile   : {cfg.profile}")
    print(f"  scope     : {cfg.crawl_scope} ({'this host only' if cfg.crawl_scope == 'host' else 'whole domain'})")
    print(f"  max_pages : {cfg.max_pages}")
    print(f"  timeout   : {cfg.timeout}s (retries {cfg.max_retries}, backoff {cfg.backoff_base}s)")
    print(f"  user_agent: {cfg.user_agent}")
    print(f"  external  : {external}")
    print(f"  skills    : {', '.join(s.id for s in skills)}")


if __name__ == "__main__":
    raise SystemExit(main())
