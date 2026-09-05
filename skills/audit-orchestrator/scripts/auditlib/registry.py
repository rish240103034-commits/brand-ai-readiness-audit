"""Skill auto-discovery for the orchestrator.

Instead of hardcoding which checks to run, the orchestrator scans the ``skills/`` tree,
validates each ``SKILL.md`` against the agentskills.io essentials (name + description), reads
the marketplace manifest to find the single entrypoint, and binds each non-entrypoint skill
to its check functions via a ``metadata.checks`` list in its SKILL.md frontmatter. A new skill
can therefore be dropped in — folder + SKILL.md + manifest entry — without editing run_audit.py.
Non-compliant skills are skipped with a warning.
"""
from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

from . import frontmatter
from .logutil import get_logger

LOG = get_logger("registry")

AnalyzeFn = Callable[["object"], list]


@dataclass
class SkillSpec:
    """A discovered, validated skill and its bound check callables."""

    id: str
    path: str
    entrypoint: bool = False
    dimension: str = "discoverability"
    analyze_fns: List[AnalyzeFn] = field(default_factory=list)
    summary: str = ""


def find_marketplace_root(start: Optional[str] = None) -> Optional[str]:
    """Walk upward from *start* (or this file) to find the dir containing marketplace.json."""
    d = start or os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isfile(os.path.join(d, "marketplace.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _load_manifest(root: str) -> dict:
    """Load marketplace.json (empty dict on failure)."""
    try:
        with open(os.path.join(root, "marketplace.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:  # pragma: no cover - defensive
        LOG.warning("could not read marketplace.json: %s", e)
        return {}


def validate_skill_md(fm: dict) -> List[str]:
    """Return a list of agentskills.io compliance problems (empty if compliant)."""
    problems = []
    if not fm.get("name"):
        problems.append("missing 'name'")
    if not fm.get("description"):
        problems.append("missing 'description'")
    return problems


def _bind_checks(check_names: Sequence[str]) -> List[AnalyzeFn]:
    """Import ``auditlib.checks.<name>`` for each name and collect its ``analyze`` callable."""
    fns: List[AnalyzeFn] = []
    for name in check_names:
        try:
            mod = importlib.import_module(f"auditlib.checks.{name}")
            fn = getattr(mod, "analyze")
            fns.append(fn)
        except Exception as e:
            LOG.warning("could not bind check %r: %s", name, e)
    return fns


def discover_skills(root: Optional[str] = None) -> List[SkillSpec]:
    """Discover, validate, and bind all non-entrypoint skills, in manifest order."""
    root = root or find_marketplace_root()
    if not root:
        LOG.error("marketplace root not found")
        return []
    manifest = _load_manifest(root)
    entries = manifest.get("skills", [])
    specs: List[SkillSpec] = []
    for entry in entries:
        sid = entry.get("id", "")
        rel = entry.get("path", os.path.join("skills", sid))
        is_entry = bool(entry.get("entrypoint"))
        skill_dir = os.path.join(root, rel)
        md_path = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isfile(md_path):
            LOG.warning("skill %r: no SKILL.md at %s — skipped", sid, md_path)
            continue
        with open(md_path, encoding="utf-8") as fh:
            fm = frontmatter.parse(fh.read())
        problems = validate_skill_md(fm)
        if problems:
            LOG.warning("skill %r: non-compliant SKILL.md (%s) — skipped", sid, "; ".join(problems))
            continue
        if is_entry:
            continue  # the entrypoint composes others; it has no checks of its own
        meta = fm.get("metadata", {}) if isinstance(fm.get("metadata"), dict) else {}
        check_names = meta.get("checks", [])
        if isinstance(check_names, str):
            check_names = [check_names]
        fns = _bind_checks(check_names)
        if not fns:
            LOG.warning("skill %r: no bindable checks in metadata.checks — skipped", sid)
            continue
        specs.append(SkillSpec(
            id=sid, path=skill_dir, entrypoint=False,
            dimension=str(meta.get("dimension", entry.get("dimension", "discoverability"))),
            analyze_fns=fns, summary=str(entry.get("summary", "")),
        ))
    return specs


def select_skills(skills: List[SkillSpec], only: Optional[Sequence[str]]) -> List[SkillSpec]:
    """Filter discovered skills by id (accepts ids with or without the ``-audit`` suffix)."""
    if not only:
        return skills
    wanted = {s.strip().lower() for s in only}
    out = []
    for s in skills:
        sid = s.id.lower()
        if sid in wanted or sid.replace("-audit", "") in wanted:
            out.append(s)
    unknown = wanted - {s.id.lower() for s in out} - {s.id.lower().replace("-audit", "") for s in out}
    for u in sorted(unknown):
        LOG.warning("unknown skill id in --skills: %r", u)
    return out
