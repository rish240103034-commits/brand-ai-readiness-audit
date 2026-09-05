"""Minimal, dependency-free parser for SKILL.md YAML frontmatter.

Not a general YAML implementation — it handles exactly the constructs this marketplace's
SKILL.md files use: ``key: value`` scalars, folded block scalars (``>-``/``>``/``|``), inline
lists (``[a, b]``), block lists (``- item``), and a single level of nested mapping (used by
``metadata:``). That is enough to validate a skill and read its check bindings without adding
a third-party dependency.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

_FM_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*", re.S)


def split_frontmatter(text: str) -> Tuple[Optional[str], str]:
    """Return (frontmatter_text, body). frontmatter_text is None if no block is present."""
    m = _FM_RE.match(text or "")
    if not m:
        return None, text or ""
    return m.group(1), (text or "")[m.end():]


def parse(text: str) -> Dict[str, Any]:
    """Parse the frontmatter block of a SKILL.md into a dict (empty if none)."""
    fm, _ = split_frontmatter(text)
    if fm is None:
        return {}
    return _parse_mapping(fm.splitlines(), base_indent=0)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_mapping(lines: List[str], base_indent: int) -> Dict[str, Any]:
    """Parse a block of lines at *base_indent* into a mapping."""
    result: Dict[str, Any] = {}
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        if _indent(raw) != base_indent:
            i += 1
            continue
        m = re.match(r"^(\s*)([\w][\w\-]*):\s?(.*)$", raw)
        if not m:
            i += 1
            continue
        key, rest = m.group(2), m.group(3).strip()
        # Gather the indented block that follows this key.
        block, j = [], i + 1
        while j < n and (not lines[j].strip() or _indent(lines[j]) > base_indent):
            block.append(lines[j])
            j += 1

        if rest in (">", ">-", ">+", "|", "|-", "|+"):
            result[key] = " ".join(b.strip() for b in block if b.strip())
            i = j
        elif rest == "" and block:
            non_empty = [b for b in block if b.strip()]
            if non_empty and all(b.strip().startswith("- ") for b in non_empty):
                result[key] = [b.strip()[2:].strip().strip("'\"") for b in non_empty]
            elif non_empty and all(":" in b for b in non_empty):
                child_indent = _indent(non_empty[0])
                result[key] = _parse_mapping(block, child_indent)
            else:  # implicit folded scalar
                result[key] = " ".join(b.strip() for b in non_empty)
            i = j
        else:
            result[key] = _scalar_or_list(rest)
            i += 1
    return result


def _scalar_or_list(value: str) -> Any:
    """Parse an inline scalar or ``[a, b, c]`` list value."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
    return value.strip("'\"")
