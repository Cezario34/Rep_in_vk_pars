from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "limits.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS allowances (
            name TEXT PRIMARY KEY,
            remaining INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    return conn


def list_allowances() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT name, remaining FROM allowances ORDER BY remaining DESC, name"
        ).fetchall()
    return [dict(row) for row in rows]


def get_remaining(name: str) -> int:
    name = name.strip()
    with _connect() as conn:
        row = conn.execute(
            "SELECT remaining FROM allowances WHERE name = ?",
            (name,),
        ).fetchone()
    return int(row["remaining"]) if row else 0


def set_remaining(name: str, remaining: int) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Имя не может быть пустым")
    remaining = max(0, int(remaining))
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO allowances(name, remaining) VALUES(?, ?)
            ON CONFLICT(name) DO UPDATE SET remaining = excluded.remaining
            """,
            (name, remaining),
        )
        conn.commit()


def consume_attempt(name: str) -> bool:
    name = name.strip()
    with _connect() as conn:
        row = conn.execute(
            "SELECT remaining FROM allowances WHERE name = ?",
            (name,),
        ).fetchone()
        if not row or row["remaining"] <= 0:
            return False
        conn.execute(
            "UPDATE allowances SET remaining = remaining - 1 WHERE name = ? AND remaining > 0",
            (name,),
        )
        conn.commit()
        return conn.total_changes > 0