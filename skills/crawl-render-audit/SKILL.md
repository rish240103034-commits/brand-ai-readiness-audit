---
name: crawl-render-audit
description: >-
  Detect why a crawler can't reach or read a site's pages — the first two gates of
  AI discoverability. Checks robots.txt (including explicit blocks on AI-assistant
  crawlers like GPTBot, ClaudeBot, PerplexityBot, Google-Extended), HTTP status,
  noindex / X-Robots-Tag, sitemap presence, and client-side-render gaps where the
  primary content only appears after JavaScript runs. Use when a brand is invisible
  to AI assistants despite looking fine in a browser. Read-only.
license: MIT
allowed-tools: [Bash]
metadata:
  dimension: discoverability
  checks: [crawl_render]
---

# Crawl & Render Audit

Visibility starts with two gates: the crawler must be **let in**, then it must be able to
**read** the page. This skill checks both.

## When to use
The brand doesn't appear in AI answers at all; pages look fine to a human but may be
blocked, non-200, `noindex`, or rendered entirely in the browser.

## Inputs
`url` (required); optional `--max-pages N`.

## Procedure
1. Fetch `robots.txt`; parse user-agent groups. Flag a full-site `Disallow: /`, and — nuanced,
   not "allow everything" — distinguish blocked **AI retrieval/citation** crawlers (OAI-SearchBot,
   ChatGPT-User, PerplexityBot… → *critical*) from blocked **AI training** crawlers (GPTBot,
   ClaudeBot, Google-Extended… → a low-severity, explicit policy note, since excluding training is
   a legitimate choice).
2. Over the sampled pages, flag non-200 status, robots-blocked paths, and `noindex`
   (meta robots or `X-Robots-Tag`).
3. **Canonical**: flag `rel=canonical` pointing to a *different domain* (consolidates this site away).
4. **hreflang / i18n** (only on internationalized sites — silent on single-language sites): missing
   `x-default`, invalid language codes, and non-reciprocal (return-link) hreflang.
5. **Link health**: internal links marked `rel=nofollow`; and a bounded, time-capped probe of a few
   internal links for real **4xx/5xx** targets (a timeout is *not* treated as broken).
6. Detect **JS-render gaps**: an app-shell marker (empty `#root`/`#app`, `__NEXT_DATA__`,
   Nuxt/Angular markers) plus very little server-rendered text, or a `<noscript>` "enable
   JavaScript" notice — signals that a fetch-only retriever sees an empty shell.
7. Check for an XML sitemap (file or `robots.txt` `Sitemap:` directive).

Render analysis is **static only**: JS-render gaps are inferred from the raw HTML and reported at
medium confidence; true rendered-DOM parity is not executed and is marked *not verified* in coverage.
See [crawlability-checklist](references/crawlability-checklist.md) and
[js-render-checklist](references/js-render-checklist.md) for the full signal list and rationale.

## Output
Findings in `crawlability`, `indexability`, `reachability`, and `js-render-gap` categories, each
with evidence, severity, and a suggested action. Standalone:
```bash
python skills/crawl-render-audit/scripts/run.py https://example.com
```
The orchestrator calls the same `analyze(ctx)` to fold these into the full report.

## Guardrails
Read-only; obeys robots.txt (and reports, rather than bypasses, anything it disallows).
