"""AI answer-readiness scorecard — can an assistant answer common questions about the brand?

Reframes discoverability as concrete questions (who / what / where / contact / pricing / hours)
and grades each on whether the answer is **machine-readable** (in structured data — the strongest
form), merely **text-only** (present in prose, weaker), or **missing**. Questions that don't apply
to a site (e.g. opening hours for a pure-SaaS site) are marked ``n/a`` and excluded from the score.

Pure function of the crawl context; no network. Attached as ``report['answer_readiness']``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .context import AuditContext
from .htmlparse import jsonld_types

MR, TXT, MISSING, NA = "machine_readable", "text_only", "missing", "n/a"
_PRICE_RE = re.compile(r"[$€£₹]\s?\d|\b\d+(?:\.\d{2})?\s?(?:USD|EUR|GBP|INR)\b", re.I)
_HOURS_RE = re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\s*[:–-]|\bopening hours\b|\bhours?\s*:", re.I)
_OFFER_TEXT_RE = re.compile(r"/(product|products|shop|store|pricing|plans|services?|solutions?)(/|$)", re.I)


def build(ctx: AuditContext) -> Dict[str, Any]:
    pages = ctx.pages
    if not pages:
        return {"score": 0, "applicable": 0, "items": []}
    objs = [o for p in pages for o in p.jsonld]
    types = set()
    for p in pages:
        types |= {t.lower() for t in jsonld_types(p)}
    text = " ".join(p.visible_text for p in pages[:4])
    hrefs = " ".join(a.get("href", "") for p in pages for a in p.links)
    link_text = " ".join(a.get("text", "") for p in pages for a in p.links)

    commerce = ("product" in types or bool(re.search(r"add to (cart|bag)", " ".join(p.raw_html for p in pages[:3]), re.I))
                or "/pricing" in hrefs.lower())
    local = bool({"localbusiness", "restaurant", "store"} & types) or _has(objs, "address")

    items: List[Dict[str, Any]] = []

    # 1. Who is this? (identity)
    if {"organization", "website", "localbusiness"} & types and _org_name(objs):
        items.append(_it("identity", "Who is this brand?", MR, "Organization/WebSite schema with a name."))
    elif pages[0].meta.get("og:site_name") or pages[0].title:
        items.append(_it("identity", "Who is this brand?", TXT, "Brand named in title/OG tags but no Organization schema."))
    else:
        items.append(_it("identity", "Who is this brand?", MISSING, "No clear brand identity found."))

    # 2. What does it offer?
    if {"product", "service", "offer", "course", "offercatalog"} & types:
        items.append(_it("offerings", "What does it offer?", MR, "Offerings described in schema (Product/Service/Offer/Course)."))
    elif _OFFER_TEXT_RE.search(hrefs) or re.search(r"\b(products?|services?|pricing|plans)\b", link_text, re.I):
        items.append(_it("offerings", "What does it offer?", TXT, "Offerings linked in navigation but not in structured data."))
    else:
        items.append(_it("offerings", "What does it offer?", MISSING, "No clear offerings found."))

    # 3. Where is it? (location)
    if _has(objs, "address"):
        items.append(_it("location", "Where is it based?", MR, "Postal address present in structured data."))
    elif re.search(r"\b\d{5,6}\b", text) and re.search(r"\b(street|st\.|road|rd\.|ave|suite|floor|city)\b", text, re.I):
        items.append(_it("location", "Where is it based?", TXT, "Address-like text present but not in structured data."))
    else:
        items.append(_it("location", "Where is it based?", MISSING, "No location/address found."))

    # 4. How to contact?
    if _has(objs, "contactpoint") or _has(objs, "telephone") or _has(objs, "email"):
        items.append(_it("contact", "How to contact it?", MR, "Contact details in structured data."))
    elif "tel:" in hrefs.lower() or "mailto:" in hrefs.lower():
        items.append(_it("contact", "How to contact it?", MR, "Machine-readable tel:/mailto: links present."))
    elif re.search(r"/contact", hrefs, re.I) or re.search(r"\bcontact\b", link_text, re.I):
        items.append(_it("contact", "How to contact it?", TXT, "Contact page linked but no machine-readable contact details."))
    else:
        items.append(_it("contact", "How to contact it?", MISSING, "No contact path found."))

    # 5. Pricing (commerce only)
    if not commerce:
        items.append(_it("pricing", "What does it cost?", NA, "No commerce signals — pricing not expected."))
    elif _has(objs, "price") or _has(objs, "offers"):
        items.append(_it("pricing", "What does it cost?", MR, "Prices in Offer structured data."))
    elif _PRICE_RE.search(text):
        items.append(_it("pricing", "What does it cost?", TXT, "Prices in text but not machine-readable Offers."))
    else:
        items.append(_it("pricing", "What does it cost?", MISSING, "No pricing found."))

    # 6. Opening hours (local only)
    if not local:
        items.append(_it("hours", "When is it open?", NA, "Not a local business — opening hours not expected."))
    elif _has(objs, "openinghours") or _has(objs, "openinghoursspecification"):
        items.append(_it("hours", "When is it open?", MR, "Opening hours in structured data."))
    elif _HOURS_RE.search(text):
        items.append(_it("hours", "When is it open?", TXT, "Hours in text but not machine-readable."))
    else:
        items.append(_it("hours", "When is it open?", MISSING, "No opening hours found."))

    applicable = [i for i in items if i["state"] != NA]
    mr = sum(1 for i in applicable if i["state"] == MR)
    return {
        "score": mr,
        "applicable": len(applicable),
        "machine_readable": mr,
        "text_only": sum(1 for i in applicable if i["state"] == TXT),
        "missing": sum(1 for i in applicable if i["state"] == MISSING),
        "items": items,
    }


def _it(key, question, state, evidence):
    return {"key": key, "question": question, "state": state, "evidence": evidence}


def _org_name(objs) -> bool:
    for o in objs:
        t = o.get("@type")
        t = (t[0] if isinstance(t, list) and t else t) or ""
        if str(t).lower() in ("organization", "website", "localbusiness") and o.get("name"):
            return True
    return False


def _has(objs, key: str) -> bool:
    """Shallow + one-level-nested check for a schema property (case-insensitive)."""
    key = key.lower()
    for o in objs:
        for k, v in o.items():
            if k.lower() == key:
                return True
            if isinstance(v, dict) and any(kk.lower() == key for kk in v):
                return True
            if isinstance(v, dict):
                t = v.get("@type", "")
                if str(t).lower() == key:
                    return True
    return False
