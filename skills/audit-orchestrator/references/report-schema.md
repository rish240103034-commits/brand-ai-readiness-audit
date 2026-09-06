# Audit report schema

The entrypoint emits a single JSON object. The contest's required fields are the **floor**;
this marketplace adds a few additive fields. Consumers should ignore unknown fields.

## Top level
| field | type | required | notes |
|---|---|---|---|
| `site` | string | ✅ | Registrable host of the audited URL, e.g. `example.com`. |
| `audited_at` | string (ISO-8601 UTC) | ✅ | When the report was produced. |
| `started_at` | string (ISO-8601 UTC) | — | When the crawl began. |
| `auditor` | string | — | `brand-ai-readiness-audit/<version>`. |
| `pages_crawled` | int | — | Size of the analyzed sample. |
| `summary` | object | ✅ | Counts (see below). |
| `score` | object | — | AI Visibility Score (see below). |
| `scores` | object | — | Flat headline view: `overall_ai_readiness`, `discoverability`, `citation_readiness`, `engagement_readiness` (see below). |
| `claims` | object | — | Extracted brand-fact inventory + status summary (see below). |
| `citation_readiness` | object | — | 0–100 composite: will an AI *quote & attribute* this brand? (see below). |
| `ai_answer_simulation` | array | — | Per-question projection of what an answer engine would say and whether it would cite the site (see below). |
| `action_plan` | array | — | Flat, ranked do-this-next plan (reshaped `fix_plan` + why/how; see below). |
| `coverage` | object | — | Per-area assessment matrix (see below) — distinguishes not-assessed from healthy. |
| `analytics` | object | — | Analyst layer derived from the scored report (see below). |
| `opportunities` | array | — | Proactive, context-justified recommendations (non-defect; see below). |
| `pages` | array | — | Per-page detail for the page explorer (see below). |
| `sections` | array | — | Per-URL-section scores (see below). |
| `scoring_model` | object | — | The exact deduction model, so the report can recompute "what-if" scores identically (see below). |
| `external_verification` | object | — | Present only with `--verify-external`: off-site corroboration results (see below). |
| `answer_readiness` | object | — | Who/what/where machine-readability scorecard (see below). |
| `llms_txt` | object | — | llms.txt presence + a generated suggestion (see below). |
| `funnel` | object | — | Visibility funnel: reach→read→quote→trust gate scores + bottleneck (see below). |
| `benchmark` | object | — | Present with `--compare-with`: competitor comparison + gaps (see below). |
| `fix_plan` | array | — | Ordered, machine-executable remediation steps (see below). |
| `consistency` | object | — | Hallucination-risk scan: self-contradictions across the site (see below). |
| `knowledge_graph` | object | — | Entity graph an AI can build from the markup (see below). |
| `prompt_pack` | object | — | Real-query readiness grades (see below). |
| `findings` | array | ✅ | Zero or more finding objects. |
| `profile` | string | — | Scoring profile used (`strict`/`balanced`/`lenient`). |
| `skills_run` | array<string> | — | Ids of the skills that executed. |
| `comparison` | object | — | Present with `--compare-previous`: `previous_score`, `delta`, `previous_at`, `run_count`. |
| `notes` | array<string> | — | Run metadata + any skipped-check / schema warnings. |

## `score`
| field | type | notes |
|---|---|---|
| `value` | int | 0–100 overall AI Visibility Score. |
| `grade` | enum | `A` (≥90) `B` (≥80) `C` (≥70) `D` (≥60) `F` (<60). |
| `discoverability` | number | 0–100 sub-score. |
| `engagement` | number | 0–100 sub-score. |
| `headline` | string | e.g. `AI Visibility Score 72/100 (C)`. |

See [severity-model](severity-model.md) for the scoring weights and the `impact`/`priority` model.

## `analytics`
Additive analyst layer computed **deterministically from the scored report** (no extra data is
collected). Built by `auditlib/analytics.py`; consumers may ignore it.

| field | type | notes |
|---|---|---|
| `kpis` | object | Headline metrics: `ai_visibility_score`, `grade`, `total_findings`, `critical_high`, `quick_wins`, `projected_score`/`projected_gain`, `potential_score`, `pages_analyzed`, `weakest_pillar`(`_score`), `strongest_pillar`, `total_effort_points`, `effort_band`. |
| `pillars` | array | Six areas — `crawl_render`, `structured_data`, `extractability`, `freshness`, `corroboration`, `engagement` — each `{key, label, dimension, score (0–100), status (healthy/warning/critical), findings}`. |
| `distribution` | object | `by_severity` / `by_confidence` / `by_dimension` / `by_category`, each a list of `{key, count, pct}`. |
| `matrix` | array | One record per finding: `{id, title, severity, dimension, category, confidence, priority, impact (1–5), effort (1–5), effort_label, quadrant, points_at_stake, affected_pages}`. |
| `quadrant_counts` | object | Count of findings per quadrant (`quick_win`, `major_project`, `fill_in`, `low_priority`). |
| `quick_wins` | array | The `quick_win` findings (high impact, low effort), best first. |
| `projection` | object | "What-if" scores: `current`, `after_quick_wins`(`_grade`), `quick_win_gain`, `after_all_fixed`(`_grade`), `headroom`, `to_next_grade {grade, points, at_least}` or `null`, `quick_wins_reach_next_grade`. |
| `hotspots` | array | Pages carrying the most weighted issues: `{url, findings, impact, top_severity}`. |
| `roadmap` | object | `now` / `next` / `later`, each a list of finding refs. |
| `narrative` | array<string> | Auto-written executive-summary sentences. |

**Effort** (1 easy … 5 architectural) is a transparent, category-based heuristic (+1 for
site-wide findings). A finding is a **quick win** at impact ≥ 3 and effort ≤ 2. `points_at_stake`
is how many overall points the score would recover if that finding alone were fixed; every
projection reuses the one score model in `scoring.py`, so the numbers are consistent.

## `summary`
| field | type | required | notes |
|---|---|---|---|
| `total_findings` | int | ✅ | Length of `findings`. |
| `critical`/`high`/`medium`/`low`/`info` | int | — | Present only when non-zero. |
| `by_dimension` | object | — | `{ "discoverability": n, "engagement": n }`. |

## `findings[]`
| field | type | required | notes |
|---|---|---|---|
| `id` | string | ✅ | Stable within a report: `F-001`, `F-002`, … (severity-ordered). |
| `title` | string | ✅ | One-line problem statement. |
| `severity` | enum | ✅ | `critical` > `high` > `medium` > `low` > `info`. |
| `dimension` | enum | — | `discoverability` \| `engagement`. |
| `category` | string | — | e.g. `crawlability`, `structured-data`, `performance`. |
| `confidence` | enum | — | `high` \| `medium` \| `low` — how sure the static check is. |
| `evidence` | string | ✅ | Concrete, countable proof (e.g. "0/12 pages have JSON-LD"). |
| `why` | string | — | **Specific** reason this finding hurts (set per-check; a category default only fills in when a check omits it). |
| `how_to_fix` | string | — | Concrete, mechanism-sound remediation steps. |
| `scope` | string | — | Prevalence, e.g. `8 of 12 page(s) (67%)`. |
| `measurements` | object | — | Observed numbers behind the finding (e.g. `{"pages_without_h1": 4}`). |
| `expected_impact` | string | — | What fixing it is expected to improve. |
| `fix_snippet` | string | — | Ready-to-paste remediation code (when a template exists for the finding type). |
| `kind` | enum | — | `defect` (default) — opportunities live in the top-level `opportunities` array. |
| `impact` | int | — | 1–5 estimated impact (used for prioritization). |
| `priority` | int | — | Rank across all findings; `1` = act first. |
| `affected_pages` | array<string> | — | Up to 10 example URLs. |
| `suggested_action` | object | ✅ | `{ "summary": string, "priority": enum }`. |
| `details` | object | — | Optional structured extras per check. |

## `coverage`
Explicit per-area assessment so **0 findings ≠ healthy**. Built by `auditlib/coverage.py`.

`coverage.areas[]` — one row per area (`Crawlability`, `Rendering`, `Structured Data`,
`Extractability`, `Entity Identity`, `Freshness`, `Corroboration`, `Engagement`, `Proactive
Opportunities`): `{ key, label, status, status_label, checks[], checks_total, passed, failed,
not_verified, partial_checks, pages_assessed, findings, confidence, note }`. Each `checks[]` entry
is `{ id, label, state, note }` where `state` ∈ `pass` · `fail` · `not_verified` (browser/render
dependent — this static audit executes no browser) · `partial` (e.g. corroboration's external
verification). `status` ∈ `healthy` (all checks pass) · `issues` (≥1 finding) · `partial` (clean
but some checks not_verified/partial — e.g. Rendering, whose rendered-DOM parity is never executed)
· `not_assessed` (skill didn't run / no signal — e.g. Freshness with no dates) · `opportunities`.
`coverage.summary` gives `{ areas_total, areas_fully_assessed, areas_partial, areas_not_assessed,
areas_assessed, pages_crawled }`.

## `pages`
Per-page detail powering the report's **page explorer** (built by `auditlib/pages.py`). One record
per sampled URL: `{ url, final_url, redirected, status, is_home, score, finding_count, finding_ids,
top_severity, dimensions, confidence, title, title_len, meta_description, h1, h1_count, h2_count,
headings_outline, structured_data_types, lang, canonical, indexable, internal_links,
external_links, pdf_links, cta_signal, images, images_missing_alt, scripts, html_kb, response_ms,
word_count, rendering }`. `rendering` is `{ static_text_words, verified: false, note }` — rendering
is assessed from static HTML only and explicitly marked not verified. The per-page `score` is
`100 − Σ penalties` of the findings affecting that page (site-wide findings attach to the homepage).

## `sections`
Pages grouped by top-level URL path so the weakest area of the site is obvious. One entry per
section, weakest-first: `{ key (e.g. "/products"), label, pages, score (mean of the section's page
scores), findings (distinct finding ids in the section), top_severity, dimensions, examples }`.
Present only when the crawl spans ≥2 sections.

## `scoring_model`
The exact deduction model, embedded so the report's **what-if planner** recomputes scores
identically to the engine (one source of truth): `{ severity_penalty, confidence_factor,
weights (restricted to the dimensions actually assessed), grade_bands }`. Overall =
`round(Σ dimension_score × weight / Σ weight)`, where each dimension starts at 100 and loses
`severity_penalty × confidence_factor` per finding.

## `external_verification`
Present **only** when the user opts in with `--verify-external` (the default audit never queries
third-party sites). Built by `auditlib/external.py` from keyless, ToS-friendly public sources plus
the brand's own declared links — never search-engine/social scraping, never fabricated.
`{ performed: true, brand, domain, sources, verified (bool), wikidata { searched, found,
links_back, id, label, description, official_website, wikipedia }, profiles [ { url, state
(verified|unreachable|skipped), status } ], notes }`. `wikidata.links_back` is true only when the
entity's official-website property (P856) resolves to the audited domain — a definitive match; a
name-only hit is `found` but not `links_back`. When present, this drives Corroboration's
`external_verification` coverage check to PASS/FAIL instead of the default PARTIAL.

Also carries `corpus` from the **provider-neutral `SearchProvider`** (`auditlib/search_provider.py`):
`{ provider, status (present|absent|unavailable), records?, index?, detail }`. The default provider is
a **keyless Common Crawl** presence check (is the domain in the open web corpus AI models learn from?);
`--search-provider none` limits corroboration to Wikidata + declared links. A positive `absent` adds a
single low/low finding; `unavailable`/`present` add none — the source is pluggable and never fabricated.

## `answer_readiness`
Can an assistant answer common questions about the brand? (`auditlib/answer_readiness.py`.) Grades
six questions on machine-readability: `{ score (machine-readable count), applicable, machine_readable,
text_only, missing, items[ { key, question, state, evidence } ] }`. `state` ∈ `machine_readable`
(in structured data) · `text_only` (in prose only) · `missing` · `n/a` (not applicable to this site
— excluded from `applicable`/`score`). Questions: identity, offerings, location, contact, pricing
(commerce sites only), hours (local businesses only).

## `llms_txt`
`{ present (bool), url, status, suggested (Markdown string), note }`. `present` is true when the site
serves a non-empty `/llms.txt`; otherwise `suggested` holds a generated file (brand, description, key
pages) for copy-paste. Recommend-only; llms.txt is an optional emerging convention, never a defect.

## `consistency`
Hallucination-risk scan (`auditlib/consistency.py`) — the site audited against itself.
`{ risk (none|low|elevated), facts_checked, conflicts[ { type, label, severity, values[ { value,
examples[urls], pages } ] } ], unverifiable_claims[ { claim, context, page } ], note }`. Only facts
expected to be singular are compared (founding year, per-platform social handles); conflicts surface
as `entity-identity` findings. `unverifiable_claims` are absolute superlatives ("world's #1", "the
leading platform") found on identity pages — a low/low `trust-signals` finding recommending they be
attributed or softened (soft marketing is deliberately not flagged). `pages[].extractable_preview` / `extractable_words` / `render_risk` carry the
"what a fetch-only AI sees" view per page.

## `knowledge_graph`
The entity graph an AI can assemble from the site's JSON-LD (`auditlib/knowledge_graph.py`).
`{ nodes[ { id, type, label, core? } ], edges[ { from, to, rel } ], missing[ { from, rel, note } ],
summary { nodes, edges, missing, has_identity } }`. `missing` lists absent-but-expected edges
(no sameAs, product without brand, article without author, no identity node).

## `prompt_pack`
Real-query readiness (`auditlib/prompts.py`). `{ brand, ready, total, prompts[ { prompt, state
(ready|partial|weak|n/a), needs } ] }` — grades whether the site exposes the machine-readable facts
to be the source of a good answer for common assistant prompts.

## `funnel`
Discoverability scored as a pipeline (`auditlib/funnel.py`): `{ gates[ { key (reach|read|quote|
trust), label, mechanism, score, status, findings } ], weakest, weakest_label, weakest_score, note }`.
An early gate caps the rest, so the **bottleneck** (weakest gate) is where a fix unlocks the most.

## `benchmark`
Present only with `--compare-with` (`auditlib/benchmark.py`): `{ you {site,score,grade,pillars,
answer_ready,…}, competitors[ …same… ], gaps[ { pillar, you, best, leader } ], note }`. `gaps` are
pillars where a competitor leads by ≥15 points.

## `fix_plan`
An ordered, machine-consumable remediation graph (`auditlib/snippets.py`): a list of `{ step,
finding_id, title, category, action, severity, effort, expected_gain_points, affected_pages,
has_snippet }`, sequenced Now→Next→Later — designed for another agent to execute.

## `scores`
Flat headline view over the detailed `score` block, framed as the three questions a reader asks:
`{ overall_ai_readiness (int, == score.value), discoverability, citation_readiness (== citation_readiness.score),
engagement_readiness }`. Additive; `score` remains the source of truth for discoverability/engagement.

## `claims`
The brand-fact inventory (`auditlib/claims.py`). Every checkable statement the brand makes about
itself is extracted **once**, so downstream layers reason about facts, not markup.
`{ claims[ { id (C-001…), type (brand_name|founding_year|location|offering|contact|
identity_link|social_profile|price_signal), subject, predicate, value, in_structured_data (bool),
in_visible_text (bool), off_site (bool), source_pages[], status, confidence, corroboration } ],
summary { total, by_status, quotable, quotable_pct, machine_readable_pct, contradicted, note } }`.
`status` ∈ `quotable` (in schema **and** text) / `structured_only` / `text_only` / `external_only`
/ `contradicted` (the hallucination scan flags a conflict) / `unverified`.

## `citation_readiness`
Deterministic 0–100 composite (`auditlib/citation.py`) answering "once found, will an AI *quote and
attribute* this brand?": `{ score, grade, headline, weakest, method, components[ { key, label, value
(0–100), weight, detail } ], limits? }`. Components + weights: machine_quotability .30, extractability
.20, corroboration .25, stability .15, attribution .10. Without `--verify-external` the corroboration
component is capped and `limits` says so — the number is never overstated.

## `ai_answer_simulation`
A transparent, offline projection (`auditlib/answersim.py`) of what an answer engine would do per
common question — not a model call. List of `{ question, answerable (yes|partial|risky|no),
basis (structured|text|off-site|conflicting|none), would_cite (bool), confidence, supporting_claims[],
gap }`. Rule: an engine can only state a fact it can extract, and prefers to cite facts that are
machine-readable and non-contradictory — applied to the `claims` inventory.

## `action_plan`
Flat, ranked "do this next" plan reshaped from `fix_plan` + the impact/effort matrix: `{ rank,
finding_id, action, why, how, dimension, severity, effort, expected_gain_points, quadrant,
has_snippet }`. Same ordering as `fix_plan`; adds the plain-English *why*/*how* per step.

## `opportunities`
Proactive, context-justified recommendations that raise AI-readiness beyond fixing defects. They
**never affect the score** and are only surfaced when the crawl justifies them (e.g. author markup
only when the site has articles). Each: `{ id (OP-001…), title, category, dimension, kind:
"opportunity", rationale, suggested_action, expected_impact, effort, confidence, evidence }`.

Findings are ordered most-actionable-first (by impact × confidence) and `id`s are assigned in
that order, so `F-001` is always the top-priority fix.

## `suggested_action`
| field | type | required |
|---|---|---|
| `summary` | string | ✅ |
| `priority` | enum (`critical`/`high`/`medium`/`low`) | ✅ |

`scripts/validate_report.py` checks a report against this contract; the entrypoint also
self-validates before returning and appends any warning to `notes`.
