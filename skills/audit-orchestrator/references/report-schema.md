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
| `why` | string | — | Plain-English reason it hurts AI discoverability/engagement. |
| `impact` | int | — | 1–5 estimated impact (used for prioritization). |
| `priority` | int | — | Rank across all findings; `1` = act first. |
| `affected_pages` | array<string> | — | Up to 10 example URLs. |
| `suggested_action` | object | ✅ | `{ "summary": string, "priority": enum }`. |
| `details` | object | — | Optional structured extras per check. |

Findings are ordered most-actionable-first (by impact × confidence) and `id`s are assigned in
that order, so `F-001` is always the top-priority fix.

## `suggested_action`
| field | type | required |
|---|---|---|
| `summary` | string | ✅ |
| `priority` | enum (`critical`/`high`/`medium`/`low`) | ✅ |

`scripts/validate_report.py` checks a report against this contract; the entrypoint also
self-validates before returning and appends any warning to `notes`.
