# AI Readiness Audit — smashingmagazine.com

**AI Visibility Score: 56/100 (Grade F)** · discoverability 31.0 · engagement 94.0

_Audited 2026-09-06T09:13:16Z · profile balanced · 12 page(s) crawled_

> smashingmagazine.com scores 56/100 (grade F — At risk). Core problems make the brand hard for AI assistants to find or trust.
> 2 finding(s) are critical or high severity and should be addressed first; the weakest area is Structured Data (48/100).
> 2 quick win(s) (high impact, low effort) would lift the score by about 10 point(s) to ~66/100 — enough to move up a grade.
> Fixing every finding would raise the score to about 100/100 (+44); estimated effort overall is substantial.
> Discoverability (31) and engagement (94) diverge by 63 points; discoverability is the side pulling the score down.
> Assessed 8 of 8 areas. 2 proactive opportunity(ies) identified.

## Key metrics

| Metric | Value |
|---|---|
| AI Visibility Score | 56/100 (F) |
| Total findings | 10 |
| Critical + high | 2 |
| Quick wins | 2 |
| Projected after quick wins | 66/100 (+10) |
| Full potential | 100/100 |
| Weakest pillar | Structured Data (48.0/100) |
| Estimated effort | Substantial |
| Pages analyzed | 12 |

## Pillar breakdown

| Pillar | Score | Status | Findings |
|---|---|---|---|
| Crawl & Render | 100/100 | partial | 0 |
| Structured Data | 48/100 | critical | 4 |
| Extractability | 83/100 | warning | 5 |
| Freshness | 100/100 | healthy | 0 |
| Corroboration | 100/100 | partial | 0 |
| Engagement | 94/100 | healthy | 1 |

## Quick wins (do these first)

- **Homepage lacks Organization/WebSite structured data** — impact 3/5, low effort, +5 pts (F-004)
- **Pages missing an H1 heading** — impact 3/5, low effort, +5 pts (F-005)

## Roadmap

**Now**

- 🟠 No structured data anywhere in the sampled pages (high, medium effort)
- 🟠 Product-like pages missing Product/Offer schema (high, high effort)
- 🟡 Homepage lacks Organization/WebSite structured data (medium, low effort)
- 🟡 Pages missing an H1 heading (medium, low effort)

**Next**

- 🟡 Article/blog pages missing Article schema (medium, medium effort)
- 🟡 Slow server response on sampled pages (medium, high effort)

**Later**

- 🟢 Heading hierarchy skips levels (low, low effort)
- 🟢 Meta descriptions likely to be truncated (low, low effort)
- 🟢 Substantial content offloaded to PDF files (low, low effort)
- 🟢 Title tags outside the useful length range (low, low effort)

## Findings

### 🟠 F-001 · No structured data anywhere in the sampled pages  
`high` · discoverability / structured-data · confidence high · impact 4/5

- **Why it hurts:** With no machine-readable markup, an assistant must infer every fact (who the brand is, what it sells, prices, dates) from prose — error-prone and rarely quoted with confidence.
- **Evidence:** 0 of 12 sampled pages contain JSON-LD, microdata, or RDFa.
- **Fix (high):** Add schema.org JSON-LD to key templates: Organization + WebSite on the homepage, and the page-appropriate type (Product/Offer, Article, FAQPage, LocalBusiness, BreadcrumbList) elsewhere. This is the highest-leverage discoverability fix.

### 🟠 F-002 · Product-like pages missing Product/Offer schema  
`high` · discoverability / structured-data · confidence high · impact 4/5

- **Why it hurts:** Without Product/Offer markup an assistant cannot reliably read price, availability, or rating, so the brand is left out of shopping-style answers where those facts are required.
- **Evidence:** 7 of 12 page(s) (58%) look like product pages (cart/price cues) but have no Product JSON-LD, e.g. https://www.smashingmagazine.com/ebook-bundles/smashing-library/.
- **Fix (high):** Add Product JSON-LD with name, image, description, brand, and an Offer (price, priceCurrency, availability) to every product page.
- **Affected pages:** https://www.smashingmagazine.com/ebook-bundles/smashing-library/, https://www.smashingmagazine.com/ebook-bundles/accessibility-ebook-bundle-3-ebooks/, https://www.smashingmagazine.com/ebook-bundles/business-ebook-bundle-8-ebooks/, https://www.smashingmagazine.com/ebook-bundles/content-strategy-ebook-bundle-3-ebooks/, https://www.smashingmagazine.com/ebook-bundles/front-end-ebook-bundle-4-ebooks/ …

### 🟡 F-003 · Article/blog pages missing Article schema  
`medium` · discoverability / structured-data · confidence high · impact 3/5

- **Why it hurts:** Without Article markup an assistant cannot reliably attribute the piece to an author or date it, so it is trusted and cited less for topical questions.
- **Evidence:** 1 of 12 page(s) (8%) look like articles but lack Article/BlogPosting JSON-LD, e.g. https://www.smashingmagazine.com/articles/.
- **Fix (medium):** Add Article/BlogPosting JSON-LD with headline, author, datePublished, and dateModified so assistants can attribute and date the content.
- **Affected pages:** https://www.smashingmagazine.com/articles/

### 🟡 F-004 · Homepage lacks Organization/WebSite structured data  
`medium` · discoverability / entity-identity · confidence high · impact 3/5

- **Why it hurts:** Without an Organization/WebSite node, an assistant has no stable, machine-readable identity for the brand and cannot confidently attribute facts or citations to it.
- **Evidence:** Homepage (https://www.smashingmagazine.com/) has no Organization, LocalBusiness, or WebSite JSON-LD; detected types: none.
- **Fix (high):** Add an Organization (or LocalBusiness) node with name, url, logo, and sameAs, plus a WebSite node with name and optional SearchAction. This gives assistants a stable, unambiguous identity for the brand.

### 🟡 F-005 · Pages missing an H1 heading  
`medium` · discoverability / extractability · confidence high · impact 3/5

- **Why it hurts:** The H1 is the primary topic anchor a machine uses to decide what a page is about; without it the page's subject must be guessed from weaker signals.
- **Evidence:** 1 of 12 page(s) (8%) have no H1, e.g. https://www.smashingmagazine.com/articles/.
- **Fix (medium):** Add exactly one descriptive H1 per page stating what the page is about in plain words.
- **Affected pages:** https://www.smashingmagazine.com/articles/

### 🟡 F-006 · Slow server response on sampled pages  
`medium` · engagement / performance · confidence medium · impact 3/5

- **Why it hurts:** A slow first byte (TTFB) delays everything downstream, so the page starts rendering late and visitors abandon before it appears.
- **Evidence:** 2 of 12 page(s) (17%) took over 3s to return HTML (e.g. https://www.smashingmagazine.com/articles/: 30812 ms).
- **Fix (medium):** Investigate TTFB (caching, CDN, server work) so pages start rendering quickly; each added second measurably increases abandonment.
- **Affected pages:** https://www.smashingmagazine.com/ebook-bundles/web-design-ebook-bundle-10-ebooks/, https://www.smashingmagazine.com/articles/

### 🟢 F-007 · Heading hierarchy skips levels  
`low` · discoverability / extractability · confidence medium · impact 2/5

- **Why it hurts:** A machine reconstructs a page's outline from heading levels; skipped levels break that nesting, so the relationship between sections is ambiguous.
- **Evidence:** 12 of 12 page(s) (100%) jump heading levels (e.g. H1→H3 with no H2), e.g. https://www.smashingmagazine.com/.
- **Fix (low):** Nest headings in order (no H1→H3 jumps) so the document outline is unambiguous.
- **Affected pages:** https://www.smashingmagazine.com/, https://www.smashingmagazine.com/ebook-bundles/smashing-library/, https://www.smashingmagazine.com/ebook-bundles/accessibility-ebook-bundle-3-ebooks/, https://www.smashingmagazine.com/ebook-bundles/business-ebook-bundle-8-ebooks/, https://www.smashingmagazine.com/ebook-bundles/content-strategy-ebook-bundle-3-ebooks/ …

### 🟢 F-008 · Meta descriptions likely to be truncated  
`low` · discoverability / extractability · confidence medium · impact 2/5

- **Why it hurts:** Over-long descriptions are cut off, so the most important summary sentence may never be shown or quoted.
- **Evidence:** 8 of 12 page(s) (67%) have a meta description longer than 160 characters, e.g. https://www.smashingmagazine.com/ebook-bundles/smashing-library/ (434 chars).
- **Fix (low):** Keep meta descriptions under ~160 characters, key fact first.
- **Affected pages:** https://www.smashingmagazine.com/ebook-bundles/smashing-library/, https://www.smashingmagazine.com/ebook-bundles/accessibility-ebook-bundle-3-ebooks/, https://www.smashingmagazine.com/ebook-bundles/business-ebook-bundle-8-ebooks/, https://www.smashingmagazine.com/ebook-bundles/content-strategy-ebook-bundle-3-ebooks/, https://www.smashingmagazine.com/ebook-bundles/front-end-ebook-bundle-4-ebooks/ …

### 🟢 F-009 · Substantial content offloaded to PDF files  
`low` · discoverability / extractability · confidence medium · impact 2/5

- **Why it hurts:** Scanned or image-only PDFs are frequently unreadable to crawlers, so any key information that lives only inside them cannot be extracted or cited.
- **Evidence:** 3 PDF link(s) found across sampled pages.
- **Fix (low):** Publish the key information as HTML pages (the PDF can remain as a download). Ensure any essential PDFs contain real, selectable text, not scans.

### 🟢 F-010 · Title tags outside the useful length range  
`low` · discoverability / extractability · confidence medium · impact 2/5

- **Why it hurts:** Very short titles under-describe the page while very long ones get truncated in results and answers, so the specific topic is lost either way.
- **Evidence:** 9 of 12 page(s) (75%) have a <title> shorter than 15 or longer than 65 characters, e.g. https://www.smashingmagazine.com/ (75 chars).
- **Fix (low):** Keep titles roughly 15–65 characters and topic-first.
- **Affected pages:** https://www.smashingmagazine.com/, https://www.smashingmagazine.com/ebook-bundles/smashing-library/, https://www.smashingmagazine.com/ebook-bundles/accessibility-ebook-bundle-3-ebooks/, https://www.smashingmagazine.com/ebook-bundles/business-ebook-bundle-8-ebooks/, https://www.smashingmagazine.com/ebook-bundles/content-strategy-ebook-bundle-3-ebooks/ …

---
_Generated by brand-ai-readiness-audit · brand-ai-readiness-audit/2.5 · read-only, recommend-only. JSON is the canonical output._