# Engagement checklist (keep the visitor once they arrive)

Mechanism: engagement is the Round-2 "bouncing" half — a visitor who can't read, orient,
act, or wait will leave. Each signal is a measurable proxy for that.

| Signal | How detected | Threshold | Why it matters | Severity |
|---|---|---|---|---|
| No responsive viewport | missing `<meta name=viewport>` on ≥ half the sample | — | Mobile renders a zoomed-out desktop layout; mobile visitors bounce immediately. | high |
| No clear CTA | no action link/button on the homepage | buy/shop/sign up/subscribe/contact/book/request/demo/download/try | Visitor sees no valuable next step and leaves. | medium |
| No semantic nav | no `<nav>`/`role=navigation` on any page | — | No clear menu to explore; disorientation. | medium |
| Dead-end pages | internal onward links | < 3 | Nowhere relevant to go next. | low |
| Heavy pages | HTML size or external script count | > 1.5 MB or > 40 scripts | Delays interactivity, raises bounce. | medium |
| Slow response | server time-to-HTML | > 3000 ms | Slow first byte compounds every later delay. | medium |
| Wall of text | words vs headings | ≥ 900 words and ≤ 1 heading | Unscannable; visitors skim and abandon. | low |
| No breadcrumbs on deep pages | breadcrumb markup on pages > 3 path segments | none across deep pages | Visitors landing mid-site can't tell where they are (context retention). | low |
| Intrusive interstitial | on-load newsletter/subscribe modal markup | — | An overlay before the visitor sees value drives early exits. | low (confidence low) |

## How this connects to appendix E (personalization & prior context)
Appendix E is about assistants tailoring answers to who's asking. The on-site analogue that a
static audit can act on is **orientation and context retention**: a visitor arriving deep
(e.g. from an AI answer) needs to instantly know where they are and where to go — clear nav,
breadcrumbs, and onward links. Those are what this skill checks; deeper personalization
(remembering a returning user) is a build recommendation, not a static defect.

## Honesty about proxies
Page weight and TTFB come from a single server-side fetch, so they are directional signals
reported at medium confidence, not lab/field Core Web Vitals. They tell you *where to look*,
and the suggested action points at the real fix (defer scripts, cache/CDN, lazy-load).
