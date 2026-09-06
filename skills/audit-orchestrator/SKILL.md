---
name: audit-orchestrator
description: >-
  Entrypoint for the brand-ai-readiness-audit marketplace. Given a website URL,
  audit it for AI-discoverability problems (crawlability, JS-render gaps,
  missing/invalid structured data, facts locked in non-text, stale or
  uncorroborated facts, entity ambiguity) and on-site-engagement problems (weak
  orientation, no clear next step, mobile/perf issues, no context retention),
  then compose one prioritized audit report of findings plus suggested actions.
  Use when asked why a brand is missing or misrepresented in AI assistants, or
  why visitors who arrive don't engage. Recommend-only; never modifies the site.
license: MIT
allowed-tools: [Bash, Read]
---

# Audit Orchestrator (entrypoint)

The single skill the marketplace invokes. It turns a URL into one audit report by
running every other skill's checks over a shared crawl and merging their findings.

## When to use
- "Audit `<url>` for AI discoverability / engagement."
- "Why don't AI assistants cite this brand?" / "Why do visitors bounce?"
- Any request for a brand-AI-readiness or GEO/AEO (generative/answer-engine optimization) audit.

## Inputs
- **`url`** (required): the website or domain to audit, e.g. `https://example.com` (a bare
  domain is fine; https is assumed).
- Optional: `--max-pages N` (default 12), `--profile strict|balanced|lenient`,
  `--crawl-scope host|domain` (default host), `--skills a,b` (subset),
  `--format json|html|md`, `--out FILE`, `--csv FILE`, `--no-external`,
  `--verify-external` (opt-in Wikidata + declared-profile + corpus-presence corroboration),
  `--search-provider commoncrawl|none` (provider-neutral corpus check used with `--verify-external`),
  `--compare-previous` (+ `--history-db PATH`), `--dry-run`, `--verbose`/`--quiet`.

## Procedure (deterministic)
1. **Normalize** the URL (add scheme if missing) and derive the start host.
2. **Fetch once, share everywhere.** Crawl a small, deterministic, robots-respecting
   sample: homepage → in-page internal links → sitemap-declared URLs, capped at `--max-pages`.
   **Smart sampling** orders the frontier by page *type* — about, contact, product, pricing,
   services, faq first (they carry brand facts), everything else after — with alphabetical
   tie-breaks so the sample stays deterministic. Every page is fetched read-only, size- and
   time-capped, and cached so no URL is requested twice. This shared sample is passed to all
   checks — the orchestration contract is "crawl once, analyze many times."
3. **Invoke each skill's checks** over the shared sample (see [orchestration](references/orchestration.md)):
   - `crawl-render-audit` — is the crawler let in, and can it read the page?
   - `structured-data-audit` — is the key fact machine-quotable?
   - `content-extractability-audit` — is the fact in readable text?
   - `freshness-corroboration` — is it current and agreed upon elsewhere?
   - `engagement-audit` — will the visitor stay?
   A failure in any one check is caught and noted; it never sinks the report.
4. **Merge & normalize** all findings: assign stable ids (`F-001`…), sort by severity then
   dimension, and de-duplicate.
5. **Score**: compute the 0–100 AI Visibility Score (+ A–F grade and per-dimension
   sub-scores), enrich each finding with a plain-English *why* and an `impact`, and order
   findings most-actionable-first.
6. **Coverage + opportunities + pages + sections + scorecards**: build the per-area coverage matrix
   with named PASS/FAIL/NOT_VERIFIED/PARTIAL checks (so 0 findings ≠ healthy and rendered-DOM parity
   is marked not-verified, not healthy), surface proactive opportunities, assemble per-page detail
   for the page explorer, score each URL section, compute the **AI answer-readiness** scorecard,
   detect/generate **llms.txt**, run the **hallucination-risk** (self-contradiction) scan, build the
   **knowledge-graph** preview, and grade the **prompt-pack**. The scoring model is embedded so the
   report's what-if planner recomputes scores identically to the engine.
6b. **Fact layer** (reason about facts, not markup): extract every brand claim once into a **claim
   inventory** (`claims`) recording where each fact lives (structured data vs. visible text vs.
   off-site) and whether the site contradicts itself; score **citation readiness** (`citation_readiness`
   — will an AI quote *and attribute* the brand, not just find it?); and run a deterministic, offline
   **AI answer simulation** (`ai_answer_simulation`) projecting, per common question, whether an
   answer engine could answer and would cite this site. Emit the flat headline `scores`
   (overall / discoverability / citation / engagement) and a ranked `action_plan`.
7. **Analyze** (analyst layer): derive pillar sub-scores (with coverage-aware status), an
   impact×effort matrix with quick wins, a "what-if" score projection, page hotspots, a
   Now/Next/Later roadmap, a short auto-written executive summary (`analytics`); the **visibility
   funnel** (reach→read→quote→trust with the bottleneck gate); a **machine-executable fix plan**
   plus copy-paste fix snippets; and, opt-in (`--compare-with`), a **competitor benchmark**.
   A standalone `scripts/eval.py` proves generalization + zero false positives on a labeled corpus.
8. **Summarize**: counts by severity and by dimension (discoverability vs engagement).
9. **Emit** one JSON audit report (schema below); or the self-contained HTML dashboard
   (`--format html`), a Markdown brief (`--format md`), and/or a findings CSV (`--csv FILE`).
   Validate before returning.

Run it:
```bash
python skills/audit-orchestrator/scripts/run_audit.py https://example.com --max-pages 12
```

## How it composes the other skills
Each sub-skill exposes a pure `analyze(ctx) -> [Finding]` function over the shared crawl
context; the orchestrator (`scripts/run_audit.py`) imports and calls them, then assembles
the report. This is genuine separation of concerns: each skill owns one failure class and
can run standalone (`skills/<skill>/scripts/run.py <url>`), while the orchestrator owns the
crawl, the merge, and the single-report contract. Shared crawl/parse/report logic lives in
`scripts/auditlib/` so no skill re-implements HTTP or HTML parsing.

## Output (fixed schema — floor, not ceiling)
```json
{
  "site": "example.com",
  "audited_at": "2026-09-20T14:32:00Z",
  "summary": { "total_findings": 6, "critical": 1, "high": 2, "medium": 3,
               "by_dimension": { "discoverability": 4, "engagement": 2 } },
  "findings": [
    {
      "id": "F-001",
      "title": "No JSON-LD structured data on product pages",
      "severity": "high",
      "dimension": "discoverability",
      "category": "structured-data",
      "confidence": "high",
      "evidence": "Crawled 12 product pages; 0/12 contain schema.org markup.",
      "affected_pages": ["https://example.com/p/1"],
      "suggested_action": { "summary": "Add Product/Offer JSON-LD to every product page.",
                            "priority": "high" }
    }
  ]
}
```
Required per finding: `id`, `title`, `severity`, `evidence`, `suggested_action{summary,priority}`.
Required summary metadata: `site`, `audited_at`, counts-by-severity. Everything else is an
additive extension — including `score` and the `analytics` block (pillars, impact×effort matrix,
projection, hotspots, roadmap, KPIs, narrative). See [report-schema](references/report-schema.md)
and [severity-model](references/severity-model.md).

## Guardrails
Recommend-only, read-only, robots-respecting, no authenticated or destructive actions,
size/time-capped, target runtime < 5 minutes. Suggested actions may include proactive
improvements beyond detected defects.
