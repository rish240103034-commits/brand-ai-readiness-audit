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


def _section_of(url: str) -> tuple:
    """Return (key, label) for a URL's top-level section, e.g. /products/x -> ('/products','/products/')."""
    path = urllib.parse.urlsplit(url).path or "/"
    segs = [s for s in path.split("/") if s]
    if not segs:
        return ("/", "Home (/)")
    return ("/" + segs[0], "/" + segs[0] + "/")


def build_sections(page_records: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group pages by top-level URL section and score each, so the weakest area of the site is
    obvious. Returns [] for a single-section site (nothing to compare)."""
    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    by_id = {f.get("id"): f for f in findings}
    groups: Dict[str, Dict[str, Any]] = {}
    for p in page_records:
        key, label = _section_of(p["url"])
        g = groups.setdefault(key, {"key": key, "label": label, "pages": 0, "_scores": [],
                                    "_fids": set(), "examples": []})
        g["pages"] += 1
        g["_scores"].append(p["score"])
        g["_fids"].update(p.get("finding_ids") or [])
        if len(g["examples"]) < 3:
            g["examples"].append(p["url"])

    sections = []
    for g in groups.values():
        fids = [i for i in g["_fids"] if i in by_id]
        sev = sorted((by_id[i].get("severity", "info") for i in fids),
                     key=lambda s: sev_rank.get(s, 5))
        dims = sorted({by_id[i].get("dimension", "") for i in fids if by_id[i].get("dimension")})
        sections.append({
            "key": g["key"], "label": g["label"], "pages": g["pages"],
            "score": round(sum(g["_scores"]) / len(g["_scores"])) if g["_scores"] else 100,
            "findings": len(fids),
            "top_severity": sev[0] if sev else None,
            "dimensions": dims,
            "examples": g["examples"],
        })
    if len(sections) < 2:
        return []
    sections.sort(key=lambda s: (s["score"], -s["findings"]))
    return sections


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
        # "What the AI sees": the exact fetch-only text a JS-less retriever extracts, plus a
        # content-density risk (how much a fetch-only bot is likely to be missing).
        "extractable_preview": (p.visible_text[:400] + ("…" if len(p.visible_text) > 400 else "")),
        "extractable_words": p.word_count,
        "render_risk": ("high" if p.word_count < 60 else "medium" if p.word_count < 120 else "low"),
    }
