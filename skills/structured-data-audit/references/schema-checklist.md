# Structured-data checklist (gate 3: can the machine quote a clear fact?)

Mechanism (Round-2 appendix B/C): assistants prefer sources they can *easily quote a clear
fact from*. schema.org markup is that fact, pre-extracted.

## What to check, by page type
| Page | Expected type(s) | Key properties | If missing |
|---|---|---|---|
| Homepage | `Organization` or `LocalBusiness` + `WebSite` | name, url, logo, sameAs; WebSite name (+ optional SearchAction) | Assistants lack a stable brand identity to attach facts to → entity ambiguity. |
| Product / detail | `Product` + `Offer` | name, image, description, brand, offers(price, priceCurrency, availability) | No rich product answers; price/availability unquotable. |
| Article / blog | `Article`/`BlogPosting`/`NewsArticle` | headline, author, datePublished, dateModified | Content can't be attributed or dated → discounted. |
| FAQ | `FAQPage` | mainEntity(Question→acceptedAnswer) | Q&A not eligible to be lifted directly into answers. |
| Deep pages | `BreadcrumbList` | itemListElement | Weaker structure/orientation signal. |

## Validity, not just presence
- **Invalid JSON-LD** (trailing commas, comments, unescaped quotes, single quotes) is
  silently dropped by consumers. A block that is present but unparseable scores as *worse*
  than absent, because the effort hides the gap. Flagged as `high`.
- **Wrong nesting** (e.g. `Offer` not inside `Product`, or `@type` misspelled) makes the node
  ineligible; check the required-property table above.
- Prefer **JSON-LD** over microdata/RDFa: it is decoupled from layout, easiest to emit
  correctly, and the format assistants parse most reliably.

## Detection precision
Product detection requires a product-shaped URL (`/product/`, `/shop/`, `/item/`, `/p/`, …)
**or** a real cart control (`add to cart/bag/basket`) together with a price — so a blog post
that mentions "$99" is not mistaken for a product page. Article detection uses URL shape or
explicit "min read / posted on / published" cues.

## Beyond-defect suggestions
Even where markup exists, recommend: `sameAs` on Organization (corroboration), `BreadcrumbList`
on deep pages, `FAQPage` where Q&A content exists, and `dateModified` upkeep — all strengthen
how the brand is understood, not just whether it is present.
