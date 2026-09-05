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
| `coverage` | object | — | Per-area assessment matrix (see below) — distinguishes not-assessed from healthy. |
| `analytics` | object | — | Analyst layer derived from the scored report (see below). |
| `opportunities` | array | — | Proactive, context-justified recommendations (non-defect; see below). |
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
Opportunities`): `{ key, label, status, status_label, checks, pages_assessed, findings,
confidence, note }`. `status` ∈ `healthy` (verified) · `issues` · `partial` · `not_assessed` ·
`opportunities`. A skill that didn't run, or an area without enough signal (e.g. Freshness with no
dates), is `not_assessed` — never silently scored as healthy. Corroboration is at most `partial`
(on-page signals only; no independent external verification). `coverage.summary` gives
`{ areas_total, areas_assessed, areas_not_assessed, pages_crawled }`.

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
