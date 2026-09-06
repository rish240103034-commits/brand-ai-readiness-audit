"""Prompt-pack readiness — grade the real questions people ask AI assistants about the brand.

Reframes the whole audit around actual user queries ("is <brand> legit?", "<brand> pricing",
"how to contact <brand>") and, for each, judges whether the site exposes the machine-readable
facts needed to be the *source* of a good answer: ready / partial / weak (or n/a). Builds on the
answer-readiness scorecard plus a couple of extra signals. Attached as ``report['prompt_pack']``.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .context import AuditContext
from .htmlparse import jsonld_types

READY, PARTIAL, WEAK, NA = "ready", "partial", "weak", "n/a"
_MAP = {"machine_readable": READY, "text_only": PARTIAL, "missing": WEAK, "n/a": NA}


def build(ctx: AuditContext, answer_readiness: Dict[str, Any]) -> Dict[str, Any]:
    brand = _brand(ctx)
    ar = {i["key"]: i["state"] for i in (answer_readiness or {}).get("items", [])}
    objs = [o for p in ctx.pages for o in p.jsonld]
    has_sameas = any(o.get("sameAs") for o in objs)
    has_org = any({"organization", "website", "localbusiness"} & {str(t).lower() for t in jsonld_types(p)}
                  for p in ctx.pages)
    has_reviews = any(("aggregateRating" in o or "review" in o) for o in objs)
    has_founder = any((o.get("founder") or o.get("foundingDate")) for o in objs)

    prompts: List[Dict[str, Any]] = []

    # Trust / legitimacy
    if has_org and has_sameas:
        prompts.append(_p(f"Is {brand} legitimate / trustworthy?", READY,
                          "Identity schema + external profiles present."))
    elif has_org or has_sameas:
        prompts.append(_p(f"Is {brand} legitimate / trustworthy?", PARTIAL,
                          "Add external corroboration (sameAs to Wikidata/LinkedIn) and reviews."))
    else:
        prompts.append(_p(f"Is {brand} legitimate / trustworthy?", WEAK,
                          "No Organization schema and no external profiles to corroborate the brand."))

    prompts.append(_p(f"What does {brand} offer?", _MAP.get(ar.get("offerings"), WEAK),
                      "Describe offerings in Product/Service schema." if ar.get("offerings") != "machine_readable" else "Offerings are machine-readable."))
    prompts.append(_p(f"How much does {brand} cost?", _MAP.get(ar.get("pricing"), WEAK),
                      "Expose prices in Offer schema." if ar.get("pricing") not in ("machine_readable", "n/a") else ""))
    prompts.append(_p(f"How do I contact {brand}?", _MAP.get(ar.get("contact"), WEAK),
                      "Add ContactPoint schema or tel:/mailto: links." if ar.get("contact") != "machine_readable" else ""))
    prompts.append(_p(f"Where is {brand} based?", _MAP.get(ar.get("location"), WEAK),
                      "Add a PostalAddress in Organization/LocalBusiness schema." if ar.get("location") != "machine_readable" else ""))

    # Founder / people
    if has_founder:
        prompts.append(_p(f"Who founded {brand}?", READY, "founder/foundingDate present in schema."))
    else:
        prompts.append(_p(f"Who founded {brand}?", WEAK,
                          "Add founder and foundingDate to Organization schema (and an About page)."))

    # Reviews / reputation
    if has_reviews:
        prompts.append(_p(f"{brand} reviews and ratings?", READY, "aggregateRating/review markup present."))
    elif has_sameas:
        prompts.append(_p(f"{brand} reviews and ratings?", PARTIAL,
                          "Reviews live off-site only; add aggregateRating where genuine reviews exist."))
    else:
        prompts.append(_p(f"{brand} reviews and ratings?", WEAK,
                          "No review markup and no external profiles carrying reviews."))

    applicable = [p for p in prompts if p["state"] != NA]
    return {
        "brand": brand,
        "ready": sum(1 for p in applicable if p["state"] == READY),
        "total": len(applicable),
        "prompts": prompts,
    }


def _p(prompt, state, needs):
    return {"prompt": prompt, "state": state, "needs": needs}


def _brand(ctx: AuditContext) -> str:
    if ctx.pages:
        home = ctx.pages[0]
        name = home.meta.get("og:site_name", "").strip()
        if name:
            return name
        for obj in home.jsonld:
            if {"organization", "website", "localbusiness"} & {str(t).lower() for t in jsonld_types(home)} and obj.get("name"):
                return str(obj["name"]).strip()
    from . import http as _http
    host = _http.host_of(ctx.start_url)
    return host.split(".")[0].capitalize() if host else "the brand"
