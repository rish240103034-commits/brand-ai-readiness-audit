"""Opt-in off-site corroboration (`--verify-external`).

By default the audit never touches third-party sites (deterministic, read-only, no keys). When the
user explicitly opts in, this module adds *real* external corroboration using only keyless,
ToS-friendly public sources plus the brand's own declared links:

  * **Wikidata** (public API, no key) — is there an entity for the brand, does it point back to this
    domain (P856 official website), and does it have a Wikipedia article? This is the knowledge
    graph AI assistants actually use for entity grounding.
  * **Declared profiles** — the `sameAs`/social URLs the brand *itself* linked on its site are
    fetched to confirm they resolve (verifying the brand's own claims, not scraping search engines).

It never scrapes search engines or social feeds (ToS/auth/non-determinism), and never fabricates a
result: unreachable or absent signals are reported as such. All calls are bounded and time-capped,
and every target host is SSRF-validated before it is fetched. Returns (result_dict, [Finding]).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple

from .context import AuditContext
from .report import Finding
from . import http as _http
from .htmlparse import Page, jsonld_types

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
MAX_PROFILES = 8
TIMEOUT_S = 12
SOCIAL_RE = re.compile(
    r"(facebook|twitter|x\.com|linkedin|instagram|youtube|tiktok|github|wikipedia|wikidata|"
    r"crunchbase|g\.page|maps\.google|yelp)\.", re.I)


def verify(ctx: AuditContext) -> Tuple[Dict[str, Any], List[Finding]]:
    """Run opt-in external corroboration; return (result, findings)."""
    home = ctx.pages[0] if ctx.pages else None
    brand = _brand_name(home, ctx.start_url)
    result: Dict[str, Any] = {
        "performed": True,
        "brand": brand,
        "domain": _http.host_of(ctx.start_url),
        "sources": ["wikidata", "declared-profiles"],
        "wikidata": {"searched": False, "found": False, "links_back": False},
        "profiles": [],
        "verified": False,
        "notes": [],
    }
    findings: List[Finding] = []

    candidates = _brand_candidates(home, ctx.start_url)
    result["wikidata"] = _wikidata(candidates, ctx.start_url, result["notes"])
    result["profiles"] = _profiles(ctx, result["notes"])

    wd = result["wikidata"]
    profiles_ok = sum(1 for p in result["profiles"] if p["state"] == "verified")
    result["verified"] = bool(wd.get("links_back") or profiles_ok >= 1)

    findings += _findings_from(result, wd, profiles_ok)
    return result, findings


# --- Wikidata -----------------------------------------------------------------------

def _wikidata(candidates: List[str], start_url: str, notes: List[str]) -> Dict[str, Any]:
    out = {"searched": True, "found": False, "links_back": False, "id": None,
           "label": None, "description": None, "official_website": None, "wikipedia": None}
    if not candidates:
        out["searched"] = False
        return out
    # Try each candidate name; prefer an entity whose official website (P856) matches the domain
    # (a definitive link-back). The P856 gate keeps precision high even with a broad domain-label
    # search term. Entity fetches are globally capped so recall never costs many requests.
    best, best_entity, fetches = None, None, 0
    for brand in candidates:
        try:
            hits = _wd_get({"action": "wbsearchentities", "search": brand, "language": "en",
                            "format": "json", "type": "item", "limit": 5}).get("search", [])
        except Exception as e:
            notes.append(f"Wikidata search failed for '{brand}': {e}")
            continue
        for h in hits[:5]:
            if fetches >= 8:
                break
            fetches += 1
            try:
                ent = _wd_get({"action": "wbgetentities", "ids": h["id"],
                               "props": "claims|sitelinks|descriptions|labels", "format": "json"}
                              ).get("entities", {}).get(h["id"], {})
            except Exception:
                continue
            site = _official_website(ent)
            if site and _http.same_registrable_domain(site, start_url):
                out["links_back"] = True
                out["official_website"] = site
                best, best_entity = h, ent
                break
            if best is None:
                best, best_entity = h, ent
        if out["links_back"]:
            break
    if not best:
        return out
    out["found"] = True
    out["id"] = best["id"]
    out["label"] = best.get("label")
    out["description"] = best.get("description")
    if best_entity:
        enwiki = best_entity.get("sitelinks", {}).get("enwiki", {})
        if enwiki.get("title"):
            out["wikipedia"] = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
                enwiki["title"].replace(" ", "_"))
        if not out["official_website"]:
            out["official_website"] = _official_website(best_entity)
    return out


def _official_website(entity: Dict[str, Any]):
    for claim in entity.get("claims", {}).get("P856", []):  # P856 = official website
        try:
            return claim["mainsnak"]["datavalue"]["value"]
        except Exception:
            continue
    return None


_UA = "brand-ai-readiness-audit (+read-only external corroboration; opt-in)"


def _wd_get(params: Dict[str, str]) -> Dict[str, Any]:
    url = WIKIDATA_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # nosec - fixed public API host
        return json.loads(r.read().decode("utf-8", "replace"))


# --- declared profiles --------------------------------------------------------------

def _profiles(ctx: AuditContext, notes: List[str]) -> List[Dict[str, Any]]:
    urls = _collect_profile_urls(ctx.pages)
    out = []
    for u in list(urls)[:MAX_PROFILES]:
        host = urllib.parse.urlsplit(u).netloc.split(":")[0]
        # SSRF guard: only fetch public hosts (a malicious sameAs could point at an internal IP).
        if _http.classify_host(host) != "public":
            out.append({"url": u, "state": "skipped", "reason": "non-public host", "status": None})
            continue
        state, status = _probe(u)
        out.append({"url": u, "state": state, "status": status})
    return out


def _collect_profile_urls(pages: List[Page]) -> List[str]:
    seen, out = set(), []
    for p in pages:
        for obj in p.jsonld:  # declared sameAs
            sa = obj.get("sameAs")
            vals = sa if isinstance(sa, list) else ([sa] if isinstance(sa, str) else [])
            for v in vals:
                v = str(v)
                if v.startswith("http") and v not in seen:
                    seen.add(v); out.append(v)
        for a in p.links:  # linked social/authority profiles
            href = a.get("href", "")
            if href.startswith("http") and SOCIAL_RE.search(href) and href not in seen:
                seen.add(href); out.append(href)
    return out


def _probe(url: str) -> Tuple[str, Any]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "brand-ai-readiness-audit/verify"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # nosec - user-opted external check
            return ("verified", r.status)
    except urllib.error.HTTPError as e:
        # Some platforms block bots with 403/429 but the profile exists — report honestly.
        return (("verified" if e.code in (403, 429, 999) else "unreachable"), e.code)
    except Exception:
        return ("unreachable", None)


# --- findings -----------------------------------------------------------------------

def _findings_from(result, wd, profiles_ok) -> List[Finding]:
    out: List[Finding] = []
    total_profiles = len([p for p in result["profiles"] if p["state"] != "skipped"])
    domain = result["domain"]

    if wd.get("links_back"):
        pass  # strong corroboration — no defect
    elif wd.get("found"):
        out.append(Finding(
            title="Wikidata entity exists but is not linked to this site",
            severity="low", dimension="discoverability", category="corroboration", confidence="medium",
            evidence=f"A Wikidata entity ({wd['id']}, \"{wd.get('label')}\") matches the brand name but its "
                     f"official-website property does not point to {domain}.",
            why="An assistant grounding the brand via Wikidata can't be sure that entity is this site, so it may "
                "attribute facts to a namesake or not at all.",
            how_to_fix=f"On Wikidata, set the entity's official website (P856) to {domain}, and add a sameAs link "
                       "to the Wikidata entity from the site's Organization schema.",
            measurements={"wikidata_id": wd["id"], "links_back": False},
            suggested_action_summary="Link the Wikidata entity to this domain (P856) and add a sameAs back to it.",
            suggested_action_priority="low"))
    else:
        out.append(Finding(
            title="No independent external corroboration found",
            severity="medium", dimension="discoverability", category="corroboration", confidence="medium",
            evidence=f"Searched Wikidata and the site's declared profiles: no entity links back to {domain}, "
                     f"and {profiles_ok}/{total_profiles} declared profile link(s) were reachable.",
            why="Assistants trust facts that are echoed by independent, authoritative sources; with no external "
                "corroboration the brand's claims rest on the site alone and are weighted lower.",
            how_to_fix="Establish and link authoritative profiles (Wikidata/Wikipedia entity, LinkedIn, Crunchbase, "
                       "industry directories) and reference them via Organization sameAs.",
            measurements={"wikidata_found": False, "profiles_verified": profiles_ok, "profiles_total": total_profiles},
            suggested_action_summary="Create/claim authoritative external profiles (starting with Wikidata) and link them via sameAs.",
            suggested_action_priority="medium"))

    unreachable = [p["url"] for p in result["profiles"] if p["state"] == "unreachable"]
    if unreachable:
        out.append(Finding(
            title="Declared brand profiles are unreachable",
            severity="low", dimension="discoverability", category="corroboration", confidence="high",
            evidence=f"{len(unreachable)} declared sameAs/profile link(s) did not resolve, e.g. {unreachable[0]}.",
            why="A broken corroboration link points assistants at nothing, wasting the trust signal the brand intended.",
            how_to_fix="Fix or remove the dead profile URLs in the site's links and Organization sameAs.",
            measurements={"unreachable_profiles": len(unreachable)},
            affected_pages=[], suggested_action_summary="Correct or remove unreachable sameAs/profile URLs.",
            suggested_action_priority="low"))
    return out


# --- helpers ------------------------------------------------------------------------

def _brand_candidates(home, start_url: str) -> List[str]:
    """Ordered, de-duplicated brand search terms: declared name, name minus TLD, domain label."""
    cands: List[str] = []
    primary = _brand_name(home, start_url)
    if primary:
        cands.append(primary)
        # "Python.org" -> "Python": drop a trailing .tld the brand name sometimes carries.
        stripped = re.sub(r"\.\w{2,}$", "", primary).strip()
        if stripped and stripped.lower() != primary.lower():
            cands.append(stripped)
    host = _http.host_of(start_url)
    label = host.split(".")[0] if host else ""
    if label and label.capitalize() not in cands and label not in cands:
        cands.append(label.capitalize())
    # de-dup case-insensitively, keep order
    seen, out = set(), []
    for c in cands:
        k = c.lower()
        if k and k not in seen:
            seen.add(k); out.append(c)
    return out[:3]


def _brand_name(home, start_url: str) -> str:
    if home is not None:
        name = home.meta.get("og:site_name", "").strip()
        if name:
            return name
        for obj in home.jsonld:
            types = {str(t).lower() for t in jsonld_types(home)}
            if {"organization", "website", "localbusiness"} & types and obj.get("name"):
                return str(obj["name"]).strip()
    host = _http.host_of(start_url)
    label = host.split(".")[0] if host else ""
    return label.capitalize()
