"""Logging setup shared by every entrypoint and runner.

All diagnostic output goes through the ``audit`` logger hierarchy on stderr, keeping stdout
clean for the JSON (or HTML) report so the tools stay pipe-friendly.
"""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure the root ``audit`` logger once.

    Args:
        verbose: emit DEBUG and above.
        quiet: emit ERROR and above only. ``quiet`` wins over ``verbose`` if both are set.
    """
    global _CONFIGURED
    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    if quiet:
        level = logging.ERROR

    root = logging.getLogger("audit")
    root.setLevel(level)
    if not _CONFIGURED:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
        root.propagate = False
        _CONFIGURED = True
    else:
        for h in root.handlers:
            h.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a child of the ``audit`` logger."""
    return logging.getLogger(f"audit.{name}")
