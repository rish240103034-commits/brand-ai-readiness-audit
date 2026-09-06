"""Agent-native remediation — ready-to-paste fix code + a machine-executable fix plan.

For the common finding types, generate the actual snippet to ship (prefilled with the brand's
name/URL where possible), attached to each finding as ``fix_snippet``. Then assemble
``report['fix_plan']`` — an ordered, machine-consumable remediation graph another agent could
execute (step, finding id, action, effort, expected point gain, whether a snippet is available).
Pure function of the scored report + crawl context.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .context import AuditContext
from .htmlparse import jsonld_types


def attach(report: Dict[str, Any], ctx: AuditContext) -> None:
    """Add `fix_snippet` to findings that have a template, and build report['fix_plan']."""
    brand, url = _brand_url(ctx)
    for f in report.get("findings", []):
        snip = _snippet_for(f, brand, url)
        if snip:
            f["fix_snippet"] = snip
    report["fix_plan"] = _build_plan(report)


def _snippet_for(f: Dict[str, Any], brand: str, url: str) -> Optional[str]:
    t = (f.get("title") or "").lower()
    dom = url.rstrip("/")

    def has(*keys):
        return any(k in t for k in keys)

    if has("no structured data", "homepage lacks organization"):
        return (f'<script type="application/ld+json">\n'
                f'{{"@context":"https://schema.org","@type":"Organization",\n'
                f'  "name":"{brand}","url":"{dom}/","logo":"{dom}/logo.png",\n'
                f'  "sameAs":["https://www.linkedin.com/company/…","https://www.wikidata.org/wiki/…"]}}\n'
                f'</script>\n'
                f'<script type="application/ld+json">\n'
                f'{{"@context":"https://schema.org","@type":"WebSite","name":"{brand}","url":"{dom}/"}}\n'
                f'</script>')
    if has("product-like pages missing"):
        return ('<script type="application/ld+json">\n'
                '{"@context":"https://schema.org","@type":"Product","name":"<product name>",\n'
                '  "image":"<image url>","description":"<desc>","brand":{"@type":"Brand","name":"' + brand + '"},\n'
                '  "offers":{"@type":"Offer","price":"0.00","priceCurrency":"USD","availability":"https://schema.org/InStock"}}\n'
                '</script>')
    if has("article/blog pages missing"):
        return ('<script type="application/ld+json">\n'
                '{"@context":"https://schema.org","@type":"Article","headline":"<title>",\n'
                '  "author":{"@type":"Person","name":"<author>"},"datePublished":"2026-01-01","dateModified":"2026-01-01"}\n'
                '</script>')
    if has("sameas corroboration"):
        return ('// add to the Organization node:\n'
                '"sameAs":["https://www.linkedin.com/company/…","https://www.wikidata.org/wiki/…","https://x.com/…"]')
    if has("breadcrumb"):
        return ('<script type="application/ld+json">\n'
                '{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[\n'
                f'  {{"@type":"ListItem","position":1,"name":"Home","item":"{dom}/"}},\n'
                '  {"@type":"ListItem","position":2,"name":"<section>","item":"<url>"}]}\n'
                '</script>')
    if has("missing a meta description", "meta descriptions likely"):
        return '<meta name="description" content="<≈150-char, fact-bearing summary of this page>">'
    if has("missing a <title>", "title tags outside"):
        return '<title><Page-specific topic> — ' + brand + '</title>'
    if has("missing an h1"):
        return '<h1><the single main topic of this page, in plain words></h1>'
    if has("responsive viewport"):
        return '<meta name="viewport" content="width=device-width, initial-scale=1">'
    if has("retrieval crawlers are blocked", "disallows all crawlers"):
        return ('# robots.txt — allow AI retrieval/citation crawlers\n'
                'User-agent: OAI-SearchBot\nAllow: /\n'
                'User-agent: PerplexityBot\nAllow: /\n'
                'User-agent: *\nAllow: /\n'
                f'Sitemap: {dom}/sitemap.xml')
    if has("no xml sitemap"):
        return f'# add to robots.txt:\nSitemap: {dom}/sitemap.xml'
    if has("without an x-default"):
        return '<link rel="alternate" hreflang="x-default" href="' + dom + '/">'
    if has("canonical tags point"):
        return '<link rel="canonical" href="' + dom + '/<this-page-path>">'
    if has("iframes without a title"):
        return '<iframe src="…" title="<what this embed shows>"></iframe>'
    if has("form controls without"):
        return '<label for="q">Search</label>\n<input id="q" name="q" type="search">'
    if has("noindex"):
        return '<!-- remove this from pages you want found: -->\n<meta name="robots" content="noindex">'
    return None


def _build_plan(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ordered, machine-consumable remediation steps from the analytics roadmap + matrix."""
    an = report.get("analytics", {}) or {}
    matrix = {m["id"]: m for m in an.get("matrix", [])}
    roadmap = an.get("roadmap", {}) or {}
    by_id = {f.get("id"): f for f in report.get("findings", [])}
    order = (roadmap.get("now", []) + roadmap.get("next", []) + roadmap.get("later", []))
    plan = []
    for i, ref in enumerate(order, start=1):
        fid = ref.get("id")
        f = by_id.get(fid, {})
        m = matrix.get(fid, {})
        plan.append({
            "step": i, "finding_id": fid, "title": f.get("title", ""),
            "category": f.get("category", ""), "action": _action(f.get("category", "")),
            "severity": f.get("severity", ""), "effort": m.get("effort_label", ""),
            "expected_gain_points": m.get("points_at_stake", 0),
            "affected_pages": f.get("affected_pages", [])[:5],
            "has_snippet": bool(f.get("fix_snippet")),
        })
    return plan


def _action(category: str) -> str:
    return {
        "structured-data": "add_or_fix_structured_data", "entity-identity": "strengthen_entity_identity",
        "extractability": "edit_page_markup", "crawlability": "edit_robots_or_sitemap",
        "indexability": "fix_index_directive", "reachability": "fix_server_response",
        "js-render-gap": "server_render_content", "freshness": "refresh_dates_or_content",
        "corroboration": "add_external_profiles", "mobile": "add_responsive_layout",
        "conversion": "add_cta_or_remove_barrier", "orientation": "improve_navigation",
        "performance": "optimize_performance", "readability": "restructure_content",
        "accessibility": "fix_accessibility",
    }.get(category, "review_and_fix")


def _brand_url(ctx: AuditContext):
    from . import http as _http
    url = ctx.start_url
    brand = ""
    if ctx.pages:
        home = ctx.pages[0]
        brand = home.meta.get("og:site_name", "").strip()
        if not brand:
            for obj in home.jsonld:
                if {"organization", "website", "localbusiness"} & {str(t).lower() for t in jsonld_types(home)} and obj.get("name"):
                    brand = str(obj["name"]).strip(); break
    if not brand:
        h = _http.host_of(url)
        brand = h.split(".")[0].capitalize() if h else "Your Brand"
    return brand, url
