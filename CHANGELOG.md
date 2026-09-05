# Changelog

All notable changes to the **brand-ai-readiness-audit** marketplace are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [2.2.0] — 2026-09-05

Analysis tools. Two features that turn the report from a readout into something you explore.

### Added
- **Interactive what-if planner**: tick findings you plan to fix and the AI Visibility Score
  recomputes **live** in the page. The exact scoring model is now embedded as
  `report.scoring_model` (severity penalties, confidence factors, dimension weights, grade bands),
  so the in-page recompute is identical to the engine — one source of truth. Includes "tick all
  quick wins", "tick all", and reset; the planner's *Current* value always equals the engine score.
- **Site-section analysis** (`report.sections`, via `pages.build_sections`): pages are grouped by
  top-level URL path (`/products/*`, `/blog/*`, …) and each section is scored (mean of its page
  scores) with its distinct finding count and worst severity — so the weakest part of the site is
  obvious at a glance. Rendered as a weakest-first bar list (shown only when ≥2 sections exist).

### Changed
- `scoring.py` exposes `report.scoring_model`; `render.py` adds the what-if panel (a "mark fixed"
  checkbox per finding that doesn't expand it) and the section-analysis card.
- Version strings bumped to `2.2`.

## [2.1.0] — 2026-09-05

Interactive report + engine depth. The HTML report is now rendered from the **embedded canonical
JSON** (so the report and the exported JSON can never disagree), with a page explorer, combined
filters, and per-area passed-check breakdowns. Still one entrypoint, stdlib-only, read-only.

### Added
- **Page explorer** (`auditlib/pages.py`, `report.pages`): one record per audited URL — score,
  finding count/ids, top severity, dimensions, title, meta, H1/H2, structured-data types, lang,
  canonical, indexability, internal/external/PDF link counts, CTA/accessibility/performance
  signals, redirect + HTTP status, and confidence. Rendered as a searchable, sortable explorer.
- **Passed checks** — `coverage.py` is now driven by an explicit **check registry**: each area
  reports named checks resolved to PASS / FAIL / NOT_VERIFIED / PARTIAL, with counts. Rendering's
  rendered-DOM parity is honestly **NOT_VERIFIED** (this static audit executes no browser), so
  Rendering reads *partial*, never a false "healthy". Coverage summary now says
  "N fully assessed · M partially · K not assessed".
- **Interactive report**: sticky **Download JSON / Copy JSON / Print** toolbar; **combined**
  findings filters (dimension + severity + confidence, AND-combined) with **search**, **sort**
  (priority/severity/impact/affected-pages), reset, and a live result count; clickable affected
  pages (`target=_blank rel=noopener noreferrer`) with two-way **finding ↔ page** navigation.
- **Accessibility checks** (`engagement.py`): form controls without an associated label, and
  content iframes without a title (both medium-confidence, static-safe).

### Changed
- `render.py` embeds the canonical report and renders the page explorer/coverage/filters from it.
- Roadmap "Now" bucket label clarified ("critical & high, plus quick wins of any severity").
- SVG charts no longer set an invalid `height="auto"` attribute (no console warning).
- Version strings bumped to `2.1`.

## [2.0.0] — 2026-09-05

Round-3 depth pass. Substantially more detection, an honest coverage model, a richer evidence
model, proactive opportunities, and a fully traceable score — all in-place on the existing
architecture (one entrypoint, stdlib-only, read-only, robots-respecting).

### Added
- **Coverage matrix** (`auditlib/coverage.py`, `report.coverage`): a per-area status for the 9
  areas (Crawlability, Rendering, Structured Data, Extractability, Entity Identity, Freshness,
  Corroboration, Engagement, Proactive Opportunities). **0 findings ≠ healthy** — an area is
  `not_assessed` when its skill didn't run or there wasn't enough signal (e.g. Freshness with no
  dates), and Corroboration is at most `partial` (on-page signals only, no external verification).
- **Richer evidence model** on every finding: specific `why`, `how_to_fix`, `scope`
  (`8 of 12 pages (67%)`), structured `measurements`, and `expected_impact`. Explanations are now
  set per-check, so they always match the defect (fixes the mis-attributed Multiple-H1 reason).
- **Proactive opportunities** (`auditlib/proactive.py`, `report.opportunities`): context-justified
  recommendations (author markup, product ratings, FAQPage, BreadcrumbList, SearchAction, logo,
  key-facts summary) that never affect the score and only appear when the crawl justifies them.
- **Score explanation** in the report: the exact formula plus each finding's traceable point cost.
- **New detections** — crawl/render: retrieval-vs-training bot distinction in robots (nuanced,
  not "allow everything"), cross-domain canonical conflicts, nofollow'd internal links, bounded
  broken-internal-link probing. Structured data: incomplete/empty property values, conflicting
  Organization identities. Extractability: title/meta length quality, heading-hierarchy skips.
  Entity identity: name-neutral cross-signal consistency (og:site_name vs schema name).
  Engagement: render-blocking head resources, login/paywall walls, non-descriptive link text.
- **Report UI**: coverage matrix, proactive-opportunities and limitations sections, a score
  explanation, per-finding evidence (scope/measurements/expected impact), and **dynamic filters**
  that only show severities/dimensions that actually occur (no empty "Critical"/dimension chips).

### Changed
- `scoring.py`: a check's own `why` is kept; the category default is a fallback only.
- Robots handling recommends allowing **retrieval** crawlers (critical if blocked) while treating
  a **training**-crawler block as a low-severity, explicit policy choice — not a blanket "allow all".
- Version strings bumped to `2.0`.

### Fixed
- Multiple-H1 (and other extractability) findings no longer reuse an unrelated "locked in an image"
  explanation — each carries its own accurate `why`.
- Removed a brand-identity false positive from title-segment guessing (identity consistency now
  compares only the explicit og:site_name and schema name).

## [1.3.0] — 2026-09-05

Fairness pass — remove site-type bias so the score reflects AI-readiness, not a site's
language, front-end architecture, host layout, or brand-name length.

### Fixed (bias removal)
- **Language bias.** CTA detection is now language-neutral — it recognizes conversion-path links
  (`/cart`, `/contact`, `/signup`, `tel:`, `mailto:`…) and `cta`/`button` markup, not only English
  verbs — so non-English homepages with a real CTA are no longer flagged. Word counting now credits
  CJK / Thai / Korean characters (which carry meaning without word spaces) instead of splitting on
  whitespace alone, so content-rich non-Latin pages are no longer mis-flagged as "thin",
  "requires JavaScript", or "content in images". English counts are unchanged.
- **Third-party subdomain bias.** The crawl is now **host-scoped by default** (`--crawl-scope
  host`): a brand is no longer scored on help-desk / status subdomains it doesn't build (e.g.
  `support.brand.com`). `--crawl-scope domain` restores whole-domain crawling.
- **Brand-name-length bias.** Removed the check that penalized short/generic brand names; entity
  identity is judged only by name-neutral markup (Organization/WebSite schema + `sameAs`).

### Added
- `--crawl-scope host|domain` flag and `crawl_scope` config (default `host`); `same_host` /
  `scope_predicate` helpers in `http.py`; `count_words` (language-aware) in `htmlparse.py`.
- 12 fairness regression tests (`tests/test_bias.py`) — 84 total, all offline.
- README "Fairness, bias & limitations" section + severity-model "Fairness across site types",
  documenting the by-design biases that are deliberately kept (fetch-only assumption; type-scaled
  structured-data expectations).

### Changed
- Version strings bumped to `1.3`. Removed the now-unused `brand_generic_len` threshold.

## [1.2.0] — 2026-09-05

Analyst-grade reporting. The audit now ships a full data-analytics view on top of the same
deterministic checks, with three new output formats — and no new dependencies (still stdlib-only).

### Added
- **Analytics layer** (`auditlib/analytics.py`) attached to every report as `analytics`:
  - **Six pillar sub-scores** (crawl & render, structured data, extractability, freshness,
    corroboration, engagement) with a health status each.
  - **Impact × effort matrix** — every finding placed in a quadrant (**quick win** / major
    project / fill-in / low priority) using a transparent, category-based effort model.
  - **Score projection** — what the AI Visibility Score becomes if the quick wins (or all
    findings) are fixed, plus distance to the next grade; every projection re-scores through the
    one model in `scoring.py`, and each finding carries the score `points_at_stake`.
  - **Page hotspots**, a **Now / Next / Later roadmap**, severity/confidence/category
    distributions, a headline **KPI** set, and an auto-written **executive summary**.
- **HTML dashboard rewrite** (`auditlib/render.py`): KPI row, executive summary, projection bars,
  a pillar **radar**, a severity **donut** + confidence bar, an **impact × effort** scatter, the
  roadmap, a hotspots table, and client-side **finding filters** — all inline SVG/CSS/JS, no
  external assets, everything escaped.
- **New output formats**: `--format md` (a portable Markdown brief) and `--csv FILE` (one row per
  finding with impact, effort, quadrant, and points-at-stake) via `auditlib/exports.py`.
- **19 new offline tests** for the analytics layer and exporters (72 total).
- Example report regenerated in **all four formats** from one real audit
  (`examples/sample-report.{json,html,md,csv}`).

### Changed
- `scoring.py` refactored to expose one reusable `compute_scores()` / `dimensions_present()` so
  the headline score and every "what-if" projection share a single source of truth (headline
  numbers are unchanged).
- Version strings bumped to `1.2` (User-Agent, `auditor`).

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
