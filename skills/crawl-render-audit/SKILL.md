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
1. Fetch `robots.txt`; parse user-agent groups. Flag a full-site `Disallow: /` and — a
   discoverability-specific check — any group that blocks a known **AI-assistant crawler**.
2. Over the sampled pages, flag non-200 status, robots-blocked paths, and `noindex`
   (meta robots or `X-Robots-Tag`).
3. Detect **JS-render gaps**: an app-shell marker (empty `#root`/`#app`, `__NEXT_DATA__`,
   Nuxt/Angular markers) plus very little server-rendered text, or a `<noscript>` "enable
   JavaScript" notice — signals that a fetch-only retriever sees an empty shell.
4. Check for an XML sitemap (file or `robots.txt` `Sitemap:` directive).

See [crawlability-checklist](references/crawlability-checklist.md) and
[js-render-checklist](references/js-render-checklist.md) for the full signal list and rationale.

## Output
A list of findings (`crawlability`, `indexability`, `reachability`, `js-render-gap`
categories), each with evidence, severity, and a suggested action. Standalone:
```bash
python skills/crawl-render-audit/scripts/run.py https://example.com
```
The orchestrator calls the same `analyze(ctx)` to fold these into the full report.

## Guardrails
Read-only; obeys robots.txt (and reports, rather than bypasses, anything it disallows).
