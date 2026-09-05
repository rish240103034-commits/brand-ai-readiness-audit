"""Content-extractability checks (Round-2 appendix C).

A fact plainly visible to a human can be invisible to a machine when it is locked in an
image, a canvas, or a PDF, or when the page gives a machine no textual anchors (title,
meta description, headings, language, clean heading hierarchy). The more explicitly a fact is
stated in readable, well-structured text, the more reliably it is extracted and quoted.

Each finding carries a specific ``why`` and ``how_to_fix`` so explanations always match the
actual defect (no shared category-level boilerplate).
"""
from __future__ import annotations

import re
from typing import List

from ..context import AuditContext
from ..report import Finding, scope_str
from ..htmlparse import Page

CONTACT_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)|([\w.+-]+@[\w-]+\.[\w.-]+)")
# Heading-quality bounds (chars). Titles outside these read poorly in results/answers.
TITLE_MIN, TITLE_MAX = 15, 65
DESC_MIN, DESC_MAX = 50, 160


def analyze(ctx: AuditContext) -> List[Finding]:
    findings: List[Finding] = []
    pages = ctx.pages
    if not pages:
        return findings

    findings += _title_meta(pages)
    findings += _title_meta_quality(pages)
    findings += _headings(pages)
    findings += _heading_hierarchy(pages)
    findings += _images_alt(pages, ctx.cfg)
    findings += _text_in_images(pages, ctx.cfg)
    findings += _language(pages)
    findings += _pdf_primary(ctx)
    return findings


def _title_meta(pages: List[Page]) -> List[Finding]:
    out: List[Finding] = []
    total = len(pages)
    no_title = [p.url for p in pages if not p.title.strip()]
    no_desc = [p.url for p in pages if not p.meta.get("description", "").strip()]
    dup_titles = _duplicates([p.title.strip() for p in pages if p.title.strip()])
    if no_title:
        out.append(Finding(
            title="Pages missing a <title>",
            severity="high", dimension="discoverability", category="extractability",
            evidence=f"{scope_str(len(no_title), total)} have no <title>, e.g. {no_title[0]}.",
            why="The <title> is the single strongest textual label a machine reads; without it an "
                "assistant has no reliable name for the page and rarely surfaces or cites it.",
            how_to_fix="Add a unique, descriptive <title> (≈15–65 chars) to every page, front-loading "
                       "the page's specific topic and the brand.",
            scope=scope_str(len(no_title), total),
            measurements={"pages_without_title": len(no_title), "pages": total},
            suggested_action_summary="Give every page a unique, descriptive <title>; it is the single strongest textual label a machine reads first.",
            suggested_action_priority="high", affected_pages=no_title,
        ))
    if no_desc:
        out.append(Finding(
            title="Pages missing a meta description",
            severity="medium", dimension="discoverability", category="extractability",
            evidence=f"{scope_str(len(no_desc), total)} have no meta description.",
            why="Assistants and search engines frequently quote the meta description verbatim as the "
                "page summary; without one they must synthesize a summary from raw prose, often poorly.",
            how_to_fix="Add a concise, fact-bearing meta description (≈50–160 chars) per page that states "
                       "what the page offers in plain language.",
            scope=scope_str(len(no_desc), total),
            measurements={"pages_without_description": len(no_desc), "pages": total},
            suggested_action_summary="Add a concise, fact-bearing meta description per page; assistants frequently quote it as the page summary.",
            suggested_action_priority="medium", affected_pages=no_desc,
        ))
    if dup_titles:
        out.append(Finding(
            title="Duplicate <title> tags across pages",
            severity="low", dimension="discoverability", category="extractability",
            evidence=f"{len(dup_titles)} title string(s) are reused across multiple sampled pages, e.g. \"{dup_titles[0][:60]}\".",
            why="Identical titles make distinct pages indistinguishable to a machine, so it cannot tell "
                "which page to cite for a given question and may collapse them into one.",
            how_to_fix="Template titles as \"<page-specific topic> — <brand>\" so each page's title is unique.",
            measurements={"duplicate_title_strings": len(dup_titles)},
            suggested_action_summary="Make each title unique so machines can tell pages apart and pick the right one to cite.",
            suggested_action_priority="low",
        ))
    return out


def _title_meta_quality(pages: List[Page]) -> List[Finding]:
    """Flag titles/descriptions that exist but are too short/long to be useful."""
    out: List[Finding] = []
    total = len(pages)
    bad_title = [(p.url, len(p.title.strip())) for p in pages
                 if p.title.strip() and not (TITLE_MIN <= len(p.title.strip()) <= TITLE_MAX)]
    long_desc = [(p.url, len(p.meta.get("description", "").strip())) for p in pages
                 if len(p.meta.get("description", "").strip()) > DESC_MAX]
    if bad_title:
        u, n = bad_title[0]
        out.append(Finding(
            title="Title tags outside the useful length range",
            severity="low", dimension="discoverability", category="extractability",
            evidence=f"{scope_str(len(bad_title), total)} have a <title> shorter than {TITLE_MIN} or longer than {TITLE_MAX} characters, e.g. {u} ({n} chars).",
            why="Very short titles under-describe the page while very long ones get truncated in results "
                "and answers, so the specific topic is lost either way.",
            how_to_fix=f"Rewrite titles to ≈{TITLE_MIN}–{TITLE_MAX} characters: lead with the unique topic, then the brand.",
            scope=scope_str(len(bad_title), total),
            measurements={"pages_with_offlength_title": len(bad_title), "min": TITLE_MIN, "max": TITLE_MAX},
            suggested_action_summary=f"Keep titles roughly {TITLE_MIN}–{TITLE_MAX} characters and topic-first.",
            suggested_action_priority="low", confidence="medium",
            affected_pages=[u for u, _ in bad_title],
        ))
    if long_desc:
        u, n = long_desc[0]
        out.append(Finding(
            title="Meta descriptions likely to be truncated",
            severity="low", dimension="discoverability", category="extractability",
            evidence=f"{scope_str(len(long_desc), total)} have a meta description longer than {DESC_MAX} characters, e.g. {u} ({n} chars).",
            why="Over-long descriptions are cut off, so the most important summary sentence may never be shown or quoted.",
            how_to_fix=f"Trim descriptions to ≈{DESC_MIN}–{DESC_MAX} characters, leading with the key fact.",
            scope=scope_str(len(long_desc), total),
            measurements={"pages_with_long_description": len(long_desc), "max": DESC_MAX},
            suggested_action_summary=f"Keep meta descriptions under ~{DESC_MAX} characters, key fact first.",
            suggested_action_priority="low", confidence="medium",
            affected_pages=[u for u, _ in long_desc],
        ))
    return out


def _headings(pages: List[Page]) -> List[Finding]:
    out: List[Finding] = []
    total = len(pages)
    no_h1 = [p.url for p in pages if not any(h[0] == "h1" for h in p.headings)]
    multi_h1 = [p.url for p in pages if sum(1 for h in p.headings if h[0] == "h1") > 1]
    if no_h1:
        out.append(Finding(
            title="Pages missing an H1 heading",
            severity="medium", dimension="discoverability", category="extractability",
            evidence=f"{scope_str(len(no_h1), total)} have no H1, e.g. {no_h1[0]}.",
            why="The H1 is the primary topic anchor a machine uses to decide what a page is about; "
                "without it the page's subject must be guessed from weaker signals.",
            how_to_fix="Add exactly one descriptive H1 per page that states the page's topic in plain words.",
            scope=scope_str(len(no_h1), total),
            measurements={"pages_without_h1": len(no_h1), "pages": total},
            suggested_action_summary="Add exactly one descriptive H1 per page stating what the page is about in plain words.",
            suggested_action_priority="medium", affected_pages=no_h1,
        ))
    if multi_h1:
        out.append(Finding(
            title="Multiple H1 headings on a page",
            severity="low", dimension="discoverability", category="extractability",
            evidence=f"{scope_str(len(multi_h1), total)} declare more than one H1, e.g. {multi_h1[0]}.",
            why="Several competing H1s give a machine more than one candidate 'main topic' for the same "
                "page, diluting the primary-topic signal it relies on to classify and cite the page.",
            how_to_fix="Keep a single H1 for the page's main topic and demote the others to H2/H3 to form a clear outline.",
            scope=scope_str(len(multi_h1), total),
            measurements={"pages_with_multiple_h1": len(multi_h1), "pages": total},
            suggested_action_summary="Use a single H1 for the main topic and H2/H3 for sub-sections to give a clean outline.",
            suggested_action_priority="low", confidence="medium", affected_pages=multi_h1,
        ))
    return out


def _heading_hierarchy(pages: List[Page]) -> List[Finding]:
    """Flag pages whose heading levels skip (e.g. H1 → H3 with no H2)."""
    total = len(pages)
    skipped = []
    for p in pages:
        levels = [int(h[0][1]) for h in p.headings if h[0][:1] == "h" and h[0][1:].isdigit()]
        if len(levels) < 3:
            continue
        prev = levels[0]
        for lv in levels[1:]:
            if lv - prev >= 2:  # jumped a level going deeper
                skipped.append(p.url)
                break
            prev = lv
    if skipped:
        return [Finding(
            title="Heading hierarchy skips levels",
            severity="low", dimension="discoverability", category="extractability",
            evidence=f"{scope_str(len(skipped), total)} jump heading levels (e.g. H1→H3 with no H2), e.g. {skipped[0]}.",
            why="A machine reconstructs a page's outline from heading levels; skipped levels break that "
                "nesting, so the relationship between sections is ambiguous.",
            how_to_fix="Use headings in order (H1→H2→H3) without skipping a level; style, don't skip, to change size.",
            scope=scope_str(len(skipped), total),
            measurements={"pages_with_skipped_levels": len(skipped)},
            suggested_action_summary="Nest headings in order (no H1→H3 jumps) so the document outline is unambiguous.",
            suggested_action_priority="low", confidence="medium", affected_pages=skipped,
        )]
    return []


def _images_alt(pages: List[Page], cfg) -> List[Finding]:
    """Flag a high proportion of images with no alt attribute."""
    out: List[Finding] = []
    total_imgs = sum(len(p.images) for p in pages)
    missing = []
    for p in pages:
        m = sum(1 for im in p.images if im.get("alt") == "__MISSING__")
        if m:
            missing.append((p.url, m, len(p.images)))
    total_missing = sum(m for _, m, _ in missing)
    if (total_imgs and total_missing / max(total_imgs, 1) > cfg.t("alt_missing_ratio")
            and total_missing >= cfg.t("alt_missing_min")):
        worst = max(missing, key=lambda x: x[1])
        pct = round(100 * total_missing / total_imgs)
        out.append(Finding(
            title="Many images lack alt text",
            severity="medium", dimension="discoverability", category="extractability",
            evidence=f"{total_missing}/{total_imgs} sampled images ({pct}%) have no alt attribute (e.g. {worst[1]}/{worst[2]} on {worst[0]}).",
            why="Any fact carried only by an image (a logo's brand name, a product spec, an infographic's "
                "numbers) is invisible to text-based retrievers when the image has no alt text.",
            how_to_fix="Add descriptive alt text to informative images; use empty alt=\"\" for purely decorative ones.",
            scope=f"{total_missing}/{total_imgs} images ({pct}%)",
            measurements={"images_missing_alt": total_missing, "images_total": total_imgs, "pct": pct},
            suggested_action_summary="Add descriptive alt text to informative images (logos, product shots, infographics). Decorative images should use empty alt=\"\".",
            suggested_action_priority="medium",
            affected_pages=[u for u, _, _ in missing],
        ))
    return out


def _text_in_images(pages: List[Page], cfg) -> List[Finding]:
    """Heuristic: pages that are visually rich but textually thin likely carry copy in images."""
    out: List[Finding] = []
    total = len(pages)
    suspects = []
    for p in pages:
        if (len(p.images) >= cfg.t("text_in_image_min_images")
                and p.word_count < cfg.t("text_in_image_max_words")
                and p.html_len > cfg.t("text_in_image_min_html")):
            suspects.append(p.url)
    if suspects:
        maxw = int(cfg.t("text_in_image_max_words"))
        out.append(Finding(
            title="Key content may be embedded in images rather than text",
            severity="medium", dimension="discoverability", category="extractability",
            evidence=f"{scope_str(len(suspects), total)} are image-heavy with very little extractable text (<{maxw} words), e.g. {suspects[0]}.",
            why="Text baked into images (offers, specs, contact details) is not machine-readable, so those "
                "facts cannot be extracted, quoted, or answered from.",
            how_to_fix="Move factual copy out of images into real HTML text; keep images for illustration and mirror any embedded words in alt text.",
            scope=scope_str(len(suspects), total),
            measurements={"image_heavy_thin_pages": len(suspects), "word_threshold": maxw},
            suggested_action_summary="Move factual copy out of images into real HTML text; keep images for illustration with alt text mirroring any embedded words.",
            suggested_action_priority="medium", confidence="medium", affected_pages=suspects,
        ))
    return out


def _language(pages: List[Page]) -> List[Finding]:
    out: List[Finding] = []
    no_lang = [p.url for p in pages if not p.lang.strip()]
    if no_lang and len(no_lang) == len(pages):
        out.append(Finding(
            title="Page language is not declared",
            severity="low", dimension="discoverability", category="extractability",
            evidence="No sampled page sets a <html lang=…> attribute.",
            why="Without a declared language, machines can mis-detect the page's language and route or "
                "interpret its content for the wrong audience.",
            how_to_fix="Set <html lang=\"…\"> (e.g. lang=\"en\") on every page, matching the actual content language.",
            measurements={"pages_without_lang": len(no_lang), "pages": len(pages)},
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
            severity="low", dimension="discoverability", category="extractability",
            evidence=f"{len(pdf_links)} PDF link(s) found across sampled pages.",
            why="Scanned or image-only PDFs are frequently unreadable to crawlers, so any key information "
                "that lives only inside them cannot be extracted or cited.",
            how_to_fix="Publish the key information as HTML (keep the PDF as an optional download) and ensure essential PDFs contain real, selectable text, not scans.",
            measurements={"pdf_links": len(pdf_links)},
            suggested_action_summary="Publish the key information as HTML pages (the PDF can remain as a download). Ensure any essential PDFs contain real, selectable text, not scans.",
            suggested_action_priority="low", confidence="medium",
        )]
    return []


def _duplicates(items: List[str]) -> List[str]:
    seen, dups = set(), set()
    for x in items:
        if x in seen:
            dups.add(x)
        seen.add(x)
    return sorted(dups)
