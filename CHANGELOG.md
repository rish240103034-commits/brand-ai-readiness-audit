# Changelog

All notable changes to the **brand-ai-readiness-audit** marketplace are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-09-05

Hardening and "demo-ready" upgrade. Same detection philosophy, much stronger engineering.

### Added
- **AI Visibility Score** (0–100) with an **A–F grade** and per-dimension sub-scores
  (discoverability / engagement) — a single headline number, computed by a transparent,
  deterministic model in `auditlib/scoring.py`.
- **Prioritized fixes**: every finding now carries a plain-English *why it hurts*, an
  `impact` (1–5), and a `priority` rank; findings are ordered most-actionable-first.
- **Self-contained HTML report** via `--format html` (inline CSS, SVG score gauge,
  collapsible findings, no external assets).
- **Skill auto-discovery**: the orchestrator discovers skills by scanning `skills/`,
  validating each `SKILL.md` against the agentskills.io essentials, and binding checks from
  `metadata.checks` — a new skill can be dropped in without editing `run_audit.py`.
- **Concurrent skill execution** (`ThreadPoolExecutor`) with a global analysis-timeout guard
  that reports a partial result instead of hanging.
- **Historical comparison** (`--compare-previous`, `--history-db`) storing scores in a local
  SQLite file and reporting the delta vs. the previous run for the domain.
- **Config profiles** (`--profile strict|balanced|lenient`) and a **`--skills`** subset flag.
- **SSRF protection**: `validate_target` rejects non-http(s) schemes and localhost/private/
  reserved addresses before any crawl.
- **`--dry-run`**, `--verbose`/`--quiet` logging, and documented exit codes (0/1/2).
- Full offline test suite (`unittest`): ≥3 cases per check, frontmatter/registry, URL/SSRF,
  report/scoring, and a mock-HTTP-server integration test.

### Changed
- Centralized every tunable (User-Agent, timeout, size cap, retries/backoff, and all check
  thresholds) in `auditlib/config.py`; nothing is magic-numbered inline.
- Network calls now retry transient failures with exponential backoff and remain polite
  (per-host crawl delay, robots `Crawl-delay` honored). `Fetcher` is thread-safe.
- Standalone skill runners share one hardened runner (`auditlib/runner.py`) and never crash:
  on failure they still emit a schema-valid (partial or fatal) report.
- Large functions split for single-responsibility; docstrings/type hints added throughout.

### Fixed
- Bare-domain input (e.g. `example.com`) is now accepted (https:// assumed).
- False positives removed: stale-copyright now requires the absence of any recent-date
  signal; brand-name-consistency ignores localized/translated `og:site_name`; product-page
  detection requires real commerce cues, not prose mentioning a price.

## [1.0.0] — 2026-09-05

Initial marketplace: entrypoint orchestrator + five focused skills (crawl-render,
structured-data, content-extractability, freshness-corroboration, engagement), standard-
library-only engine, JSON audit report against the required schema, read-only and
robots-respecting.
