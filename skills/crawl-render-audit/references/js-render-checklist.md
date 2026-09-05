# JS-render-gap checklist (gate 2: can the crawler read the page?)

The mechanism (Round-2 appendix C): a page that looks complete to a person can be empty to a
machine when the content is assembled by JavaScript *after* the initial HTML loads. Many AI
retrievers fetch the raw HTML and do **not** execute JS, so client-rendered facts are invisible.

## Signals
| Signal | How detected | Confidence |
|---|---|---|
| Empty app-shell | `<div id="root/app/__next/__nuxt"></div>` with no server markup | medium |
| Framework hydration island with thin text | `__NEXT_DATA__`, `window.__NUXT__`, `ng-version`, `data-reactroot` **and** < ~120 visible words | medium |
| Script-dominated shell | inline+referenced script bytes ≫ visible-text bytes, and < 60 visible words | medium |
| "Enable JavaScript" notice | `<noscript>` telling the user to turn on JS | medium |
| Thin server text vs page size | < 50 visible words despite > 2 KB HTML | medium |

## Why confidence is "medium"
This skill does not run a headless browser (that would break the "portable, no heavy deps,
< 5 min" guardrail). Instead it reasons from the **raw HTML** exactly as a fetch-only
retriever would — which is the population that actually suffers the render gap. When a full
render comparison is available, treat these as candidates to confirm.

## The fix (what the suggested action recommends)
Make the primary content exist in the initial HTML response:
- Server-side rendering (SSR) or static generation (SSG),
- Dynamic rendering / prerendering for bots,
- Or hydration that ships real HTML (not an empty root) so copy, headings, prices, and key
  facts are present before JavaScript executes.

Confirm by fetching the URL with JavaScript disabled (or `curl`) and checking the fact is in
the bytes.
