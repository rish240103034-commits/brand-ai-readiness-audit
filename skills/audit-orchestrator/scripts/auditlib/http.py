"""Read-only HTTP fetching, robots.txt compliance, SSRF-safe target validation, and
small-sample crawling.

Standard library only. Everything here is strictly GET, size-capped, timeout-bounded,
robots-respecting, retried with exponential backoff, and deterministic (sorted discovery,
fixed caps). Nothing writes to or authenticates against the target site.
"""
from __future__ import annotations

import gzip
import io
import ipaddress
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .config import CONFIG, Config
from .logutil import get_logger

LOG = get_logger("http")

# Back-compat aliases (some callers/tests reference these module constants).
USER_AGENT = CONFIG.user_agent
TIMEOUT = CONFIG.timeout
MAX_BYTES = CONFIG.max_bytes
DELAY = CONFIG.delay
MAX_PAGES = CONFIG.max_pages


@dataclass
class Response:
    """The outcome of a single read-only fetch (success or handled failure)."""

    url: str
    final_url: str
    status: int
    headers: Dict[str, str]
    body: str
    raw_len: int
    content_type: str
    elapsed_ms: int
    ok: bool
    error: Optional[str] = None
    from_cache: bool = False
    attempts: int = 1


# --- SSRF-safe target validation --------------------------------------------------
_PRIVATE_CLASSES = ("loopback", "private", "link-local", "reserved", "multicast")


def _ip_class(ip: "ipaddress._BaseAddress") -> str:
    """Classify an IP address into a routing category (or 'public').

    ``is_global`` is the deciding signal for public: some globally-routable addresses (notably
    the NAT64 well-known prefix 64:ff9b::/96) also carry ``is_reserved``, so checking the
    reserved flag first would wrongly block real sites reached over NAT64.
    """
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        return "link-local"
    if ip.is_private and not ip.is_global:
        return "private"
    if ip.is_global:
        return "public"
    if ip.is_multicast:
        return "multicast"
    if ip.is_reserved or ip.is_unspecified:
        return "reserved"
    return "reserved"


def classify_host(host: str) -> str:
    """Classify *host* as 'public', one of the private classes, or 'unresolvable'.

    Distinguishes an internal/loopback address (SSRF risk) from a name that simply doesn't
    resolve (a typo or a pasted Markdown link), so callers can report the right reason.
    """
    host = host.split(":")[0].strip("[]").lower()
    if host in ("localhost", "localhost.localdomain", ""):
        return "loopback"
    try:
        return _ip_class(ipaddress.ip_address(host))  # IP literal
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return "unresolvable"
    for info in infos:
        try:
            cls = _ip_class(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
        if cls != "public":
            return cls
    return "public"


def _is_private_host(host: str) -> bool:
    """Return True if *host* is a loopback/private/reserved address (SSRF-blocked)."""
    return classify_host(host) in _PRIVATE_CLASSES


def validate_target(raw: str, cfg: Config = CONFIG) -> Tuple[bool, str, str]:
    """Validate and normalize an audit target.

    Returns ``(ok, normalized_url, reason)``. ``ok`` is False for empty input, a non-http(s)
    scheme, a malformed URL, an unresolvable host, or (unless ``cfg.allow_private_hosts``) a
    private/loopback host.
    """
    if not raw or not raw.strip():
        return False, "", "empty target"
    url = ensure_url(raw)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False, url, f"unsupported scheme {parts.scheme!r} (only http/https)"
    if not parts.netloc:
        return False, url, "no host in URL"
    status = classify_host(parts.netloc)
    if status == "unresolvable" and not cfg.allow_private_hosts:
        return False, url, ("host does not resolve — check the URL (a full Markdown link, "
                            "surrounding brackets, or a typo?)")
    if status in _PRIVATE_CLASSES and not cfg.allow_private_hosts:
        return False, url, f"target resolves to a {status} address (blocked for SSRF safety)"
    return True, url, ""


def host_of(url: str) -> str:
    """Return the registrable-ish host (``www.`` stripped) for reporting."""
    net = urllib.parse.urlsplit(url).netloc
    return net[4:] if net.startswith("www.") else net or url


@dataclass
class Fetcher:
    """A polite, caching, robots-aware read-only fetcher scoped to one audit run."""

    cfg: Config = CONFIG
    _cache: Dict[str, Response] = field(default_factory=dict)
    _robots: Dict[str, urllib.robotparser.RobotFileParser] = field(default_factory=dict)
    _last_hit: Dict[str, float] = field(default_factory=dict)
    request_count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def respect_robots(self) -> bool:
        """Whether robots.txt rules are enforced for this run."""
        return self.cfg.respect_robots

    # -- robots.txt ---------------------------------------------------------------
    def _origin(self, url: str) -> str:
        p = urllib.parse.urlsplit(url)
        return f"{p.scheme}://{p.netloc}"

    def robots(self, url: str) -> urllib.robotparser.RobotFileParser:
        """Fetch and cache the robots.txt parser for *url*'s origin (permissive on error)."""
        origin = self._origin(url)
        if origin in self._robots:
            return self._robots[origin]
        rp = urllib.robotparser.RobotFileParser()
        robots_url = origin + "/robots.txt"
        try:
            req = urllib.request.Request(robots_url, headers={"User-Agent": self.cfg.user_agent})
            with urllib.request.urlopen(req, timeout=self.cfg.timeout) as resp:
                data = resp.read(self.cfg.max_bytes).decode("utf-8", "replace")
            rp.parse(data.splitlines())
        except Exception as e:
            LOG.debug("no robots.txt for %s (%s); allowing all", origin, e)
            rp.parse([])
        self._robots[origin] = rp
        return rp

    def allowed(self, url: str) -> bool:
        """Return True if robots.txt permits fetching *url* for our User-Agent."""
        if not self.respect_robots:
            return True
        try:
            return self.robots(url).can_fetch(self.cfg.user_agent, url)
        except Exception:
            return True

    def crawl_delay(self, url: str) -> float:
        """Effective per-host delay: the larger of our default and robots' Crawl-delay."""
        try:
            cd = self.robots(url).crawl_delay(self.cfg.user_agent)
            if cd:
                return max(self.cfg.delay, float(cd))
        except Exception:
            pass
        return self.cfg.delay

    # -- fetching -----------------------------------------------------------------
    def _throttle(self, url: str) -> None:
        """Sleep as needed to honor the per-host crawl delay."""
        host = urllib.parse.urlsplit(url).netloc
        wait = self.crawl_delay(url)
        last = self._last_hit.get(host)
        if last is not None:
            elapsed = time.time() - last
            if elapsed < wait:
                time.sleep(wait - elapsed)
        self._last_hit[host] = time.time()

    def _build_request(self, url: str, method: str) -> urllib.request.Request:
        """Construct the read-only GET/HEAD request with our headers."""
        headers = {
            "User-Agent": self.cfg.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip",
        }
        return urllib.request.Request(url, headers=headers, method=method)

    def _parse_success(self, url: str, r, start: float, attempts: int) -> Response:
        """Turn a successful urlopen response into a Response (decoding text safely)."""
        raw = r.read(self.cfg.max_bytes)
        if r.headers.get("Content-Encoding", "").lower() == "gzip":
            try:
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            except Exception as e:
                LOG.debug("gzip decode failed for %s: %s", url, e)
        hdrs = {k.lower(): v for k, v in r.headers.items()}
        ctype = hdrs.get("content-type", "")
        charset = _charset(ctype) or _charset_from_html(raw) or "utf-8"
        body = raw.decode(charset, "replace") if _is_texty(ctype) else ""
        return Response(
            url=url, final_url=r.geturl(), status=r.status, headers=hdrs, body=body,
            raw_len=len(raw), content_type=ctype,
            elapsed_ms=int((time.time() - start) * 1000), ok=200 <= r.status < 400,
            attempts=attempts)

    def fetch(self, url: str, method: str = "GET") -> Response:
        """Fetch *url* read-only with caching, robots enforcement, and retry+backoff.

        Never raises: transport failures, HTTP errors, and robots blocks are all returned as
        a Response with ``ok=False`` and an ``error`` tag, so callers degrade gracefully.
        """
        with self._lock:
            cached = self._cache.get(url)
        if cached is not None:
            return Response(**{**cached.__dict__, "from_cache": True})

        if self.respect_robots and not self.allowed(url):
            LOG.debug("robots blocked %s", url)
            return self._store(url, self._error_response(url, 0, "blocked_by_robots"))

        self._throttle(url)
        start = time.time()
        last_err = "fetch_failed"
        for attempt in range(1, self.cfg.max_retries + 2):  # 1 initial + N retries
            try:
                with urllib.request.urlopen(self._build_request(url, method),
                                            timeout=self.cfg.timeout) as r:
                    resp = self._parse_success(url, r, start, attempt)
                    self._bump()
                    return self._store(url, resp)
            except urllib.error.HTTPError as e:
                # 4xx/5xx are definitive answers, not transient — do not retry.
                hdrs = {k.lower(): v for k, v in (e.headers or {}).items()}
                self._bump()
                return self._store(url, Response(
                    url=url, final_url=url, status=e.code, headers=hdrs, body="",
                    raw_len=0, content_type=hdrs.get("content-type", ""),
                    elapsed_ms=int((time.time() - start) * 1000), ok=False,
                    error=f"http_{e.code}", attempts=attempt))
            except Exception as e:  # timeout, DNS, TLS reset, etc. — retry with backoff
                last_err = str(e)
                if attempt <= self.cfg.max_retries:
                    backoff = self.cfg.backoff_base * (2 ** (attempt - 1))
                    LOG.debug("fetch %s attempt %d failed (%s); backing off %.1fs",
                              url, attempt, e, backoff)
                    time.sleep(backoff)
                else:
                    LOG.warning("fetch %s failed after %d attempts: %s", url, attempt, e)
        return self._store(url, self._error_response(
            url, 0, last_err, elapsed_ms=int((time.time() - start) * 1000),
            attempts=self.cfg.max_retries + 1))

    def _store(self, url: str, resp: Response) -> Response:
        """Cache and return a response (thread-safe)."""
        with self._lock:
            self._cache[url] = resp
        return resp

    def _bump(self) -> None:
        """Atomically increment the request counter."""
        with self._lock:
            self.request_count += 1

    @staticmethod
    def _error_response(url: str, status: int, error: str, elapsed_ms: int = 0,
                        attempts: int = 1) -> Response:
        """Construct a uniform failure Response."""
        return Response(url=url, final_url=url, status=status, headers={}, body="", raw_len=0,
                        content_type="", elapsed_ms=elapsed_ms, ok=False, error=error,
                        attempts=attempts)


# --- text/encoding helpers --------------------------------------------------------
def _charset(content_type: str) -> Optional[str]:
    """Extract a charset from a Content-Type header, if present."""
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    return m.group(1) if m else None


def _charset_from_html(raw: bytes) -> Optional[str]:
    """Sniff a charset from the first bytes of an HTML document."""
    head = raw[:2048].decode("ascii", "replace")
    m = re.search(r'charset=["\']?([\w\-]+)', head, re.I)
    return m.group(1) if m else None


def _is_texty(content_type: str) -> bool:
    """Return True for content types we should decode as text."""
    ct = (content_type or "").lower()
    return "text/" in ct or "html" in ct or "xml" in ct or "json" in ct or ct == ""


# --- URL helpers ------------------------------------------------------------------
_TWO_LABEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "co.in", "net.in", "org.in", "gov.in",
    "co.jp", "com.au", "com.br", "co.nz", "com.sg", "co.za",
}


def same_registrable_domain(a: str, b: str) -> bool:
    """Loose eTLD+1 comparison (handles common two-label public suffixes)."""
    ha = urllib.parse.urlsplit(a).netloc.lower().split(":")[0]
    hb = urllib.parse.urlsplit(b).netloc.lower().split(":")[0]
    return _reg(ha) == _reg(hb)


def _bare_host(url: str) -> str:
    """Hostname without port or a leading ``www.`` (so www and apex compare equal)."""
    net = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    return net[4:] if net.startswith("www.") else net


def same_host(a: str, b: str) -> bool:
    """Exact-host comparison (apex == www), so subdomains are distinct properties."""
    return _bare_host(a) == _bare_host(b)


def scope_predicate(scope: str):
    """Return the in-scope test for a crawl scope: 'host' (default) or 'domain'."""
    return same_registrable_domain if scope == "domain" else same_host


def _reg(host: str) -> str:
    """Best-effort registrable domain (eTLD+1) for a hostname."""
    host = host[4:] if host.startswith("www.") else host
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    last2 = ".".join(parts[-2:])
    last3 = ".".join(parts[-3:])
    return last3 if last2 in _TWO_LABEL_SUFFIXES else last2


def ensure_url(raw: str) -> str:
    """Turn user input into a fetchable URL, adding ``https://`` when no scheme is given.

    Use for the top-level target (a bare domain like ``example.com`` is common); use
    :func:`normalize` for link resolution where a missing scheme should be rejected.
    """
    raw = (raw or "").strip()
    if not raw:
        return raw
    # Tolerate a pasted Markdown link `[text](url)` — take the url in parens.
    md = re.match(r"^\[[^\]]*\]\(\s*([^)\s]+)\s*\)$", raw)
    if md:
        raw = md.group(1)
    # Strip common wrappers: angle brackets, backticks, quotes.
    raw = raw.strip().strip("`<>\"' ")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", raw):
        raw = "https://" + raw.lstrip("/")
    return normalize(raw) or raw


def normalize(url: str, base: Optional[str] = None) -> Optional[str]:
    """Normalize/resolve a URL; return None for non-http(s) or unparyable links."""
    try:
        if base:
            url = urllib.parse.urljoin(base, url)
        # Encode spaces and strip control chars so slightly-malformed links stay fetchable
        # (urllib rejects raw control characters / spaces in a URL).
        url = "".join(ch for ch in url if ord(ch) >= 0x20 and ch != "\x7f").replace(" ", "%20")
        p = urllib.parse.urlsplit(url)
        if p.scheme not in ("http", "https"):
            return None
        path = p.path or "/"
        return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, ""))  # drop fragment
    except Exception:
        return None


# --- discovery / sampling ---------------------------------------------------------
def discover_sitemap_urls(start_url: str, fetcher: Fetcher, limit: int = 50,
                          in_scope=None) -> List[str]:
    """Read sitemap locations from robots.txt and /sitemap.xml; return a sample of page URLs."""
    in_scope = in_scope or same_registrable_domain
    origin = fetcher._origin(start_url)
    candidates: List[str] = []
    try:
        rp = fetcher.robots(start_url)
        sm = getattr(rp, "site_maps", None)
        if callable(sm):
            candidates.extend(rp.site_maps() or [])
    except Exception:
        pass
    candidates.append(origin + "/sitemap.xml")
    seen_maps = set()
    urls: List[str] = []
    for sm_url in candidates:
        if sm_url in seen_maps:
            continue
        seen_maps.add(sm_url)
        r = fetcher.fetch(sm_url)
        if not r.ok or "xml" not in (r.content_type.lower() + r.body[:100].lower()):
            continue
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.body, re.I):
            if loc.endswith(".xml") and len(seen_maps) < 5:
                candidates.append(loc)  # nested sitemap index
            else:
                n = normalize(loc)
                if n and in_scope(n, start_url):
                    urls.append(n)
        if len(urls) >= limit:
            break
    out, seen = [], set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:limit]


def sample_pages(start_url: str, fetcher: Fetcher, max_pages: Optional[int] = None) -> List[Response]:
    """Deterministic breadth-first sample: homepage + internal links + sitemap seeds.

    Returns fetched HTML Responses, capped at ``max_pages`` (defaults to the fetcher's config),
    robots-respected and de-duplicated.
    """
    max_pages = max_pages or fetcher.cfg.max_pages
    in_scope = scope_predicate(getattr(fetcher.cfg, "crawl_scope", "host"))
    start = normalize(start_url) or start_url
    home = fetcher.fetch(start)
    results: List[Response] = []
    if home.ok and _is_html(home):
        results.append(home)

    # Anchor scope to the host we actually landed on (after any redirect).
    scope_base = home.final_url or start
    from_home = _internal_links(home, scope_base, in_scope) if home.ok else []
    from_map = discover_sitemap_urls(scope_base, fetcher, limit=max_pages * 2, in_scope=in_scope)

    queue: List[str] = []
    seen = {home.final_url, start}
    for u in from_home + from_map:
        if u not in seen:
            seen.add(u)
            queue.append(u)

    for u in queue:
        if len(results) >= max_pages:
            break
        r = fetcher.fetch(u)
        if r.ok and _is_html(r):
            results.append(r)
    return results


def _is_html(resp: Response) -> bool:
    """Return True if a response looks like an HTML document."""
    ct = (resp.content_type or "").lower()
    return "html" in ct or (ct == "" and "<html" in resp.body[:2000].lower())


def _internal_links(resp: Response, base: str, in_scope=None) -> List[str]:
    """Extract sorted, de-duplicated in-scope page links from a response."""
    in_scope = in_scope or same_registrable_domain
    links = re.findall(r'href\s*=\s*["\']([^"\'#]+)["\']', resp.body or "", re.I)
    out, seen = [], set()
    for href in links:
        n = normalize(href, base=resp.final_url or base)
        if not n or not in_scope(n, base):
            continue
        if re.search(r"\.(png|jpe?g|gif|svg|webp|css|js|ico|pdf|zip|mp4|woff2?)(\?|$)", n, re.I):
            continue
        if n not in seen:
            seen.add(n)
            out.append(n)
    return sorted(out)
