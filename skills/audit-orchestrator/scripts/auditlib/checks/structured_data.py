"""Structured-data checks — JSON-LD / microdata / RDFa presence, validity, and completeness.

Structured data is the machine-readable restatement of a page's key facts. When it is
absent, malformed, incomplete, contradictory, or duplicated, assistants must guess from prose
(and often get it wrong); when it is present and valid, a clear fact is trivially quotable.
Also anchors entity identity (Organization/WebSite). Presence alone is not enough — this
module also checks required properties, empty/placeholder values, and duplicate nodes, so a
site is not scored as healthy merely for shipping some markup.
"""
from __future__ import annotations

import re
from typing import List

from ..context import AuditContext
from ..report import Finding, scope_str
from ..htmlparse import Page, jsonld_types

PRODUCT_URL_RE = re.compile(r"/(product|products|shop|store|item|items|dp|p)(/|$)", re.I)
CART_RE = re.compile(r"add to (cart|bag|basket)|addtocart|data-add-to-cart", re.I)
ARTICLE_URL_RE = re.compile(r"/(blog|article|articles|news|post|posts)(/|$)", re.I)
ARTICLE_HINTS = re.compile(r"\bmin read\b|\bposted on\b|\bpublished (on|in)\b", re.I)
PRICE_HINTS = re.compile(r"[$€£₹]\s?\d|\bUSD\b|\bINR\b|priceCurrency", re.I)

# Recommended properties per type (used for completeness + empty-value checks).
RECOMMENDED = {
    "organization": ["name", "url"],
    "localbusiness": ["name", "address"],
    "product": ["name", "offers"],
    "offer": ["price", "priceCurrency"],
    "article": ["headline", "datePublished"],
    "blogposting": ["headline", "datePublished"],
    "newsarticle": ["headline", "datePublished"],
    "faqpage": ["mainEntity"],
    "breadcrumblist": ["itemListElement"],
    "person": ["name"],
    "course": ["name", "provider"],
}


def analyze(ctx: AuditContext) -> List[Finding]:
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
    findings += _empty_values(pages)
    findings += _duplicate_identity(pages)
    return findings


def _absence(pages: List[Page]) -> List[Finding]:
    if any(p.jsonld or p.has_microdata or p.has_rdfa for p in pages):
        return []
    return [Finding(
        title="No structured data anywhere in the sampled pages",
        severity="high", dimension="discoverability", category="structured-data",
        evidence=f"0 of {len(pages)} sampled pages contain JSON-LD, microdata, or RDFa.",
        why="With no machine-readable markup, an assistant must infer every fact (who the brand is, "
            "what it sells, prices, dates) from prose — error-prone and rarely quoted with confidence.",
        how_to_fix="Add schema.org JSON-LD to key templates: Organization + WebSite on the homepage, and the "
                   "page-appropriate type (Product/Offer, Article, FAQPage, Course, BreadcrumbList) elsewhere.",
        scope=f"0 of {len(pages)} pages",
        measurements={"pages_with_structured_data": 0, "pages": len(pages)},
        expected_impact="Makes core facts directly quotable; typically the highest-leverage discoverability fix.",
        suggested_action_summary=(
            "Add schema.org JSON-LD to key templates: Organization + WebSite on the homepage, "
            "and the page-appropriate type (Product/Offer, Article, FAQPage, LocalBusiness, "
            "BreadcrumbList) elsewhere. This is the highest-leverage discoverability fix."),
        suggested_action_priority="high",
    )]


def _invalid_jsonld(pages: List[Page]) -> List[Finding]:
    invalid = [p.url for p in pages
               if re.search(r'type=["\']application/ld\+json["\']', p.raw_html, re.I) and not p.jsonld]
    if not invalid:
        return []
    return [Finding(
        title="Invalid JSON-LD (present but unparseable)",
        severity="high", dimension="discoverability", category="structured-data",
        evidence=f"{len(invalid)} page(s) declare an ld+json block that fails JSON parsing, e.g. {invalid[0]}.",
        why="Invalid JSON-LD is silently discarded by consumers, so the markup effort is wasted and the "
            "facts it was meant to expose stay invisible to machines.",
        how_to_fix="Fix the JSON syntax (trailing commas, unescaped quotes, comments, single quotes) and "
                   "validate with a schema.org / Rich Results test before shipping.",
        measurements={"pages_with_invalid_jsonld": len(invalid)},
        suggested_action_summary="Fix the JSON syntax (trailing commas, unescaped quotes, comments). Invalid JSON-LD is silently ignored, so the markup effort is wasted.",
        suggested_action_priority="high", affected_pages=invalid,
    )]


def _homepage_identity(pages: List[Page]) -> List[Finding]:
    home = pages[0]
    home_types = {t.lower() for t in jsonld_types(home)}
    if {"organization", "website", "localbusiness"} & home_types:
        return []
    return [Finding(
        title="Homepage lacks Organization/WebSite structured data",
        severity="medium", dimension="discoverability", category="entity-identity",
        evidence=f"Homepage ({home.url}) has no Organization, LocalBusiness, or WebSite JSON-LD; detected types: {sorted(home_types) or 'none'}.",
        why="Without an Organization/WebSite node, an assistant has no stable, machine-readable identity "
            "for the brand and cannot confidently attribute facts or citations to it.",
        how_to_fix="Add an Organization (or LocalBusiness) node with name, url, logo, and sameAs, plus a WebSite "
                   "node with name and optional SearchAction, on the homepage template.",
        measurements={"homepage_identity_types": sorted(home_types)},
        suggested_action_summary=(
            "Add an Organization (or LocalBusiness) node with name, url, logo, and sameAs, plus a "
            "WebSite node with name and optional SearchAction. This gives assistants a stable, "
            "unambiguous identity for the brand."),
        suggested_action_priority="high",
    )]


def _product_type(pages: List[Page]) -> List[Finding]:
    total = len(pages)
    missing = [p.url for p in pages if _looks_product(p)
               and "product" not in {t.lower() for t in jsonld_types(p)}]
    if not missing:
        return []
    return [Finding(
        title="Product-like pages missing Product/Offer schema",
        severity="high", dimension="discoverability", category="structured-data",
        evidence=f"{scope_str(len(missing), total)} look like product pages (cart/price cues) but have no Product JSON-LD, e.g. {missing[0]}.",
        why="Without Product/Offer markup an assistant cannot reliably read price, availability, or rating, "
            "so the brand is left out of shopping-style answers where those facts are required.",
        how_to_fix="Add Product JSON-LD (name, image, description, brand) with an Offer (price, priceCurrency, availability) to each product template.",
        scope=scope_str(len(missing), total),
        measurements={"product_like_without_schema": len(missing), "pages": total},
        expected_impact="Enables price/availability to be cited in answer-engine shopping results.",
        suggested_action_summary="Add Product JSON-LD with name, image, description, brand, and an Offer (price, priceCurrency, availability) to every product page.",
        suggested_action_priority="high", affected_pages=missing,
    )]


def _article_type(pages: List[Page]) -> List[Finding]:
    total = len(pages)
    missing = [p.url for p in pages if _looks_article(p)
               and not ({"article", "blogposting", "newsarticle"} & {t.lower() for t in jsonld_types(p)})]
    if not missing:
        return []
    return [Finding(
        title="Article/blog pages missing Article schema",
        severity="medium", dimension="discoverability", category="structured-data",
        evidence=f"{scope_str(len(missing), total)} look like articles but lack Article/BlogPosting JSON-LD, e.g. {missing[0]}.",
        why="Without Article markup an assistant cannot reliably attribute the piece to an author or date it, "
            "so it is trusted and cited less for topical questions.",
        how_to_fix="Add Article/BlogPosting JSON-LD with headline, author, datePublished, and dateModified to the article template.",
        scope=scope_str(len(missing), total),
        measurements={"article_like_without_schema": len(missing), "pages": total},
        suggested_action_summary="Add Article/BlogPosting JSON-LD with headline, author, datePublished, and dateModified so assistants can attribute and date the content.",
        suggested_action_priority="medium", affected_pages=missing,
    )]


def _property_completeness(pages: List[Page]) -> List[Finding]:
    """Flag existing structured-data nodes that omit recommended properties."""
    incomplete = []
    for p in pages:
        for obj in p.jsonld:
            t = _type_of(obj)
            missing = [k for k in RECOMMENDED.get(t, []) if k not in obj]
            if missing:
                incomplete.append((p.url, t, missing))
    if not incomplete:
        return []
    url, t, miss = incomplete[0]
    return [Finding(
        title="Structured-data nodes missing recommended properties",
        severity="medium", dimension="discoverability", category="structured-data",
        evidence=f"{len(incomplete)} node(s) omit key properties, e.g. {t} on {url} missing {miss}.",
        why="A schema node that ships without its key properties is present but not useful — the fact it was "
            "meant to expose (price, date, address…) still isn't machine-readable.",
        how_to_fix="Populate the recommended properties for each type (see the RECOMMENDED map) so the markup is eligible for rich understanding, not just presence.",
        measurements={"incomplete_nodes": len(incomplete)},
        details={"examples": [{"page": u, "type": tt, "missing": m} for u, tt, m in incomplete[:5]]},
        suggested_action_summary="Populate the recommended properties for each schema type so the markup is eligible for rich understanding, not just presence.",
        suggested_action_priority="medium", confidence="high",
    )]


def _empty_values(pages: List[Page]) -> List[Finding]:
    """Flag schema properties that exist but hold empty or placeholder values."""
    bad = []
    for p in pages:
        for obj in p.jsonld:
            t = _type_of(obj)
            for k in RECOMMENDED.get(t, []):
                if k in obj and _is_empty(obj[k]):
                    bad.append((p.url, t, k))
    if not bad:
        return []
    url, t, k = bad[0]
    return [Finding(
        title="Structured-data properties present but empty",
        severity="low", dimension="discoverability", category="structured-data",
        evidence=f"{len(bad)} recommended property value(s) are empty or placeholder, e.g. {t}.{k} on {url}.",
        why="An empty property value is worse than an absent one — it looks complete to a validator but "
            "carries no fact for a machine to read.",
        how_to_fix="Populate the property with a real value, or remove it if genuinely not applicable.",
        measurements={"empty_property_values": len(bad)},
        details={"examples": [{"page": u, "type": tt, "property": kk} for u, tt, kk in bad[:5]]},
        suggested_action_summary="Fill in empty schema property values with real data, or drop the property.",
        suggested_action_priority="low", confidence="medium",
    )]


def _duplicate_identity(pages: List[Page]) -> List[Finding]:
    """Flag a homepage that declares conflicting/duplicate Organization identities."""
    home = pages[0]
    org_names = []
    for obj in home.jsonld:
        if _type_of(obj) in ("organization", "localbusiness") and obj.get("name"):
            org_names.append(str(obj["name"]).strip())
    distinct = {n.lower() for n in org_names if n}
    if len(org_names) > 1 and len(distinct) > 1:
        return [Finding(
            title="Conflicting Organization identities in structured data",
            severity="medium", dimension="discoverability", category="entity-identity",
            evidence=f"The homepage declares {len(org_names)} Organization nodes with differing names: {sorted(distinct)}.",
            why="Multiple, differently-named Organization nodes on one page make it ambiguous which entity the "
                "site represents, undermining confident attribution.",
            how_to_fix="Keep a single canonical Organization node (use @id references if other nodes must link to it) with one consistent name.",
            measurements={"organization_nodes": len(org_names), "distinct_names": len(distinct)},
            suggested_action_summary="Consolidate to one canonical Organization node with a single consistent name.",
            suggested_action_priority="medium", confidence="high",
        )]
    return []


# --- helpers ----------------------------------------------------------------------
def _type_of(obj: dict) -> str:
    t = obj.get("@type")
    t = (t[0] if isinstance(t, list) and t else t) or ""
    return str(t).lower()


def _is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip() or v.strip().lower() in ("n/a", "tbd", "todo", "-")
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


def _looks_product(p: Page) -> bool:
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
