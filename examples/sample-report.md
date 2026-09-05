# AI Readiness Audit — smashingmagazine.com

**AI Visibility Score: 63/100 (Grade D)** · discoverability 37.8 · engagement 100.0

_Audited 2026-09-05T10:00:57Z · profile balanced · 12 page(s) crawled_

> smashingmagazine.com scores 63/100 (grade D — Weak). Several issues are actively limiting how the brand is found and read.
> 2 finding(s) are critical or high severity and should be addressed first; the weakest area is Structured Data (48/100).
> 2 quick win(s) (high impact, low effort) would lift the score by about 9 point(s) to ~72/100 — enough to move up a grade.
> Fixing every finding would raise the score to about 100/100 (+37); estimated effort overall is substantial.
> Discoverability (38) and engagement (100) diverge by 62 points; discoverability is the side pulling the score down.

## Key metrics

| Metric | Value |
|---|---|
| AI Visibility Score | 63/100 (D) |
| Total findings | 6 |
| Critical + high | 2 |
| Quick wins | 2 |
| Projected after quick wins | 72/100 (+9) |
| Full potential | 100/100 |
| Weakest pillar | Structured Data (48.0/100) |
| Estimated effort | Substantial |
| Pages analyzed | 12 |

## Pillar breakdown

| Pillar | Score | Status | Findings |
|---|---|---|---|
| Crawl & Render | 100/100 | healthy | 0 |
| Structured Data | 48/100 | critical | 4 |
| Extractability | 90/100 | warning | 2 |
| Freshness | 100/100 | healthy | 0 |
| Corroboration | 100/100 | healthy | 0 |
| Engagement | 100/100 | healthy | 0 |

## Quick wins (do these first)

- **Homepage lacks Organization/WebSite structured data** — impact 3/5, low effort, +4 pts (F-004)
- **Pages missing an H1 heading** — impact 3/5, low effort, +4 pts (F-005)

## Roadmap

**Now**

- 🟠 No structured data anywhere in the sampled pages (high, medium effort)
- 🟠 Product-like pages missing Product/Offer schema (high, high effort)
- 🟡 Homepage lacks Organization/WebSite structured data (medium, low effort)
- 🟡 Pages missing an H1 heading (medium, low effort)

**Next**

- 🟡 Article/blog pages missing Article schema (medium, medium effort)

**Later**

- 🟢 Substantial content offloaded to PDF files (low, low effort)

## Findings

### 🟠 F-001 · No structured data anywhere in the sampled pages  
`high` · discoverability / structured-data · confidence high · impact 4/5

- **Why it hurts:** Without machine-readable markup, assistants must guess facts from prose and often get them wrong.
- **Evidence:** 0 of 12 sampled pages contain JSON-LD, microdata, or RDFa.
- **Fix (high):** Add schema.org JSON-LD to key templates: Organization + WebSite on the homepage, and the page-appropriate type (Product/Offer, Article, FAQPage, LocalBusiness, BreadcrumbList) elsewhere. This is the highest-leverage discoverability fix.

### 🟠 F-002 · Product-like pages missing Product/Offer schema  
`high` · discoverability / structured-data · confidence high · impact 4/5

- **Why it hurts:** Without machine-readable markup, assistants must guess facts from prose and often get them wrong.
- **Evidence:** 7 page(s) look like product pages (cart/price cues) but have no Product JSON-LD, e.g. https://www.smashingmagazine.com/ebook-bundles/smashing-library/.
- **Fix (high):** Add Product JSON-LD with name, image, description, brand, and an Offer (price, priceCurrency, availability) to every product page.
- **Affected pages:** https://www.smashingmagazine.com/ebook-bundles/smashing-library/, https://www.smashingmagazine.com/ebook-bundles/accessibility-ebook-bundle-3-ebooks/, https://www.smashingmagazine.com/ebook-bundles/business-ebook-bundle-8-ebooks/, https://www.smashingmagazine.com/ebook-bundles/content-strategy-ebook-bundle-3-ebooks/, https://www.smashingmagazine.com/ebook-bundles/front-end-ebook-bundle-4-ebooks/ …

### 🟡 F-003 · Article/blog pages missing Article schema  
`medium` · discoverability / structured-data · confidence high · impact 3/5

- **Why it hurts:** Without machine-readable markup, assistants must guess facts from prose and often get them wrong.
- **Evidence:** 1 article-like page(s) lack Article/BlogPosting JSON-LD, e.g. https://www.smashingmagazine.com/articles/.
- **Fix (medium):** Add Article/BlogPosting JSON-LD with headline, author, datePublished, and dateModified so assistants can attribute and date the content.
- **Affected pages:** https://www.smashingmagazine.com/articles/

### 🟡 F-004 · Homepage lacks Organization/WebSite structured data  
`medium` · discoverability / entity-identity · confidence high · impact 3/5

- **Why it hurts:** With no stable, disambiguated identity, assistants can't confidently attribute facts to the brand.
- **Evidence:** Homepage (https://www.smashingmagazine.com/) has no Organization, LocalBusiness, or WebSite JSON-LD; its detected types: none.
- **Fix (high):** Add an Organization (or LocalBusiness) node with name, url, logo, and sameAs, plus a WebSite node with name and optional SearchAction. This gives assistants a stable, unambiguous identity for the brand.

### 🟡 F-005 · Pages missing an H1 heading  
`medium` · discoverability / extractability · confidence high · impact 3/5

- **Why it hurts:** A fact locked in an image or missing its text anchor can't be extracted or quoted.
- **Evidence:** 1 sampled page(s) have no H1, e.g. https://www.smashingmagazine.com/articles/. The H1 is the primary topic anchor.
- **Fix (medium):** Add exactly one descriptive H1 per page stating what the page is about in plain words.
- **Affected pages:** https://www.smashingmagazine.com/articles/

### 🟢 F-006 · Substantial content offloaded to PDF files  
`low` · discoverability / extractability · confidence medium · impact 2/5

- **Why it hurts:** A fact locked in an image or missing its text anchor can't be extracted or quoted.
- **Evidence:** 3 PDF link(s) found across sampled pages. Scanned or image-based PDFs are often unreadable to crawlers.
- **Fix (low):** Publish the key information as HTML pages (the PDF can remain as a download). Ensure any essential PDFs contain real, selectable text, not scans.

---
_Generated by brand-ai-readiness-audit · brand-ai-readiness-audit/1.2 · read-only, recommend-only. JSON is the canonical output._