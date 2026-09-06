# AI Readiness Audit — smashingmagazine.com

**AI Visibility Score: 68/100 (Grade D)** · discoverability 51.2 · engagement 93.0

_Audited 2026-09-06T18:26:45Z · profile balanced · 6 page(s) crawled_

> smashingmagazine.com scores 68/100 (grade D — Weak). Several issues are actively limiting how the brand is found and read.
> 1 finding(s) are critical or high severity and should be addressed first; the weakest area is Structured Data (66/100).
> 2 quick win(s) (high impact, low effort) would lift the score by about 10 point(s) to ~78/100 — enough to move up a grade.
> Fixing every finding would raise the score to about 100/100 (+32); estimated effort overall is substantial.
> Discoverability (51) and engagement (93) diverge by 42 points; discoverability is the side pulling the score down.
> Assessed 8 of 8 areas. 3 proactive opportunity(ies) identified.

## Key metrics

| Metric | Value |
|---|---|
| AI Visibility Score | 68/100 (D) |
| Total findings | 9 |
| Critical + high | 1 |
| Quick wins | 2 |
| Projected after quick wins | 78/100 (+10) |
| Full potential | 100/100 |
| Weakest pillar | Structured Data (66.0/100) |
| Estimated effort | Substantial |
| Pages analyzed | 6 |

## AI readiness at a glance

| Dimension | Score |
|---|---|
| Overall AI readiness | 68/100 |
| Discoverability (can an AI find it?) | 51/100 |
| Citation readiness (will an AI quote it?) | 61/100 |
| Engagement readiness (will visitors stay?) | 93/100 |

### Citation readiness — 61/100 (D)

| Signal | Score | Detail |
|---|---|---|
| Machine-quotable facts | 0/100 | 0% of extracted claims are in structured data. |
| Facts readable as text | 100/100 | 4/4 claims appear in visible page text. |
| Independent corroboration | 65/100 | 2 declared off-site identity links, but not externally verified. |
| Fact stability (no self-contradiction) | 100/100 | No contradictory facts detected. |
| Citable entity identity | 100/100 | Organization entity + identity links present. |

> _Corroboration is capped without live verification. Re-run with --verify-external to confirm identity links (Wikidata + declared profiles)._

### What an AI would answer about this brand

| Question | Answerable | Would cite this site? | Basis |
|---|---|---|---|
| Who is Smashing Magazine and what do they do? | yes | no | text |
| When was Smashing Magazine founded? | no | no | none |
| Where is Smashing Magazine based / headquartered? | no | no | none |
| What does Smashing Magazine sell or offer? | no | no | none |
| How do I contact Smashing Magazine? | yes | no | text |
| How much do Smashing Magazine's products/services cost? | no | no | none |
| Is Smashing Magazine a legitimate, established company? | yes | no | text |

### Claim inventory

- 4 brand facts extracted; 0% machine-readable, 0% quotable verbatim, 0 contradicted.

## Pillar breakdown

| Pillar | Score | Status | Findings |
|---|---|---|---|
| Crawl & Render | 100/100 | partial | 0 |
| Structured Data | 66/100 | critical | 3 |
| Extractability | 85/100 | warning | 4 |
| Freshness | 100/100 | healthy | 0 |
| Corroboration | 100/100 | partial | 0 |
| Engagement | 93/100 | healthy | 2 |

## Quick wins (do these first)

- **Homepage lacks Organization/WebSite structured data** — impact 3/5, low effort, +5 pts (F-003)
- **Pages missing an H1 heading** — impact 3/5, low effort, +5 pts (F-004)

## Roadmap

**Now**

- 🟠 No structured data anywhere in the sampled pages (high, medium effort)
- 🟡 Homepage lacks Organization/WebSite structured data (medium, low effort)
- 🟡 Pages missing an H1 heading (medium, low effort)

**Next**

- 🟡 Article/blog pages missing Article schema (medium, medium effort)
- 🟡 Slow server response on sampled pages (medium, high effort)

**Later**

- 🟢 Deep pages lack breadcrumbs / positional context (low, low effort)
- 🟢 Heading hierarchy skips levels (low, low effort)
- 🟢 Meta descriptions likely to be truncated (low, low effort)
- 🟢 Title tags outside the useful length range (low, low effort)

## Findings

### 🟠 F-001 · No structured data anywhere in the sampled pages  
`high` · discoverability / structured-data · confidence high · impact 4/5

- **Why it hurts:** With no machine-readable markup, an assistant must infer every fact (who the brand is, what it sells, prices, dates) from prose — error-prone and rarely quoted with confidence.
- **Evidence:** 0 of 6 sampled pages contain JSON-LD, microdata, or RDFa.
- **Fix (high):** Add schema.org JSON-LD to key templates: Organization + WebSite on the homepage, and the page-appropriate type (Product/Offer, Article, FAQPage, LocalBusiness, BreadcrumbList) elsewhere. This is the highest-leverage discoverability fix.

### 🟡 F-002 · Article/blog pages missing Article schema  
`medium` · discoverability / structured-data · confidence high · impact 3/5

- **Why it hurts:** Without Article markup an assistant cannot reliably attribute the piece to an author or date it, so it is trusted and cited less for topical questions.
- **Evidence:** 1 of 6 page(s) (17%) look like articles but lack Article/BlogPosting JSON-LD, e.g. https://www.smashingmagazine.com/articles/.
- **Fix (medium):** Add Article/BlogPosting JSON-LD with headline, author, datePublished, and dateModified so assistants can attribute and date the content.
- **Affected pages:** https://www.smashingmagazine.com/articles/

### 🟡 F-003 · Homepage lacks Organization/WebSite structured data  
`medium` · discoverability / entity-identity · confidence high · impact 3/5

- **Why it hurts:** Without an Organization/WebSite node, an assistant has no stable, machine-readable identity for the brand and cannot confidently attribute facts or citations to it.
- **Evidence:** Homepage (https://www.smashingmagazine.com/) has no Organization, LocalBusiness, or WebSite JSON-LD; detected types: none.
- **Fix (high):** Add an Organization (or LocalBusiness) node with name, url, logo, and sameAs, plus a WebSite node with name and optional SearchAction. This gives assistants a stable, unambiguous identity for the brand.

### 🟡 F-004 · Pages missing an H1 heading  
`medium` · discoverability / extractability · confidence high · impact 3/5

- **Why it hurts:** The H1 is the primary topic anchor a machine uses to decide what a page is about; without it the page's subject must be guessed from weaker signals.
- **Evidence:** 1 of 6 page(s) (17%) have no H1, e.g. https://www.smashingmagazine.com/articles/.
- **Fix (medium):** Add exactly one descriptive H1 per page stating what the page is about in plain words.
- **Affected pages:** https://www.smashingmagazine.com/articles/

### 🟡 F-005 · Slow server response on sampled pages  
`medium` · engagement / performance · confidence low · impact 2/5

- **Why it hurts:** A slow first byte (TTFB) delays everything downstream, so the page starts rendering late and visitors abandon before it appears.
- **Evidence:** 4 of 6 page(s) (67%) took over 3s to return HTML in this run (e.g. https://www.smashingmagazine.com/author/cosima-mielke/: 64043 ms). Single-sample timing — confirm with a repeat measurement.
- **Fix (medium):** Investigate TTFB (caching, CDN, server work); confirm the slowness is consistent before prioritizing.
- **Affected pages:** https://www.smashingmagazine.com/2026/08/desktop-wallpaper-calendars-september-2026/, https://www.smashingmagazine.com/2026/08/rethinking-data-visualisation-ux-approach-dashboards/, https://www.smashingmagazine.com/2026/08/why-website-should-never-stop-changing/, https://www.smashingmagazine.com/author/cosima-mielke/

### 🟢 F-006 · Deep pages lack breadcrumbs / positional context  
`low` · engagement / orientation · confidence high · impact 2/5

- **Why it hurts:** A visitor landing on a deep page from search/an answer can't tell where they are in the site or move up a level, so they leave rather than explore.
- **Evidence:** 4 of 4 page(s) (100%) deep page(s) show no breadcrumb trail.
- **Fix (low):** Add a breadcrumb trail (and BreadcrumbList schema) on deep pages so visitors keep their bearings and explore laterally.
- **Affected pages:** https://www.smashingmagazine.com/2026/08/desktop-wallpaper-calendars-september-2026/, https://www.smashingmagazine.com/2026/08/rethinking-data-visualisation-ux-approach-dashboards/, https://www.smashingmagazine.com/2026/08/why-website-should-never-stop-changing/, https://www.smashingmagazine.com/author/cosima-mielke/

### 🟢 F-007 · Heading hierarchy skips levels  
`low` · discoverability / extractability · confidence medium · impact 2/5

- **Why it hurts:** A machine reconstructs a page's outline from heading levels; skipped levels break that nesting, so the relationship between sections is ambiguous.
- **Evidence:** 6 of 6 page(s) (100%) jump heading levels (e.g. H1→H3 with no H2), e.g. https://www.smashingmagazine.com/.
- **Fix (low):** Nest headings in order (no H1→H3 jumps) so the document outline is unambiguous.
- **Affected pages:** https://www.smashingmagazine.com/, https://www.smashingmagazine.com/2026/08/desktop-wallpaper-calendars-september-2026/, https://www.smashingmagazine.com/2026/08/rethinking-data-visualisation-ux-approach-dashboards/, https://www.smashingmagazine.com/2026/08/why-website-should-never-stop-changing/, https://www.smashingmagazine.com/articles/ …

### 🟢 F-008 · Meta descriptions likely to be truncated  
`low` · discoverability / extractability · confidence medium · impact 2/5

- **Why it hurts:** Over-long descriptions are cut off, so the most important summary sentence may never be shown or quoted.
- **Evidence:** 3 of 6 page(s) (50%) have a meta description longer than 160 characters, e.g. https://www.smashingmagazine.com/2026/08/desktop-wallpaper-calendars-september-2026/ (265 chars).
- **Fix (low):** Keep meta descriptions under ~160 characters, key fact first.
- **Affected pages:** https://www.smashingmagazine.com/2026/08/desktop-wallpaper-calendars-september-2026/, https://www.smashingmagazine.com/2026/08/rethinking-data-visualisation-ux-approach-dashboards/, https://www.smashingmagazine.com/2026/08/why-website-should-never-stop-changing/

### 🟢 F-009 · Title tags outside the useful length range  
`low` · discoverability / extractability · confidence medium · impact 2/5

- **Why it hurts:** Very short titles under-describe the page while very long ones get truncated in results and answers, so the specific topic is lost either way.
- **Evidence:** 4 of 6 page(s) (67%) have a <title> shorter than 15 or longer than 65 characters, e.g. https://www.smashingmagazine.com/ (75 chars).
- **Fix (low):** Keep titles roughly 15–65 characters and topic-first.
- **Affected pages:** https://www.smashingmagazine.com/, https://www.smashingmagazine.com/2026/08/desktop-wallpaper-calendars-september-2026/, https://www.smashingmagazine.com/2026/08/rethinking-data-visualisation-ux-approach-dashboards/, https://www.smashingmagazine.com/2026/08/why-website-should-never-stop-changing/

---
_Generated by brand-ai-readiness-audit · brand-ai-readiness-audit/2.7 · read-only, recommend-only. JSON is the canonical output._