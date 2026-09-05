"""Lightweight HTML inspection built on the standard-library html.parser.

Produces a structured, queryable view of a page (tags, text, meta, links, JSON-LD,
images, headings) without any third-party dependency. Intentionally tolerant of
malformed markup — real sites are messy.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

# Tags whose text content is not human-visible copy.
_NON_CONTENT = {"script", "style", "noscript", "template", "svg", "head"}


@dataclass
class Element:
    tag: str
    attrs: Dict[str, str]
    text: str = ""


@dataclass
class Page:
    url: str
    raw_html: str
    title: str = ""
    meta: Dict[str, str] = field(default_factory=dict)          # name/property -> content
    links: List[Dict[str, str]] = field(default_factory=list)   # {href,text,rel}
    images: List[Dict[str, str]] = field(default_factory=list)  # {src,alt}
    headings: List[Tuple[str, str]] = field(default_factory=list)  # (h1.., text)
    jsonld: List[dict] = field(default_factory=list)
    scripts_src: List[str] = field(default_factory=list)
    inline_script_bytes: int = 0
    visible_text: str = ""
    html_len: int = 0
    has_microdata: bool = False
    has_rdfa: bool = False
    lang: str = ""
    canonical: str = ""
    meta_robots: str = ""

    @property
    def visible_text_len(self) -> int:
        return len(self.visible_text)

    @property
    def word_count(self) -> int:
        return len(self.visible_text.split())


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.meta: Dict[str, str] = {}
        self.links: List[Dict[str, str]] = []
        self.images: List[Dict[str, str]] = []
        self.headings: List[Tuple[str, str]] = []
        self.jsonld_blocks: List[str] = []
        self.scripts_src: List[str] = []
        self.inline_script_bytes = 0
        self.has_microdata = False
        self.has_rdfa = False
        self.lang = ""
        self.canonical = ""
        self._text_parts: List[str] = []
        self._suppress_depth = 0
        self._cur_heading: Optional[str] = None
        self._heading_buf: List[str] = []
        self._cur_link: Optional[Dict[str, str]] = None
        self._link_buf: List[str] = []
        self._in_ld = False
        self._ld_buf: List[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"]
        if tag == "title":
            self._in_title = True
        if tag in _NON_CONTENT:
            self._suppress_depth += 1
        if tag == "script":
            src = a.get("src")
            if src:
                self.scripts_src.append(src)
            if a.get("type", "").lower() == "application/ld+json":
                self._in_ld = True
                self._ld_buf = []
        if tag == "meta":
            key = a.get("name") or a.get("property") or a.get("http-equiv")
            if key:
                self.meta[key.lower()] = a.get("content", "")
        if tag == "link":
            rel = a.get("rel", "").lower()
            if "canonical" in rel and a.get("href"):
                self.canonical = a["href"]
        if tag == "a" and a.get("href"):
            self._cur_link = {"href": a["href"], "rel": a.get("rel", ""), "text": ""}
            self._link_buf = []
        if tag == "img":
            self.images.append({"src": a.get("src", ""), "alt": a.get("alt", "__MISSING__" if "alt" not in a else "")})
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._cur_heading = tag
            self._heading_buf = []
        if "itemscope" in a or "itemprop" in a or "itemtype" in a:
            self.has_microdata = True
        if any(k in a for k in ("vocab", "typeof", "property")) and tag not in ("meta",):
            self.has_rdfa = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in _NON_CONTENT and self._suppress_depth > 0:
            self._suppress_depth -= 1
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.jsonld_blocks.append("".join(self._ld_buf))
        if tag == "a" and self._cur_link is not None:
            self._cur_link["text"] = " ".join(self._link_buf).strip()
            self.links.append(self._cur_link)
            self._cur_link = None
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._cur_heading:
            self.headings.append((self._cur_heading, " ".join(self._heading_buf).strip()))
            self._cur_heading = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self._ld_buf.append(data)
            return
        if self._suppress_depth == 0:
            stripped = data.strip()
            if stripped:
                self._text_parts.append(stripped)
                if self._cur_heading:
                    self._heading_buf.append(stripped)
                if self._cur_link is not None:
                    self._link_buf.append(stripped)

    def visible_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._text_parts)).strip()


def parse(url: str, html: str) -> Page:
    c = _Collector()
    try:
        c.feed(html or "")
    except Exception:
        pass  # tolerant: keep whatever we collected

    jsonld: List[dict] = []
    for block in c.jsonld_blocks:
        for obj in _loads_lenient(block):
            jsonld.append(obj)

    # inline script byte estimate (SPA heuristic input)
    inline = sum(len(m) for m in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html or "", re.S | re.I))

    page = Page(
        url=url,
        raw_html=html or "",
        title=(c.title or "").strip(),
        meta=c.meta,
        links=c.links,
        images=c.images,
        headings=c.headings,
        jsonld=jsonld,
        scripts_src=c.scripts_src,
        inline_script_bytes=inline,
        visible_text=c.visible_text(),
        html_len=len(html or ""),
        has_microdata=c.has_microdata,
        has_rdfa=c.has_rdfa,
        lang=c.lang,
        canonical=c.canonical,
        meta_robots=c.meta.get("robots", ""),
    )
    return page


def _loads_lenient(block: str) -> List[dict]:
    block = block.strip()
    if not block:
        return []
    out: List[dict] = []
    try:
        data = json.loads(block)
        if isinstance(data, list):
            out.extend(x for x in data if isinstance(x, dict))
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                out.extend(x for x in data["@graph"] if isinstance(x, dict))
            else:
                out.append(data)
    except Exception:
        # try to salvage multiple concatenated objects
        for m in re.finditer(r"\{.*?\}(?=\s*[\{\[]|\s*$)", block, re.S):
            try:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
    return out


def jsonld_types(page: Page) -> List[str]:
    types: List[str] = []
    for obj in page.jsonld:
        t = obj.get("@type")
        if isinstance(t, list):
            types.extend(str(x) for x in t)
        elif t:
            types.append(str(t))
    return types


def text_visible_ratio(page: Page) -> float:
    if page.html_len == 0:
        return 0.0
    return round(page.visible_text_len / page.html_len, 4)
