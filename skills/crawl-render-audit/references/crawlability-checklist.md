# Crawlability checklist (gate 1: can the crawler get in?)

The mechanism: a fact is only citable if a crawler can reach the URL. Each signal below is
a way that fails, ordered by impact.

| # | Signal | How detected | Why it matters | Severity |
|---|---|---|---|---|
| 1 | AI-assistant crawlers blocked in robots.txt | Per-agent group with `Disallow: /` for GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended, CCBot, etc. | These are the exact bots ChatGPT/Claude/Perplexity/Gemini use to fetch and cite pages. Blocking them removes the brand from those answers even if Googlebot is allowed. | critical |
| 2 | All crawlers blocked (`User-agent: *` → `Disallow: /`) | robots.txt parse | Site is invisible to search and AI alike. | critical |
| 3 | Key pages disallowed | `RobotFileParser.can_fetch` on sampled URLs | Public brand content hidden from crawlers. | high |
| 4 | Server errors (5xx) | HTTP status on sample | Crawlers drop failing pages and may deprioritize the host. | high |
| 5 | `noindex` (meta robots or `X-Robots-Tag`) on public pages | header + `<meta name=robots>` | Explicitly tells engines not to index — the page can be read but never surfaced. | high |
| 6 | No XML sitemap | `/sitemap.xml` 404 **and** no `Sitemap:` in robots | Slower/incomplete discovery of deep pages. | low |

## Notes on AI-bot policy
Some brands intentionally block **training** crawlers (e.g. `Google-Extended`, `CCBot`) while
wanting to appear in **answers**. The fix should preserve that nuance: at minimum allow the
retrieval/search agents (`OAI-SearchBot`, `ChatGPT-User`, `Perplexity-User`) so pages remain
citable, even if training bots stay disallowed.

## Robots parsing caveats
robots.txt is matched case-insensitively on user-agent tokens; a longer, more specific
`Disallow` can be re-opened by a more specific `Allow`. This checker flags only a clear
root-level block that is not re-allowed at `/`, to avoid false positives on partial rules.
