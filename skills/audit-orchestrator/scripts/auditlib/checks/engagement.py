"""On-site engagement checks — the 'keep the visitor once they arrive' half.

Discoverability gets a visitor to the page; engagement decides whether they stay. Poor
mobile rendering, no clear next action, weak orientation, heavy slow pages, and
dead-end navigation all drive the bounce that Round 2 asked about. These are read from
static markup and timing — mechanism-sound proxies, reported with honest confidence.
"""
from __future__ import annotations

import re
from typing import List

from ..context import AuditContext
from ..report import Finding
from ..htmlparse import Page

CTA_RE = re.compile(
    r"\b(buy|shop|get started|sign up|sign-up|subscribe|contact|book|"
    r"request|demo|start free|add to cart|learn more|download|try)\b", re.I)
NAV_RE = re.compile(r"<nav[\s>]|role=[\"']navigation[\"']", re.I)
BREADCRUMB_RE = re.compile(r"breadcrumb|BreadcrumbList", re.I)
POPUP_RE = re.compile(r"(newsletter|subscribe|cookie).{0,40}(modal|popup|overlay|interstitial)|"
                      r"(modal|popup|overlay|interstitial).{0,40}(newsletter|subscribe)", re.I)
BUTTON_RE = re.compile(r"<button[\s>]|type=[\"']submit[\"']", re.I)


def analyze(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []
    pages = ctx.pages
    if not pages:
        return findings

    findings += _viewport(pages, ctx.cfg)
    findings += _primary_cta(ctx)
    findings += _navigation(pages, ctx.cfg)
    findings += _page_weight(ctx)
    findings += _readability(pages, ctx.cfg)
    findings += _orientation(pages, ctx.cfg)
    findings += _intrusive(pages)
    return findings


def _viewport(pages: List[Page], cfg) -> List[Finding]:
    """Flag a missing responsive viewport meta across the sampled pages."""
    no_vp = [p.url for p in pages if not p.meta.get("viewport", "").strip()]
    if no_vp and len(no_vp) >= max(1, int(len(pages) * cfg.t("viewport_min_fraction"))):
        return [Finding(
            title="No responsive viewport meta tag",
            severity="high",
            dimension="engagement",
            category="mobile",
            evidence=f"{len(no_vp)} of {len(pages)} sampled page(s) omit <meta name=\"viewport\">, so mobile browsers render a zoomed-out desktop layout.",
            suggested_action_summary="Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> and verify a responsive layout; mobile visitors bounce fast from unreadable pages.",
            suggested_action_priority="high",
            affected_pages=no_vp,
        )]
    return []


def _primary_cta(ctx: AuditContext) -> List[Finding]:
    home = ctx.pages[0]
    link_text = " ".join(a.get("text", "") for a in home.links)
    has_cta = bool(CTA_RE.search(link_text) or CTA_RE.search(_button_text(home)))
    if not has_cta:
        return [Finding(
            title="Homepage has no clear call-to-action",
            severity="medium",
            dimension="engagement",
            category="conversion",
            evidence=f"No action-oriented link or button (buy/contact/sign up/book/demo…) was found among the homepage's {len(home.links)} links.",
            suggested_action_summary="Add one prominent, unambiguous primary CTA above the fold that tells the visitor the single most valuable next step.",
            suggested_action_priority="medium",
            confidence="medium",
        )]
    return []


def _navigation(pages: List[Page], cfg) -> List[Finding]:
    """Flag missing semantic navigation and dead-end pages with few onward links."""
    no_nav = [p.url for p in pages if not NAV_RE.search(p.raw_html)]
    thin_links = [p.url for p in pages if len(_internal(p)) < cfg.t("deadend_min_links")]
    out: List[Finding] = []
    if no_nav and len(no_nav) == len(pages):
        out.append(Finding(
            title="No semantic navigation region",
            severity="medium",
            dimension="engagement",
            category="orientation",
            evidence="No sampled page exposes a <nav> element or role=\"navigation\"; visitors and machines lack a clear menu structure.",
            suggested_action_summary="Wrap the primary menu in a <nav> with descriptive links so visitors can orient and move deeper instead of bouncing.",
            suggested_action_priority="medium",
        ))
    if thin_links:
        out.append(Finding(
            title="Dead-end pages with few onward links",
            severity="low",
            dimension="engagement",
            category="orientation",
            evidence=f"{len(thin_links)} sampled page(s) offer fewer than 3 internal links, e.g. {thin_links[0]}, giving visitors nowhere to go next.",
            suggested_action_summary="Add contextual links (related pages, next steps, related products/articles) so each page leads somewhere relevant.",
            suggested_action_priority="low",
            affected_pages=thin_links,
        ))
    return out


def _page_weight(ctx: AuditContext) -> List[Finding]:
    """Flag heavy pages and slow server responses (bounce-driving performance proxies)."""
    heavy = []
    slow = []
    max_bytes = ctx.cfg.t("page_weight_bytes")
    max_scripts = ctx.cfg.t("page_weight_scripts")
    slow_ms = ctx.cfg.t("slow_ms")
    for p, r in zip(ctx.pages, ctx.responses):
        script_refs = len(p.scripts_src)
        if r.raw_len > max_bytes or script_refs > max_scripts:
            heavy.append((p.url, r.raw_len, script_refs))
        if r.elapsed_ms > slow_ms:
            slow.append((p.url, r.elapsed_ms))
    out: List[Finding] = []
    if heavy:
        w = max(heavy, key=lambda x: x[1])
        out.append(Finding(
            title="Heavy pages likely to slow first render",
            severity="medium",
            dimension="engagement",
            category="performance",
            evidence=f"{len(heavy)} page(s) are large or script-dense (e.g. {w[0]}: {w[1]//1024} KB HTML, {w[2]} external scripts). Weight delays interactivity and raises bounce.",
            suggested_action_summary="Trim and defer non-critical scripts, split bundles, and lazy-load below-the-fold assets to cut time-to-content.",
            suggested_action_priority="medium",
            confidence="medium",
            affected_pages=[u for u, _, _ in heavy],
        ))
    if slow:
        s = max(slow, key=lambda x: x[1])
        out.append(Finding(
            title="Slow server response on sampled pages",
            severity="medium",
            dimension="engagement",
            category="performance",
            evidence=f"{len(slow)} page(s) took over 3s to return HTML (e.g. {s[0]}: {s[1]} ms). Slow first byte compounds every downstream delay.",
            suggested_action_summary="Investigate TTFB (caching, CDN, server work) so pages start rendering quickly; each added second measurably increases abandonment.",
            suggested_action_priority="medium",
            confidence="medium",
            affected_pages=[u for u, _ in slow],
        ))
    return out


def _readability(pages: List[Page], cfg) -> List[Finding]:
    """Flag long content with almost no subheadings (a wall of text)."""
    walls = []
    min_words = cfg.t("wall_words")
    max_headings = cfg.t("wall_max_headings")
    for p in pages:
        headings = len(p.headings)
        if p.word_count > min_words and headings <= max_headings:
            walls.append(p.url)
    if walls:
        return [Finding(
            title="Long content with almost no subheadings",
            severity="low",
            dimension="engagement",
            category="readability",
            evidence=f"{len(walls)} page(s) have 900+ words but 0–1 headings, e.g. {walls[0]}: a wall of text visitors skim and abandon.",
            suggested_action_summary="Break long copy into scannable sections with descriptive H2/H3 headings, short paragraphs, and lists.",
            suggested_action_priority="low",
            affected_pages=walls,
        )]
    return []


def _orientation(pages: List[Page], cfg) -> List[Finding]:
    """Context retention across a visit: breadcrumbs on deeper pages."""
    seg = cfg.t("deep_path_segments")
    deep = [p for p in pages if p.url.rstrip("/").count("/") > seg]
    if len(deep) >= cfg.t("deep_min_pages"):
        no_crumb = [p.url for p in deep if not BREADCRUMB_RE.search(p.raw_html)]
        if len(no_crumb) == len(deep):
            return [Finding(
                title="Deep pages lack breadcrumbs / positional context",
                severity="low",
                dimension="engagement",
                category="orientation",
                evidence=f"{len(no_crumb)} deep page(s) show no breadcrumb trail, so visitors landing mid-site can't tell where they are or move up a level.",
                suggested_action_summary="Add a breadcrumb trail (and BreadcrumbList schema) on deep pages so visitors keep their bearings and explore laterally.",
                suggested_action_priority="low",
                affected_pages=no_crumb,
            )]
    return []


def _intrusive(pages: List[Page]) -> List[Finding]:
    hits = [p.url for p in pages if POPUP_RE.search(p.raw_html)]
    if hits:
        return [Finding(
            title="Possible intrusive interstitial / pop-up on load",
            severity="low",
            dimension="engagement",
            category="conversion",
            evidence=f"{len(hits)} page(s) contain markup suggesting an on-load newsletter/subscribe overlay, e.g. {hits[0]}.",
            suggested_action_summary="Delay or soften entry pop-ups (exit-intent or scroll-triggered instead of immediate); an interstitial before the visitor sees value drives early exits.",
            suggested_action_priority="low",
            confidence="low",
            affected_pages=hits,
        )]
    return []


# --- helpers ----------------------------------------------------------------------
def _button_text(page: Page) -> str:
    return " ".join(re.findall(r"<button[^>]*>(.*?)</button>", page.raw_html, re.S | re.I))[:2000]


def _internal(page: Page) -> List[str]:
    from ..http import same_registrable_domain
    return [a["href"] for a in page.links
            if a["href"].startswith(("/", "#")) or same_registrable_domain(a["href"], page.url)]
