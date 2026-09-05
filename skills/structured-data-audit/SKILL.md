---
name: structured-data-audit
description: >-
  Detect missing, invalid, or incomplete machine-readable structured data — the
  restatement of a page's key facts that lets an assistant quote a clear answer
  without guessing from prose. Checks JSON-LD / microdata / RDFa presence and
  validity, entity identity (Organization/WebSite on the homepage), and
  page-appropriate types (Product/Offer, Article/BlogPosting, FAQPage) with their
  recommended properties. Use when a brand is found but misquoted, or absent from
  rich AI answers despite readable content. Read-only.
license: MIT
allowed-tools: [Bash]
metadata:
  dimension: discoverability
  checks: [structured_data]
---

# Structured Data Audit

Structured data is the fact stated in a form a machine can lift verbatim. When it is absent
or malformed, assistants must infer from prose (lossy, error-prone); when present and valid,
the fact is trivially quotable and the brand's identity is unambiguous.

## When to use
The brand is readable but under-cited, misattributed, or missing from rich results;
product/article pages lack machine-readable specs, prices, dates, or authorship.

## Inputs
`url` (required); optional `--max-pages N`.

## Procedure
1. Parse all JSON-LD, microdata, and RDFa on the sampled pages.
2. Flag **sitewide absence** of any structured data.
3. Flag **invalid JSON-LD**: an `application/ld+json` block that exists but fails to parse
   (so it is silently ignored — wasted markup).
4. Flag a homepage lacking **Organization / LocalBusiness / WebSite** identity nodes.
5. Flag **page-type mismatches**: product-shaped pages without `Product`/`Offer`; article
   pages without `Article`/`BlogPosting`.
6. Flag existing nodes **missing recommended properties** (e.g. `Product` without `offers`,
   `Article` without `datePublished`).

Page-type detection uses URL shape plus cart/price cues, deliberately narrow to avoid
flagging blog posts that merely mention a price. See
[schema-checklist](references/schema-checklist.md).

## Output
Findings in the `structured-data` and `entity-identity` categories with evidence, severity,
and concrete "add this schema with these fields" actions. Standalone:
```bash
python skills/structured-data-audit/scripts/run.py https://example.com
```

## Guardrails
Read-only; parses only what the page already ships.
