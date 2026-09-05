"""Structured-data checks — JSON-LD / microdata / RDFa presence and validity.

Structured data is the machine-readable restatement of a page's key facts. When it is
absent or malformed, assistants must guess from prose; when it is present and valid,
a clear fact is trivially quotable. Also anchors entity identity (Organization/WebSite).
"""
from __future__ import annotations

import re
from typing import List

from ..context import AuditContext
from ..report import Finding
from ..htmlparse import Page, jsonld_types

# Strong URL signals for a product/detail page.
PRODUCT_URL_RE = re.compile(r"/(product|products|shop|store|item|items|dp|p)(/|$)", re.I)
# Cart-specific cues — deliberately narrow to avoid matching prose about pricing.
CART_RE = re.compile(r"add to (cart|bag|basket)|addtocart|data-add-to-cart", re.I)
ARTICLE_URL_RE = re.compile(r"/(blog|article|articles|news|post|posts)(/|$)", re.I)
ARTICLE_HINTS = re.compile(r"\bmin read\b|\bposted on\b|\bpublished (on|in)\b", re.I)
PRICE_HINTS = re.compile(r"[$€£₹]\s?\d|\bUSD\b|\bINR\b|priceCurrency", re.I)


def analyze(ctx: AuditContext) -> List[Finding]:
    """Run every structured-data sub-check over the sampled pages and return findings."""
    pages = ctx.pages
    if not pages:
        return []
    findings: List[Finding] = []
    findings += _absence(pages)
    findings += _invalid_jsonld(pages)
    findings += _homepage_identity(pages)
    findings += _product_type(pages)
    findings += _article_type(pages)
    findings += _property_completeness(pages)
    return findings


def _absence(pages: List[Page]) -> List[Finding]:
    """Flag a total absence of structured data across the sample."""
    if any(p.jsonld or p.has_microdata or p.has_rdfa for p in pages):
        return []
    return [Finding(
        title="No structured data anywhere in the sampled pages",
        severity="high", dimension="discoverability", category="structured-data",
        evidence=f"0 of {len(pages)} sampled pages contain JSON-LD, microdata, or RDFa.",
        suggested_action_summary=(
            "Add schema.org JSON-LD to key templates: Organization + WebSite on the homepage, "
            "and the page-appropriate type (Product/Offer, Article, FAQPage, LocalBusiness, "
            "BreadcrumbList) elsewhere. This is the highest-leverage discoverability fix."),
        suggested_action_priority="high",
    )]


def _invalid_jsonld(pages: List[Page]) -> List[Finding]:
    """Flag pages that declare an ld+json block which fails to parse."""
    invalid = [p.url for p in pages
               if re.search(r'type=["\']application/ld\+json["\']', p.raw_html, re.I) and not p.jsonld]
    if not invalid:
        return []
    return [Finding(
        title="Invalid JSON-LD (present but unparseable)",
        severity="high", dimension="discoverability", category="structured-data",
        evidence=f"{len(invalid)} page(s) declare an ld+json block that fails JSON parsing, e.g. {invalid[0]}.",
        suggested_action_summary="Fix the JSON syntax (trailing commas, unescaped quotes, comments). Invalid JSON-LD is silently ignored, so the markup effort is wasted.",
        suggested_action_priority="high", affected_pages=invalid,
    )]


def _homepage_identity(pages: List[Page]) -> List[Finding]:
    """Flag a homepage lacking Organization/LocalBusiness/WebSite identity nodes."""
    home = pages[0]
    home_types = {t.lower() for t in jsonld_types(home)}
    if {"organization", "website", "localbusiness"} & home_types:
        return []
    return [Finding(
        title="Homepage lacks Organization/WebSite structured data",
        severity="medium", dimension="discoverability", category="entity-identity",
        evidence=f"Homepage ({home.url}) has no Organization, LocalBusiness, or WebSite JSON-LD; its detected types: {sorted(home_types) or 'none'}.",
        suggested_action_summary=(
            "Add an Organization (or LocalBusiness) node with name, url, logo, and sameAs, plus a "
            "WebSite node with name and optional SearchAction. This gives assistants a stable, "
            "unambiguous identity for the brand."),
        suggested_action_priority="high",
    )]


def _product_type(pages: List[Page]) -> List[Finding]:
    """Flag product-shaped pages that lack Product/Offer schema."""
    missing = [p.url for p in pages if _looks_product(p)
               and "product" not in {t.lower() for t in jsonld_types(p)}]
    if not missing:
        return []
    return [Finding(
        title="Product-like pages missing Product/Offer schema",
        severity="high", dimension="discoverability", category="structured-data",
        evidence=f"{len(missing)} page(s) look like product pages (cart/price cues) but have no Product JSON-LD, e.g. {missing[0]}.",
        suggested_action_summary="Add Product JSON-LD with name, image, description, brand, and an Offer (price, priceCurrency, availability) to every product page.",
        suggested_action_priority="high", affected_pages=missing,
    )]


def _article_type(pages: List[Page]) -> List[Finding]:
    """Flag article-shaped pages that lack Article/BlogPosting schema."""
    missing = [p.url for p in pages if _looks_article(p)
               and not ({"article", "blogposting", "newsarticle"} & {t.lower() for t in jsonld_types(p)})]
    if not missing:
        return []
    return [Finding(
        title="Article/blog pages missing Article schema",
        severity="medium", dimension="discoverability", category="structured-data",
        evidence=f"{len(missing)} article-like page(s) lack Article/BlogPosting JSON-LD, e.g. {missing[0]}.",
        suggested_action_summary="Add Article/BlogPosting JSON-LD with headline, author, datePublished, and dateModified so assistants can attribute and date the content.",
        suggested_action_priority="medium", affected_pages=missing,
    )]


def _property_completeness(pages: List[Page]) -> List[Finding]:
    """Flag existing structured-data nodes that omit recommended properties."""
    out: List[Finding] = []
    incomplete = []
    for p in pages:
        for obj in p.jsonld:
            t = obj.get("@type")
            t = (t[0] if isinstance(t, list) and t else t) or ""
            t = str(t).lower()
            missing = _required_missing(t, obj)
            if missing:
                incomplete.append((p.url, t, missing))
    if incomplete:
        url, t, miss = incomplete[0]
        out.append(Finding(
            title="Structured-data nodes missing recommended properties",
            severity="medium",
            dimension="discoverability",
            category="structured-data",
            evidence=f"{len(incomplete)} node(s) omit key properties, e.g. {t} on {url} missing {miss}.",
            suggested_action_summary="Populate the recommended properties for each schema type so the markup is eligible for rich understanding, not just presence.",
            suggested_action_priority="medium",
            details={"examples": [{"page": u, "type": tt, "missing": m} for u, tt, m in incomplete[:5]]},
        ))
    return out


def _required_missing(t: str, obj: dict) -> List[str]:
    req = {
        "organization": ["name", "url"],
        "localbusiness": ["name", "address"],
        "product": ["name", "offers"],
        "offer": ["price", "priceCurrency"],
        "article": ["headline", "datePublished"],
        "blogposting": ["headline", "datePublished"],
        "faqpage": ["mainEntity"],
    }.get(t, [])
    return [k for k in req if k not in obj]


def _looks_product(p: Page) -> bool:
    # A product page needs either a product-shaped URL, or a real cart control *plus* a price.
    if PRODUCT_URL_RE.search(_path(p.url)):
        return True
    return bool(CART_RE.search(p.raw_html) and PRICE_HINTS.search(p.visible_text))


def _looks_article(p: Page) -> bool:
    if ARTICLE_URL_RE.search(_path(p.url)):
        return True
    return bool(ARTICLE_HINTS.search(p.visible_text[:400]))


def _path(url: str) -> str:
    import urllib.parse
    return urllib.parse.urlsplit(url).path
