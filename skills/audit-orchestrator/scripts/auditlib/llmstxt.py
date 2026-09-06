"""llms.txt detection + generator.

`llms.txt` is an emerging convention: a Markdown file at the site root that tells LLMs what the
site is and points to its key content. This module checks whether the site publishes one and, if
not, **generates a suggested llms.txt** from what the audit already knows (brand, description, key
pages) — recommend-only, copy-paste. Attached as ``report['llms_txt']``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .context import AuditContext
from . import http as _http
from .htmlparse import jsonld_types

# Map a URL path to a human note for the "key pages" list.
_SECTION_NOTE = [
    (re.compile(r"/(about|company|who-we-are)(/|$)", re.I), "About the organization"),
    (re.compile(r"/(product|products|shop|store)(/|$)", re.I), "Products"),
    (re.compile(r"/(service|services|solutions)(/|$)", re.I), "Services"),
    (re.compile(r"/(pricing|plans)(/|$)", re.I), "Pricing"),
    (re.compile(r"/(contact)(/|$)", re.I), "Contact"),
    (re.compile(r"/(blog|articles|news)(/|$)", re.I), "Articles / blog"),
    (re.compile(r"/(docs|documentation|help|support)(/|$)", re.I), "Documentation / help"),
    (re.compile(r"/(faq)(/|$)", re.I), "FAQ"),
]


def build(ctx: AuditContext) -> Dict[str, Any]:
    present, status = _check(ctx)
    suggested = _generate(ctx)
    return {
        "present": present,
        "url": _http.host_of(ctx.start_url) and (_origin(ctx) + "/llms.txt"),
        "status": status,
        "suggested": suggested,
        "note": ("Site already publishes an llms.txt." if present else
                 "No llms.txt found. A suggested one is generated below (emerging standard for "
                 "telling AI assistants what the site is and where its key content lives)."),
    }


def _origin(ctx: AuditContext) -> str:
    return ctx.fetcher._origin(ctx.start_url)


def _check(ctx: AuditContext):
    try:
        r = ctx.fetcher.fetch(_origin(ctx) + "/llms.txt")
    except Exception:
        return False, None
    ct = (r.content_type or "").lower()
    ok = bool(r.ok and r.body.strip() and ("text" in ct or "markdown" in ct or ct == ""))
    return ok, (r.status if r else None)


def _generate(ctx: AuditContext) -> str:
    if not ctx.pages:
        return ""
    home = ctx.pages[0]
    brand = _brand(home, ctx.start_url)
    desc = (home.meta.get("description") or home.meta.get("og:description") or "").strip()
    lines: List[str] = [f"# {brand}"]
    if desc:
        lines.append("")
        lines.append(f"> {desc}")
    lines.append("")
    lines.append("## Key pages")
    for url, note in _key_pages(ctx):
        title = note
        lines.append(f"- [{title}]({url})")
    sm = _origin(ctx) + "/sitemap.xml"
    lines.append("")
    lines.append("## Optional")
    lines.append(f"- [Sitemap]({sm})")
    return "\n".join(lines)


def _key_pages(ctx: AuditContext) -> List[tuple]:
    """Pick representative pages (homepage + recognizable sections), de-duplicated by note."""
    out, seen_notes = [], set()
    home = ctx.pages[0]
    out.append((home.url, _first_line(home.title) or "Home"))
    for p in ctx.pages[1:]:
        for pat, note in _SECTION_NOTE:
            if pat.search(p.url) and note not in seen_notes:
                out.append((p.url, note))
                seen_notes.add(note)
                break
        if len(out) >= 8:
            break
    return out


def _first_line(s: str) -> str:
    return re.split(r"[|\-–—:]", (s or "").strip())[0].strip()


def _brand(home, start_url: str) -> str:
    name = home.meta.get("og:site_name", "").strip()
    if name:
        return name
    for obj in home.jsonld:
        types = {str(t).lower() for t in jsonld_types(home)}
        if {"organization", "website", "localbusiness"} & types and obj.get("name"):
            return str(obj["name"]).strip()
    host = _http.host_of(start_url)
    return host.split(".")[0].capitalize() if host else "This site"
