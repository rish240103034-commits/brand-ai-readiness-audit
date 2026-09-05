"""Shared test helpers: a network-free FakeFetcher and an AuditContext builder.

Lets every check be exercised against in-memory HTML fixtures with zero live requests.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from auditlib import http, htmlparse
from auditlib.config import make_config, Config
from auditlib.context import AuditContext


class FakeFetcher:
    """Stand-in for http.Fetcher that serves canned robots.txt / sitemap / page bodies."""

    def __init__(self, cfg: Config, robots: str = "", sitemap: Optional[str] = None,
                 extra: Optional[Dict[str, http.Response]] = None):
        self.cfg = cfg
        self._robots_body = robots
        self._sitemap = sitemap
        self._extra = extra or {}
        self.request_count = 0

    def _origin(self, url: str) -> str:
        import urllib.parse
        p = urllib.parse.urlsplit(url)
        return f"{p.scheme}://{p.netloc}"

    def fetch(self, url: str, method: str = "GET") -> http.Response:
        self.request_count += 1
        if url in self._extra:
            return self._extra[url]
        if url.endswith("/robots.txt"):
            body = self._robots_body
            return _resp(url, body, ok=bool(body), content_type="text/plain")
        if url.endswith("/sitemap.xml"):
            if self._sitemap is None:
                return _resp(url, "", ok=False, status=404)
            return _resp(url, self._sitemap, ok=True, content_type="application/xml")
        return _resp(url, "", ok=False, status=404)


def _resp(url: str, body: str, ok: bool = True, status: int = 200,
          content_type: str = "text/html", headers: Optional[Dict[str, str]] = None) -> http.Response:
    return http.Response(
        url=url, final_url=url, status=status if ok else (status or 200),
        headers=headers or {}, body=body, raw_len=len(body.encode("utf-8")),
        content_type=content_type, elapsed_ms=5, ok=ok, error=None if ok else f"http_{status}")


def make_ctx(pages: List[Tuple[str, str]], *, robots: str = "", sitemap: Optional[str] = None,
             responses: Optional[List[http.Response]] = None, profile: str = "balanced",
             cfg: Optional[Config] = None) -> AuditContext:
    """Build an AuditContext from (url, html) pairs without any network access.

    Args:
        pages: list of (url, html) tuples; the first is treated as the homepage.
        robots / sitemap: canned bodies served by the FakeFetcher for secondary fetches.
        responses: optional explicit Response objects (for status/header-specific tests);
                   must align 1:1 with *pages*.
        profile / cfg: scoring profile or an explicit Config.
    """
    cfg = cfg or make_config(profile)
    parsed = [htmlparse.parse(u, h) for u, h in pages]
    if responses is None:
        responses = [_resp(u, h) for u, h in pages]
    fetcher = FakeFetcher(cfg, robots=robots, sitemap=sitemap)
    return AuditContext(start_url=pages[0][0], cfg=cfg, fetcher=fetcher,
                        responses=responses, pages=parsed)


# --- reusable HTML fixtures -------------------------------------------------------
GOOD_HOME = """<!doctype html><html lang="en"><head>
<title>Acme Robotics — Industrial Automation</title>
<meta name="description" content="Acme Robotics builds industrial automation systems.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Organization","name":"Acme Robotics",
 "url":"https://acme.example","logo":"https://acme.example/logo.png",
 "sameAs":["https://www.linkedin.com/company/acme","https://www.wikidata.org/wiki/Q1"]}
</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"Acme Robotics"}</script>
</head><body>
<nav><a href="/products">Products</a><a href="/about">About</a><a href="/contact">Contact</a></nav>
<h1>Industrial automation that ships</h1>
<p>Acme Robotics designs and builds automation cells for manufacturing. Founded 2004 in Pune.</p>
<p>We serve automotive, electronics, and logistics customers across India and Europe.</p>
<a href="/contact" class="cta">Request a demo</a>
<a href="https://twitter.com/acme">Twitter</a>
<footer>© 2026 Acme Robotics</footer>
</body></html>"""

BARE_SPA = """<!doctype html><html><head><title>App</title>
<script src="/static/app.js"></script></head>
<body><div id="root"></div><noscript>You need to enable JavaScript to run this app.</noscript>
</body></html>"""

NO_META_PAGE = """<!doctype html><html><body>
<img src="/a.png"><img src="/b.png"><img src="/c.png"><img src="/d.png">
<p>Short.</p></body></html>"""
