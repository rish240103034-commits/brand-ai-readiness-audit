# Severity & prioritization model

Severity answers "how much does this hurt being found/cited or keeping the visitor?"
Priority (on the suggested action) answers "how urgently, given impact vs. effort?"
They usually match, but a high-impact, low-effort fix can be prioritized above a
higher-severity but expensive one.

## Severity ladder
| severity | meaning | examples |
|---|---|---|
| `critical` | The page/brand is effectively invisible or unauditable. | robots.txt blocks all/AI crawlers; homepage returns 5xx / unreachable. |
| `high` | A whole class of key facts can't be found, read, or quoted. | primary content requires JS; no structured data anywhere; missing `<title>`; noindex on public pages; no mobile viewport. |
| `medium` | A meaningful signal is missing or weak. | homepage lacks Organization schema; missing meta descriptions; no clear CTA; slow/heavy pages; missing sameAs. |
| `low` | A refinement that helps at the margin. | duplicate titles; multiple H1s; no breadcrumbs; stale copyright with no other recency signal. |
| `info` | Neutral observation / proactive-only note. | reserved for beyond-defect suggestions surfaced as findings. |

## Confidence
Static analysis can't render JavaScript or read a human's mind, so each finding carries a
confidence:
- **high** — directly observed in the fetched bytes (missing tag, robots rule, HTTP status).
- **medium** — strong heuristic (app-shell markers implying a render gap; image-heavy/text-thin page implying text-in-images).
- **low** — suggestive pattern (possible on-load interstitial).

Low-confidence findings are still reported (they are cheap to verify) but never inflated in
severity. This is how the marketplace keeps recall high without manufacturing false positives.

## Ordering
Findings are sorted by severity, then dimension, then title, and only then assigned ids —
so `F-001` is always the most important problem on the site.
