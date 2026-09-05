"""Content-extractability checks (Round-2 appendix C).

A fact plainly visible to a human can be invisible to a machine when it is locked in an
image, a canvas, or a PDF, or when the page gives a machine no textual anchors (title,
meta description, headings, language). The more explicitly a fact is stated in readable
text, the more reliably it is extracted and quoted.
"""
from __future__ import annotations

import re
from typing import List

from ..context import AuditContext
from ..report import Finding
from ..htmlparse import Page

CONTACT_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)|([\w.+-]+@[\w-]+\.[\w.-]+)")


def analyze(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []
    pages = ctx.pages
    if not pages:
        return findings

    findings += _title_meta(pages)
    findings += _headings(pages)
    findings += _images_alt(pages, ctx.cfg)
    findings += _text_in_images(pages, ctx.cfg)
    findings += _language(pages)
    findings += _pdf_primary(ctx)
    return findings


def _title_meta(pages: List[Page]) -> List[Finding]:
    out: List[Finding] = []
    no_title = [p.url for p in pages if not p.title.strip()]
    no_desc = [p.url for p in pages if not p.meta.get("description", "").strip()]
    dup_titles = _duplicates([p.title.strip() for p in pages if p.title.strip()])
    if no_title:
        out.append(Finding(
            title="Pages missing a <title>",
            severity="high",
            dimension="discoverability",
            category="extractability",
            evidence=f"{len(no_title)} sampled page(s) have no <title>, e.g. {no_title[0]}.",
            suggested_action_summary="Give every page a unique, descriptive <title>; it is the single strongest textual label a machine reads first.",
            suggested_action_priority="high",
            affected_pages=no_title,
        ))
    if no_desc:
        out.append(Finding(
            title="Pages missing a meta description",
            severity="medium",
            dimension="discoverability",
            category="extractability",
            evidence=f"{len(no_desc)} of {len(pages)} sampled page(s) have no meta description.",
            suggested_action_summary="Add a concise, fact-bearing meta description per page; assistants frequently quote it as the page summary.",
            suggested_action_priority="medium",
            affected_pages=no_desc,
        ))
    if dup_titles:
        out.append(Finding(
            title="Duplicate <title> tags across pages",
            severity="low",
            dimension="discoverability",
            category="extractability",
            evidence=f"{len(dup_titles)} title string(s) are reused across multiple sampled pages, e.g. \"{dup_titles[0][:60]}\".",
            suggested_action_summary="Make each title unique so machines can tell pages apart and pick the right one to cite.",
            suggested_action_priority="low",
        ))
    return out


def _headings(pages: List[Page]) -> List[Finding]:
    out: List[Finding] = []
    no_h1 = [p.url for p in pages if not any(h[0] == "h1" for h in p.headings)]
    multi_h1 = [p.url for p in pages if sum(1 for h in p.headings if h[0] == "h1") > 1]
    if no_h1:
        out.append(Finding(
            title="Pages missing an H1 heading",
            severity="medium",
            dimension="discoverability",
            category="extractability",
            evidence=f"{len(no_h1)} sampled page(s) have no H1, e.g. {no_h1[0]}. The H1 is the primary topic anchor.",
            suggested_action_summary="Add exactly one descriptive H1 per page stating what the page is about in plain words.",
            suggested_action_priority="medium",
            affected_pages=no_h1,
        ))
    if multi_h1:
        out.append(Finding(
            title="Multiple H1 headings on a page",
            severity="low",
            dimension="discoverability",
            category="extractability",
            evidence=f"{len(multi_h1)} page(s) declare more than one H1, e.g. {multi_h1[0]}, diluting the topic signal.",
            suggested_action_summary="Use a single H1 for the main topic and H2/H3 for sub-sections to give a clean outline.",
            suggested_action_priority="low",
            affected_pages=multi_h1,
        ))
    return out


def _images_alt(pages: List[Page], cfg) -> List[Finding]:
    """Flag a high proportion of images with no alt attribute."""
    out: List[Finding] = []
    total_imgs = sum(len(p.images) for p in pages)
    missing = []
    for p in pages:
        # Count only images with no alt attribute at all (htmlparse marks these "__MISSING__").
        m = sum(1 for im in p.images if im.get("alt") == "__MISSING__")
        if m:
            missing.append((p.url, m, len(p.images)))
    total_missing = sum(m for _, m, _ in missing)
    if (total_imgs and total_missing / max(total_imgs, 1) > cfg.t("alt_missing_ratio")
            and total_missing >= cfg.t("alt_missing_min")):
        worst = max(missing, key=lambda x: x[1])
        out.append(Finding(
            title="Many images lack alt text",
            severity="medium",
            dimension="discoverability",
            category="extractability",
            evidence=f"{total_missing}/{total_imgs} sampled images have no alt attribute (e.g. {worst[1]}/{worst[2]} on {worst[0]}). Any fact carried by those images is invisible to text-based machines.",
            suggested_action_summary="Add descriptive alt text to informative images (logos, product shots, infographics). Decorative images should use empty alt=\"\".",
            suggested_action_priority="medium",
            affected_pages=[u for u, _, _ in missing],
        ))
    return out


def _text_in_images(pages: List[Page], cfg) -> List[Finding]:
    """Heuristic: pages that are visually rich but textually thin likely carry copy in images."""
    out: List[Finding] = []
    suspects = []
    for p in pages:
        if (len(p.images) >= cfg.t("text_in_image_min_images")
                and p.word_count < cfg.t("text_in_image_max_words")
                and p.html_len > cfg.t("text_in_image_min_html")):
            suspects.append(p.url)
    if suspects:
        out.append(Finding(
            title="Key content may be embedded in images rather than text",
            severity="medium",
            dimension="discoverability",
            category="extractability",
            evidence=f"{len(suspects)} image-heavy page(s) have very little extractable text (<120 words), e.g. {suspects[0]}. Text baked into images (offers, specs, contact) is not machine-readable.",
            suggested_action_summary="Move factual copy out of images into real HTML text; keep images for illustration with alt text mirroring any embedded words.",
            suggested_action_priority="medium",
            confidence="medium",
            affected_pages=suspects,
        ))
    return out


def _language(pages: List[Page]) -> List[Finding]:
    out: List[Finding] = []
    no_lang = [p.url for p in pages if not p.lang.strip()]
    if no_lang and len(no_lang) == len(pages):
        out.append(Finding(
            title="Page language is not declared",
            severity="low",
            dimension="discoverability",
            category="extractability",
            evidence="No sampled page sets a <html lang=...> attribute.",
            suggested_action_summary="Declare the page language (e.g. <html lang=\"en\">) so machines interpret and route the content to the right audience.",
            suggested_action_priority="low",
        ))
    return out


def _pdf_primary(ctx: AuditContext) -> List[Finding]:
    """Flag when substantive content seems to live only in linked PDFs."""
    pdf_links = set()
    for p in ctx.pages:
        for a in p.links:
            if a["href"].lower().endswith(".pdf"):
                pdf_links.add(a["href"])
    if len(pdf_links) >= ctx.cfg.t("pdf_link_min"):
        return [Finding(
            title="Substantial content offloaded to PDF files",
            severity="low",
            dimension="discoverability",
            category="extractability",
            evidence=f"{len(pdf_links)} PDF link(s) found across sampled pages. Scanned or image-based PDFs are often unreadable to crawlers.",
            suggested_action_summary="Publish the key information as HTML pages (the PDF can remain as a download). Ensure any essential PDFs contain real, selectable text, not scans.",
            suggested_action_priority="low",
            confidence="medium",
        )]
    return []


def _duplicates(items: List[str]) -> List[str]:
    seen, dups = set(), set()
    for x in items:
        if x in seen:
            dups.add(x)
        seen.add(x)
    return sorted(dups)
