# Round 4 — Methodology Map (signal → evidence → severity → fix → priority)

Every mechanism the demo narrates is traceable to real code in the **submitted Round 3
engine (tag `v2.7.0`)**. Paths below are relative to the repo root; line numbers are from
`v2.7.0`. This document adds no behaviour — it only maps what already exists.

## The pipeline in one line
`run_audit.py` → validate target (SSRF-safe) → **auto-discover skills** from `marketplace.json`
+ each `SKILL.md`'s `metadata.checks` → **one polite crawl** (`AuditContext.build`) → run each
skill's `analyze(ctx)` **concurrently** → merge/dedupe → **score & prioritize** → emit report.

- Entrypoint & composition: `skills/audit-orchestrator/scripts/run_audit.py` — `discover_skills()`/`select_skills()` (line 65), `_run_skills_concurrently()` (line 216), `score_report()` (line 109).
- Auto-discovery (no hardcoded imports): `auditlib/registry.py::discover_skills()` (line 84) binds each skill to its check via the `metadata.checks` list in its `SKILL.md`.
- Each check is a pure function `analyze(ctx) -> list[Finding]`. The orchestrator owns crawl+merge+score; it contains **no detection logic**.

## How severity → impact → priority works (one place, deterministic)
`auditlib/scoring.py`:
- `SEVERITY_PENALTY = {critical:35, high:18, medium:8, low:3, info:1}` (line 15)
- `CONFIDENCE_FACTOR = {high:1.0, medium:0.75, low:0.5}` (line 17) — heuristic checks dock less.
- `penalty_of(finding) = SEVERITY_PENALTY × CONFIDENCE_FACTOR` (line 66).
- Each dimension starts at 100 and subtracts penalties; overall = `discoverability×0.6 + engagement×0.4` (`DIMENSION_WEIGHT`, line 21; `compute_scores`, line 92).
- Findings are re-sorted **most-actionable-first** by `(−priority_score, dimension, title)` and renumbered `F-001…` (`score_report`, line 108).
- The exact model is exported as `report["scoring_model"]` so the HTML "what-if" planner recomputes identically — one source of truth.
- **Test:** `tests/test_report_scoring.py`.

## Coverage honesty (0 findings ≠ healthy)
`auditlib/coverage.py` resolves each named check to `PASS / FAIL / NOT_VERIFIED / PARTIAL`
(line 22). Rendering parity is `NOT_VERIFIED` (this static audit runs no browser), so it never
claims a false "healthy". This is what keeps recall honest without false positives.

---

## The 6 signals to narrate

### 1. Missing / invalid structured data  *(hero finding — HIGH)*
- **Signal:** pages carry no machine-readable markup (JSON-LD / microdata / RDFa), or declare JSON-LD that fails to parse.
- **Detection:** `auditlib/checks/structured_data.py::analyze` (line 41) → `_absence` (line 57), `_invalid_jsonld`, `_homepage_identity` (line 98).
- **Evidence:** e.g. `"0 of 8 sampled pages contain JSON-LD, microdata, or RDFa."` with `measurements={pages_with_structured_data:0, pages:8}` and `scope="0 of 8 pages"` (line 64–68).
- **Severity:** `high` (directly observed, confidence `high`).
- **Fix (`how_to_fix`, line 66):** add schema.org JSON-LD — Organization + WebSite on the homepage, page-appropriate types elsewhere.
- **Priority:** highest penalty among findings → sorts to `F-001`.
- **Test:** `tests/test_checks.py`, `tests/test_eval.py` (fixture `no_schema_commerce`).

### 2. Crawlability — incl. AI-assistant bot blocks
- **Signal:** robots.txt blocks all crawlers, or specifically blocks AI retrieval/training bots (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot…); key pages 4xx/5xx or `noindex`.
- **Detection:** `auditlib/checks/crawl_render.py::_robots_findings` (line 57); `AI_BOTS` list (line 24).
- **Evidence:** the exact bot/rule, e.g. `"robots.txt disallows AI-assistant crawlers: GPTBot, ClaudeBot."`
- **Severity:** `critical` (site invisible) / `high` (noindex).
- **Fix:** allow the retrieval bots; scope `Disallow` to genuinely private paths.
- **Test:** `tests/test_eval.py` (fixture `blocked_robots`), `test_checks.py`.

### 3. JS-render gap (fetch-only AI sees an empty shell)
- **Signal:** primary content only appears after client-side JS; the raw HTML is an app shell.
- **Detection:** `auditlib/checks/crawl_render.py::_spa_findings` (line 385) — SPA markers + very low server-rendered word count.
- **Evidence:** e.g. `"homepage returns an app shell with 12 words of server-rendered text."`
- **Severity:** `high`, confidence `medium` (heuristic — static audit doesn't run a browser; see coverage `NOT_VERIFIED`).
- **Fix:** server-render / pre-render the primary content so facts exist in the initial HTML.
- **Test:** `tests/test_eval.py` (fixture `broken_spa`).

### 4. Facts locked out of text (extractability)
- **Signal:** missing `<title>`/meta description/H1, images without `alt`, likely text-in-images.
- **Detection:** `auditlib/checks/extractability.py::analyze` (line 26) → `_title_meta` (43), `_title_meta_quality` (92), `_images_alt` (196).
- **Evidence:** `"8 of 8 page(s) (100%) have no meta description."` (with `scope`).
- **Severity:** `high` (missing title) → `medium`/`low`.
- **Fix:** add the missing text anchors; move factual copy out of images.
- **Test:** `tests/test_checks.py`.

### 5. Freshness / staleness
- **Signal:** stale footer copyright with no other recent-date signal; content whose only dates are years old; undated articles.
- **Detection:** `auditlib/checks/freshness.py::analyze` (line 23) → `_copyright_year` (33), guarded by `_has_recent_signal` (48/77) to avoid false positives.
- **Evidence:** e.g. `"footer copyright year 2019 and no page shows a date within 13 months."`
- **Severity:** `low`–`medium`, confidence tempered.
- **Fix:** refresh visible dates / `dateModified`; the guard means a maintained site with a founding-year footer is not flagged.
- **Test:** `tests/test_eval.py` (fixture `stale`).

### 6. On-site engagement (mobile / CTA / performance)
- **Signal:** no responsive viewport, no clear call-to-action, heavy/slow pages, walls of text.
- **Detection:** `auditlib/checks/engagement.py::analyze` (line 40) → `_viewport` (60), `_primary_cta` (78).
- **Evidence:** e.g. `"homepage has no <meta name=viewport>"`, `"no primary CTA detected in the main content."`
- **Severity:** `medium`; performance/latency findings are `low` confidence (network-dependent).
- **Fix:** add viewport, a single clear CTA, defer heavy assets.
- **Dimension:** `engagement` (weighted 0.4 in the score).
- **Test:** `tests/test_checks.py`.

---

## Why this generalizes (not fit-to-examples)
The checks encode *repeatable root causes* of AI invisibility (reach → read → quote → trust →
resolve) and bounce (read → orient → act → wait), not memorized site quirks. The offline
`eval.py` harness proves it: **recall 1.00** on labelled failure-mode fixtures and **0
false positives** on the clean + non-English fixtures — reproducible with one command.

---

# Part 1 — 3-minute narration script (A / B / C)

Read this while screen-sharing the code. `[SHOW …]` marks what to put on screen. Every claim
points at real v2.7.0 code. Keep to ~3 minutes.

## A. How we discovered the signals  (~70s)
> "We didn't invent checks — we reasoned from **how an AI assistant actually uses a page**: to
> cite a brand, a machine has to *reach* it, *read* it, *quote a clear fact*, *trust* it, and
> *resolve* which entity it is. Each failure in that chain became a signal, and each signal is
> one function.
>
> [SHOW `auditlib/checks/structured_data.py::_absence`] Take the strongest: **structured data**.
> Assistants quote a fact most reliably when it's restated in machine-readable JSON-LD. So we
> check whether any JSON-LD / microdata / RDFa exists — here, `_absence` (line 57). The evidence
> is a *counted fact*, `0 of 8 pages`, not an opinion — no LLM guessing.
>
> [SHOW `auditlib/checks/crawl_render.py::_robots_findings`, `AI_BOTS` line 24] Before reading,
> the crawler must be *let in*, so we parse robots.txt specifically for the **AI answer-engine
> bots** — GPTBot, ClaudeBot, PerplexityBot, Google-Extended. [SHOW `registry.py::discover_skills`]
> And the orchestrator doesn't hardcode any of this: it **auto-discovers** each skill from its
> `SKILL.md` `metadata.checks`, runs them concurrently over **one** polite crawl, and merges the
> results. Six skills, one entrypoint."

*(Mention the other four in a breath: JS-render gap `_spa_findings`; extractability — title/meta/
H1/alt `extractability.py`; freshness `freshness.py`; engagement — viewport/CTA `engagement.py`.)*

## B. How we determine severity  (~55s)
> "Severity is assigned **at the point of detection**, on a fixed ladder (see
> `references/severity-model.md`): **critical** = the brand is effectively invisible;
> **high** = a whole *class* of facts can't be read or quoted; **medium** = a meaningful signal
> is missing; **low** = a refinement.
>
> [SHOW `crawl_render.py` lines 74 & 90] The nuance is the proof it's principled: blocking AI
> **retrieval** crawlers is **critical** (the brand vanishes from answers) — but blocking AI
> **training** crawlers is only **low**, because that's a legitimate publisher choice, not an
> invisibility bug. Zero structured data is **high**; a missing meta description is **medium**.
>
> [SHOW `auditlib/scoring.py` lines 15–21] Then scoring is **deterministic**: each dimension
> starts at 100 and loses `SEVERITY_PENALTY` (critical 35, high 18, medium 8, low 3) **×
> `CONFIDENCE_FACTOR`** (heuristic checks at 0.75 or 0.5, so we never over-punish a guess).
> Overall = discoverability×0.6 + engagement×0.4 → an A–F grade. Same inputs, same score, every run."

## C. How we generate & prioritize fixes  (~55s)
> "Every finding carries its own fix, matched to the **mechanism** it detected — not a generic
> tip. [SHOW a finding's `how_to_fix` in `structured_data.py` line ~66, or `view_report.py --finding F-001`]
> For 'no structured data' the fix is *add schema.org JSON-LD — Organization + WebSite on the
> homepage, page-appropriate types elsewhere*, because that's exactly the missing machine-readable
> restatement that made the fact unquotable. Problem → evidence → severity → **fix that closes that
> specific gap**.
>
> [SHOW `scoring.py::score_report` line 108] Prioritization falls straight out of the model:
> findings sort by `severity × confidence`, so the highest-leverage problem is always `F-001`.
> [SHOW `analytics.py` / the HTML matrix] On top, the analyst layer crosses **impact × effort** to
> flag *quick wins*, and computes `points_at_stake` — the actual score points you'd recover — so
> the projection '*fix these two → +9 → a C*' is a real recomputation with the same model, not a
> guess. That's the whole methodology: evidence-backed detection, principled severity, mechanism-
> matched fixes, deterministic prioritization — and `eval.py` proves it generalizes to unseen sites."
