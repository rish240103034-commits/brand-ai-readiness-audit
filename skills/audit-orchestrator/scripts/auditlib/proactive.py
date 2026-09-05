"""Proactive opportunities — improvements that raise AI-readiness beyond fixing defects.

These are NOT defects and never reduce the score. Each one is only surfaced when the crawl
context justifies it (e.g. suggest author markup only when the site actually has articles), so
the section stays specific and defensible rather than generic SEO advice. Emitted as a separate
``report['opportunities']`` list so scoring, severity counts, and the matrix stay defect-only.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .context import AuditContext
from .htmlparse import Page, jsonld_types

_QMARK_HEADING = re.compile(r"\?\s*$")
_SEARCH_RE = re.compile(r'type=["\']search["\']|role=["\']search["\']|action=["\'][^"\']*search', re.I)


def build(ctx: AuditContext) -> List[Dict[str, Any]]:
    """Return context-justified opportunity records for the sampled site."""
    pages = ctx.pages
    if not pages:
        return []
    all_types = set()
    for p in pages:
        all_types |= {t.lower() for t in jsonld_types(p)}

    opps: List[Dict[str, Any]] = []
    for fn in (_org_logo, _author_markup, _product_ratings, _faq_schema,
               _breadcrumb_schema, _website_searchaction, _key_facts_summary):
        opps += fn(pages, all_types)

    for i, o in enumerate(opps, start=1):
        o["id"] = f"OP-{i:03d}"
    return opps


def _op(title, category, rationale, action, impact, effort="Low", confidence="medium",
        evidence="") -> Dict[str, Any]:
    return {"title": title, "category": category, "dimension": "discoverability",
            "kind": "opportunity", "rationale": rationale, "suggested_action": action,
            "expected_impact": impact, "effort": effort, "confidence": confidence,
            "evidence": evidence}


def _has_org(pages: List[Page]) -> bool:
    return any({"organization", "localbusiness"} & {t.lower() for t in jsonld_types(p)} for p in pages)


def _org_nodes(pages: List[Page]):
    for p in pages:
        for obj in p.jsonld:
            t = obj.get("@type")
            t = (t[0] if isinstance(t, list) and t else t) or ""
            if str(t).lower() in ("organization", "localbusiness"):
                yield obj


def _org_logo(pages, all_types) -> List[Dict[str, Any]]:
    orgs = list(_org_nodes(pages))
    if orgs and not any(o.get("logo") for o in orgs):
        return [_op(
            "Add a logo to the Organization schema", "entity-identity",
            "The site declares an Organization node but no logo; a machine-readable logo strengthens brand knowledge panels and disambiguation.",
            "Add a logo (ImageObject or URL) to the Organization JSON-LD node.",
            "Stronger, more citable brand identity in AI and search knowledge surfaces.",
            evidence=f"{len(orgs)} Organization node(s) present, none with a logo property.")]
    return []


def _author_markup(pages, all_types) -> List[Dict[str, Any]]:
    has_articles = ("article" in all_types or "blogposting" in all_types
                    or any(re.search(r"/(blog|article|news|post)", p.url, re.I) for p in pages))
    has_author = any("author" in obj for p in pages for obj in p.jsonld) or "person" in all_types
    if has_articles and not has_author:
        return [_op(
            "Add author (Person) markup to articles", "corroboration",
            "The site publishes articles but exposes no author/Person markup; explicit authorship is a trust and attribution signal assistants use.",
            "Add an author (Person, with name and optionally sameAs) to Article/BlogPosting JSON-LD and a visible byline.",
            "Better attribution and topical authority for cited content.",
            effort="Low", evidence="Article-like content found with no author markup.")]
    return []


def _product_ratings(pages, all_types) -> List[Dict[str, Any]]:
    if "product" not in all_types:
        return []
    has_rating = any(("aggregateRating" in obj or "review" in obj) for p in pages for obj in p.jsonld)
    if not has_rating:
        return [_op(
            "Add ratings/reviews markup to products", "structured-data",
            "Products carry Product schema but no aggregateRating/review; rating markup is what lets answer engines surface star ratings and social proof.",
            "Add aggregateRating and/or review to Product JSON-LD where genuine reviews exist (never fabricate ratings).",
            "Eligibility for rich rating snippets in shopping-style answers.",
            effort="Medium", evidence="Product schema present without aggregateRating/review.")]
    return []


def _faq_schema(pages, all_types) -> List[Dict[str, Any]]:
    if "faqpage" in all_types:
        return []
    faqish = any("faq" in p.url.lower() for p in pages) or any(
        sum(1 for h in p.headings if _QMARK_HEADING.search(h[1])) >= 3 for p in pages)
    if faqish:
        return [_op(
            "Add FAQPage schema to question-and-answer content", "structured-data",
            "The site has FAQ-style content (a FAQ page or several question headings) but no FAQPage markup, which can win direct-answer placements.",
            "Wrap genuine Q&A in FAQPage JSON-LD (Question/acceptedAnswer) — only for real, visible Q&A, not invented questions.",
            "Eligibility to be quoted directly as an answer to matching questions.",
            evidence="FAQ-style content detected without FAQPage schema.")]
    return []


def _breadcrumb_schema(pages, all_types) -> List[Dict[str, Any]]:
    if "breadcrumblist" in all_types:
        return []
    deep = [p for p in pages if p.url.rstrip("/").count("/") > 3]
    if len(deep) >= 3:
        return [_op(
            "Add BreadcrumbList schema on deep pages", "structured-data",
            "The site has deep pages but no BreadcrumbList markup; breadcrumbs give machines the page's place in the site hierarchy.",
            "Add BreadcrumbList JSON-LD (and a visible trail) on section/detail pages.",
            "Clearer site structure for machines and better orientation for visitors.",
            evidence=f"{len(deep)} deep page(s) sampled with no BreadcrumbList schema.")]
    return []


def _website_searchaction(pages, all_types) -> List[Dict[str, Any]]:
    home = pages[0]
    has_search = bool(_SEARCH_RE.search(home.raw_html))
    has_searchaction = any("searchaction" in str(obj).lower() for obj in home.jsonld)
    if has_search and not has_searchaction:
        return [_op(
            "Expose a WebSite SearchAction (sitelinks searchbox)", "structured-data",
            "The homepage has a search box but no WebSite/SearchAction markup describing it, which powers the sitelinks searchbox.",
            "Add a WebSite node with a potentialAction of type SearchAction and the query template.",
            "Enables a search box directly in search/answer results for the brand.",
            confidence="low", evidence="On-page search detected without SearchAction markup.")]
    return []


def _key_facts_summary(pages, all_types) -> List[Dict[str, Any]]:
    """Only when the homepage is thin on plain text — suggest an explicit key-facts summary."""
    home = pages[0]
    if 30 <= home.word_count <= 90 and not any("faqpage" in all_types for _ in [0]):
        return [_op(
            "Add an explicit key-facts summary to the homepage", "extractability",
            "The homepage carries relatively little plain text; a short, factual summary block (who/what/where) gives machines an unambiguous statement to quote.",
            "Add a concise paragraph or definition list stating the core facts (what the brand does, who it serves, where).",
            "A clean, quotable statement of the brand's core facts.",
            confidence="low", evidence=f"Homepage has ~{home.word_count} words of plain text.")]
    return []
