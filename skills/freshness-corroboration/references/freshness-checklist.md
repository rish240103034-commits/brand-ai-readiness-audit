# Freshness checklist (recency half of appendix D)

Mechanism: content that looks abandoned is trusted and surfaced less. Recency is a proxy for
"is this still true?"

| Signal | How detected | Guard against false positives | Severity |
|---|---|---|---|
| Stale copyright year | max year in a `©/Copyright …` footer span < last year | **Skip** if the page shows any year within ~13 months or a date < 400 days old elsewhere (a founding-year footer beside a fresh "last updated" is fine). Range like `2001–2025` uses the end year. | medium |
| Only-old content dates | newest ISO date in the page > 2 years old | Skip if a recent-date signal exists on the page. | low |
| Undated articles | article-type URL/"min read" with no visible or structured date | — | low |

## Why the guards matter
The naive version of these checks is a false-positive factory: many maintained sites carry a
founding year (`© 2001`) in the footer, and reference/docs pages legitimately cite old dates in
their body. Flagging those as "stale" erodes trust in the whole report. The rule here is:
**only flag apparent staleness when there is no competing evidence of recency on the page.**

## The fix
- Generate the footer year from the server clock (or use a maintained range).
- Show and mark up a genuine `datePublished`/`dateModified`; refresh evergreen pages and
  restate the fact so the recency signal is honest, not cosmetic.
