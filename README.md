# brand-ai-readiness-audit

> **Speak to Agents — brand visibility.** Point this at any website and it tells you, with
> evidence and a single score, why AI assistants aren't finding or citing the brand, and why
> visitors who do arrive don't stay — plus exactly how to fix each problem.

An **Agent Skill Marketplace** (Adobe University Hackathon 2026 — Round 3): an entrypoint
orchestrator that composes five focused, [agentskills.io](https://agentskills.io)-compliant
skills into **one prioritized audit report**. Standard-library Python only. **Read-only and
recommend-only** — it audits and reports, never modifies, authenticates against, or
rate-abuses the target.

---

## Why this matters
People increasingly ask an AI assistant instead of scrolling a results page. To be in that
answer, a brand's pages must clear a chain of gates a machine runs on its behalf:

```
        OFF-SITE DISCOVERABILITY                         ON-SITE ENGAGEMENT
  reach ─► read ─► quote ─► trust ─► resolve   │   read ─► orient ─► act ─► wait
    │       │       │        │        │         │     │       │       │       │
 robots  render  schema   fresh/   entity      │  mobile/  nav/   clear    fast
  /404   /JS gap  markup  corrob.  identity     │  text   crumbs   CTA     pages
```

If any gate fails, the brand is invisible or misrepresented — plainly there for a human, gone
for the machine. Each skill below targets one gate. The checks encode **repeatable root
causes** (from how these systems actually work), not memorized example sites, so they
generalize to sites they've never seen.

## Quickstart (one command)
Requires **Python 3.8+** — no packages, no model weights, no services.

```bash
python skills/audit-orchestrator/scripts/run_audit.py example.com
```

Show the demo view (self-contained HTML with a score gauge):

```bash
python skills/audit-orchestrator/scripts/run_audit.py example.com --format html --out report.html
```

Run the tests (fully offline):

```bash
python -m unittest discover -t . -s tests
```

## What you get: the AI Visibility Score
Every audit produces a headline **0–100 score** with an **A–F grade** and discoverability /
engagement sub-scores, then lists findings **most-actionable-first** — each with evidence,
the *why it hurts*, an impact rating, and a concrete one-line fix.

```
AI Visibility Score  72 / 100  (C)
  Discoverability ▓▓▓▓▓▓▓░░░  68
  Engagement      ▓▓▓▓▓▓▓▓░░  80

F-001  HIGH   discoverability  No structured data anywhere in the sampled pages   impact 4
       why    Without machine-readable markup, assistants must guess facts from prose.
       fix    Add schema.org JSON-LD (Organization+WebSite on home; Product/Article elsewhere).
```

## The skills
| Skill | Dimension | Gate → what it detects |
|---|---|---|
| **audit-orchestrator** *(entrypoint)* | both | Crawls once, runs every skill over the shared sample, scores, prioritizes, and emits the single report. No detection logic of its own. |
| **crawl-render-audit** | discoverability | *reach + read* — robots.txt (incl. **AI bots**: GPTBot, ClaudeBot, PerplexityBot, Google-Extended…), status, `noindex`, sitemap; client-side-render gaps. |
| **structured-data-audit** | discoverability | *quote* — JSON-LD / microdata / RDFa presence **and validity**; Organization/WebSite identity; Product/Article types + required props. |
| **content-extractability-audit** | discoverability | *read* — title/meta/headings, image alt & text-in-images, language, PDF-locked content. |
| **freshness-corroboration** | discoverability | *trust + resolve* — staleness (FP-guarded), `sameAs`/external corroboration, entity disambiguation. |
| **engagement-audit** | engagement | *orient/act/wait* — mobile viewport, CTA, nav/breadcrumbs, page weight & TTFB, readability, pop-ups. |

## Architecture
```
run_audit.py (ENTRYPOINT)
   │  validate_target (SSRF)  ·  logging  ·  --dry-run  ·  exit codes
   │
   ├─ registry.discover_skills()      ← scans skills/, validates SKILL.md, binds metadata.checks
   ├─ AuditContext.build(url, cfg)    ← ONE polite, robots-respecting, retrying crawl
   │
   ├─ ThreadPoolExecutor (global timeout guard)
   │     ├─ crawl_render.analyze(ctx)
   │     ├─ structured_data.analyze(ctx)
   │     ├─ extractability.analyze(ctx)
   │     ├─ freshness/corroboration.analyze(ctx)
   │     └─ engagement.analyze(ctx)
   │
   ├─ report.build_report()  →  scoring.score_report()  →  report.validate()
   └─ render (json | html)   ·  history.record_and_compare() [optional]

auditlib/  (shared engine, stdlib only)
   config.py  logutil.py  http.py  htmlparse.py  frontmatter.py
   registry.py  context.py  report.py  scoring.py  render.py  history.py  runner.py
   checks/  crawl_render · structured_data · extractability · freshness · corroboration · engagement
```
Each skill exposes one pure `analyze(ctx) -> [Finding]`; the orchestrator owns only the
crawl, the merge, the score, and the report contract — genuine separation of concerns.
Full flow: [orchestration.md](skills/audit-orchestrator/references/orchestration.md).

## CLI reference
| Flag | Meaning |
|---|---|
| `--max-pages N` | Pages to sample (default 12). |
| `--profile strict\|balanced\|lenient` | Threshold/scoring profile for the site type. |
| `--skills a,b` | Run a subset (e.g. `crawl-render,structured-data`). |
| `--format json\|html` | Output format (JSON is canonical; HTML is the demo view). |
| `--out FILE` | Write to a file instead of stdout. |
| `--compare-previous` / `--history-db PATH` | Store the score and show the delta vs last run. |
| `--no-external` | Skip off-site corroboration lookups. |
| `--dry-run` | Validate inputs and print the plan; no network calls. |
| `--verbose` / `--quiet` | Logging level. |
| `--allow-private` | Permit localhost/private targets (testing only). |

**Exit codes:** `0` completed · `1` partial (a check errored/timed out) · `2` bad input / unauditable.

## Output schema
JSON is the canonical output: `site`, `audited_at`, `score`, a severity- and dimension-counted
`summary`, and a prioritized `findings[]` (each with `id`, `title`, `severity`, `dimension`,
`category`, `confidence`, `evidence`, `why`, `impact`, `priority`, `affected_pages`,
`suggested_action{summary,priority}`). Contract:
[report-schema.md](skills/audit-orchestrator/references/report-schema.md); worked example:
[`examples/sample-report.json`](examples/sample-report.json).

## Add a new skill (no core edits)
1. Create `skills/<your-skill>/SKILL.md` with valid frontmatter and a
   `metadata: { checks: [<module>] }` binding.
2. Add `auditlib/checks/<module>.py` exposing `analyze(ctx) -> [Finding]`.
3. Add the skill to `marketplace.json`.

Auto-discovery validates the `SKILL.md`, binds the check, and includes it — `run_audit.py` is
never touched. Non-compliant skills are skipped with a warning.

## Safety & guardrails
Read-only · recommend-only · robots.txt-respecting · SSRF-guarded · size/time-capped ·
deterministic · self-contained · target runtime < 5 min · zip ≤ 50 MB · no model weights.

## Layout
```
brand-ai-readiness-audit/
  marketplace.json     README.md     CHANGELOG.md
  examples/sample-report.json
  tests/               ← offline unittest suite (unit + mock-server integration)
  skills/
    audit-orchestrator/   SKILL.md  scripts/{run_audit,validate_report,auditlib/…}  references/
    crawl-render-audit/           SKILL.md  scripts/run.py  references/
    structured-data-audit/        SKILL.md  scripts/run.py  references/
    content-extractability-audit/ SKILL.md  scripts/run.py  references/
    freshness-corroboration/      SKILL.md  scripts/run.py  references/
    engagement-audit/             SKILL.md  scripts/run.py  references/
```

## License
MIT.
