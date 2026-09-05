"""Freshness checks (Round-2 appendix D — recency half).

Machines and the humans tuning them prefer facts that look current. Stale copyright
years, old 'last updated' dates, and undated claims all lower confidence that a page
still reflects reality, making it less likely to be surfaced or repeated.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import List

from ..context import AuditContext
from ..report import Finding, scope_str
from ..htmlparse import Page

COPYRIGHT_SPAN_RE = re.compile(r"(?:©|&copy;|copyright)[^\n<]{0,40}", re.I)
YEAR_IN_SPAN_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
UPDATED_RE = re.compile(r"(?:last\s+updated|updated on|last\s+modified)[:\s]+([A-Za-z0-9 ,\-/]{6,20})", re.I)


def analyze(ctx: AuditContext) -> List[Finding]:
    now = _dt.datetime.now(_dt.timezone.utc)
    cfg = ctx.cfg
    findings: List[Finding] = []
    findings += _copyright_year(ctx.pages, now, cfg)
    findings += _stale_modified(ctx.pages, now, cfg)
    findings += _undated_articles(ctx.pages)
    return findings


def _copyright_year(pages: List[Page], now, cfg) -> List[Finding]:
    """Flag footer copyright years that predate last year with no other recent-date signal."""
    stale = []
    for p in pages:
        tail = p.visible_text[-800:]  # footer tends to be last
        years = []
        for span in COPYRIGHT_SPAN_RE.findall(tail):
            years.extend(int(y) for y in YEAR_IN_SPAN_RE.findall(span))
        if not years:
            continue
        newest = max(years)  # a "2001-2025" range is current, not stale
        if newest >= now.year - 1:
            continue
        # A recent "last updated" / date signal anywhere on the page means the copyright
        # year is just a founding year, not evidence of an abandoned page — skip it.
        if _has_recent_signal(p, now, cfg):
            continue
        stale.append((p.url, newest))
    if stale:
        oldest = min(stale, key=lambda x: x[1])
        return [Finding(
            title="Stale copyright year in footer",
            severity="medium",
            dimension="discoverability",
            category="freshness",
            evidence=f"{scope_str(len(stale), len(pages))} show a copyright year of {oldest[1]} (current year is {now.year}) with no other recent-date signal, e.g. {oldest[0]}.",
            why="A years-old copyright with no other recency signal reads as an abandoned site, which assistants "
                "trust and surface less than content that looks maintained.",
            how_to_fix="Auto-generate the footer year from the server clock and add a visible 'last updated' date where content genuinely changes.",
            scope=scope_str(len(stale), len(pages)),
            measurements={"stale_copyright_pages": len(stale), "oldest_year": oldest[1], "current_year": now.year},
            suggested_action_summary="Auto-generate the footer year from the server clock and refresh visible 'last updated' stamps; a years-old date signals an abandoned site.",
            suggested_action_priority="medium",
            affected_pages=[u for u, _ in stale],
        )]
    return []


def _stale_modified(pages: List[Page], now, cfg) -> List[Finding]:
    """Flag pages whose only dates are older than the configured staleness window."""
    stale = []
    stale_days = cfg.t("stale_days")
    for p in pages:
        dates = _all_dates(p)
        if dates and not _has_recent_signal(p, now, cfg):
            newest = max(dates)
            age_days = (now.date() - newest).days
            if age_days > stale_days:
                stale.append((p.url, newest.isoformat(), age_days))
    if stale:
        oldest = max(stale, key=lambda x: x[2])
        return [Finding(
            title="Content dates are more than two years old",
            severity="low",
            dimension="discoverability",
            category="freshness",
            evidence=f"{scope_str(len(stale), len(pages))} expose only old dates (newest {oldest[1]}, ~{oldest[2]//365}y ago), e.g. {oldest[0]}.",
            why="Content whose only dates are years old is discounted as possibly outdated, so it is surfaced and "
                "cited less — even when the information is still correct.",
            how_to_fix="Review the page; if still accurate, restate it and set an honest dateModified. If outdated, update the facts.",
            scope=scope_str(len(stale), len(pages)),
            measurements={"stale_pages": len(stale), "stale_days": int(stale_days)},
            suggested_action_summary="Review and refresh evergreen pages, then update dateModified. If content is still accurate, restate it so the recency signal is honest.",
            suggested_action_priority="low",
            confidence="medium",
            affected_pages=[u for u, _, _ in stale],
        )]
    return []


def _undated_articles(pages: List[Page]) -> List[Finding]:
    undated = []
    for p in pages:
        if re.search(r"/blog/|/news/|/article/", p.url) or re.search(r"min read", p.visible_text[:300], re.I):
            has_date = bool(_all_dates(p)) or "datepublished" in " ".join(str(o) for o in p.jsonld).lower()
            if not has_date:
                undated.append(p.url)
    if undated:
        return [Finding(
            title="Articles published without a visible date",
            severity="low",
            dimension="discoverability",
            category="freshness",
            evidence=f"{len(undated)} article-like page(s) expose no publication or modified date, e.g. {undated[0]}.",
            why="An undated article can't be placed in time, so assistants can't judge whether it is current and "
                "tend to discount it for time-sensitive questions.",
            how_to_fix="Show a clear published/updated date on every article and mirror it in datePublished/dateModified.",
            measurements={"undated_articles": len(undated)},
            suggested_action_summary="Show a clear published/updated date on every article and mirror it in datePublished/dateModified; undated content is discounted as unverifiable.",
            suggested_action_priority="low",
            affected_pages=undated,
        )]
    return []


def has_date_signal(p: Page) -> bool:
    """True if a page exposes any date/copyright signal freshness could reason about."""
    if _all_dates(p):
        return True
    tail = p.visible_text[-800:]
    if any(YEAR_IN_SPAN_RE.findall(span) for span in COPYRIGHT_SPAN_RE.findall(tail)):
        return True
    return bool(UPDATED_RE.search(p.visible_text) or "datepublished" in
                " ".join(str(o) for o in p.jsonld).lower())


def count_date_signal_pages(pages: List[Page]) -> int:
    """How many sampled pages carry a date signal (used by the coverage matrix)."""
    return sum(1 for p in pages if has_date_signal(p))


def _has_recent_signal(p: Page, now, cfg) -> bool:
    """True if the page shows any recent date/year — i.e. it looks maintained."""
    recent_year = str(now.year) in p.visible_text or str(now.year - 1) in p.visible_text
    if recent_year:
        return True
    window = cfg.t("recent_signal_days")
    for d in _all_dates(p):
        if (now.date() - d).days < window:
            return True
    return False


def _all_dates(p: Page):
    dates = []
    for y, m, d in ISO_DATE_RE.findall(p.raw_html):
        try:
            dates.append(_dt.date(int(y), int(m), int(d)))
        except ValueError:
            continue
    return dates
