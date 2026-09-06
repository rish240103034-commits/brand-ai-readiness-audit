"""Brand knowledge-graph preview — what an AI can actually learn about the brand from its markup.

Builds the entity graph an assistant would assemble from the site's JSON-LD: the Organization/
WebSite hub, its external identities (sameAs), and the Products / Articles / People it declares —
and, crucially, the **missing edges** (no sameAs, products with no brand link, articles with no
author) that leave the machine's picture of the brand incomplete. Pure function of the crawl;
rendered as a small node diagram. Attached as ``report['knowledge_graph']``.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List

from .context import AuditContext
from . import http as _http
from .htmlparse import Page, jsonld_types

_HUB_TYPES = ("organization", "localbusiness", "website")


def build(ctx: AuditContext) -> Dict[str, Any]:
    pages = ctx.pages
    objs = [o for p in pages for o in p.jsonld]
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    hub_obj = _find_hub(objs)
    if hub_obj is not None:
        hub_label = str(hub_obj.get("name") or _http.host_of(ctx.start_url))
        nodes.append({"id": "hub", "type": "Organization", "label": hub_label[:32], "core": True})
    else:
        nodes.append({"id": "hub", "type": "Site", "label": _http.host_of(ctx.start_url)[:32], "core": True})
        missing.append({"from": "hub", "rel": "identity",
                        "note": "No Organization/WebSite schema — the brand has no machine-readable identity node."})

    # sameAs external identities
    sameas = _collect_sameas(objs)
    if sameas:
        for i, url in enumerate(sameas[:5]):
            host = urllib.parse.urlsplit(url).netloc.replace("www.", "") or url
            nodes.append({"id": f"sa{i}", "type": "sameAs", "label": host[:26]})
            edges.append({"from": "hub", "to": f"sa{i}", "rel": "sameAs"})
    elif hub_obj is not None:
        missing.append({"from": "hub", "rel": "sameAs",
                        "note": "Organization has no sameAs — not linked to any external identity (Wikidata, LinkedIn…)."})

    # Products
    products = _by_type(objs, {"product"})
    if products:
        nodes.append({"id": "prod", "type": "Product", "label": f"Products ×{len(products)}"})
        edges.append({"from": "hub", "to": "prod", "rel": "offers"})
        if not any(o.get("brand") for o in products):
            missing.append({"from": "prod", "rel": "brand",
                            "note": "Products declare no brand — not linked back to the Organization."})
        if not any(("aggregateRating" in o or "review" in o) for o in products):
            missing.append({"from": "prod", "rel": "rating",
                            "note": "Products have no rating/review markup — no social proof for assistants."})

    # Articles
    articles = _by_type(objs, {"article", "blogposting", "newsarticle"})
    if articles:
        nodes.append({"id": "art", "type": "Article", "label": f"Articles ×{len(articles)}"})
        edges.append({"from": "hub", "to": "art", "rel": "publishes"})
        if not any(o.get("author") for o in articles):
            missing.append({"from": "art", "rel": "author",
                            "note": "Articles declare no author — no attribution/E-E-A-T signal."})

    # People
    people = [o for o in _by_type(objs, {"person"}) if o.get("name")]
    for i, o in enumerate(people[:2]):
        nodes.append({"id": f"pers{i}", "type": "Person", "label": str(o["name"])[:26]})
        edges.append({"from": "art" if articles else "hub", "to": f"pers{i}", "rel": "author"})

    return {
        "nodes": nodes,
        "edges": edges,
        "missing": missing,
        "summary": {"nodes": len(nodes), "edges": len(edges), "missing": len(missing),
                    "has_identity": hub_obj is not None},
    }


def _find_hub(objs):
    for o in objs:
        if _type_of(o) in _HUB_TYPES and o.get("name"):
            return o
    for o in objs:
        if _type_of(o) in _HUB_TYPES:
            return o
    return None


def _collect_sameas(objs) -> List[str]:
    out, seen = [], set()
    for o in objs:
        sa = o.get("sameAs")
        vals = sa if isinstance(sa, list) else ([sa] if isinstance(sa, str) else [])
        for v in vals:
            v = str(v)
            if v.startswith("http") and v not in seen:
                seen.add(v); out.append(v)
    return out


def _by_type(objs, types) -> List[dict]:
    return [o for o in objs if _type_of(o) in types]


def _type_of(o: dict) -> str:
    t = o.get("@type")
    t = (t[0] if isinstance(t, list) and t else t) or ""
    return str(t).lower()
