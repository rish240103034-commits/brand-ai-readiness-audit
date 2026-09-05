"""Local audit history for score-over-time tracking (stdlib sqlite3).

Stores one row per audit (domain, timestamp, score, grade, findings) in a local SQLite file
and, on request, attaches the delta versus the previous run for the same domain to the report.
Purely local and optional — nothing is uploaded.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, Optional

DEFAULT_DB = os.path.join(os.getcwd(), ".audit-history.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    audited_at TEXT NOT NULL,
    score INTEGER NOT NULL,
    grade TEXT NOT NULL,
    total_findings INTEGER NOT NULL,
    profile TEXT
);
CREATE INDEX IF NOT EXISTS idx_domain_time ON audits(domain, audited_at);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    """Open (creating if needed) the history database and ensure the schema exists."""
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def latest_for_domain(conn: sqlite3.Connection, domain: str) -> Optional[sqlite3.Row]:
    """Return the most recent stored audit row for *domain*, or None."""
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM audits WHERE domain=? ORDER BY audited_at DESC, id DESC LIMIT 1",
        (domain,))
    return cur.fetchone()


def record_and_compare(report: Dict[str, Any], db_path: str = DEFAULT_DB,
                       compare: bool = True) -> Dict[str, Any]:
    """Persist this audit and, if *compare*, attach the delta vs. the previous run.

    Adds ``report['comparison'] = {previous_score, delta, previous_at, run_count}`` when a
    prior run for the same domain exists. Failures are swallowed (history is best-effort).
    """
    domain = report.get("site", "")
    score = int(report.get("score", {}).get("value", 0))
    grade = str(report.get("score", {}).get("grade", "F"))
    total = int(report.get("summary", {}).get("total_findings", 0))
    profile = str(report.get("profile", "balanced"))
    audited_at = str(report.get("audited_at", ""))

    try:
        conn = _connect(db_path)
    except Exception:
        return report  # history is optional; never fail the audit over it

    try:
        prev = latest_for_domain(conn, domain) if compare else None
        run_count = conn.execute("SELECT COUNT(*) FROM audits WHERE domain=?", (domain,)).fetchone()[0]
        conn.execute(
            "INSERT INTO audits(domain, audited_at, score, grade, total_findings, profile) "
            "VALUES(?,?,?,?,?,?)",
            (domain, audited_at, score, grade, total, profile))
        conn.commit()
        if compare and prev is not None:
            report["comparison"] = {
                "previous_score": prev["score"],
                "previous_grade": prev["grade"],
                "previous_at": prev["audited_at"],
                "delta": score - prev["score"],
                "run_count": run_count + 1,
            }
        elif compare:
            report["comparison"] = {"previous_score": None, "delta": None,
                                    "note": "first recorded audit for this domain", "run_count": 1}
    except Exception:
        pass
    finally:
        conn.close()
    return report
