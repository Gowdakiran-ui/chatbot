"""Piece 3 of the security/auth hardening task — conversation ownership.

A `conversation_id` lets a client continue an existing thread. If a client passes
one that already belongs to a *different* client, that's an IDOR-class bug if
left unchecked — one client could read or extend another client's conversation
just by guessing or reusing an id. Worth catching now while the concept is new
rather than after real conversation data/history exists.

Ownership is claimed on first use: whichever client first sends a given
conversation_id becomes its owner; every subsequent request carrying that id must
come from the same client, or it's rejected (403).

SQLite, single table — same "don't over-build the user service yet" reasoning as
serving/auth.py.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "conversations.db"


def _get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS conversations ("
        "conversation_id TEXT PRIMARY KEY, "
        "client_id TEXT NOT NULL, "
        "created_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )
    return conn


class ConversationOwnershipStore:
    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path

    def check_and_claim(self, conversation_id: str, client_id: str) -> bool:
        """Returns True if this client may use this conversation_id — either they
        already own it, or they're claiming it for the first time. Returns False
        if it's already owned by a different client."""
        conn = _get_connection(self._db_path)
        try:
            row = conn.execute(
                "SELECT client_id FROM conversations WHERE conversation_id = ?", (conversation_id,)
            ).fetchone()
            if row is None:
                with conn:
                    conn.execute(
                        "INSERT INTO conversations (conversation_id, client_id) VALUES (?, ?)",
                        (conversation_id, client_id),
                    )
                return True
            return row[0] == client_id
        finally:
            conn.close()
