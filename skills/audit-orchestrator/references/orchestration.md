# Orchestration: how the entrypoint composes the marketplace

## The contract
Every non-entrypoint skill exposes one pure function over a shared context:

```python
analyze(ctx: AuditContext) -> list[Finding]
```

`AuditContext` (see `scripts/auditlib/context.py`) holds:
- `start_url` — the normalized target,
- `fetcher` — the shared, caching, robots-aware read-only `Fetcher` (for any extra
  request a check needs, e.g. `robots.txt`), so secondary fetches are deduplicated too,
- `responses` — the raw HTTP responses for the sampled pages,
- `pages` — those responses parsed into queryable `Page` objects,
- `external_lookups` — whether off-site corroboration checks may run.

`Finding` (see `scripts/auditlib/report.py`) is the one currency all skills return.

## Flow
```
run_audit.py (entrypoint)
  │
  ├─ AuditContext.build(url)          # crawl ONCE (homepage → links → sitemap), robots-respected
  │
  ├─ crawl_render.analyze(ctx)        # skills/crawl-render-audit
  ├─ structured_data.analyze(ctx)     # skills/structured-data-audit
  ├─ extractability.analyze(ctx)      # skills/content-extractability-audit
  ├─ freshness.analyze(ctx)           # skills/freshness-corroboration
  ├─ corroboration.analyze(ctx)       # skills/freshness-corroboration
  ├─ engagement.analyze(ctx)          # skills/engagement-audit
  │
  ├─ report.build_report(...)         # merge, sort, id, summarize
  └─ report.validate(...)             # self-check against the schema
```

## Why this is separation of concerns, not padding
- Each skill owns exactly one Round-2 failure class and can be run, tested, and reasoned
  about in isolation (`skills/<skill>/scripts/run.py <url>` emits a valid partial report).
- The orchestrator owns only what is genuinely shared: the crawl, the merge, the ordering,
  and the single-report contract. It contains no detection logic of its own.
- Detection logic lives in `scripts/auditlib/checks/<concern>.py`; the skill folders are the
  documented, independently-invocable units, and each thin runner calls its own check.
- Adding a new concern = add one `checks/<x>.py` + one skill folder + one manifest entry +
  one line in `CHECKS`. Nothing else changes.

## Failure isolation & determinism
- A raised exception in any single check is caught, recorded in `notes`, and the remaining
  checks still run — one flaky check never voids the audit.
- Discovery is sorted and capped, requests are cached, and no randomness is used, so the
  same site yields the same findings run to run (timing-based notes aside).
