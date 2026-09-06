"""Provider-neutral web-corroboration abstraction.

The audit is deterministic and offline by default. When the user opts into external corroboration
(``--verify-external``), it may also consult a *corpus/search* provider to check whether the brand
has a footprint in the wider web an AI model learns from. This module defines the provider interface
so that source is **pluggable and never hard-wired to one vendor** — the exact property the brief
asks for.

Bundled providers:
  * ``CommonCrawlProvider`` — **keyless**, ToS-friendly: queries Common Crawl's public index to see
    whether the brand's domain was captured in the open crawl corpus (a proxy for "is this brand in
    the training-scale web?"). Bounded, wrapped, single lookup.
  * ``NullProvider`` — the honest default when nothing is configured or reachable: it reports
    ``status: "unavailable"`` rather than inventing corroboration.

Adding another provider (a search API, an enterprise index) is: subclass :class:`SearchProvider`,
implement ``corroborate``, register it in ``_REGISTRY``. Nothing else changes. No network is ever
touched unless the opt-in flag selected a network provider.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

_UA = "brand-ai-readiness-audit (+read-only corpus-presence check; opt-in)"
_TIMEOUT_S = 10
# Fallback index if the live collection list can't be fetched (kept recent; only a fallback).
_FALLBACK_INDEX = "CC-MAIN-2026-34"


class SearchProvider:
    """Interface for an off-site corroboration source. Implementations must be read-only,
    bounded, and must never raise — unknown/unreachable results are returned as ``unavailable``."""

    name = "base"

    def available(self) -> bool:
        return True

    def corroborate(self, brand: str, domain: str,
                    notes: Optional[List[str]] = None) -> Dict[str, Any]:
        raise NotImplementedError


class NullProvider(SearchProvider):
    """Deterministic default: declares that no corpus/search corroboration was performed."""

    name = "none"

    def corroborate(self, brand, domain, notes=None):
        return {"provider": "none", "status": "unavailable",
                "detail": "No corpus/search provider configured; corroboration limited to "
                          "Wikidata + declared links."}


class CommonCrawlProvider(SearchProvider):
    """Keyless presence check against Common Crawl's public index."""

    name = "commoncrawl"
    COLLINFO = "https://index.commoncrawl.org/collinfo.json"
    INDEX_TMPL = "https://index.commoncrawl.org/{index}-index"

    def corroborate(self, brand, domain, notes=None):
        notes = notes if notes is not None else []
        domain = (domain or "").strip().lower()
        if not domain:
            return {"provider": self.name, "status": "unavailable", "detail": "no domain to check."}
        index = self._latest_index()
        try:
            records = self._query(domain, index)
        except urllib.error.HTTPError as e:
            # Common Crawl returns 404 "No Captures found" when the domain isn't in the index —
            # that is a real *absent* signal, not a lookup failure.
            if e.code == 404:
                return _interpret([], index, domain)
            notes.append(f"Common Crawl lookup unavailable (HTTP {e.code}).")
            return {"provider": self.name, "status": "unavailable", "index": index,
                    "detail": "Common Crawl index returned an error; corroboration limited."}
        except Exception as e:  # transport/timeout → honest "unavailable", never a crash
            notes.append(f"Common Crawl lookup unavailable ({type(e).__name__}).")
            return {"provider": self.name, "status": "unavailable", "index": index,
                    "detail": "Common Crawl index was unreachable; corroboration limited."}
        return _interpret(records, index, domain)

    # -- network (thin; parsing is in the pure _interpret) --------------------------------
    def _latest_index(self) -> str:
        try:
            data = _get_json(self.COLLINFO)
            if isinstance(data, list) and data and data[0].get("id"):
                return str(data[0]["id"])
        except Exception:
            pass
        return _FALLBACK_INDEX

    def _query(self, domain: str, index: str) -> List[dict]:
        url = (self.INDEX_TMPL.format(index=index) + "?" +
               urllib.parse.urlencode({"url": domain, "matchType": "domain",
                                       "output": "json", "limit": "5"}))
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as r:
            body = r.read().decode("utf-8", "replace")
        out = []
        for line in body.splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
        return out


def _interpret(records: List[dict], index: str, domain: str) -> Dict[str, Any]:
    """Pure interpretation of Common Crawl index records (unit-testable, no network)."""
    if records:
        return {"provider": "commoncrawl", "status": "present", "index": index,
                "records": len(records),
                "detail": f"{domain} is captured in the Common Crawl open corpus ({index}) — "
                          "it has a footprint in the web AI models learn from."}
    return {"provider": "commoncrawl", "status": "absent", "index": index, "records": 0,
            "detail": f"{domain} was not found in the Common Crawl open corpus ({index}) — a thin "
                      "footprint in the training-scale web; expect weak model priors about the brand."}


_REGISTRY = {"none": NullProvider, "commoncrawl": CommonCrawlProvider}


def for_config(cfg) -> SearchProvider:
    """Return the provider selected by config (provider-neutral; defaults to Common Crawl)."""
    name = (getattr(cfg, "search_provider", "commoncrawl") or "commoncrawl").lower()
    return _REGISTRY.get(name, NullProvider)()


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8", "replace"))
