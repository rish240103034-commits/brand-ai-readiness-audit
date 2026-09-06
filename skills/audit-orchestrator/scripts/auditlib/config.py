"""Centralized configuration for the whole marketplace.

Every tunable — network behavior, crawl limits, the User-Agent, retry/backoff, and every
check threshold — lives here, so nothing is magic-numbered inline. A single immutable
``Config`` is threaded through the crawl and every check via the audit context.

Profiles (``strict`` | ``balanced`` | ``lenient``) overlay threshold sets for different site
types; ``Config.derive()`` produces a modified copy for CLI overrides.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Mapping

# --- Network / crawl defaults -----------------------------------------------------
DEFAULT_USER_AGENT = "brand-ai-readiness-audit/2.5 (+read-only audit bot; respects robots.txt)"
DEFAULT_TIMEOUT = 15            # seconds per request
DEFAULT_MAX_BYTES = 3_000_000   # 3 MB body cap
DEFAULT_DELAY = 0.4             # polite seconds between requests to one host
DEFAULT_MAX_PAGES = 12          # pages sampled for a full audit
DEFAULT_MAX_RETRIES = 2         # additional attempts on transient failure
DEFAULT_BACKOFF_BASE = 0.5      # exponential backoff base (0.5, 1.0, 2.0, …)

# --- Check thresholds (the "balanced" baseline) -----------------------------------
# Named so every check reads a value instead of embedding a literal.
BASE_THRESHOLDS: Dict[str, float] = {
    # crawl / render
    "render_spa_max_words": 120,
    "render_spa_hard_max_words": 60,
    "render_script_ratio": 4,
    "render_thin_words": 50,
    "render_thin_html": 2000,
    # extractability
    "alt_missing_ratio": 0.30,
    "alt_missing_min": 3,
    "text_in_image_min_images": 5,
    "text_in_image_max_words": 120,
    "text_in_image_min_html": 3000,
    "pdf_link_min": 3,
    # freshness
    "stale_days": 730,
    "recent_signal_days": 400,
    # engagement
    "page_weight_bytes": 1_500_000,
    "page_weight_scripts": 40,
    "slow_ms": 3000,
    "wall_words": 900,
    "wall_max_headings": 1,
    "deadend_min_links": 3,
    "deep_path_segments": 3,
    "deep_min_pages": 3,
    "viewport_min_fraction": 0.5,
    "render_blocking_head_max": 6,   # blocking CSS+JS in <head> above which first render stalls
    "generic_link_min": 4,           # min "click here"/"read more" links before flagging
    "empty_link_ratio": 0.25,        # share of links with no discernible text
    "empty_link_min": 4,
    "login_wall_min_pages": 2,       # min content pages behind an apparent login before flagging
    "unlabeled_controls_min": 2,     # min form controls with no associable label before flagging
}

# Profile overlays: multiply/replace selected thresholds. "strict" flags more aggressively
# (lower tolerances), "lenient" flags less. Only listed keys change.
PROFILE_OVERLAYS: Dict[str, Dict[str, float]] = {
    "balanced": {},
    "strict": {
        "render_spa_max_words": 160,
        "render_thin_words": 80,
        "alt_missing_ratio": 0.20,
        "slow_ms": 2000,
        "page_weight_bytes": 1_200_000,
        "wall_words": 700,
        "stale_days": 540,
    },
    "lenient": {
        "render_spa_max_words": 80,
        "render_thin_words": 30,
        "alt_missing_ratio": 0.50,
        "slow_ms": 5000,
        "page_weight_bytes": 2_500_000,
        "wall_words": 1200,
        "stale_days": 1095,
    },
}

VALID_PROFILES = tuple(PROFILE_OVERLAYS.keys())


@dataclass(frozen=True)
class Config:
    """Immutable run configuration shared across the crawl and all checks."""

    user_agent: str = DEFAULT_USER_AGENT
    timeout: int = DEFAULT_TIMEOUT
    max_bytes: int = DEFAULT_MAX_BYTES
    delay: float = DEFAULT_DELAY
    max_pages: int = DEFAULT_MAX_PAGES
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_base: float = DEFAULT_BACKOFF_BASE
    analysis_timeout: int = 240    # global guard (s) for the analysis phase; well under 5 min
    max_workers: int = 6           # thread pool size for concurrent skill execution
    # Crawl scope: "host" audits only the exact host given (treating support./blog./shop.
    # subdomains as separate properties — fair attribution); "domain" spans the whole
    # registrable domain. Host-scoped by default so a brand isn't scored on third-party
    # subdomains (help desks, status pages) it doesn't hand-build.
    crawl_scope: str = "host"
    respect_robots: bool = True
    allow_private_hosts: bool = False  # SSRF guard; True only for local testing
    profile: str = "balanced"
    thresholds: Mapping[str, float] = field(default_factory=lambda: dict(BASE_THRESHOLDS))

    def t(self, name: str) -> float:
        """Return a named check threshold (raises KeyError if the name is unknown)."""
        return self.thresholds[name]

    def derive(self, **overrides: Any) -> "Config":
        """Return a copy with the given non-None fields overridden.

        ``None`` values are ignored so CLI defaults (unset flags) never clobber config.
        A ``profile`` override re-applies the matching threshold overlay.
        """
        clean = {k: v for k, v in overrides.items() if v is not None}
        profile = clean.pop("profile", self.profile)
        thresholds = dict(BASE_THRESHOLDS)
        thresholds.update(PROFILE_OVERLAYS.get(profile, {}))
        # allow explicit per-key threshold overrides too
        thresholds.update(clean.pop("thresholds", {}))
        return replace(self, profile=profile, thresholds=thresholds, **clean)


def make_config(profile: str = "balanced", **overrides: Any) -> Config:
    """Build a Config for a named profile with optional field overrides."""
    if profile not in VALID_PROFILES:
        raise ValueError(f"unknown profile {profile!r}; choose from {VALID_PROFILES}")
    thresholds = dict(BASE_THRESHOLDS)
    thresholds.update(PROFILE_OVERLAYS[profile])
    base = Config(profile=profile, thresholds=thresholds)
    return base.derive(**overrides) if overrides else base


# The default configuration used unless a caller derives its own.
CONFIG = make_config("balanced")
