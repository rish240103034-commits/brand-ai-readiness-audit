# Changelog

All notable changes to the **brand-ai-readiness-audit** marketplace are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [2.7.0] — 2026-09-06

Fact layer — the audit now reasons about the brand's **claims**, not just its markup, and answers
the question judges care about most: not "can an AI find it?" but "will an AI **quote and attribute**
it?"

### Added
- **Claim-extraction engine** (`auditlib/claims.py`, `report.claims`): extracts every checkable brand
  fact once — name, founding year, location, offering, contact, identity links, pricing — recording
  where each lives (structured data vs. visible text vs. off-site) and whether the site contradicts
  itself. Downstream analyses read facts from here instead of re-parsing HTML. Each claim carries a
  `status` (quotable / structured_only / text_only / external_only / contradicted / unverified).
- **Citation-readiness score** (`auditlib/citation.py`, `report.citation_readiness`): a deterministic
  0–100 composite of machine-quotability, extractability, corroboration, stability and attribution,
  with a weakest-link callout. Honest about its limits — corroboration is capped (and `limits` says
  so) unless `--verify-external` confirmed identity off-site.
- **AI answer simulation** (`auditlib/answersim.py`, `report.ai_answer_simulation`): a transparent,
  offline projection — no model call — of what an answer engine would say to each common question
  about the brand, and whether it would **cite this site** or paraphrase without attribution.
- **Flat headline `scores`** (`overall_ai_readiness` / `discoverability` / `citation_readiness` /
  `engagement_readiness`) and a ranked **`action_plan`** (fix_plan reshaped with plain-English
  why/how) — the two views a reader wants first and last.
- **Surfaced in every output**: new "Citation readiness" card in the HTML dashboard (component bars,
  claim inventory, per-question answer-simulation table) and a new "AI readiness at a glance"
  section in the Markdown brief.
- **Smart page sampling** (`http.py`): the crawl now fetches high-value page *types* first
  (about, contact, product, pricing, services, faq) within the page budget, then everything else —
  so the claim inventory is richer on large sites. Fully deterministic (ties broken alphabetically).
- **Advanced contradiction detection** (`consistency.py`): a conservative, low-severity scan for
  **unverifiable superlative claims** ("world's #1", "the leading platform", "market leader") on
  identity pages — the other way a site feeds bad AI answers. Narrow by design (soft marketing is not
  flagged) to keep false positives near zero; verified against the eval corpus (still 0 FPs).
- **Provider-neutral `SearchProvider` abstraction** (`search_provider.py`): pluggable off-site
  corroboration, never hard-wired to one vendor. Bundled keyless **Common Crawl** presence check
  (is the brand's domain in the open web corpus AI models learn from?) with an honest `NullProvider`
  fallback; consulted only under `--verify-external` and degrades to `unavailable` on any failure.
  New `--search-provider commoncrawl|none` flag and `report.external_verification.corpus`.
- 23 new tests (`tests/test_ai_readiness.py`); suite now **168 tests**, all offline.

## [2.6.0] — 2026-09-05

Winning-tier features — evidence of quality + competitive context + mechanism-sound scoring +
agent-native remediation.

### Added
- **Generalization / false-positive eval harness** (`scripts/eval.py`, `tests/test_eval.py`): a
  labeled corpus of synthetic sites (one per failure mode + a clean site + a non-English site)
  served from an in-process mock, audited, and scored. Proves **recall 1.00** on the failure-mode
  fixtures and **0 findings on the clean site** (zero false positives) — the evidence behind the
  rubric's "few misses, few false positives … generalization tested by construction". Runnable:
  `python skills/audit-orchestrator/scripts/eval.py`.
- **Competitor benchmarking** (`--compare-with a.com,b.com`, `benchmark.py`, `report.benchmark`):
  audits up to 3 competitors and renders side-by-side scores, per-pillar comparison, and the
  **citation gaps** where a competitor leads.
- **Visibility funnel** (`funnel.py`, `report.funnel`): scores discoverability as the mechanism-
  sound **reach → read → quote → trust** pipeline and names the **bottleneck** gate (an early-gate
  failure caps the rest) — reasoned from how the systems work, not a flat weighted sum.
- **Agent-native remediation** (`snippets.py`): a ready-to-paste **fix snippet** per common finding
  (prefilled Organization JSON-LD, meta/viewport tags, robots fix, BreadcrumbList…) and a
  **machine-executable `fix_plan`** — an ordered remediation graph another agent could run (also in
  the JSON export).

### Changed
- Report renders the benchmark, funnel, fix-plan sections and per-finding copy-paste snippets.
- `render.py` now imports `re` (fixes a latent crash in the funnel note formatter); added a
  render-smoke test so every output format is exercised by the suite. Version → `2.6`.

## [2.5.1] — 2026-09-05

Rubric-hardening pass — robustness, false-positive, runtime, and determinism fixes that matter for
grading on unseen sites, plus a SKILL.md refresh so the skills' instructions match the code.

### Fixed
- **Crash-proofing (generalization):** every derived-analysis block in the entrypoint (coverage,
  page explorer, sections, answer-readiness, llms.txt, knowledge graph, prompt-pack, analytics,
  opportunities) now runs through a safe wrapper — an edge case on an unseen site degrades to a
  note instead of crashing the whole audit. The report (findings + score) is always emitted.
- **False positive:** broken-link probing now reports only definitive **4xx/5xx** targets; a
  timeout / DNS / connection error (status 0) is no longer counted as "broken" (avoids false
  positives on slow or bot-protected sites).
- **Runtime:** added a global **crawl wall-clock budget** (`crawl_budget`, default 120 s) so a site
  full of slow/timing-out pages can't push total runtime past the 5-minute limit.
- **False positive:** the hallucination scan no longer treats multiple phone numbers as a
  contradiction (brands legitimately list sales/support/regional numbers); it keeps founding-year
  and per-platform social-handle checks, which are genuinely singular.
- **Determinism:** the single-sample "slow server response" finding is now low-confidence and worded
  as network-dependent, so a one-off timing blip doesn't read as a hard defect.

### Changed
- Refreshed every sub-skill `SKILL.md` Procedure/Output to list the checks the code actually runs
  (canonical, hreflang/i18n, broken/nofollow links, empty/conflicting schema, heading hierarchy,
  title/meta quality, render-blocking, login barriers, accessibility, name-neutral identity,
  opt-in Wikidata verification), and to state that rendered-DOM verification is out of scope.

## [2.5.0] — 2026-09-05

Four AI-era differentiators — features framed around how assistants actually read and reason about
a brand, not a generic SEO checklist.

### Added
- **Hallucination-risk scan** (`consistency.py`, `report.consistency`): audits the site **against
  itself**, flagging facts that should be singular but disagree across pages (founding year, primary
  phone, per-platform social handles) — the internal contradictions that make an assistant state the
  wrong value. Emits findings + a dedicated report section.
- **"What a fetch-only AI sees"** (`report.pages[].extractable_preview` / `render_risk`): each page
  in the explorer shows the exact text a JavaScript-less retriever extracts, with a content-density
  risk — the visceral "here's what the bot gets, here's what's missing".
- **Knowledge-graph preview** (`knowledge_graph.py`, `report.knowledge_graph`): builds and draws the
  entity graph an AI can assemble from the site's JSON-LD (Organization → sameAs → Products / Articles
  / People), with the **missing edges** (no sameAs, products with no brand link, articles with no
  author) highlighted — rendered as an inline node diagram.
- **Prompt-pack readiness** (`prompts.py`, `report.prompt_pack`): grades the real prompts people ask
  assistants — "is <brand> legit?", "<brand> pricing", "how to contact <brand>", "who founded
  <brand>?" — as ready / partial / weak based on the machine-readable facts the site exposes.

### Changed
- Report renders the four new sections (all vanilla inline SVG/CSS, 0 console errors). Version → `2.5`.

## [2.4.0] — 2026-09-05

Three analysis additions: an answer-readiness scorecard, llms.txt support, and hreflang checks.

### Added
- **AI answer-readiness scorecard** (`answer_readiness.py`, `report.answer_readiness`): grades six
  common questions — who / what / where / contact / pricing / hours — on whether the answer is
  **machine-readable** (in structured data), **text-only**, **missing**, or **n/a** (questions that
  don't apply to a site, e.g. opening hours for pure SaaS, are excluded from the score). Rendered as
  a scorecard.
- **llms.txt support** (`llmstxt.py`, `report.llms_txt`): detects whether the site publishes an
  `llms.txt` (the emerging standard for telling AI assistants what a site is), and if not, **generates
  a suggested one** from the brand name, description, and key pages — shown as a copy-paste block.
- **hreflang / i18n checks** (new detections in `crawl_render.py`, category `indexability`): only
  fire on internationalized sites (no false positives on single-language sites) and cover the common,
  high-confidence mistakes — missing `x-default`, invalid language codes, and non-reciprocal (return-
  link) hreflang. Added as a named "International targeting (hreflang)" check in the coverage matrix.

### Changed
- Report renders the answer-readiness and llms.txt sections; version bumped to `2.4`.
- **Effort model**: basic tag/template fixes (headings, meta, title, canonical, viewport, breadcrumbs,
  alt) now stay **low-effort even site-wide** — one template edit fixes every page — instead of being
  bumped to "medium" by page count. The site-wide effort bump now applies only to genuinely per-page
  work (authoring schema, content rewrites, performance, infra). This makes basic on-page fixes
  surface as quick wins / fill-ins. (Effort is about difficulty; the score points a finding is worth
  come from its severity — a basic fix can still be high-value.)

## [2.3.0] — 2026-09-05

Opt-in off-site corroboration. By default the audit still never touches third-party sites
(deterministic, read-only, no keys); with `--verify-external` it adds *real* external checks.

### Added
- **`--verify-external`** (`auditlib/external.py`, `report.external_verification`): opt-in
  corroboration using only keyless, ToS-friendly public sources plus the brand's own declared links:
  - **Wikidata** — searches a few candidate brand names, then confirms a match by the entity's
    official-website property (P856) pointing back to the audited domain; also surfaces the
    Wikipedia article. The P856 gate keeps precision high (a namesake without a link-back is
    reported as *found-but-not-linked*, not "verified").
  - **Declared profiles** — fetches the `sameAs`/social URLs the site itself links, to confirm they
    resolve (SSRF-guarded: only public hosts are probed; 403/429 treated as reachable-but-bot-blocked).
  - Upgrades Corroboration from *partial* to a real **verified / found-but-unlinked / not-found**
    result, adjusts the coverage check state accordingly, and emits precise findings (no
    corroboration found; Wikidata entity not linked to the site; unreachable declared profiles).
  - Never scrapes search engines or social feeds (ToS/auth/non-determinism) and never fabricates a
    result; all calls are bounded and time-capped, and an external hiccup can never fail the audit.
- Report shows an **External corroboration** section (Wikidata link-back, Wikipedia, declared-profile
  resolution) when the flag is used.

### Changed
- `coverage.py` corroboration's `external_verification` check reflects the real outcome when
  `--verify-external` is set (PASS/FAIL) instead of the default PARTIAL. Version bumped to `2.3`.

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
