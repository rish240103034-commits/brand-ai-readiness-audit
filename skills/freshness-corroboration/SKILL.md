---
name: freshness-corroboration
description: >-
  Detect two trust problems that keep facts out of AI answers: staleness (content
  that looks abandoned — old copyright years with no other recent signal, undated
  articles, dates years old) and weak corroboration (a claim that lives in only one
  place, no sameAs links to external profiles, no presence on independent sources,
  and an ambiguous brand name that invites mistaken identity). Use when a brand is
  distrusted, out-of-date, or confused with something else in AI answers. Read-only.
license: MIT
allowed-tools: [Bash]
metadata:
  dimension: discoverability
  checks: [freshness, corroboration]
---

# Freshness & Corroboration Audit

Mechanism (Round-2 appendix D): machines treat a fact as more trustworthy when it looks
current and when many independent sources agree on it. A lone, undated claim is fragile; a
recent claim echoed across the web is repeated back confidently. Shared names cause mistaken
identity unless something clearly distinguishes the brand.

## When to use
The brand is found but distrusted, dated, or conflated with a namesake; AI answers cite
competitors or repeat stale facts.

## Inputs
`url` (required); optional `--max-pages N`, `--no-external`.

## Procedure
1. **Freshness**: stale footer copyright year *with no other recent-date signal on the page*
   (a founding-year footer beside "Last updated 2026" is not flagged); content whose only
   dates are > 2 years old; article-type pages published with no visible date.
2. **Corroboration**: an `Organization` node with no `sameAs`; no links anywhere to external
   brand/authority profiles (social, Wikipedia/Wikidata, Crunchbase, maps/reviews).
3. **Entity disambiguation**: a short/generic brand name with no distinguishing attributes
   (address, foundingDate, founder, legalName, sameAs); conflicting `og:site_name` across
   same-language pages.

See [freshness-checklist](references/freshness-checklist.md) and
[corroboration-checklist](references/corroboration-checklist.md).

## Output
Findings in `freshness`, `corroboration`, and `entity-identity` categories. Standalone:
```bash
python skills/freshness-corroboration/scripts/run.py https://example.com
```

## Guardrails
Read-only. Off-site checks inspect only links the site already publishes; no third-party
scraping. Freshness checks are guarded against false positives by requiring the *absence* of
any recent-date signal before flagging.
