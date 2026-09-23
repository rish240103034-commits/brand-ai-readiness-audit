"""Regional 'branch' detection — India, Global, UK, US, … variants of one brand.

Large brands run locale/region variants: a global site, an India site, a UK site. Each can have
very different AI-readiness, and a mis-declared or dead regional branch directly causes an assistant
to send Indian users to the wrong page — or to miss the local entity entirely. This module
inventories the regional branches a brand *declares* (hreflang alternates, ``og:locale:alternate``,
and region-selector / URL heuristics) and, for each, records how it's declared, whether it's
reciprocal, and whether it actually resolves (a small, bounded, robots-respecting reachability probe).

Deterministic; the probe is capped in count and wall-clock so it can never threaten the runtime
budget. Returns ``(block, [Finding])`` — mirroring the consistency scan so findings merge normally.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Tuple

from .context import AuditContext
from .report import Finding
from . import http as _http
from .checks.crawl_render import _alternates  # reuse the one hreflang extractor

# Reachability probing is LIGHT by default (small footprint, like any routine audit) and only goes
# EXHAUSTIVE on request (--check-regions / --audit-regions) — so a normal audit never fires ~100+
# extra requests at the brand's hosts (which bot-protected sites may then throttle).
REGION_PROBES_LIGHT = 8         # default: probe only a handful of declared variants
REGION_PROBES_EXHAUSTIVE = 120  # opt-in: probe (almost) every declared variant
REGION_BUDGET_LIGHT_S = 15      # wall-clock cap, default
REGION_BUDGET_EXHAUSTIVE_S = 60 # wall-clock cap, exhaustive
REGION_PROBE_WORKERS = 10       # concurrent HEAD probes (each host still throttled by the fetcher)
REGION_PROBE_TIMEOUT_S = 7      # per-request timeout for the liveness probe (no retries)

# Country / region codes → human labels (common set; unknown codes fall back to the raw code).
_REGION_NAMES = {
    "IN": "India", "GB": "United Kingdom", "UK": "United Kingdom", "US": "United States",
    "CA": "Canada", "AU": "Australia", "NZ": "New Zealand", "IE": "Ireland", "SG": "Singapore",
    "AE": "UAE", "SA": "Saudi Arabia", "ZA": "South Africa", "DE": "Germany", "FR": "France",
    "ES": "Spain", "IT": "Italy", "NL": "Netherlands", "SE": "Sweden", "CH": "Switzerland",
    "BE": "Belgium", "AT": "Austria", "PT": "Portugal", "BR": "Brazil", "MX": "Mexico",
    "AR": "Argentina", "JP": "Japan", "CN": "China", "HK": "Hong Kong", "TW": "Taiwan",
    "KR": "South Korea", "RU": "Russia", "PL": "Poland", "TR": "Turkey", "ID": "Indonesia",
    "MY": "Malaysia", "PH": "Philippines", "TH": "Thailand", "VN": "Vietnam", "BD": "Bangladesh",
    "PK": "Pakistan", "LK": "Sri Lanka", "NG": "Nigeria", "EG": "Egypt", "IL": "Israel",
}
# URL-path / subdomain locale hints (fallback when a site uses no hreflang).
_URL_LOCALE_RE = re.compile(
    r"(?:^|[/.])(?:"
    r"(?P<langreg>[a-z]{2}-[a-z]{2})"                 # en-in, en-gb
    r"|(?P<reg>in|uk|us|au|ca|sg|ae|de|fr|es|it|jp|cn|br|global|intl|international|row)"
    r")(?:[/.]|$)", re.I)


def scan(ctx: AuditContext, exhaustive: bool = False) -> Tuple[Dict[str, Any], List[Finding]]:
    """Detect declared regional variants and probe reachability. Never raises.

    ``exhaustive`` (opt-in) probes (almost) every declared variant; the default probes only a small
    bounded set so a routine audit keeps a light request footprint on the brand's hosts.
    """
    pages = ctx.pages or []
    empty = {"count": 0, "variants": [], "has_global": False,
             "note": "No regional/locale variants declared — single-region site."}
    if not pages:
        return empty, []

    variants: Dict[str, Dict[str, Any]] = {}   # keyed by normalized url

    # 1) hreflang alternates — the authoritative, one-entry-per-locale source. When a site declares
    #    hreflang we trust ONLY this: each alternate href is a region's canonical entrypoint.
    hreflang_pairs: Dict[str, str] = {}        # code -> url (first seen)
    for p in pages:
        for code, href in _alternates(p):
            url = _http.normalize(href, base=p.url) or href
            code_l = code.strip().lower()
            hreflang_pairs.setdefault(code_l, url)
            v = variants.setdefault(url, _blank(url))
            if not v.get("locale"):
                v["locale"] = code_l
            _add_via(v, "hreflang")

    # 2) Fallback ONLY when there is no hreflang at all: derive region roots from locale-path /
    #    region-selector links, collapsed to one entry per region (never per deep page).
    if not variants:
        _fallback_from_links(pages, variants)

    if not variants:
        return empty, []

    # Enrich: region label, default flag, reciprocity, in-sample status.
    sample_status = {r.final_url or r.url: r.status for r in ctx.responses}
    for url, v in variants.items():
        _label(v)
        if url in sample_status:
            v["in_sample"] = True
            v["status"] = sample_status[url]
            v["reachable"] = "ok" if _ok(sample_status[url]) else "error"
    _mark_reciprocity(variants, hreflang_pairs)

    # Reachability: probe declared-but-not-sampled variants (concurrent HEAD, bounded). Light by
    # default; the whole set only under --check-regions / --audit-regions.
    cap = REGION_PROBES_EXHAUSTIVE if exhaustive else REGION_PROBES_LIGHT
    budget = REGION_BUDGET_EXHAUSTIVE_S if exhaustive else REGION_BUDGET_LIGHT_S
    checked = _probe_reachability(ctx, variants, cap, budget)

    variant_list = _sorted(variants.values())
    block = _summary(variant_list, checked, exhaustive)
    return block, _findings(variant_list)


# --- helpers ----------------------------------------------------------------------

def _blank(url: str) -> Dict[str, Any]:
    return {"url": url, "locale": "", "region": "", "language": "", "declared_via": [],
            "is_default": False, "reciprocal": None, "in_sample": False,
            "reachable": "unchecked", "status": None}


def _add_via(v: Dict[str, Any], src: str) -> None:
    if src not in v["declared_via"]:
        v["declared_via"].append(src)


def _label(v: Dict[str, Any]) -> None:
    code = (v.get("locale") or "").lower()
    if code in ("x-default", "x_default"):
        v["is_default"] = True
        v["region"], v["language"] = "Global (x-default)", ""
        return
    lang, region = "", ""
    m = re.match(r"^([a-z]{2,3})(?:-([a-z]{2}|\d{3}))?$", code)
    if m:
        lang = m.group(1)
        if m.group(2):
            region = _REGION_NAMES.get(m.group(2).upper(), m.group(2).upper())
    elif code:  # bare region hint from URL (e.g. "in", "uk", "global")
        if code in ("global", "intl", "international", "row"):
            v["is_default"] = True
            v["region"] = "Global"
        else:
            region = _REGION_NAMES.get(code.upper(), code.upper())
    v["language"] = lang
    v["region"] = v["region"] or region or (lang.upper() if lang else "Unspecified")


def _locale_from_url(url: str) -> str:
    host = _http.host_of(url)
    path = url[len(host):] if host in url else url
    m = _URL_LOCALE_RE.search(path) or _URL_LOCALE_RE.search(host)
    if not m:
        return ""
    return (m.group("langreg") or m.group("reg") or "").lower()


def _mark_reciprocity(variants: Dict[str, Dict[str, Any]], hreflang_pairs: Dict[str, str]) -> None:
    """A variant is 'reciprocal' if the whole hreflang cluster is mutually linked within the sample.
    We only assert this at the cluster level (conservative): if ≥2 hreflang variants exist, they are
    reciprocal by construction of the shared alternate block; otherwise leave None."""
    hreflang_urls = {u for u, v in variants.items() if "hreflang" in v["declared_via"]}
    reciprocal = len(hreflang_urls) >= 2
    for u in hreflang_urls:
        variants[u]["reciprocal"] = reciprocal


def _fallback_from_links(pages: List[Page], variants: Dict[str, Dict[str, Any]]) -> None:
    """No hreflang on the site → derive region roots from locale-path / region-selector links.
    Conservative: one entry per region code, collapsed to the region ROOT (never per deep page)."""
    seen_codes = set()
    for p in pages:
        for a in p.links:
            url = _http.normalize(a.get("href", ""), base=p.url)
            if not url:
                continue
            code = _locale_from_url(url)
            if not code or code in seen_codes:
                continue
            root = _locale_root(url, code)
            if root in variants:
                continue
            seen_codes.add(code)
            v = variants.setdefault(root, _blank(root))
            v["locale"] = code
            _add_via(v, "selector")
            if len(variants) >= 40:   # hard cap for the fallback path
                return


def _locale_root(url: str, code: str) -> str:
    """Collapse a locale URL to its region root, e.g. .../in/en/deep/x → .../in/en/."""
    scheme, _, rest = url.partition("://")
    host, _, path = rest.partition("/")
    tokens = set(code.lower().split("-")) | {code.lower()}
    segs, kept = [s for s in path.split("/") if s], []
    for s in segs:
        kept.append(s)
        if s.lower() in tokens:
            break
    root = "/".join(kept)
    return f"{scheme}://{host}/" + (root + "/" if root else "")


def _probe_reachability(ctx: AuditContext, variants: Dict[str, Dict[str, Any]],
                        cap: int, budget_s: float) -> int:
    """Probe declared-but-not-sampled variants with a lightweight HEAD, concurrently and within a
    wall-clock budget (each host is still throttled by the fetcher, so we stay polite). ``cap`` limits
    how many are probed. Returns the number actually checked. Transport errors stay 'unchecked'."""
    import concurrent.futures as cf

    targets = sorted(u for u, v in variants.items()
                     if not v["in_sample"] and v["reachable"] == "unchecked")[:cap]
    if not targets:
        return 0

    # A liveness probe wants to fail FAST on slow/dead hosts, not retry — the crawl fetcher's
    # retries+backoff would let a handful of dead regional hosts exhaust the whole budget. So use a
    # dedicated no-retry, short-timeout fetcher (still robots- and SSRF-respecting). In tests the
    # injected FakeFetcher is used as-is (offline).
    fetcher = ctx.fetcher
    if isinstance(fetcher, _http.Fetcher):
        fetcher = _http.Fetcher(cfg=ctx.cfg.derive(max_retries=0, timeout=REGION_PROBE_TIMEOUT_S))

    def probe(u):
        try:
            r = fetcher.fetch(u, method="HEAD")
            st = r.status if isinstance(r.status, int) else None
            # some servers reject HEAD (405/501) — fall back to a GET to learn the real status
            if st in (405, 501):
                r = fetcher.fetch(u)
                st = r.status if isinstance(r.status, int) else None
            return u, st
        except Exception:  # pragma: no cover - defensive
            return u, None

    checked = 0
    with cf.ThreadPoolExecutor(max_workers=REGION_PROBE_WORKERS) as ex:
        futs = {ex.submit(probe, u): u for u in targets}
        try:
            for fut in cf.as_completed(futs, timeout=budget_s):
                u, st = fut.result()
                variants[u]["status"] = st
                variants[u]["reachable"] = _reach_of(st)
                checked += 1
        except cf.TimeoutError:  # budget hit — remaining stay 'unchecked'
            pass
    return checked


def _reach_of(status) -> str:
    """Map an HTTP status to a reachability verdict. 401/403/405 mean the URL exists (gated / method
    blocked), so they are NOT 'dead'; only 404/410 and 5xx are a real broken regional branch."""
    if status is None or status == 0:
        return "unchecked"          # transport error ≠ definitive 'dead'
    if status in (404, 410) or 500 <= status < 600:
        return "error"
    return "ok"


def _sorted(vals) -> List[Dict[str, Any]]:
    # Global first, then by region label, stable.
    return sorted(vals, key=lambda v: (0 if v["is_default"] else 1, v.get("region", ""), v["url"]))


def _summary(variant_list: List[Dict[str, Any]], checked: int = 0,
             exhaustive: bool = False) -> Dict[str, Any]:
    reachable = sum(1 for v in variant_list if v["reachable"] == "ok")
    dead = [v for v in variant_list if v["reachable"] == "error"]
    unchecked = sum(1 for v in variant_list if v["reachable"] == "unchecked")
    has_global = any(v["is_default"] for v in variant_list)
    regions = [v["region"] for v in variant_list]
    # explain WHY some are unchecked: light default vs. budget in exhaustive mode
    unchecked_note = ""
    if unchecked:
        unchecked_note = (f", {unchecked} not checked "
                          + ("(budget)" if exhaustive else "(run --check-regions to probe all)"))
    return {
        "count": len(variant_list),
        "variants": variant_list,
        "regions": regions,
        "has_global": has_global,
        "reachable": reachable,
        "unreachable": len(dead),
        "unchecked": unchecked,
        "checked": checked,
        "exhaustive": exhaustive,
        "note": (f"{len(variant_list)} regional variant(s) declared — {reachable} reachable"
                 + (f", {len(dead)} dead" if dead else "")
                 + unchecked_note
                 + ("; global fallback present" if has_global else "; no global/x-default fallback")
                 + "."),
    }


def _findings(variant_list: List[Dict[str, Any]]) -> List[Finding]:
    out: List[Finding] = []
    dead = [v for v in variant_list if v["reachable"] == "error"]
    if dead:
        shown = ", ".join(f'{v["region"]} ({v["url"]} → {v["status"]})' for v in dead[:4])
        out.append(Finding(
            title="Declared regional variant is unreachable",
            severity="high", dimension="discoverability", category="i18n", confidence="high",
            evidence=f"{len(dead)} declared regional branch(es) return an error: {shown}.",
            why="A regional variant announced via hreflang/selector but returning 4xx/5xx sends that "
                "country's visitors — and AI assistants resolving the local entity — to a dead page, "
                "so the brand is effectively missing in that market.",
            how_to_fix="Fix or remove the broken regional URL: make the variant resolve (200), or drop "
                       "its hreflang/selector entry so engines don't route users to a dead branch.",
            measurements={"regional_variants": len(variant_list), "unreachable": len(dead)},
            suggested_action_summary="Fix or remove dead regional variant URLs.",
            suggested_action_priority="high",
            affected_pages=[v["url"] for v in dead][:10],
        ))
    return out


def _ok(status) -> bool:
    return isinstance(status, int) and 200 <= status < 400


# --- opt-in full per-region audit (--audit-regions) --------------------------------

def audit_candidates(block: Dict[str, Any], primary_url: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Which regional variants are worth a full audit: distinct hosts+paths, likely-live, not the
    primary itself. Bounded so the opt-in pass stays within the runtime budget."""
    primary = _http.host_of(primary_url)
    seen, out = set(), []
    for v in block.get("variants", []):
        if v.get("reachable") == "error":       # skip dead branches (nothing to score)
            continue
        key = v["url"].rstrip("/")
        host = _http.host_of(v["url"])
        # skip the exact primary URL (already audited); allow same-host locale sub-paths
        if key == primary_url.rstrip("/") or key in seen:
            continue
        seen.add(key)
        out.append(v)
        if len(out) >= limit:
            break
    return out


def build_audits(primary_rpt: Dict[str, Any], primary_variant: Dict[str, Any],
                 audited: List[Any]) -> Dict[str, Any]:
    """Assemble the per-region score comparison. ``audited`` is a list of (variant, report) pairs.
    The primary report is included as the anchor row. Pure function of already-produced reports."""
    rows = [_cap_region(primary_variant, primary_rpt, is_primary=True)]
    for variant, rpt in audited:
        if rpt:
            rows.append(_cap_region(variant, rpt, is_primary=False))
    rows.sort(key=lambda r: (not r["is_primary"], -(r["score"] or 0)))
    note = _audit_note(rows)
    return {"regions": rows, "audited": len(rows), "note": note}


def _cap_region(variant: Dict[str, Any], rpt: Dict[str, Any], is_primary: bool) -> Dict[str, Any]:
    sc = rpt.get("score", {}) or {}
    cr = rpt.get("citation_readiness", {}) or {}
    return {
        "url": variant.get("url") or rpt.get("site", ""),
        "region": variant.get("region") or "Primary",
        "locale": variant.get("locale", ""),
        "score": sc.get("value"),
        "grade": sc.get("grade", ""),
        "discoverability": round(sc.get("discoverability", 0)),
        "citation": cr.get("score"),
        "engagement": round(sc.get("engagement", 0)),
        "findings": rpt.get("summary", {}).get("total_findings", 0),
        "is_primary": is_primary,
    }


def _audit_note(rows: List[Dict[str, Any]]) -> str:
    scored = [r for r in rows if r["score"] is not None]
    if len(scored) < 2:
        return "Per-region audit complete."
    anchor = next((r for r in scored if r["is_primary"]), scored[0])
    weakest = min(scored, key=lambda r: r["score"])
    if weakest["url"] == anchor["url"]:
        return (f"{anchor['region']} scores highest; regional branches are consistent "
                f"or ahead across the set.")
    gap = anchor["score"] - weakest["score"]
    dims = {"Discoverability": weakest["discoverability"],
            "Citation": weakest.get("citation") or 0, "Engagement": weakest["engagement"]}
    weak_dim = min(dims, key=dims.get)
    return (f"{weakest['region']} ({weakest['score']}/100, {weakest['grade']}) trails "
            f"{anchor['region']} ({anchor['score']}/100) by {gap} point(s) — weakest on {weak_dim}.")
