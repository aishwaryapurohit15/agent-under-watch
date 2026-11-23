"""Append-only, tamper-evident audit log in SQLite.

- Every proposal, decision and human review is written here.
- UPDATE and DELETE are refused by database triggers.
- Each row stores a SHA-256 hash of its content plus the previous row's hash,
  so any later edit to the file breaks the chain and verify_chain() reports it.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event TEXT NOT NULL,                -- 'decision' or 'review'
    action_id TEXT NOT NULL,
    session_id TEXT,
    agent_id TEXT,
    agent_owner TEXT,
    authenticated_subject TEXT,
    tool TEXT,
    target_subject TEXT,
    record_count INTEGER,
    fields TEXT,
    purpose TEXT,
    verdict TEXT,
    reasons TEXT,
    risk_score INTEGER,
    risk_components TEXT,
    anomaly TEXT,
    executed INTEGER,
    reviewer TEXT,
    note TEXT,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""

COLUMNS = [
    "ts", "event", "action_id", "session_id", "agent_id", "agent_owner",
    "authenticated_subject", "tool", "target_subject", "record_count", "fields",
    "purpose", "verdict", "reasons", "risk_score", "risk_components", "anomaly",
    "executed", "reviewer", "note",
]
GENESIS = "0" * 64


def _hash(prev_hash: str, row: dict) -> str:
    payload = json.dumps({k: row.get(k) for k in COLUMNS}, sort_keys=True, default=str)
    return hashlib.sha256((prev_hash + payload).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.executescript(SCHEMA)
        last = self.conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        self._last_hash = last[0] if last else GENESIS

    def append(self, **row) -> None:
        for key in ("fields", "reasons", "risk_components", "anomaly"):
            if key in row and not isinstance(row[key], str):
                row[key] = json.dumps(row[key], default=str)
        if "executed" in row:
            row["executed"] = int(bool(row["executed"]))
        clean = {k: row.get(k) for k in COLUMNS}
        h = _hash(self._last_hash, clean)
        cols = ", ".join(COLUMNS + ["prev_hash", "hash"])
        marks = ", ".join("?" for _ in range(len(COLUMNS) + 2))
        self.conn.execute(
            f"INSERT INTO audit_log ({cols}) VALUES ({marks})",
            [clean[c] for c in COLUMNS] + [self._last_hash, h],
        )
        self.conn.commit()
        self._last_hash = h

    def rows(self, limit: int | None = None) -> list[dict]:
        sql = "SELECT * FROM audit_log ORDER BY id DESC" + (f" LIMIT {int(limit)}" if limit else "")
        cur = self.conn.execute(sql)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]

    def count(self, event: str | None = None) -> int:
        if event:
            return self.conn.execute("SELECT COUNT(*) FROM audit_log WHERE event = ?", (event,)).fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

    def verify_chain(self) -> tuple[bool, int | None]:
        """Recompute every hash. Returns (ok, id_of_first_bad_row)."""
        prev = GENESIS
        cur = self.conn.execute("SELECT * FROM audit_log ORDER BY id")
        names = [d[0] for d in cur.description]
        for values in cur:
            row = dict(zip(names, values))
            if row["prev_hash"] != prev or _hash(prev, row) != row["hash"]:
                return False, row["id"]
            prev = row["hash"]
        return True, None
