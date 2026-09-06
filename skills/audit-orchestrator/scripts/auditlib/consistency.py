"""Hallucination-risk scan — audit the site *against itself*.

AI assistants state wrong facts about a brand largely when the brand's own pages disagree with
each other: a different founding year on the About page vs. the homepage schema, two phone numbers,
two social handles for one platform. Those internal contradictions are what a model resolves
arbitrarily (and often wrongly). This module extracts the facts that should be **singular** across
the crawled sample and flags the disagreements as hallucination triggers.

Conservative by design: only facts that are genuinely expected to be unique are compared, values
are normalized before comparison, and findings are medium/low confidence (text extraction is
heuristic). Brand/legal-name consistency is handled in ``corroboration`` and not duplicated here.
Returns (block, [Finding]).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .context import AuditContext
from .report import Finding
from .htmlparse import Page, jsonld_types

# "since" is too generic (appears in article prose); require an explicit founding verb.
_FOUNDED_RE = re.compile(r"\b(?:founded|established|est\.?|incorporated)\b[^.\d]{0,15}(19\d{2}|20\d{2})", re.I)
_SOCIAL_HANDLE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(twitter|x|instagram|facebook|linkedin|youtube|tiktok|github)\.com/"
    r"(?:company/|@)?([A-Za-z0-9_.\-]{2,40})", re.I)
# Path segments that are NOT brand handles (share/intent URLs, LinkedIn sub-namespaces, etc.).
_SKIP_HANDLE = {
    "share", "sharer", "shareoffsite", "sharearticle", "sharing", "intent", "home", "hashtag",
    "search", "explore", "watch", "channel", "user", "c", "p", "reel", "pin", "login", "privacy",
    "in", "pub", "feed", "posts", "jobs", "showcase", "school", "groups", "learning", "pulse",
    "dialog", "plugins", "embed", "i", "messages", "settings", "notifications", "help", "legal",
    "about", "tos", "policies", "profile", "results",
}


def scan(ctx: AuditContext) -> Tuple[Dict[str, Any], List[Finding]]:
    pages = ctx.pages
    if not pages:
        return {"risk": "none", "conflicts": [], "facts_checked": []}, []
    conflicts: List[Dict[str, Any]] = []
    conflicts += _founding_year(pages)
    conflicts += _social(pages)
    # NB: phone numbers are deliberately NOT compared — a brand legitimately lists several
    # (sales / support / regional), so distinct numbers are not a contradiction.

    findings = [_finding(c) for c in conflicts]
    high = any(c["severity"] == "medium" for c in conflicts)
    risk = "none" if not conflicts else ("elevated" if high else "low")
    block = {
        "risk": risk,
        "conflicts": conflicts,
        "facts_checked": ["founding year", "social handles"],
        "note": ("Facts that disagree across the site can be resolved arbitrarily by an assistant — "
                 "reconcile each to one canonical value." if conflicts else
                 "No self-contradictions found among the facts checked."),
    }
    return block, findings


def _founding_year(pages: List[Page]) -> List[Dict[str, Any]]:
    """Founding year is a brand-identity fact — read it only where a brand states it (homepage,
    About page, or Organization schema), never from arbitrary article bodies (which mention many
    years and would produce false conflicts)."""
    values: Dict[str, List[str]] = {}
    identity_pages = [p for p in pages
                      if p is pages[0] or re.search(r"/(about|company|who-we-are)", p.url, re.I)]
    for p in identity_pages:
        for m in _FOUNDED_RE.findall(p.visible_text):
            values.setdefault(m, []).append(p.url)
    for p in pages:  # schema foundingDate is authoritative wherever it appears
        for obj in p.jsonld:
            fd = str(obj.get("foundingDate", ""))
            ym = re.match(r"(19\d{2}|20\d{2})", fd)
            if ym:
                values.setdefault(ym.group(1), []).append(p.url + " (schema)")
    return _mk_conflict("founding_year", "Founding year", values, "medium") if len(values) > 1 else []


def _social(pages: List[Page]) -> List[Dict[str, Any]]:
    by_platform: Dict[str, Dict[str, List[str]]] = {}
    for p in pages:
        for a in p.links:
            m = _SOCIAL_HANDLE_RE.search(a.get("href", ""))
            if not m:
                continue
            plat = m.group(1).lower().replace("x", "twitter")
            handle = m.group(2).lower().strip("/")
            if handle in _SKIP_HANDLE or len(handle) < 2:
                continue
            by_platform.setdefault(plat, {}).setdefault(handle, []).append(p.url)
    out = []
    for plat, handles in by_platform.items():
        if len(handles) > 1:
            out += _mk_conflict(f"social_{plat}", f"{plat.title()} handle", handles, "low")
    return out


def _mk_conflict(ctype, label, values: Dict[str, List[str]], severity: str) -> List[Dict[str, Any]]:
    vals = [{"value": v, "examples": srcs[:3], "pages": len(srcs)} for v, srcs in sorted(values.items())]
    return [{"type": ctype, "label": label, "severity": severity, "values": vals}]


def _finding(c: Dict[str, Any]) -> Finding:
    shown = ", ".join(f'"{v["value"]}"' for v in c["values"][:4])
    ex = c["values"][0]["examples"][0] if c["values"] and c["values"][0]["examples"] else ""
    return Finding(
        title=f"Conflicting {c['label'].lower()} across the site",
        severity=c["severity"], dimension="discoverability", category="entity-identity",
        confidence="medium",
        evidence=f"The {c['label'].lower()} appears with {len(c['values'])} different values across the sample: {shown}. e.g. {ex}.",
        why="When the same fact disagrees across your own pages, an assistant has no canonical value to "
            "trust and may repeat whichever it saw first — a direct cause of wrong answers about the brand.",
        how_to_fix=f"Reconcile the {c['label'].lower()} to one canonical value everywhere (visible text and "
                   "schema), and expose it once in Organization structured data.",
        measurements={"distinct_values": len(c["values"]), "fact": c["type"]},
        suggested_action_summary=f"State one canonical {c['label'].lower()} across the whole site and in schema.",
        suggested_action_priority=c["severity"],
        affected_pages=[e for v in c["values"] for e in v["examples"]][:10],
    )
