"""Centralized claim-extraction engine.

A *claim* is one atomic, checkable statement a brand makes about itself — its
name, when it was founded, where it operates, what it sells, how to reach it,
who vouches for it. Historically each analysis (hallucination scan, answer
readiness, knowledge graph) re-parsed the HTML for the fact it cared about.
This module extracts every brand claim **once**, records *where the fact lives*
(machine-readable structured data vs. human-visible prose vs. off-site), and
lets the citation-readiness and answer-simulation layers reason about facts
instead of markup.

For each claim we know:
  * whether an AI can quote it verbatim from structured data (``in_structured_data``),
  * whether a reader/extractor can read it in the page text (``in_visible_text``),
  * whether it is corroborated off-site (``off_site`` — a sameAs / profile link),
  * whether the site contradicts itself about it (``status == "contradicted"``).

Deterministic and fully offline. External corroboration is layered on only when
the opt-in verifier already ran (its result is folded in by :func:`build`).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .context import AuditContext
from .htmlparse import Page, jsonld_types
from . import external as _external
from .consistency import _FOUNDED_RE, _SOCIAL_HANDLE_RE, _SKIP_HANDLE

_ORG_TYPES = {"organization", "localbusiness", "corporation", "onlinestore", "store", "website"}
_OFFER_TYPES = {"product", "offer", "service", "aggregateoffer", "productgroup"}
_PRICE_RE = re.compile(r"[$€£₹]\s?\d|\b\d+(?:\.\d{2})?\s?(?:USD|EUR|GBP|INR)\b", re.I)
_EMAIL_RE = re.compile(r"mailto:([^?\"'\s]+)", re.I)
_TEL_RE = re.compile(r"tel:([+\d][\d\s().-]{5,})", re.I)
_IDENTITY_URL_RE = re.compile(r"/(about|company|who-we-are|our-story)", re.I)


def build(ctx: AuditContext, consistency_block: Optional[Dict[str, Any]] = None,
          external_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract every brand claim from the crawl sample.

    Args:
        ctx: shared audit context (crawl sample already fetched).
        consistency_block: the hallucination-scan result, so claims the site
            contradicts itself about are marked ``contradicted``.
        external_result: the opt-in external verifier result, so claims
            corroborated off-site are marked ``corroboration == "external"``.

    Returns ``{"claims": [...], "summary": {...}}`` — additive, never raises.
    """
    pages = ctx.pages or []
    if not pages:
        return {"claims": [], "summary": _summary([])}

    home = pages[0]
    brand = _external._brand_name(home, ctx.start_url)
    contradicted = _contradicted_types(consistency_block)
    ext_ok = bool(external_result and external_result.get("verified"))

    raw: List[Dict[str, Any]] = []
    raw += _brand_name_claim(pages, brand)
    raw += _founding_claims(pages, brand)
    raw += _location_claims(pages, brand)
    raw += _offering_claims(pages, brand)
    raw += _contact_claims(pages, brand)
    raw += _identity_link_claims(pages, brand)
    raw += _price_claims(pages, brand)

    claims: List[Dict[str, Any]] = []
    for i, c in enumerate(raw, 1):
        c["id"] = f"C-{i:03d}"
        c["subject"] = brand
        c["status"] = _status(c, contradicted)
        c["confidence"] = _confidence(c)
        c["corroboration"] = _corroboration(c, ext_ok)
        claims.append(c)
    return {"claims": claims, "summary": _summary(claims)}


# --- per-type extractors -----------------------------------------------------

def _brand_name_claim(pages, brand):
    if not brand:
        return []
    in_sd = any(_type_hit(obj, _ORG_TYPES) and _str(obj.get("name")).lower() == brand.lower()
                for p in pages for obj in p.jsonld)
    home = pages[0]
    hay = (home.title + " " + home.visible_text[:4000]).lower()
    in_text = len(brand) >= 3 and brand.lower() in hay
    return [_claim("brand_name", "Brand / organization name", brand,
                   in_sd, in_text, [home.url])]


def _founding_claims(pages, brand):
    values: Dict[str, Dict[str, Any]] = {}
    identity = [p for p in pages if p is pages[0] or _IDENTITY_URL_RE.search(p.url)]
    for p in identity:
        for m in _FOUNDED_RE.findall(p.visible_text):
            v = values.setdefault(m, {"text": [], "sd": []})
            v["text"].append(p.url)
    for p in pages:
        for obj in p.jsonld:
            fd = re.match(r"(19\d{2}|20\d{2})", _str(obj.get("foundingDate")))
            if fd:
                values.setdefault(fd.group(1), {"text": [], "sd": []})["sd"].append(p.url)
    out = []
    for year, where in sorted(values.items()):
        out.append(_claim("founding_year", "Year founded", year,
                          bool(where["sd"]), bool(where["text"]),
                          (where["sd"] + where["text"])[:4]))
    return out


def _location_claims(pages, brand):
    for p in pages:
        for obj in p.jsonld:
            if not _type_hit(obj, _ORG_TYPES):
                continue
            addr = obj.get("address")
            loc = _address_str(addr)
            if loc:
                in_text = any(part.lower() in p.visible_text.lower()
                              for part in loc.split(", ") if len(part) > 2)
                return [_claim("location", "Headquarters / location", loc,
                               True, in_text, [p.url])]
    return []


def _offering_claims(pages, brand):
    names, sd_pages, text_pages = [], [], []
    for p in pages:
        for obj in p.jsonld:
            if _type_hit(obj, _OFFER_TYPES) and obj.get("name"):
                nm = _str(obj["name"])[:60]
                if nm and nm not in names:
                    names.append(nm)
                    sd_pages.append(p.url)
        for a in p.links:
            if re.search(r"/(product|products|shop|store|pricing|plans|services?|solutions?)(/|$)",
                         a.get("href", ""), re.I):
                text_pages.append(p.url)
    if names:
        return [_claim("offering", "Products / services offered", "; ".join(names[:4]),
                       True, bool(text_pages), (sd_pages + text_pages)[:4])]
    if text_pages:
        return [_claim("offering", "Products / services offered",
                       "offering section(s) linked in navigation",
                       False, True, sorted(set(text_pages))[:4])]
    return []


def _contact_claims(pages, brand):
    sd, email, tel, contact_page = False, None, None, None
    for p in pages:
        for obj in p.jsonld:
            cp = obj.get("contactPoint") or obj.get("ContactPoint")
            if cp or obj.get("telephone") or obj.get("email"):
                sd = True
        for a in p.links:
            href = a.get("href", "")
            m = _EMAIL_RE.match(href) or _EMAIL_RE.search(href)
            if m and not email:
                email = m.group(1)
            mt = _TEL_RE.search(href)
            if mt and not tel:
                tel = mt.group(1).strip()
            if re.search(r"/contact", href, re.I) and not contact_page:
                contact_page = p.url
    parts = [x for x in (email, tel) if x]
    if parts or contact_page or sd:
        val = ", ".join(parts) if parts else ("contact page present" if contact_page else "contact schema present")
        srcs = [pages[0].url]
        return [_claim("contact", "Contact details", val, sd, bool(parts or contact_page), srcs)]
    return []


def _identity_link_claims(pages, brand):
    out, seen = [], set()
    for p in pages:
        # sameAs from schema (machine-readable identity links)
        for obj in p.jsonld:
            for u in _as_list(obj.get("sameAs")):
                u = _str(u).strip()
                if u and u not in seen:
                    seen.add(u)
                    out.append(_claim("identity_link", "Off-site identity link (schema sameAs)",
                                      u, True, False, [p.url], off_site=True))
        # social handles linked in the page (visible identity links)
        for a in p.links:
            m = _SOCIAL_HANDLE_RE.search(a.get("href", ""))
            if not m:
                continue
            handle = m.group(2).lower().strip("/")
            if handle in _SKIP_HANDLE or len(handle) < 2:
                continue
            plat = m.group(1).lower().replace("x", "twitter")
            key = f"{plat}:{handle}"
            if key in seen:
                continue
            seen.add(key)
            out.append(_claim("social_profile", f"{plat.title()} profile", f"@{handle}",
                              False, True, [p.url], off_site=True))
    return out[:10]


def _price_claims(pages, brand):
    sd = any(_type_hit(obj, {"offer", "aggregateoffer"}) and (obj.get("price") or obj.get("lowPrice"))
             for p in pages for obj in p.jsonld)
    text = any(_PRICE_RE.search(p.visible_text) for p in pages)
    if sd or text:
        return [_claim("price_signal", "Pricing shown", "prices present on site", sd, text,
                       [p.url for p in pages if _PRICE_RE.search(p.visible_text)][:3] or [pages[0].url])]
    return []


# --- classification ----------------------------------------------------------

def _status(c, contradicted_types):
    if c["type"] in contradicted_types:
        return "contradicted"
    if c["in_structured_data"] and c["in_visible_text"]:
        return "quotable"
    if c["in_structured_data"]:
        return "structured_only"
    if c["in_visible_text"]:
        return "text_only"
    if c.get("off_site"):
        return "external_only"
    return "unverified"


def _confidence(c):
    if c["in_structured_data"] and c["in_visible_text"]:
        return "high"
    if c["in_structured_data"] or c["in_visible_text"]:
        return "medium"
    return "low"


def _corroboration(c, ext_ok):
    bits = []
    if c["in_structured_data"]:
        bits.append("structured")
    if c["in_visible_text"]:
        bits.append("text")
    if c.get("off_site") and ext_ok:
        bits.append("external")
    elif c.get("off_site"):
        bits.append("declared-offsite")
    return "+".join(bits) if bits else "none"


def _summary(claims):
    by_status: Dict[str, int] = {}
    for c in claims:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    total = len(claims)
    quotable = by_status.get("quotable", 0)
    machine = sum(1 for c in claims if c["in_structured_data"])
    return {
        "total": total,
        "by_status": by_status,
        "quotable": quotable,
        "quotable_pct": round(quotable / total * 100) if total else 0,
        "machine_readable_pct": round(machine / total * 100) if total else 0,
        "contradicted": by_status.get("contradicted", 0),
        "note": ("Every brand fact extracted once; status shows whether an AI can "
                 "quote it (structured), only read it (text), or would have to guess."),
    }


# --- helpers -----------------------------------------------------------------

def _claim(ctype, predicate, value, in_sd, in_text, source_pages, off_site=False):
    return {
        "type": ctype,
        "predicate": predicate,
        "value": value,
        "in_structured_data": bool(in_sd),
        "in_visible_text": bool(in_text),
        "off_site": bool(off_site),
        "source_pages": list(dict.fromkeys(source_pages))[:5],
    }


def _contradicted_types(block):
    out = set()
    for c in (block or {}).get("conflicts", []):
        t = c.get("type", "")
        if t == "founding_year":
            out.add("founding_year")
        elif t.startswith("social_"):
            out.add("social_profile")
    return out


def _type_hit(obj, types):
    t = obj.get("@type", "")
    vals = t if isinstance(t, list) else [t]
    return any(_str(v).lower() in types for v in vals)


def _address_str(addr):
    if isinstance(addr, list):
        addr = addr[0] if addr else None
    if isinstance(addr, dict):
        parts = [addr.get("streetAddress"), addr.get("addressLocality"),
                 addr.get("addressRegion"), addr.get("addressCountry")]
        parts = [_str(x) for x in parts if x]
        return ", ".join(parts)
    if isinstance(addr, str):
        return addr.strip()
    return ""


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _str(v):
    if isinstance(v, dict):
        return _str(v.get("name") or v.get("@id") or "")
    return str(v) if v is not None else ""
