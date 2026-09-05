"""Shared audit context passed to every check module.

Bundles the run configuration, the shared fetcher (for on-demand secondary requests like
robots.txt or sitemap), the crawl sample as parsed Pages, and the raw responses. Checks read
thresholds via ``ctx.cfg.t(name)`` — never inline literals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import http as _http
from . import htmlparse as _hp
from .config import CONFIG, Config


@dataclass
class AuditContext:
    """Everything a check needs: config, fetcher, raw responses, and parsed pages."""

    start_url: str
    cfg: Config
    fetcher: _http.Fetcher
    responses: List[_http.Response] = field(default_factory=list)
    pages: List[_hp.Page] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    external_lookups: bool = True

    @classmethod
    def build(cls, start_url: str, cfg: Config = CONFIG, external_lookups: bool = True,
              fetcher: Optional[_http.Fetcher] = None) -> "AuditContext":
        """Crawl a sample of *start_url* and return a populated context.

        Args:
            start_url: normalized http(s) target.
            cfg: run configuration (crawl limits, thresholds, profile).
            external_lookups: allow read-only off-site corroboration checks.
            fetcher: optional pre-built fetcher (defaults to one bound to *cfg*).
        """
        f = fetcher or _http.Fetcher(cfg=cfg)
        responses = _http.sample_pages(start_url, f, max_pages=cfg.max_pages)
        pages = [_hp.parse(r.final_url or r.url, r.body) for r in responses]
        return cls(start_url=start_url, cfg=cfg, fetcher=f, responses=responses, pages=pages,
                   external_lookups=external_lookups)

    def by_url(self) -> Dict[str, _hp.Page]:
        """Map of page URL -> parsed Page for the sampled pages."""
        return {p.url: p for p in self.pages}
