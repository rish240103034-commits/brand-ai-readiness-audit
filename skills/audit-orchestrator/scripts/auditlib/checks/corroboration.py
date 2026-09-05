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
from ..report import Finding, scope_str
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
    host_pages = [p for p in pages if urllib.parse.urlsplit(p.url).netloc.lower() == start_host] or pages

    findings += _sameas(pages)
    findings += _external_presence(pages)
    findings += _name_consistency(host_pages)
    findings += _identity_consistency(host_pages)
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
            why="sameAs links are how a machine ties this site to independent profiles (Wikidata, LinkedIn, "
                "Crunchbase); without them the brand's identity is asserted only by itself and is harder to trust.",
            how_to_fix="Add a sameAs array to the Organization node listing the brand's Wikipedia/Wikidata, LinkedIn, "
                       "Crunchbase, and primary social URLs.",
            measurements={"sameas_links": 0},
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
            why="A site that links to no independent profiles is an 'island' — assistants have nothing to cross-check it "
                "against, so its claims are harder to corroborate and trust.",
            how_to_fix="Claim and link the brand's profiles on independent platforms (LinkedIn, Wikidata, industry directories, review sites) from the site footer/about page.",
            measurements={"external_profiles_found": 0},
            suggested_action_summary=(
                "Claim and link the brand's profiles on independent platforms (LinkedIn, Wikidata, industry "
                "directories, review sites) and reference them from the site. Consistent presence across "
                "independent sources is what makes a fact believable to assistants."),
            suggested_action_priority="medium",
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
            evidence=f"og:site_name differs across same-language pages: {sorted(names)}.",
            why="When the brand name varies across pages, a machine can't be sure they belong to the same entity, "
                "so it may split or mis-attribute the brand's presence.",
            how_to_fix="Use one canonical brand name consistently in og:site_name, Organization.name, and visible branding.",
            measurements={"distinct_site_names": sorted(names)},
            suggested_action_summary="Use one canonical brand name consistently in og:site_name, Organization.name, and visible branding.",
            suggested_action_priority="low",
        )]
    return []


def _identity_consistency(pages: List[Page]) -> List[Finding]:
    """Cross-check the brand name across the three homepage identity signals (name-neutral).

    Compares the two EXPLICIT brand-name fields — og:site_name and the Organization/WebSite
    schema name. (The <title> brand segment is deliberately excluded: sites use both
    "Brand — tagline" and "Page | Brand", so a title-derived name is too ambiguous to trust and
    caused false positives.) Flags only when both are present AND share no significant token —
    a real contradiction. Replaces the old name-length heuristic with name-neutral reasoning.
    """
    home = pages[0]
    signals = {}
    site_name = home.meta.get("og:site_name", "").strip()
    if site_name:
        signals["og:site_name"] = site_name
    for obj in home.jsonld:
        types = {str(t).lower() for t in _types(obj)}
        if {"organization", "website", "localbusiness"} & types and obj.get("name"):
            signals["schema.name"] = str(obj["name"]).strip()
            break
    present = {k: v for k, v in signals.items() if v}
    if len(present) >= 2 and not _share_token(set(v.lower() for v in present.values())):
        return [Finding(
            title="Brand identity signals disagree on the homepage",
            severity="medium", dimension="discoverability", category="entity-identity",
            evidence="Homepage identity signals name different entities: "
                     + "; ".join(f"{k}=\"{v}\"" for k, v in present.items()) + ".",
            why="og:site_name, the Organization schema name, and the page title should agree on who the brand is; "
                "when they disagree an assistant cannot confidently resolve what single entity the site represents.",
            how_to_fix="Use one canonical brand name across og:site_name, Organization.name/WebSite.name, and the title's brand segment.",
            measurements={"identity_signals": present},
            suggested_action_summary="Align og:site_name, Organization/WebSite schema name, and the title's brand segment to one canonical brand name.",
            suggested_action_priority="medium", confidence="medium",
        )]
    return []


def _types(obj: dict):
    t = obj.get("@type")
    if isinstance(t, list):
        return t
    return [t] if t else []


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


def _same_host(a: str, b: str) -> bool:
    from ..http import same_registrable_domain
    return same_registrable_domain(a, b)
