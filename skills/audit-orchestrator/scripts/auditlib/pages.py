"""Per-page detail for the report's page explorer.

Turns the crawl (parsed pages + raw responses) plus the scored findings into one record per
sampled URL: the observable facts (title, meta, headings, schema, links, indexability, …), the
findings that affect it, and a per-page score derived transparently from those findings. Pure
function of the audit context + report; no extra network.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, List

from . import scoring
from .htmlparse import Page, jsonld_types
from . import http as _http

_CTA_TEXT = re.compile(r"\b(buy|shop|get started|sign up|subscribe|contact|book|request|demo|"
                       r"add to cart|download|apply|register|donate|order|enquire)\b", re.I)
_CTA_HREF = re.compile(r"/(cart|checkout|contact|signup|sign-up|register|buy|order|subscribe|book|"
                       r"demo|pricing|apply|donate|quote)(/|$|\?)|^(tel:|mailto:)", re.I)


def build(ctx, report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return a per-page record list for ``report['pages']``."""
    findings = report.get("findings", [])
    home_url = ctx.pages[0].url if ctx.pages else ""
    # Map url -> finding records affecting it (site-wide findings attach to the homepage).
    by_page: Dict[str, List[Dict[str, Any]]] = {}
    for f in findings:
        targets = f.get("affected_pages") or []
        if not targets:
            targets = [home_url]
        for u in targets:
            by_page.setdefault(u, []).append(f)

    resp_by_url = {}
    for r in ctx.responses:
        resp_by_url[r.final_url or r.url] = r
        resp_by_url.setdefault(r.url, r)

    out: List[Dict[str, Any]] = []
    for p in ctx.pages:
        r = resp_by_url.get(p.url)
        pf = by_page.get(p.url, [])
        out.append(_page_record(p, r, pf, is_home=(p.url == home_url)))
    # Most-problematic first, homepage always first.
    out.sort(key=lambda d: (not d["is_home"], d["score"], -d["finding_count"]))
    return out


def _page_record(p: Page, r, page_findings, is_home) -> Dict[str, Any]:
    internal = external = pdf = 0
    for a in p.links:
        href = a.get("href", "")
        if href.lower().endswith(".pdf"):
            pdf += 1
        if href.startswith(("/", "#")) or _http.same_registrable_domain(href, p.url):
            internal += 1
        elif href.startswith("http"):
            external += 1
    h1s = [t for lvl, t in p.headings if lvl == "h1"]
    h2s = [t for lvl, t in p.headings if lvl == "h2"]
    sd_types = sorted({t for t in jsonld_types(p)})
    meta_robots = (p.meta_robots or "").lower()
    noindex = "noindex" in meta_robots or (r and "noindex" in (r.headers.get("x-robots-tag", "").lower()))
    missing_alt = sum(1 for im in p.images if im.get("alt") == "__MISSING__")
    cta = bool(_CTA_TEXT.search(" ".join(a.get("text", "") for a in p.links))
               or _CTA_HREF.search(" ".join(a.get("href", "") for a in p.links)))

    penalty = sum(scoring.penalty_of(f) for f in page_findings)
    score = max(0, min(100, round(100 - penalty)))
    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    top_sev = min((f.get("severity", "info") for f in page_findings),
                  key=lambda s: sev_rank.get(s, 5), default=None)
    dims = sorted({f.get("dimension", "") for f in page_findings if f.get("dimension")})
    conf_order = {"high": 3, "medium": 2, "low": 1}
    confidence = (min((f.get("confidence", "high") for f in page_findings),
                      key=lambda c: conf_order.get(c, 3)) if page_findings else "high")

    return {
        "url": p.url,
        "is_home": is_home,
        "status": (r.status if r else None),
        "redirected": bool(r and r.final_url and r.final_url != r.url),
        "final_url": (r.final_url if r else p.url),
        "score": score,
        "finding_count": len(page_findings),
        "finding_ids": [f.get("id") for f in page_findings],
        "top_severity": top_sev,
        "dimensions": dims,
        "confidence": confidence,
        "title": p.title,
        "title_len": len(p.title.strip()),
        "meta_description": p.meta.get("description", ""),
        "h1": h1s[0] if h1s else "",
        "h1_count": len(h1s),
        "h2_count": len(h2s),
        "headings_outline": [[lvl, t[:80]] for lvl, t in p.headings[:12]],
        "structured_data_types": sd_types,
        "lang": p.lang,
        "canonical": p.canonical,
        "indexable": not noindex,
        "internal_links": internal,
        "external_links": external,
        "pdf_links": pdf,
        "cta_signal": cta,
        "images": len(p.images),
        "images_missing_alt": missing_alt,
        "scripts": len(p.scripts_src),
        "html_kb": (r.raw_len // 1024 if r else p.html_len // 1024),
        "response_ms": (r.elapsed_ms if r else None),
        "word_count": p.word_count,
        # Rendering is assessed statically only; true rendered-DOM parity is NOT verified.
        "rendering": {"static_text_words": p.word_count, "verified": False,
                      "note": "static HTML only — rendered DOM not executed"},
    }
