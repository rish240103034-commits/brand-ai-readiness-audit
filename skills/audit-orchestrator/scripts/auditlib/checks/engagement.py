"""On-site engagement checks — the 'keep the visitor once they arrive' half.

Discoverability gets a visitor to the page; engagement decides whether they stay. Poor
mobile rendering, no clear next action, weak orientation, heavy/slow or render-blocked pages,
login walls, dead-end navigation, and non-descriptive links all drive the bounce that Round 2
asked about. These are read from static markup and timing — mechanism-sound proxies, reported
with honest confidence, each with a specific ``why`` and ``how_to_fix``.
"""
from __future__ import annotations

import re
from typing import List

from ..context import AuditContext
from ..report import Finding, scope_str
from ..htmlparse import Page

CTA_RE = re.compile(
    r"\b(buy|shop|get started|sign up|sign-up|subscribe|contact|book|"
    r"request|demo|start free|add to cart|learn more|download|try)\b", re.I)
# Language-neutral CTA signals so non-English sites aren't falsely flagged for lacking
# English CTA words: links to conversion paths, and elements explicitly marked as CTAs.
CTA_HREF_RE = re.compile(
    r"(?:^|/)(cart|checkout|contact|sign[-_]?up|signup|log[-_]?in|register|buy|order|"
    r"subscribe|book|booking|demo|pricing|price|get[-_]?started|quote|apply|appointment|"
    r"donate|shop|store|enquir|inquir|reserve|join)(?:/|$|\?)|^(?:tel:|mailto:|https?://wa\.me/)",
    re.I)
CTA_CLASS_RE = re.compile(r'\bclass\s*=\s*["\'][^"\']*\b(cta|btn|button|add-to-cart|buy-now)\b', re.I)
NAV_RE = re.compile(r"<nav[\s>]|role=[\"']navigation[\"']", re.I)
BREADCRUMB_RE = re.compile(r"breadcrumb|BreadcrumbList", re.I)
POPUP_RE = re.compile(r"(newsletter|subscribe|cookie).{0,40}(modal|popup|overlay|interstitial)|"
                      r"(modal|popup|overlay|interstitial).{0,40}(newsletter|subscribe)", re.I)
BUTTON_RE = re.compile(r"<button[\s>]|type=[\"']submit[\"']", re.I)
GATING_RE = re.compile(
    r"(sign ?in|log ?in|register|create an account|subscribe)\s+(to|and)\s+"
    r"(continue|read|view|access|see|unlock)|members only|subscribers only", re.I)
GENERIC_LINK_RE = re.compile(r"^\s*(click here|read more|learn more|more|here|link|this|details)\s*$", re.I)


def analyze(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []
    pages = ctx.pages
    if not pages:
        return findings

    findings += _viewport(pages, ctx.cfg)
    findings += _primary_cta(ctx)
    findings += _navigation(pages, ctx.cfg)
    findings += _page_weight(ctx)
    findings += _render_blocking(ctx)
    findings += _readability(pages, ctx.cfg)
    findings += _orientation(pages, ctx.cfg)
    findings += _intrusive(pages)
    findings += _login_barrier(pages, ctx.cfg)
    findings += _link_quality(pages, ctx.cfg)
    return findings


def _viewport(pages: List[Page], cfg) -> List[Finding]:
    no_vp = [p.url for p in pages if not p.meta.get("viewport", "").strip()]
    if no_vp and len(no_vp) >= max(1, int(len(pages) * cfg.t("viewport_min_fraction"))):
        return [Finding(
            title="No responsive viewport meta tag",
            severity="high", dimension="engagement", category="mobile",
            evidence=f"{scope_str(len(no_vp), len(pages))} omit <meta name=\"viewport\">, so mobile browsers render a zoomed-out desktop layout.",
            why="Without a viewport tag mobile browsers show a shrunken desktop layout that is hard to read and tap, "
                "so mobile visitors bounce before engaging.",
            how_to_fix="Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> and verify a responsive layout.",
            scope=scope_str(len(no_vp), len(pages)),
            measurements={"pages_without_viewport": len(no_vp), "pages": len(pages)},
            suggested_action_summary="Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> and verify a responsive layout; mobile visitors bounce fast from unreadable pages.",
            suggested_action_priority="high", affected_pages=no_vp,
        )]
    return []


def _primary_cta(ctx: AuditContext) -> List[Finding]:
    home = ctx.pages[0]
    link_text = " ".join(a.get("text", "") for a in home.links)
    link_hrefs = " ".join(a.get("href", "") for a in home.links)
    has_cta = bool(
        CTA_RE.search(link_text) or CTA_RE.search(_button_text(home))
        or CTA_HREF_RE.search(link_hrefs)
        or CTA_CLASS_RE.search(home.raw_html))
    if not has_cta:
        return [Finding(
            title="Homepage has no clear call-to-action",
            severity="medium", dimension="engagement", category="conversion",
            evidence=f"No action-oriented link, button, or conversion-path link (cart/contact/sign-up/book/demo…) was found among the homepage's {len(home.links)} links.",
            why="With no obvious next step, visitors who arrive don't know what to do and leave without converting.",
            how_to_fix="Add one prominent, unambiguous primary CTA above the fold naming the single most valuable next step.",
            measurements={"homepage_links": len(home.links)},
            suggested_action_summary="Add one prominent, unambiguous primary CTA above the fold that tells the visitor the single most valuable next step.",
            suggested_action_priority="medium", confidence="medium",
        )]
    return []


def _navigation(pages: List[Page], cfg) -> List[Finding]:
    no_nav = [p.url for p in pages if not NAV_RE.search(p.raw_html)]
    thin_links = [p.url for p in pages if len(_internal(p)) < cfg.t("deadend_min_links")]
    out: List[Finding] = []
    if no_nav and len(no_nav) == len(pages):
        out.append(Finding(
            title="No semantic navigation region",
            severity="medium", dimension="engagement", category="orientation",
            evidence="No sampled page exposes a <nav> element or role=\"navigation\".",
            why="Without a semantic nav region, both visitors and assistive tech/machines struggle to find the menu, "
                "so people can't orient or move deeper and tend to bounce.",
            how_to_fix="Wrap the primary menu in a <nav> (or role=\"navigation\") with descriptive links.",
            measurements={"pages_without_nav": len(no_nav), "pages": len(pages)},
            suggested_action_summary="Wrap the primary menu in a <nav> with descriptive links so visitors can orient and move deeper instead of bouncing.",
            suggested_action_priority="medium",
        ))
    if thin_links:
        out.append(Finding(
            title="Dead-end pages with few onward links",
            severity="low", dimension="engagement", category="orientation",
            evidence=f"{scope_str(len(thin_links), len(pages))} offer fewer than {int(cfg.t('deadend_min_links'))} internal links, e.g. {thin_links[0]}.",
            why="A page with almost no onward links strands the visitor with nowhere relevant to go next, ending the visit early.",
            how_to_fix="Add contextual links (related pages, next steps, related products/articles) so each page leads somewhere relevant.",
            scope=scope_str(len(thin_links), len(pages)),
            measurements={"dead_end_pages": len(thin_links)},
            suggested_action_summary="Add contextual links (related pages, next steps, related products/articles) so each page leads somewhere relevant.",
            suggested_action_priority="low", affected_pages=thin_links,
        ))
    return out


def _page_weight(ctx: AuditContext) -> List[Finding]:
    heavy, slow = [], []
    max_bytes = ctx.cfg.t("page_weight_bytes")
    max_scripts = ctx.cfg.t("page_weight_scripts")
    slow_ms = ctx.cfg.t("slow_ms")
    for p, r in zip(ctx.pages, ctx.responses):
        if r.raw_len > max_bytes or len(p.scripts_src) > max_scripts:
            heavy.append((p.url, r.raw_len, len(p.scripts_src)))
        if r.elapsed_ms > slow_ms:
            slow.append((p.url, r.elapsed_ms))
    out: List[Finding] = []
    if heavy:
        w = max(heavy, key=lambda x: x[1])
        out.append(Finding(
            title="Heavy pages likely to slow first render",
            severity="medium", dimension="engagement", category="performance",
            evidence=f"{scope_str(len(heavy), len(ctx.pages))} are large or script-dense (e.g. {w[0]}: {w[1]//1024} KB HTML, {w[2]} external scripts).",
            why="Large documents and many scripts delay interactivity; every added second before content appears measurably raises bounce.",
            how_to_fix="Trim and defer non-critical scripts, split bundles, and lazy-load below-the-fold assets to cut time-to-content.",
            scope=scope_str(len(heavy), len(ctx.pages)),
            measurements={"heavy_pages": len(heavy), "max_html_kb": w[1] // 1024, "max_scripts": w[2]},
            suggested_action_summary="Trim and defer non-critical scripts, split bundles, and lazy-load below-the-fold assets to cut time-to-content.",
            suggested_action_priority="medium", confidence="medium", affected_pages=[u for u, _, _ in heavy],
        ))
    if slow:
        s = max(slow, key=lambda x: x[1])
        out.append(Finding(
            title="Slow server response on sampled pages",
            severity="medium", dimension="engagement", category="performance",
            evidence=f"{scope_str(len(slow), len(ctx.pages))} took over {int(slow_ms/1000)}s to return HTML (e.g. {s[0]}: {s[1]} ms).",
            why="A slow first byte (TTFB) delays everything downstream, so the page starts rendering late and visitors abandon before it appears.",
            how_to_fix="Investigate TTFB — add caching/CDN, reduce per-request server work, and warm slow endpoints.",
            scope=scope_str(len(slow), len(ctx.pages)),
            measurements={"slow_pages": len(slow), "worst_ms": s[1], "threshold_ms": int(slow_ms)},
            suggested_action_summary="Investigate TTFB (caching, CDN, server work) so pages start rendering quickly; each added second measurably increases abandonment.",
            suggested_action_priority="medium", confidence="medium", affected_pages=[u for u, _ in slow],
        ))
    return out


def _render_blocking(ctx: AuditContext) -> List[Finding]:
    """Flag pages whose <head> loads many blocking stylesheets/scripts before first paint."""
    limit = ctx.cfg.t("render_blocking_head_max")
    blocked = []
    for p in ctx.pages:
        head = re.search(r"<head[^>]*>(.*?)</head>", p.raw_html, re.S | re.I)
        h = head.group(1) if head else p.raw_html[:4000]
        css = len(re.findall(r"<link[^>]+rel=[\"']stylesheet[\"']", h, re.I))
        blocking_js = len([m for m in re.findall(r"<script\b([^>]*)>", h, re.I)
                           if "src=" in m.lower() and "async" not in m.lower() and "defer" not in m.lower()])
        if css + blocking_js > limit:
            blocked.append((p.url, css, blocking_js))
    if not blocked:
        return []
    w = max(blocked, key=lambda x: x[1] + x[2])
    return [Finding(
        title="Render-blocking resources in the page head",
        severity="low", dimension="engagement", category="performance",
        evidence=f"{scope_str(len(blocked), len(ctx.pages))} load many blocking resources before first paint (e.g. {w[0]}: {w[1]} stylesheets + {w[2]} blocking scripts in <head>).",
        why="Synchronous CSS and non-deferred scripts in the head block the first paint, so the visitor stares at a blank screen longer and is more likely to leave.",
        how_to_fix="Inline critical CSS and defer the rest; add async/defer to head scripts or move them before </body>.",
        scope=scope_str(len(blocked), len(ctx.pages)),
        measurements={"render_blocked_pages": len(blocked), "worst_css": w[1], "worst_blocking_js": w[2], "threshold": int(limit)},
        suggested_action_summary="Inline critical CSS, defer non-critical CSS, and add async/defer to head scripts to speed first paint.",
        suggested_action_priority="low", confidence="medium", affected_pages=[u for u, _, _ in blocked],
    )]


def _readability(pages: List[Page], cfg) -> List[Finding]:
    walls = []
    min_words = cfg.t("wall_words")
    max_headings = cfg.t("wall_max_headings")
    for p in pages:
        if p.word_count > min_words and len(p.headings) <= max_headings:
            walls.append(p.url)
    if walls:
        return [Finding(
            title="Long content with almost no subheadings",
            severity="low", dimension="engagement", category="readability",
            evidence=f"{scope_str(len(walls), len(pages))} have {int(min_words)}+ words but ≤{int(max_headings)} heading(s), e.g. {walls[0]}.",
            why="An unbroken wall of text is hard to scan, so visitors skim and abandon instead of reading — and machines struggle to segment it into topics.",
            how_to_fix="Break long copy into scannable sections with descriptive H2/H3 headings, short paragraphs, and lists.",
            scope=scope_str(len(walls), len(pages)),
            measurements={"wall_pages": len(walls), "word_threshold": int(min_words)},
            suggested_action_summary="Break long copy into scannable sections with descriptive H2/H3 headings, short paragraphs, and lists.",
            suggested_action_priority="low", affected_pages=walls,
        )]
    return []


def _orientation(pages: List[Page], cfg) -> List[Finding]:
    seg = cfg.t("deep_path_segments")
    deep = [p for p in pages if p.url.rstrip("/").count("/") > seg]
    if len(deep) >= cfg.t("deep_min_pages"):
        no_crumb = [p.url for p in deep if not BREADCRUMB_RE.search(p.raw_html)]
        if len(no_crumb) == len(deep):
            return [Finding(
                title="Deep pages lack breadcrumbs / positional context",
                severity="low", dimension="engagement", category="orientation",
                evidence=f"{scope_str(len(no_crumb), len(deep))} deep page(s) show no breadcrumb trail.",
                why="A visitor landing on a deep page from search/an answer can't tell where they are in the site or move up a level, so they leave rather than explore.",
                how_to_fix="Add a breadcrumb trail (and BreadcrumbList schema) on deep pages so visitors keep their bearings and explore laterally.",
                scope=scope_str(len(no_crumb), len(deep)),
                measurements={"deep_pages": len(deep), "deep_without_breadcrumbs": len(no_crumb)},
                suggested_action_summary="Add a breadcrumb trail (and BreadcrumbList schema) on deep pages so visitors keep their bearings and explore laterally.",
                suggested_action_priority="low", affected_pages=no_crumb,
            )]
    return []


def _intrusive(pages: List[Page]) -> List[Finding]:
    hits = [p.url for p in pages if POPUP_RE.search(p.raw_html)]
    if hits:
        return [Finding(
            title="Possible intrusive interstitial / pop-up on load",
            severity="low", dimension="engagement", category="conversion",
            evidence=f"{scope_str(len(hits), len(pages))} contain markup suggesting an on-load newsletter/subscribe overlay, e.g. {hits[0]}.",
            why="An interstitial shown before the visitor sees any value interrupts the first impression and drives early exits (and is penalized on mobile search).",
            how_to_fix="Trigger overlays on exit-intent or after scroll instead of immediately on load, and keep them easily dismissible.",
            scope=scope_str(len(hits), len(pages)),
            measurements={"popup_pages": len(hits)},
            suggested_action_summary="Delay or soften entry pop-ups (exit-intent or scroll-triggered instead of immediate); an interstitial before the visitor sees value drives early exits.",
            suggested_action_priority="low", confidence="low", affected_pages=hits,
        )]
    return []


def _login_barrier(pages: List[Page], cfg) -> List[Finding]:
    """Flag content pages that gate their content behind a login/registration wall."""
    walled = [p.url for p in pages if GATING_RE.search(p.visible_text[:800])]
    if len(walled) >= cfg.t("login_wall_min_pages"):
        return [Finding(
            title="Content appears gated behind a login or registration wall",
            severity="medium", dimension="engagement", category="conversion",
            evidence=f"{scope_str(len(walled), len(pages))} show sign-in/subscribe-to-continue gating near the top, e.g. {walled[0]}.",
            why="Content behind a login/paywall is invisible to crawlers and turns away first-time visitors and assistants, "
                "so the gated facts can't be read, cited, or evaluated before someone commits.",
            how_to_fix="Expose a meaningful, crawlable preview of the content before the wall, or reserve gating for genuinely private material.",
            scope=scope_str(len(walled), len(pages)),
            measurements={"gated_pages": len(walled)},
            suggested_action_summary="Show a crawlable content preview before any login/registration wall so the value is visible to visitors and machines.",
            suggested_action_priority="medium", confidence="low", affected_pages=walled,
        )]
    return []


def _link_quality(pages: List[Page], cfg) -> List[Finding]:
    """Flag non-descriptive link text (empty anchors or 'click here'/'read more')."""
    total_links = empty = generic = 0
    example = None
    for p in pages:
        for a in p.links:
            total_links += 1
            txt = (a.get("text") or "").strip()
            if not txt and not (a.get("aria-label") or a.get("title")):
                empty += 1
            elif GENERIC_LINK_RE.match(txt):
                generic += 1
                example = example or p.url
    if not total_links:
        return []
    empty_ratio = empty / total_links
    # Only flag on unambiguous generic labels: empty anchors are often icon links with an
    # aria-label we can't see in static markup, so counting them alone risks false positives.
    if generic >= cfg.t("generic_link_min"):
        return [Finding(
            title="Links with non-descriptive text",
            severity="low", dimension="engagement", category="accessibility",
            evidence=(f"{generic} link(s) use generic labels ('click here'/'read more') "
                      f"out of {total_links} sampled, e.g. {example}."),
            why="Empty or generic link text gives visitors using screen readers no idea where a link goes, and gives "
                "machines no context about the destination — weakening both accessibility and link-based discovery.",
            how_to_fix="Write link text that names the destination ('View the pricing page'); add aria-label to icon-only links.",
            measurements={"empty_links": empty, "generic_links": generic, "total_links": total_links,
                          "empty_ratio": round(empty_ratio, 3)},
            suggested_action_summary="Use descriptive link text that names the destination; add aria-label to icon-only links.",
            suggested_action_priority="low", confidence="medium",
        )]
    return []


# --- helpers ----------------------------------------------------------------------
def _button_text(page: Page) -> str:
    return " ".join(re.findall(r"<button[^>]*>(.*?)</button>", page.raw_html, re.S | re.I))[:2000]


def _internal(page: Page) -> List[str]:
    from ..http import same_registrable_domain
    return [a["href"] for a in page.links
            if a["href"].startswith(("/", "#")) or same_registrable_domain(a["href"], page.url)]
