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

## 60-second demo (for judges)
Three commands, no setup — each finishes in well under a minute.

**1 · Score a real site and open the analytics dashboard**
```bash
python skills/audit-orchestrator/scripts/run_audit.py smashingmagazine.com --format html --out report.html
```
Open `report.html` for the full analyst report: the **AI Visibility Score** gauge, a KPI row, an
auto-written **executive summary**, a **score projection** (where the score lands if you fix the
quick wins vs. everything), a **pillar radar**, **severity** and **impact × effort** charts, a
**Now / Next / Later roadmap**, **page hotspots**, and filterable findings.

**2 · Get the machine-readable report + a spreadsheet export**
```bash
python skills/audit-orchestrator/scripts/run_audit.py smashingmagazine.com --csv findings.csv
```
Prints the canonical JSON (score + `analytics` + prioritized findings) and writes `findings.csv`
— one row per finding with impact, effort, quadrant, and points-at-stake — ready for a pivot table.

**3 · Prove it generalizes: run the eval harness**
```bash
python skills/audit-orchestrator/scripts/eval.py
```
Audits a labeled corpus of synthetic sites (one per failure mode + a clean site + a non-English
site) and prints a scorecard — **recall 1.00** on the failure modes, **0 findings on the clean
site** (zero false positives). Plus the full offline test suite:
```bash
python -m unittest discover -t . -s tests
```

**No time to run anything?** Open the prebuilt
[`examples/sample-report.html`](examples/sample-report.html) (a real audit of
smashingmagazine.com) — or its [Markdown](examples/sample-report.md),
[JSON](examples/sample-report.json), and [CSV](examples/sample-report.csv) siblings.

> **What to look at:** the *score projection* ("+9 → a C with 2 quick wins") and the
> *impact × effort* matrix turn a list of problems into a defensible plan — the analyst
> judgment layered on top of the raw checks.

## What you get: an analyst-grade report
Every audit produces a headline **0–100 AI Visibility Score** with an **A–F grade** and
discoverability / engagement sub-scores, then an **analytics layer** an analyst would write on
top of it (in JSON as `analytics`, and rendered in the HTML dashboard, Markdown brief, and CSV):

- **Six pillar sub-scores** (crawl & render, structured data, extractability, freshness,
  corroboration, engagement) with a health status each — the radar chart.
- **Impact × effort matrix** placing every finding in a quadrant: **quick win**, major project,
  fill-in, or low-priority.
- **Score projection** — how far the score would rise if you fixed the quick wins, or everything,
  and how many points to the next grade.
- **Page hotspots**, a **Now / Next / Later roadmap**, severity/confidence distributions, and a
  short auto-written **executive summary**.

Findings are still listed **most-actionable-first** — each with evidence, the *why it hurts*, an
impact rating, an effort estimate, and a concrete one-line fix.

**Honest coverage — 0 findings ≠ healthy.** Every report includes a **coverage matrix** (per area:
checks, pages assessed, findings, status, confidence). An area is marked **not assessed** when its
skill didn't run or there wasn't enough signal to judge (e.g. Freshness on a page with no dates),
and Corroboration is at most **partial** (on-page signals only — no independent external
verification is claimed). This is the difference between *verified healthy* and *unknown*.

**Rich, per-finding evidence.** Each finding carries a **specific** `why` (set by the check that
raised it, so it always matches the defect), a `how_to_fix`, a `scope` (`8 of 12 pages (67%)`),
structured `measurements`, and `expected_impact` — plus a **traceable score explanation** (the
formula and each finding's exact point cost).

**Proactive opportunities.** A separate section of context-justified recommendations (author
markup, product ratings, FAQPage/BreadcrumbList, logo, key-facts summary) that raise AI-readiness
beyond fixing defects. They never affect the score and only appear when the crawl justifies them.

**Passed checks, not just failures.** Every area lists its named checks resolved to
**PASS / FAIL / NOT_VERIFIED / PARTIAL** (e.g. Rendering's rendered-DOM parity is honestly
NOT_VERIFIED — this static audit runs no browser — so Rendering reads *partial*, never a false
"healthy"). This is what makes the coverage summary trustworthy.

**Interactive report.** The HTML is rendered from the **embedded canonical JSON** (report and
export can't disagree). It ships a **page explorer** (searchable/sortable per-URL detail with
"Open ↗"), **combined filters** (dimension + severity + confidence, AND-combined) with search,
sort, and a live count, two-way **finding ↔ page** navigation, and a **Download JSON / Copy JSON /
Print** toolbar — all vanilla JS, no dependencies, degrading to a static report without JavaScript.

**What-if planner.** Tick the findings you plan to fix and the AI Visibility Score recomputes
**live** — build and compare remediation plans yourself. The scoring model is embedded
(`report.scoring_model`), so the in-page maths is identical to the engine's (the planner's
*Current* value always equals the reported score); "tick all quick wins" shows the fastest path up.

**Section analysis.** Pages are grouped by top-level URL path (`/products/*`, `/blog/*`, …) and
each section is scored, so you can see *which part* of the site drags the score down.

**Opt-in off-site corroboration** (`--verify-external`). By default the audit never touches
third-party sites (deterministic, no keys). When you opt in, it corroborates the brand against
**Wikidata** (does an entity exist whose official-website property points back to this domain? is
there a Wikipedia article?) and resolves the brand's **own declared** `sameAs`/social links — then
upgrades Corroboration from *partial* to a real **verified / found-but-unlinked / not-found**
result. Keyless, ToS-friendly public sources only; it never scrapes search engines or social feeds
and never fabricates a result.

**AI answer-readiness scorecard.** Grades six common questions — who / what / where / contact /
pricing / hours — on whether the answer is **machine-readable** (in structured data), text-only, or
missing (questions that don't apply to a site are marked n/a). It reframes discoverability as
"could an assistant actually answer questions about this brand?"

**llms.txt support.** Detects whether the site publishes an `llms.txt` (the emerging standard for
telling AI assistants what a site is and where its key content lives) and, if not, **generates a
suggested one** from the brand, description, and key pages — copy-paste ready.

**hreflang / i18n checks.** For internationalized sites, flags the common, high-confidence mistakes
(missing `x-default`, invalid language codes, non-reciprocal hreflang) — and stays silent on
single-language sites (no false positives).

### Proof, position, mechanism & action
- **Eval harness** — a labeled synthetic-site corpus + scorecard proving recall on failure modes
  and zero false positives on a clean site (evidence of generalization).
- **Competitor benchmarking** (`--compare-with`) — side-by-side scores + the citation gaps where a
  competitor leads.
- **Visibility funnel** — discoverability scored as **reach → read → quote → trust**, naming the
  bottleneck gate (an early failure caps the rest) — reasoned from how AI systems actually work.
- **Agent-native remediation** — a copy-paste fix snippet per finding and a machine-executable
  `fix_plan` another agent could run.

### The fact layer — "will an AI *quote* you?"
- **Claim inventory** — every checkable brand fact (name, founding year, location, offering,
  contact, identity links, pricing) is extracted *once* and tagged by where it lives: machine-readable
  structured data, human-visible prose, or off-site. The audit reasons about **facts, not markup**.
- **Citation-readiness score** (0–100) — the harder question beyond discoverability: once an AI has
  found you, will it **quote and attribute** you, or paraphrase a competitor? A deterministic composite
  of machine-quotability, extractability, corroboration, stability and attribution, with a weakest-link
  callout — honest about being capped until `--verify-external` confirms corroboration.
- **AI answer simulation** — for each common question ("who is X?", "when was X founded?", "how much
  does X cost?") a transparent, offline projection of whether an answer engine could answer and
  **whether it would cite your site**. Not a model call — an explainable rule over your own claims.
- **Smart sampling** fills that claim inventory by crawling the fact-bearing page *types* first
  (about, contact, product, pricing) within the page budget — deterministically.
- **Provider-neutral corroboration** (`--verify-external`): a pluggable `SearchProvider` interface
  with a bundled **keyless Common Crawl** presence check (is the brand in the open web corpus AI
  learns from?) — degrades honestly to "unavailable", never hard-wired to one vendor.

### AI-era differentiators
- **Hallucination-risk scan** — audits the site *against itself* and flags facts that should be
  singular but disagree across pages (founding year, social handles), plus **unverifiable superlative
  claims** ("world's #1", "market leader") an assistant may repeat as fact. Those are direct causes of
  assistants stating the wrong thing about a brand.
- **"What a fetch-only AI sees"** — each page shows the exact text a JavaScript-less retriever
  extracts, with a content-density risk: the visceral gap between the human page and the bot's view.
- **Knowledge-graph preview** — draws the entity graph an AI can build from your JSON-LD
  (Organization → sameAs → Products / Articles / People), with the **missing edges** highlighted.
- **Prompt-pack readiness** — grades the real prompts people ask assistants ("is <brand> legit?",
  "<brand> pricing", "who founded <brand>?") as ready / partial / weak by the facts you expose.

```
AI Visibility Score  63 / 100  (D — Weak)     → 72 (C) after 2 quick wins  → 100 if all fixed
  Discoverability ▓▓▓▓░░░░░░  38      Engagement ▓▓▓▓▓▓▓▓▓▓ 100
  Weakest pillar: Structured Data (48/100)    Est. effort: substantial

F-001  HIGH   discoverability  No structured data anywhere in the sampled pages   impact 4
       why    Without machine-readable markup, assistants must guess facts from prose.
       fix    Add schema.org JSON-LD (Organization+WebSite on home; Product/Article elsewhere).
       plan   quadrant: major project · effort: high · fixing it: +9 pts
```

## The skills
| Skill | Dimension | Gate → what it detects |
|---|---|---|
| **audit-orchestrator** *(entrypoint)* | both | Crawls once, runs every skill over the shared sample, scores, prioritizes, and emits the single report. No detection logic of its own. |
| **crawl-render-audit** | discoverability | *reach + read* — robots.txt (incl. **AI bots**: GPTBot, ClaudeBot, PerplexityBot, Google-Extended…), status, `noindex`, canonical, sitemap, **hreflang/i18n**, broken/nofollow internal links; client-side-render gaps. |
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
   ├─ report.build_report() → scoring.score_report() → proactive.build()
   │        → coverage.build() → pages.build() → analytics.attach() → report.validate()
   └─ output: json | interactive html | md brief | csv   ·  history.record_and_compare() [optional]

auditlib/  (shared engine, stdlib only)
   config.py  logutil.py  http.py  htmlparse.py  frontmatter.py
   registry.py  context.py  report.py  scoring.py  coverage.py  pages.py  proactive.py
   analytics.py  answer_readiness.py  llmstxt.py  external.py  consistency.py
   knowledge_graph.py  prompts.py  funnel.py  benchmark.py  snippets.py
   render.py  exports.py  history.py  runner.py
   (scripts/ also ships eval.py — the offline generalization/false-positive harness)
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
| `--crawl-scope host\|domain` | `host` (default) audits only the given host; `domain` spans all subdomains. |
| `--skills a,b` | Run a subset (e.g. `crawl-render,structured-data`). |
| `--format json\|html\|md` | Output format: JSON (canonical), HTML (dashboard), Markdown (brief). |
| `--out FILE` | Write to a file instead of stdout. |
| `--csv FILE` | Also write findings as CSV (one row per finding, with analytics fields). |
| `--compare-previous` / `--history-db PATH` | Store the score and show the delta vs last run. |
| `--no-external` | Skip off-site corroboration lookups. |
| `--verify-external` | Opt-in: corroborate the brand against Wikidata + its own declared profile links (bounded, read-only requests to public sources; off by default). |
| `--compare-with a.com,b.com` | Opt-in: benchmark against up to 3 competitor domains (side-by-side scores + citation gaps). |
| `--dry-run` | Validate inputs and print the plan; no network calls. |
| `--verbose` / `--quiet` | Logging level. |
| `--allow-private` | Permit localhost/private targets (testing only). |

**Exit codes:** `0` completed · `1` partial (a check errored/timed out) · `2` bad input / unauditable.

## Output schema
JSON is the canonical output: `site`, `audited_at`, `score`, a severity- and dimension-counted
`summary`, a prioritized `findings[]` (each with `id`, `title`, `severity`, `dimension`,
`category`, `confidence`, `evidence`, `why`, `impact`, `priority`, `affected_pages`,
`suggested_action{summary,priority}`), and an additive **`analytics`** block (`kpis`, `pillars`,
`distribution`, `matrix`, `quick_wins`, `projection`, `hotspots`, `roadmap`, `narrative`).
Contract: [report-schema.md](skills/audit-orchestrator/references/report-schema.md); worked
examples: [`sample-report.json`](examples/sample-report.json) ·
[`.html`](examples/sample-report.html) · [`.md`](examples/sample-report.md) ·
[`.csv`](examples/sample-report.csv).

## Fairness, bias & limitations
The audit tries to be neutral about site *type*; where it cannot be, it says so. This is what
was actively de-biased and what remains a disclosed design choice.

**Actively removed (v1.3.0):**
- **Language.** CTA detection is language-neutral (it recognizes conversion-path links and
  `cta`/`button` markup, not only English verbs), and word counts credit CJK / Thai / Korean
  characters instead of whitespace tokens alone — so a content-rich non-English page is no longer
  mis-flagged as "thin", "requires JavaScript", or "no CTA".
- **Third-party subdomains.** The crawl is scoped to the exact host you give by default
  (`--crawl-scope host`), so a brand isn't scored on help-desk / status subdomains it doesn't
  build (e.g. a Zendesk `support.brand.com`). Use `--crawl-scope domain` to span all subdomains.
- **Brand-name length.** The check that penalized short/generic names was removed; entity identity
  is now judged only by name-neutral markup (Organization/WebSite schema and `sameAs`).

**Disclosed by-design biases** (inherent to what "AI readiness" means — kept, but honest):
- **Fetch-only assumption.** JS-render-gap findings assume retrievers that don't execute
  JavaScript, which disadvantages client-rendered SPAs vs. SSR/static sites. This is the audit's
  core thesis; such findings are `medium` confidence (so they dock less) and name the assumption.
  Server-render / pre-render is the fix.
- **Structured-data expectations scale with type.** Commerce and publishing sites face more (and
  higher-severity) schema checks (Product/Offer, Article) than a brochure site — they genuinely
  need more markup to be answer-ready.
- **Composite weighting.** The headline score weights discoverability 0.6 / engagement 0.4 for
  every site; both sub-scores are always reported separately so each can be judged on its own.
- **Deduction model.** Score = 100 − penalties per *distinct problem type*, so a larger, more
  heterogeneous site has more surface area to accumulate finding types. Evidence always states
  prevalence ("4 of 12 pages"), and confidence-weighting damps the most heuristic checks.

**Known limits:** static analysis (no JS execution), a bounded page sample (default 12, not the
whole catalog), and English-oriented heuristics for a few low-severity signals (article/date hints).

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
  examples/            ← sample-report.{json,html,md,csv} (one real audit, all formats)
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
