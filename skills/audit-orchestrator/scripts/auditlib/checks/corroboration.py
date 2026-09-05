"""Corroboration & entity-disambiguation checks (Round-2 appendix D — agreement half).

A claim that lives in only one place is fragile; the same fact echoed across independent
sources is trusted and repeated. And when several things share a name, a machine mixes
them up unless something clearly distinguishes the brand. Both are off-site
discoverability risks that the on-page markup can strengthen.
"""
from __future__ import annotations

import re
from typing import List

from ..context import AuditContext
from ..report import Finding
from ..htmlparse import Page, jsonld_types

SOCIAL_RE = re.compile(
    r"(facebook|twitter|x\.com|linkedin|instagram|youtube|tiktok|github|"
    r"wikipedia|wikidata|crunchbase|g\.page|maps\.google|yelp)\.",
    re.I,
)


def analyze(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []
    pages = ctx.pages
    if not pages:
        return findings

    # Brand identity is host-specific: subdomains (docs., blog., shop.) are legitimately
    # separate properties, so name/identity checks use only pages on the start host.
    import urllib.parse
    start_host = urllib.parse.urlsplit(ctx.start_url).netloc.lower()
    same_host = [p for p in pages if urllib.parse.urlsplit(p.url).netloc.lower() == start_host] or pages

    findings += _sameas(pages)
    findings += _external_presence(pages)
    findings += _entity_disambiguation(same_host, ctx)
    findings += _name_consistency(same_host)
    return findings


def _collect_sameas(pages: List[Page]) -> List[str]:
    out: List[str] = []
    for p in pages:
        for obj in p.jsonld:
            sa = obj.get("sameAs")
            if isinstance(sa, str):
                out.append(sa)
            elif isinstance(sa, list):
                out.extend(str(x) for x in sa)
    return out


def _sameas(pages: List[Page]) -> List[Finding]:
    has_org = any({"organization", "localbusiness"} & {t.lower() for t in jsonld_types(p)} for p in pages)
    sameas = _collect_sameas(pages)
    if has_org and not sameas:
        return [Finding(
            title="Organization schema has no sameAs corroboration links",
            severity="medium",
            dimension="discoverability",
            category="corroboration",
            evidence="An Organization/LocalBusiness node exists but declares no sameAs links to external profiles.",
            suggested_action_summary=(
                "Add sameAs URLs pointing to the brand's Wikipedia/Wikidata, LinkedIn, Crunchbase, and "
                "primary social profiles. These let assistants tie your site to corroborating, independent "
                "sources and resolve who you are."),
            suggested_action_priority="medium",
        )]
    return []


def _external_presence(pages: List[Page]) -> List[Finding]:
    """Island-site check: no outbound links to recognized external/authority profiles."""
    origin_links_only = True
    social_found = set()
    for p in pages:
        for a in p.links:
            href = a["href"]
            m = SOCIAL_RE.search(href)
            if m:
                social_found.add(m.group(1).lower())
            if href.startswith("http") and not _same_host(href, p.url):
                origin_links_only = False
    if not social_found:
        return [Finding(
            title="No links to external brand profiles or authority sources",
            severity="low",
            dimension="discoverability",
            category="corroboration",
            evidence="Sampled pages link to no recognized external profiles (social, Wikipedia/Wikidata, Crunchbase, maps/reviews).",
            suggested_action_summary=(
                "Claim and link the brand's profiles on independent platforms (LinkedIn, Wikidata, industry "
                "directories, review sites) and reference them from the site. Consistent presence across "
                "independent sources is what makes a fact believable to assistants."),
            suggested_action_priority="medium",
        )]
    return []


def _entity_disambiguation(pages: List[Page], ctx: AuditContext) -> List[Finding]:
    """Short/generic brand name with no disambiguating attributes invites mistaken identity."""
    home = pages[0]
    brand = _brand_name(home)
    if not brand:
        return []
    generic = len(brand.split()) == 1 and len(brand) <= ctx.cfg.t("brand_generic_len")
    disambiguators = 0
    for p in pages:
        for obj in p.jsonld:
            for key in ("foundingDate", "founder", "address", "sameAs", "legalName", "vatID", "duns"):
                if key in obj:
                    disambiguators += 1
    if generic and disambiguators == 0:
        return [Finding(
            title="Brand name is ambiguous with no disambiguating signals",
            severity="medium",
            dimension="discoverability",
            category="entity-identity",
            evidence=f"Brand name \"{brand}\" is short/generic and the site provides no distinguishing attributes (address, foundingDate, founder, legalName, sameAs).",
            suggested_action_summary=(
                "Add distinguishing facts in Organization schema (legalName, foundingDate, founder, address, "
                "sameAs to Wikidata) and in prose, so assistants don't confuse the brand with others that "
                "share the name."),
            suggested_action_priority="medium",
            confidence="medium",
        )]
    return []


def _name_consistency(pages: List[Page]) -> List[Finding]:
    # Only compare like-language pages (localized og:site_name is not an inconsistency),
    # and only among primarily-ASCII names so translations don't create false positives.
    base_lang = (pages[0].lang or "").split("-")[0].lower()
    names = set()
    for p in pages:
        lang = (p.lang or "").split("-")[0].lower()
        if base_lang and lang and lang != base_lang:
            continue
        site_name = p.meta.get("og:site_name", "").strip()
        if site_name and site_name.isascii():
            names.add(site_name.lower())
    # Require genuinely different names (no shared significant token) to flag.
    if len(names) > 1 and not _share_token(names):
        return [Finding(
            title="Inconsistent brand name across pages",
            severity="low",
            dimension="discoverability",
            category="entity-identity",
            evidence=f"og:site_name differs across same-language pages: {sorted(names)}. Inconsistent naming weakens entity resolution.",
            suggested_action_summary="Use one canonical brand name consistently in og:site_name, Organization.name, and visible branding.",
            suggested_action_priority="low",
        )]
    return []


def _share_token(names) -> bool:
    """True if all names share at least one significant (3+ char) token — i.e. same brand."""
    token_sets = []
    for n in names:
        toks = {t for t in re.split(r"\W+", n.lower()) if len(t) >= 3}
        token_sets.append(toks)
    if not token_sets:
        return False
    common = set.intersection(*token_sets) if len(token_sets) > 1 else token_sets[0]
    return bool(common)


def _brand_name(home: Page) -> str:
    name = home.meta.get("og:site_name", "").strip()
    if name:
        return name
    for obj in home.jsonld:
        if {"organization", "website", "localbusiness"} & {str(t).lower() for t in _types(obj)}:
            if obj.get("name"):
                return str(obj["name"]).strip()
    if home.title:
        # take the segment after the last separator, commonly the brand
        parts = re.split(r"[|\-–—:]", home.title)
        return parts[-1].strip() if len(parts) > 1 else home.title.strip()
    return ""


def _types(obj: dict):
    t = obj.get("@type")
    if isinstance(t, list):
        return t
    return [t] if t else []


def _same_host(a: str, b: str) -> bool:
    from ..http import same_registrable_domain
    return same_registrable_domain(a, b)
