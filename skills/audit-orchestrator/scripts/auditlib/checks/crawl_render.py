"""Crawlability & JS-render-gap checks (Round-2 appendix A + C).

Step 1 of visibility: the crawler must be *let in*. Step 2: it must be able to *read*
the page. If a fact only appears after client-side JavaScript runs, a fetch-only
retriever (how many AI assistants ingest pages) never sees it. This module also checks
canonical consistency, nofollow'd internal links, and (bounded) broken internal links.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from typing import List

from ..context import AuditContext
from ..report import Finding, scope_str
from .. import http as _http

# Crawlers used by AI assistants / answer engines, split by purpose so recommendations can be
# nuanced (retrieval bots matter most for citation; training bots are a separate policy choice).
AI_RETRIEVAL_BOTS = ["OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Perplexity-User"]
AI_TRAINING_BOTS = ["GPTBot", "ClaudeBot", "Claude-Web", "anthropic-ai", "Google-Extended",
                    "Applebot-Extended", "CCBot", "Bytespider", "cohere-ai", "Meta-ExternalAgent"]
AI_BOTS = AI_RETRIEVAL_BOTS + AI_TRAINING_BOTS + ["Amazonbot"]

SPA_MARKERS = [
    (r'<div[^>]+id=["\'](root|app|__next|__nuxt)["\'][^>]*>\s*</div>', "empty app-root div"),
    (r"window\.__NUXT__", "Nuxt hydration payload"),
    (r"__NEXT_DATA__", "Next.js data island"),
    (r"ng-version=", "Angular app shell"),
    (r"data-reactroot", "React root without server markup"),
]
MAX_LINK_CHECKS = 6       # bounded broken-link probing to stay well within the time budget
LINK_PROBE_BUDGET_S = 20  # hard wall-clock cap for probing, so slow hosts can't blow the budget


def analyze(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []
    findings += _robots_findings(ctx)
    findings += _status_findings(ctx)
    findings += _index_directive_findings(ctx)
    findings += _canonical_findings(ctx)
    findings += _hreflang_findings(ctx)
    findings += _nofollow_findings(ctx)
    findings += _broken_link_findings(ctx)
    findings += _render_gap_findings(ctx)
    findings += _sitemap_findings(ctx)
    return findings


def _robots_raw(ctx: AuditContext) -> str:
    origin = ctx.fetcher._origin(ctx.start_url)
    r = ctx.fetcher.fetch(origin + "/robots.txt")
    return r.body if r.ok else ""


def _robots_findings(ctx: AuditContext) -> List[Finding]:
    out: List[Finding] = []
    raw = _robots_raw(ctx)
    if not raw.strip():
        return out  # absence of robots.txt is permissive; not a defect by itself

    groups = _parse_robots_groups(raw)
    blocked_retrieval, blocked_training = [], []
    for bot in AI_BOTS:
        rules = groups.get(bot.lower())
        if rules and _blocks_root(rules):
            (blocked_retrieval if bot in AI_RETRIEVAL_BOTS else blocked_training).append(bot)
    star = groups.get("*")
    star_blocks_all = bool(star and _blocks_root(star))

    if blocked_retrieval:
        out.append(Finding(
            title="AI answer-engine retrieval crawlers are blocked in robots.txt",
            severity="critical", dimension="discoverability", category="crawlability",
            evidence=f"robots.txt disallows these retrieval/citation crawlers at site root: {', '.join(blocked_retrieval)}.",
            why="Retrieval/search bots are what fetch a page at answer time to cite it; blocking them removes "
                "the brand from ChatGPT/Perplexity-style answers even if it ranks well in classic search.",
            how_to_fix=("Remove the Disallow: / rules for the retrieval crawlers "
                        f"({', '.join(blocked_retrieval)}); scope any Disallow to genuinely private paths."),
            measurements={"blocked_retrieval_bots": blocked_retrieval},
            details={"blocked_bots": blocked_retrieval},
            expected_impact="Restores eligibility to be fetched and cited in answer engines.",
            suggested_action_summary=("Allow the AI retrieval/search crawlers at minimum "
                                      f"({', '.join(blocked_retrieval)}) so answer engines can fetch and cite your pages."),
            suggested_action_priority="critical",
        ))
    if blocked_training:
        out.append(Finding(
            title="AI training crawlers are blocked in robots.txt",
            severity="low", dimension="discoverability", category="crawlability", confidence="high",
            evidence=f"robots.txt disallows these AI training crawlers at site root: {', '.join(blocked_training)}.",
            why="Blocking training crawlers keeps content out of future model training. This is a legitimate "
                "policy choice for many brands — it is only flagged so the decision is explicit, not accidental.",
            how_to_fix="If exclusion from model training is intended, keep these rules. If you want the brand to be "
                       "learned and represented, allow them — but the retrieval bots matter more for live citation.",
            measurements={"blocked_training_bots": blocked_training},
            suggested_action_summary="Confirm blocking AI training crawlers is intentional; if you want the brand represented in models, allow them. Retrieval bots matter more for live citation.",
            suggested_action_priority="low",
        ))
    if star_blocks_all:
        out.append(Finding(
            title="robots.txt disallows all crawlers at the site root",
            severity="critical", dimension="discoverability", category="crawlability",
            evidence="A `User-agent: *` group contains `Disallow: /`, blocking every compliant crawler.",
            why="A blanket root disallow makes the whole site invisible to search engines and AI assistants "
                "alike — nothing can be fetched, indexed, or cited.",
            how_to_fix="Scope Disallow rules to genuinely private paths (e.g. /admin, /cart) instead of `/`.",
            suggested_action_summary="Scope Disallow rules to genuinely private paths instead of `/`. A blanket root disallow makes the site invisible to search and AI assistants alike.",
            suggested_action_priority="critical",
        ))
    return out


def _status_findings(ctx: AuditContext) -> List[Finding]:
    out: List[Finding] = []
    blocked = [r for r in ctx.responses if r.error == "blocked_by_robots"]
    if blocked:
        out.append(Finding(
            title="Key pages are disallowed by robots.txt",
            severity="high", dimension="discoverability", category="crawlability",
            evidence=f"{len(blocked)} sampled page(s) blocked by robots rules, e.g. {blocked[0].url}.",
            why="A disallowed page cannot be fetched by any compliant crawler, so its content can never be indexed or cited.",
            how_to_fix="Confirm these paths should be hidden; if they hold public brand content, remove the Disallow rule covering them.",
            measurements={"robots_blocked_pages": len(blocked)},
            suggested_action_summary="Confirm these paths should really be hidden; if they hold public brand content, allow them.",
            suggested_action_priority="high", affected_pages=[r.url for r in blocked],
        ))
    server_errs = [r for r in ctx.responses if r.status >= 500]
    if server_errs:
        out.append(Finding(
            title="Server errors on sampled pages",
            severity="high", dimension="discoverability", category="reachability",
            evidence=f"{len(server_errs)} sampled URL(s) returned 5xx, e.g. {server_errs[0].url} ({server_errs[0].status}).",
            why="Crawlers drop pages that fail to load and, after repeated failures, may deprioritize the whole host.",
            how_to_fix="Investigate and fix the 5xx responses (application errors, timeouts, capacity); confirm they return 200 for crawlers.",
            measurements={"server_error_pages": len(server_errs)},
            suggested_action_summary="Fix the server errors; crawlers drop pages that fail to load and may deprioritize the host.",
            suggested_action_priority="high", affected_pages=[r.url for r in server_errs],
        ))
    return out


def _index_directive_findings(ctx: AuditContext) -> List[Finding]:
    noindex_pages = []
    for page, resp in zip(ctx.pages, ctx.responses):
        xrobots = (resp.headers.get("x-robots-tag", "") if resp else "").lower()
        meta = (page.meta_robots or "").lower()
        if "noindex" in meta or "noindex" in xrobots:
            noindex_pages.append(page.url)
    if not noindex_pages:
        return []
    return [Finding(
        title="Pages carry noindex directives",
        severity="high", dimension="discoverability", category="indexability",
        evidence=f"{scope_str(len(noindex_pages), len(ctx.pages))} set noindex (meta robots or X-Robots-Tag), e.g. {noindex_pages[0]}.",
        why="A noindexed page is deliberately excluded from search results and answers even though a crawler can read it, "
            "so any public content on it is invisible to discovery.",
        how_to_fix="Remove noindex from pages you want found and cited; keep it only on genuinely private or duplicate URLs.",
        scope=scope_str(len(noindex_pages), len(ctx.pages)),
        measurements={"noindex_pages": len(noindex_pages)},
        suggested_action_summary="Remove noindex from pages you want found and cited; keep it only on genuinely private/duplicate URLs.",
        suggested_action_priority="high", affected_pages=noindex_pages,
    )]


def _canonical_findings(ctx: AuditContext) -> List[Finding]:
    """Flag canonical tags that point to a different host (a real consolidation conflict)."""
    conflicts = []
    for p in ctx.pages:
        can = (p.canonical or "").strip()
        if not can:
            continue
        try:
            if _http.same_host(can, p.url):
                continue
            # cross-host canonical is the clear, defensible signal (not mere path differences)
            if urllib.parse.urlsplit(can).netloc and not _http.same_registrable_domain(can, p.url):
                conflicts.append((p.url, can))
        except Exception:
            continue
    if not conflicts:
        return []
    u, can = conflicts[0]
    return [Finding(
        title="Canonical tags point to a different domain",
        severity="medium", dimension="discoverability", category="indexability",
        evidence=f"{len(conflicts)} page(s) declare a canonical on another domain, e.g. {u} → {can}.",
        why="A cross-domain canonical tells search engines to credit and index the other domain instead of this one, "
            "so this site's version may be dropped from results and answers.",
        how_to_fix="Point rel=canonical at the preferred URL on this domain (self-referential unless you truly intend to consolidate elsewhere).",
        measurements={"cross_domain_canonical_pages": len(conflicts)},
        details={"examples": [{"page": pu, "canonical": pc} for pu, pc in conflicts[:5]]},
        suggested_action_summary="Set self-referential canonicals on this domain unless consolidation to another domain is truly intended.",
        suggested_action_priority="medium", confidence="high",
        affected_pages=[pu for pu, _ in conflicts],
    )]


_ALT_LINK_RE = re.compile(r'<link\b[^>]*\brel=["\']?alternate["\']?[^>]*>', re.I)
_HREFLANG_RE = re.compile(r'hreflang=["\']([^"\']+)["\']', re.I)
_ALT_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_LANG_CODE_RE = re.compile(r'^[a-z]{2,3}(-[a-z]{4})?(-[a-z]{2}|-\d{3})?$', re.I)


def _alternates(page) -> List[tuple]:
    """Extract (hreflang, href) pairs from a page's <link rel=alternate hreflang=…> tags."""
    out = []
    for tag in _ALT_LINK_RE.findall(page.raw_html):
        m = _HREFLANG_RE.search(tag)
        h = _ALT_HREF_RE.search(tag)
        if m and h:
            out.append((m.group(1).strip(), h.group(1).strip()))
    return out


def _hreflang_findings(ctx: AuditContext) -> List[Finding]:
    """International-targeting checks — only when the site actually uses hreflang / multiple langs.

    A single-language site legitimately has no hreflang, so nothing is flagged there (no false
    positives). When hreflang IS used, check for the common, high-confidence mistakes: no
    x-default, malformed language codes, and missing reciprocal (return) links within the sample.
    """
    alts_by_page = {p.url: _alternates(p) for p in ctx.pages}
    langs = {(p.lang or "").split("-")[0].lower() for p in ctx.pages if p.lang}
    used = any(alts_by_page.values())
    if not used and len(langs) < 2:
        return []  # not an international site — hreflang is not applicable
    if not used:
        return []  # multiple langs but no hreflang is a broader content-strategy call; don't over-flag

    out: List[Finding] = []
    total = sum(1 for a in alts_by_page.values() if a)
    # 1) x-default missing
    no_xdefault = [u for u, a in alts_by_page.items()
                   if a and not any(hl.lower() == "x-default" for hl, _ in a)]
    if no_xdefault:
        out.append(Finding(
            title="hreflang set without an x-default",
            severity="low", dimension="discoverability", category="indexability", confidence="high",
            evidence=f"{scope_str(len(no_xdefault), total)} using hreflang declare no x-default, e.g. {no_xdefault[0]}.",
            why="Without an x-default, search/answer engines have no fallback for languages you don't explicitly "
                "target, so unmatched visitors may be sent to the wrong-language page.",
            how_to_fix='Add <link rel="alternate" hreflang="x-default" href="…"> pointing at your default/'
                       "language-selector page, alongside the per-language alternates.",
            scope=scope_str(len(no_xdefault), total),
            measurements={"pages_using_hreflang": total, "missing_x_default": len(no_xdefault)},
            suggested_action_summary='Add an hreflang="x-default" alternate on internationalized pages.',
            suggested_action_priority="low", affected_pages=no_xdefault,
        ))
    # 2) malformed language codes
    malformed = []
    for u, a in alts_by_page.items():
        for hl, _ in a:
            if hl.lower() != "x-default" and not _LANG_CODE_RE.match(hl):
                malformed.append((u, hl))
    if malformed:
        u, hl = malformed[0]
        out.append(Finding(
            title="Invalid hreflang language codes",
            severity="low", dimension="discoverability", category="indexability", confidence="high",
            evidence=f"{len(malformed)} hreflang value(s) aren't valid language/region codes, e.g. \"{hl}\" on {u}.",
            why="An unrecognized hreflang code is ignored, so that language variant isn't connected to its "
                "siblings and can be treated as duplicate content.",
            how_to_fix="Use valid ISO codes: language (en), or language-region (en-GB, pt-BR) — not country-only or made-up codes.",
            measurements={"invalid_hreflang_values": len(malformed)},
            suggested_action_summary="Correct hreflang values to valid ISO language / language-region codes.",
            suggested_action_priority="low", affected_pages=[m[0] for m in malformed],
        ))
    # 3) non-reciprocal (return-link) gaps within the crawled sample
    gaps = []
    for u, a in alts_by_page.items():
        for hl, href in a:
            if hl.lower() == "x-default":
                continue
            target = _http.normalize(href, base=u)
            if target and target in alts_by_page and alts_by_page[target]:
                back = any(_http.normalize(h2, base=target) == u for _, h2 in alts_by_page[target])
                if not back:
                    gaps.append((u, target))
    if gaps:
        u, t = gaps[0]
        out.append(Finding(
            title="hreflang links are not reciprocal",
            severity="medium", dimension="discoverability", category="indexability", confidence="medium",
            evidence=f"{len(gaps)} hreflang alternate(s) are not confirmed back within the sample, e.g. {u} → {t} with no return link.",
            why="hreflang must be reciprocal — if A points to B, B must point back to A. Non-reciprocal annotations "
                "are ignored, so the language cluster isn't consolidated.",
            how_to_fix="Ensure every page in a language set lists hreflang alternates for all the others, including itself.",
            measurements={"non_reciprocal_pairs": len(gaps)},
            suggested_action_summary="Make hreflang annotations reciprocal across the whole language set.",
            suggested_action_priority="medium", affected_pages=[g[0] for g in gaps],
        ))
    return out


def _nofollow_findings(ctx: AuditContext) -> List[Finding]:
    """Flag a homepage that nofollows a large share of its own internal links."""
    home = ctx.pages[0]
    internal = [a for a in home.links if _is_internal(a.get("href", ""), home.url)]
    nofollowed = [a for a in internal if "nofollow" in (a.get("rel", "") or "").lower()]
    if len(internal) >= 5 and len(nofollowed) >= max(3, int(0.3 * len(internal))):
        return [Finding(
            title="Internal links are marked rel=nofollow",
            severity="low", dimension="discoverability", category="crawlability",
            evidence=f"{len(nofollowed)} of {len(internal)} internal homepage links carry rel=nofollow.",
            why="nofollow tells crawlers not to follow the link, so nofollowing your own internal links wastes crawl "
                "signal and can leave linked pages under-discovered.",
            how_to_fix="Remove rel=nofollow from internal navigation links; reserve nofollow for untrusted/user-generated outbound links.",
            measurements={"internal_links": len(internal), "nofollowed": len(nofollowed)},
            suggested_action_summary="Remove rel=nofollow from internal links so crawlers follow your own navigation.",
            suggested_action_priority="low", confidence="medium",
        )]
    return []


def _broken_link_findings(ctx: AuditContext) -> List[Finding]:
    """Bounded probe of a few internal links from the homepage for 4xx/5xx responses."""
    home_resp = ctx.responses[0] if ctx.responses else None
    if not home_resp or not home_resp.ok:
        return []
    crawled = {r.final_url or r.url for r in ctx.responses}
    in_scope = _http.scope_predicate(getattr(ctx.cfg, "crawl_scope", "host"))
    candidates = []
    for a in ctx.pages[0].links:
        n = _http.normalize(a.get("href", ""), base=home_resp.final_url or ctx.start_url)
        if not n or n in crawled or n in candidates:
            continue
        if not in_scope(n, home_resp.final_url or ctx.start_url):
            continue
        if re.search(r"\.(png|jpe?g|gif|svg|webp|css|js|ico|pdf|zip|mp4|woff2?)(\?|$)", n, re.I):
            continue
        candidates.append(n)
    broken, probed = [], 0
    deadline = time.monotonic() + LINK_PROBE_BUDGET_S
    for n in sorted(candidates)[:MAX_LINK_CHECKS]:
        if time.monotonic() > deadline:
            break  # respect the wall-clock budget on slow hosts
        probed += 1
        try:
            r = ctx.fetcher.fetch(n)
        except Exception:
            continue
        # Only a definitive HTTP error status is "broken". A timeout / DNS / connection error
        # (status 0) is NOT proof the link is broken — the host may be slow or bot-protected —
        # so we never report those as broken (avoids false positives on real e-commerce sites).
        if isinstance(r.status, int) and r.status >= 400:
            broken.append((n, r.status))
    if not broken:
        return []
    u, st = broken[0]
    return [Finding(
        title="Broken internal links found",
        severity="medium", dimension="discoverability", category="reachability",
        evidence=f"{len(broken)} of {probed} probed internal link(s) failed, e.g. {u} ({st}).",
        why="Broken internal links dead-end both visitors and crawlers, wasting crawl budget and stranding any content behind them.",
        how_to_fix="Fix or redirect the broken targets, and update the links that point to them.",
        measurements={"broken_links": len(broken), "links_probed": probed},
        details={"examples": [{"url": bu, "status": str(bs)} for bu, bs in broken[:5]]},
        suggested_action_summary="Repair or 301-redirect broken internal link targets and update the referring links.",
        suggested_action_priority="medium", confidence="high",
        affected_pages=[bu for bu, _ in broken],
    )]


def _render_gap_findings(ctx: AuditContext) -> List[Finding]:
    return _spa_findings(ctx) + _thin_findings(ctx) + _noscript_findings(ctx)


def _classify_render(ctx: AuditContext):
    t = ctx.cfg.t
    spa_pages, thin_pages = [], []
    for page in ctx.pages:
        marker_hit = next((label for pat, label in SPA_MARKERS if re.search(pat, page.raw_html, re.I)), None)
        script_bytes = page.inline_script_bytes + 200 * len(page.scripts_src)
        heavy_script = script_bytes > t("render_script_ratio") * max(page.visible_text_len, 1)
        if page.word_count < t("render_spa_max_words") and (marker_hit or heavy_script):
            if marker_hit or page.word_count < t("render_spa_hard_max_words"):
                spa_pages.append((page.url, marker_hit or "script-heavy shell", page.word_count))
        elif page.word_count < t("render_thin_words") and page.html_len > t("render_thin_html"):
            thin_pages.append(page.url)
    return spa_pages, thin_pages


def _spa_findings(ctx: AuditContext) -> List[Finding]:
    spa_pages, _ = _classify_render(ctx)
    if not spa_pages:
        return []
    ex = spa_pages[0]
    return [Finding(
        title="Primary content appears to require client-side JavaScript",
        severity="high", dimension="discoverability", category="js-render-gap",
        evidence=(f"{scope_str(len(spa_pages), len(ctx.pages))} return an app shell with little server-rendered text "
                  f"(e.g. {ex[0]}: {ex[2]} words, marker: {ex[1]})."),
        why="Fetch-only AI retrievers (which don't execute JavaScript) see the empty shell, not the content, so the "
            "page's facts are invisible to them even though a human browser renders them fine.",
        how_to_fix="Server-render or pre-render the primary content (SSR/SSG, dynamic rendering, or hydration with real "
                   "HTML in the initial response) so copy, headings, and key facts exist in the raw HTML before JS runs.",
        scope=scope_str(len(spa_pages), len(ctx.pages)),
        measurements={"spa_shell_pages": len(spa_pages)},
        suggested_action_summary=(
            "Server-render or pre-render the primary content (SSR/SSG, dynamic rendering, or "
            "hydration with real HTML in the initial response) so the copy, headings, and key facts "
            "exist in the raw HTML before JavaScript runs."),
        suggested_action_priority="high", confidence="medium",
        affected_pages=[u for u, _, _ in spa_pages],
    )]


def _thin_findings(ctx: AuditContext) -> List[Finding]:
    _, thin_pages = _classify_render(ctx)
    if not thin_pages:
        return []
    words = int(ctx.cfg.t("render_thin_words"))
    return [Finding(
        title="Thin server-rendered text relative to page size",
        severity="medium", dimension="discoverability", category="js-render-gap",
        evidence=f"{scope_str(len(thin_pages), len(ctx.pages))} have <{words} words of extractable text despite substantial HTML, e.g. {thin_pages[0]}.",
        why="A large HTML document with very little readable text usually means the real content is injected later by "
            "JavaScript or hidden behind interactions, leaving fetch-only retrievers with almost nothing to read.",
        how_to_fix="Ensure meaningful copy is present in the initial HTML, not injected after load or hidden behind clicks.",
        scope=scope_str(len(thin_pages), len(ctx.pages)),
        measurements={"thin_pages": len(thin_pages), "word_threshold": words},
        suggested_action_summary="Ensure meaningful copy is present in the initial HTML, not injected later or hidden behind interactions.",
        suggested_action_priority="medium", confidence="medium", affected_pages=thin_pages,
    )]


def _noscript_findings(ctx: AuditContext) -> List[Finding]:
    noscript_pages = [p.url for p in ctx.pages
                      if re.search(r"<noscript[^>]*>\s*(you|enable|requires)?\s*javascript", p.raw_html, re.I)]
    if not noscript_pages:
        return []
    return [Finding(
        title="Pages tell users to enable JavaScript",
        severity="medium", dimension="discoverability", category="js-render-gap",
        evidence=f"A <noscript> 'enable JavaScript' notice appears on {scope_str(len(noscript_pages), len(ctx.pages))}.",
        why="An 'enable JavaScript' notice is a strong signal the core content is client-rendered, so a fetch-only "
            "retriever receives the notice instead of the content.",
        how_to_fix="Provide the core content and navigation in server-rendered HTML that works without JavaScript.",
        scope=scope_str(len(noscript_pages), len(ctx.pages)),
        measurements={"noscript_pages": len(noscript_pages)},
        suggested_action_summary="Provide the core content and navigation without requiring JavaScript execution.",
        suggested_action_priority="medium", confidence="medium", affected_pages=noscript_pages,
    )]


def _sitemap_findings(ctx: AuditContext) -> List[Finding]:
    origin = ctx.fetcher._origin(ctx.start_url)
    r = ctx.fetcher.fetch(origin + "/sitemap.xml")
    raw_robots = _robots_raw(ctx)
    declared = "sitemap:" in raw_robots.lower()
    if not r.ok and not declared:
        return [Finding(
            title="No XML sitemap found",
            severity="low", dimension="discoverability", category="crawlability",
            evidence="Neither /sitemap.xml nor a Sitemap: directive in robots.txt was found.",
            why="Without a sitemap, crawlers rely solely on link discovery, so deep or poorly-linked pages may be found "
                "late or missed — slowing how quickly new content becomes citable.",
            how_to_fix="Publish an XML sitemap of canonical URLs and reference it from robots.txt (Sitemap: <url>).",
            suggested_action_summary="Publish an XML sitemap and reference it from robots.txt so crawlers discover all key pages efficiently.",
            suggested_action_priority="low",
        )]
    return []


# --- robots.txt mini-parser -------------------------------------------------------
def _parse_robots_groups(raw: str) -> dict:
    groups: dict = {}
    current_agents: List[str] = []
    pending_agent_block = False
    for line in raw.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if not pending_agent_block:
                current_agents = []
            current_agents.append(value.lower())
            groups.setdefault(value.lower(), [])
            pending_agent_block = True
        elif field in ("allow", "disallow"):
            pending_agent_block = False
            for a in current_agents:
                groups.setdefault(a, []).append((field, value))
    return groups


def _blocks_root(rules: List[tuple]) -> bool:
    disallow_root = any(f == "disallow" and v == "/" for f, v in rules)
    allow_root = any(f == "allow" and v == "/" for f, v in rules)
    return disallow_root and not allow_root


def _is_internal(href: str, base: str) -> bool:
    if href.startswith(("/", "#")):
        return True
    try:
        return _http.same_registrable_domain(href, base)
    except Exception:
        return False
