"""Crawlability & JS-render-gap checks (Round-2 appendix A + C).

Step 1 of visibility: the crawler must be *let in*. Step 2: it must be able to *read*
the page. If a fact only appears after client-side JavaScript runs, a fetch-only
retriever (how many AI assistants ingest pages) never sees it.
"""
from __future__ import annotations

import re
from typing import List

from ..context import AuditContext
from ..report import Finding
from .. import http as _http

# Crawlers used by AI assistants / answer engines. Blocking these directly removes
# the brand from those systems even if Googlebot is allowed.
AI_BOTS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",      # OpenAI
    "ClaudeBot", "Claude-Web", "anthropic-ai",       # Anthropic
    "PerplexityBot", "Perplexity-User",              # Perplexity
    "Google-Extended",                                # Gemini/Bard training & grounding
    "Applebot-Extended",                              # Apple Intelligence
    "CCBot",                                          # Common Crawl (feeds many models)
    "Bytespider", "Amazonbot", "cohere-ai", "Meta-ExternalAgent",
]

SPA_MARKERS = [
    (r'<div[^>]+id=["\'](root|app|__next|__nuxt)["\'][^>]*>\s*</div>', "empty app-root div"),
    (r"window\.__NUXT__", "Nuxt hydration payload"),
    (r"__NEXT_DATA__", "Next.js data island"),
    (r"ng-version=", "Angular app shell"),
    (r"data-reactroot", "React root without server markup"),
]


def analyze(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []
    findings += _robots_findings(ctx)
    findings += _status_findings(ctx)
    findings += _index_directive_findings(ctx)
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

    # Parse into user-agent groups.
    groups = _parse_robots_groups(raw)
    blocked_ai = []
    for bot in AI_BOTS:
        rules = groups.get(bot.lower())
        if rules and _blocks_root(rules):
            blocked_ai.append(bot)
    # Wildcard total block also blocks AI bots that fall through to '*'.
    star = groups.get("*")
    star_blocks_all = bool(star and _blocks_root(star))

    if blocked_ai:
        out.append(Finding(
            title="AI-assistant crawlers are blocked in robots.txt",
            severity="critical",
            dimension="discoverability",
            category="crawlability",
            evidence=f"robots.txt disallows these AI crawlers at site root: {', '.join(blocked_ai)}.",
            suggested_action_summary=(
                "Remove the Disallow rules for AI answer-engine crawlers "
                f"({', '.join(blocked_ai)}) so ChatGPT/Claude/Perplexity/Gemini can fetch "
                "and cite your pages. If you must gate training vs. grounding, allow the "
                "retrieval/search bots (OAI-SearchBot, ChatGPT-User, Perplexity-User) at minimum."),
            suggested_action_priority="critical",
            details={"blocked_bots": blocked_ai},
        ))
    if star_blocks_all:
        out.append(Finding(
            title="robots.txt disallows all crawlers at the site root",
            severity="critical",
            dimension="discoverability",
            category="crawlability",
            evidence="A `User-agent: *` group contains `Disallow: /`, blocking every compliant crawler.",
            suggested_action_summary=(
                "Scope Disallow rules to genuinely private paths instead of `/`. A blanket "
                "root disallow makes the site invisible to search and AI assistants alike."),
            suggested_action_priority="critical",
        ))
    return out


def _status_findings(ctx: AuditContext) -> List[Finding]:
    out: List[Finding] = []
    broken = [r for r in ctx.responses if not r.ok]
    blocked = [r for r in ctx.responses if r.error == "blocked_by_robots"]
    if blocked:
        out.append(Finding(
            title="Key pages are disallowed by robots.txt",
            severity="high",
            dimension="discoverability",
            category="crawlability",
            evidence=f"{len(blocked)} sampled page(s) blocked by robots rules, e.g. {blocked[0].url}.",
            suggested_action_summary="Confirm these paths should really be hidden; if they hold public brand content, allow them.",
            suggested_action_priority="high",
            affected_pages=[r.url for r in blocked],
        ))
    server_errs = [r for r in ctx.responses if r.status >= 500]
    if server_errs:
        out.append(Finding(
            title="Server errors on sampled pages",
            severity="high",
            dimension="discoverability",
            category="reachability",
            evidence=f"{len(server_errs)} sampled URL(s) returned 5xx, e.g. {server_errs[0].url} ({server_errs[0].status}).",
            suggested_action_summary="Fix the server errors; crawlers drop pages that fail to load and may deprioritize the host.",
            suggested_action_priority="high",
            affected_pages=[r.url for r in server_errs],
        ))
    return out


def _index_directive_findings(ctx: AuditContext) -> List[Finding]:
    out: List[Finding] = []
    noindex_pages = []
    for page, resp in zip(ctx.pages, ctx.responses):
        xrobots = (resp.headers.get("x-robots-tag", "") if resp else "").lower()
        meta = (page.meta_robots or "").lower()
        if "noindex" in meta or "noindex" in xrobots:
            noindex_pages.append(page.url)
    if noindex_pages:
        out.append(Finding(
            title="Pages carry noindex directives",
            severity="high",
            dimension="discoverability",
            category="indexability",
            evidence=f"{len(noindex_pages)} sampled page(s) set noindex (meta robots or X-Robots-Tag), e.g. {noindex_pages[0]}.",
            suggested_action_summary="Remove noindex from pages you want found and cited; keep it only on genuinely private/duplicate URLs.",
            suggested_action_priority="high",
            affected_pages=noindex_pages,
        ))
    return out


def _render_gap_findings(ctx: AuditContext) -> List[Finding]:
    """Dispatch the three JS-render-gap sub-checks (SPA shell, thin text, noscript)."""
    return _spa_findings(ctx) + _thin_findings(ctx) + _noscript_findings(ctx)


def _classify_render(ctx: AuditContext):
    """Split sampled pages into (spa_pages, thin_pages) per the configured thresholds."""
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
    """Flag pages whose primary content appears to require client-side JavaScript."""
    spa_pages, _ = _classify_render(ctx)
    out: List[Finding] = []
    if spa_pages:
        example = spa_pages[0]
        out.append(Finding(
            title="Primary content appears to require client-side JavaScript",
            severity="high",
            dimension="discoverability",
            category="js-render-gap",
            evidence=(
                f"{len(spa_pages)} sampled page(s) return an app shell with little server-rendered text "
                f"(e.g. {example[0]}: {example[2]} words, marker: {example[1]}). Fetch-only AI retrievers "
                "see the empty shell, not the content."),
            suggested_action_summary=(
                "Server-render or pre-render the primary content (SSR/SSG, dynamic rendering, or "
                "hydration with real HTML in the initial response) so the copy, headings, and key facts "
                "exist in the raw HTML before JavaScript runs."),
            suggested_action_priority="high",
            confidence="medium",
            affected_pages=[u for u, _, _ in spa_pages],
        ))
    return out


def _thin_findings(ctx: AuditContext) -> List[Finding]:
    """Flag pages with very little extractable text relative to their HTML size."""
    _, thin_pages = _classify_render(ctx)
    if not thin_pages:
        return []
    words = int(ctx.cfg.t("render_thin_words"))
    return [Finding(
        title="Thin server-rendered text relative to page size",
        severity="medium",
        dimension="discoverability",
        category="js-render-gap",
        evidence=f"{len(thin_pages)} page(s) have <{words} words of extractable text despite substantial HTML, e.g. {thin_pages[0]}.",
        suggested_action_summary="Ensure meaningful copy is present in the initial HTML, not injected later or hidden behind interactions.",
        suggested_action_priority="medium",
        confidence="medium",
        affected_pages=thin_pages,
    )]


def _noscript_findings(ctx: AuditContext) -> List[Finding]:
    """Flag pages that instruct users to enable JavaScript (strong client-render signal)."""
    noscript_pages = [p.url for p in ctx.pages
                      if re.search(r"<noscript[^>]*>\s*(you|enable|requires)?\s*javascript", p.raw_html, re.I)]
    if not noscript_pages:
        return []
    return [Finding(
        title="Pages tell users to enable JavaScript",
        severity="medium",
        dimension="discoverability",
        category="js-render-gap",
        evidence=f"A <noscript> 'enable JavaScript' notice appears on {len(noscript_pages)} page(s), a strong signal content is client-rendered.",
        suggested_action_summary="Provide the core content and navigation without requiring JavaScript execution.",
        suggested_action_priority="medium",
        confidence="medium",
        affected_pages=noscript_pages,
    )]


def _sitemap_findings(ctx: AuditContext) -> List[Finding]:
    origin = ctx.fetcher._origin(ctx.start_url)
    r = ctx.fetcher.fetch(origin + "/sitemap.xml")
    raw_robots = _robots_raw(ctx)
    declared = "sitemap:" in raw_robots.lower()
    if not r.ok and not declared:
        return [Finding(
            title="No XML sitemap found",
            severity="low",
            dimension="discoverability",
            category="crawlability",
            evidence="Neither /sitemap.xml nor a Sitemap: directive in robots.txt was found.",
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
    # True if the group disallows '/' (whole site) and doesn't re-allow it.
    disallow_root = any(f == "disallow" and v == "/" for f, v in rules)
    allow_root = any(f == "allow" and v == "/" for f, v in rules)
    return disallow_root and not allow_root
