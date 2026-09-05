---
name: engagement-audit
description: >-
  Detect why visitors who arrive don't stay — the on-site-engagement half of the
  problem. Checks the responsive mobile viewport, presence of a clear primary
  call-to-action, semantic navigation and onward links (dead-end pages), page
  weight and server response time, readability (walls of text), positional context
  on deep pages (breadcrumbs), and likely intrusive on-load pop-ups. Use when
  traffic arrives but bounces, or when AI/search sends visitors who don't convert.
  Read-only.
license: MIT
allowed-tools: [Bash]
metadata:
  dimension: engagement
  checks: [engagement]
---

# On-Site Engagement Audit

Discoverability gets the visitor to the page; engagement decides whether they stay. This
skill reads static markup and response timing for the mechanisms that drive bounce.

## When to use
Traffic arrives (from AI answers, search, ads) but bounces; pages feel disorienting, slow, or
give no obvious next step.

## Inputs
`url` (required); optional `--max-pages N`.

## Procedure
1. **Mobile**: missing responsive `viewport` meta → zoomed-out unreadable mobile layout.
2. **Next step**: homepage with no action-oriented CTA (buy/contact/sign up/book/demo…).
3. **Orientation**: no semantic `<nav>`; dead-end pages with < 3 onward internal links.
4. **Performance**: very large HTML / script-dense pages, or > 3 s server response.
5. **Readability**: 900+ words with ≤ 1 heading (a wall of text).
6. **Context retention**: deep pages with no breadcrumb trail.
7. **Interruption**: markup suggesting an on-load newsletter/subscribe interstitial.

See [engagement-checklist](references/engagement-checklist.md) for thresholds and rationale.

## Output
Findings in `mobile`, `conversion`, `orientation`, `performance`, and `readability`
categories, all on the `engagement` dimension, with evidence and prioritized actions.
Standalone:
```bash
python skills/engagement-audit/scripts/run.py https://example.com
```

## Guardrails
Read-only, static analysis. Performance signals (page weight, TTFB) are single-fetch proxies
reported at medium confidence — directional, not a substitute for field/RUM metrics.
