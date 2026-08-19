"""Piece 1 of the security/auth hardening task — Bearer-token auth for /chat.

This serves Onlyne's clients directly (engineers, business owners), not just
internal staff, so auth identifies and isolates individual client accounts, not
just "is this a valid Onlyne employee."

Tokens are issued per client account (see scripts/issue_token.py), never stored
in plaintext — only a SHA-256 hash lives in the DB, and the raw token is shown to
the operator exactly once, at issuance. `get_current_client` is a FastAPI
dependency that resolves an `Authorization: Bearer <token>` header to a
`ClientIdentity`, or raises 401 — there is no anonymous fallback.

Storage: a single SQLite table. This is deliberately the entire "user service" for
now — the project is pre-launch with a handful of client accounts; building a full
auth service before there's a reason to would be exactly the kind of speculative
generality CLAUDE.md warns against. Swapping to a real DB later is a new
`_get_connection()`/schema, not a rewrite of the dependency or the callers.
"""
from __future__ import annotations

import hashlib
import hmac
import sqlite3
from pathlib import Path

from fastapi import Header, HTTPException
from pydantic import BaseModel

from serving.config import AUTH_DISABLED

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "auth.db"


class ClientIdentity(BaseModel):
    """client_id is the only field Piece 2's per-client rate limiter needs (as the
    bucket key); label is kept for operator-facing logging/auditing."""

    client_id: str
    label: str


# team-review-prep task: the fixed identity every request resolves to while
# AUTH_DISABLED is true. Everyone on the team shares this one identity —
# conversation ownership (serving/conversations.py) is claimed per-client, so
# a shared identity naturally shares conversation access, which is fine for
# this internal-only phase (see task.md's own note).
INTERNAL_REVIEW_IDENTITY = ClientIdentity(client_id="internal-review", label="Internal Review")


def _get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS clients ("
        "client_id TEXT PRIMARY KEY, "
        "label TEXT NOT NULL, "
        "token_hash TEXT NOT NULL UNIQUE, "
        "created_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )
    return conn


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_client(client_id: str, label: str, token: str, db_path: Path | None = None) -> None:
    """Registers a new client account with the given raw token's hash. Raises
    sqlite3.IntegrityError if client_id or the token hash already exist — callers
    (scripts/issue_token.py) should let that surface rather than silently
    overwriting an existing account.

    db_path defaults to the current serving.auth.DB_PATH, looked up at call time
    (not bound as a def-time default) so tests can monkeypatch DB_PATH and have it
    actually take effect here."""
    if db_path is None:
        db_path = DB_PATH
    conn = _get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO clients (client_id, label, token_hash) VALUES (?, ?, ?)",
                (client_id, label, hash_token(token)),
            )
    finally:
        conn.close()


def _lookup_by_token(token: str, db_path: Path) -> ClientIdentity | None:
    """Finds the client whose stored token hash matches this token's hash, using
    hmac.compare_digest (never `==`) for every comparison so response timing can't
    reveal how much of a guessed token matched a given stored hash. Scans every
    row deliberately — there's no indexed short-circuit here, only constant-time
    comparisons — which is fine at the handful-of-clients scale this stage is
    built for; a production-scale client table would need a different lookup
    strategy that doesn't defeat this property some other way (e.g. via query
    timing on the index itself)."""
    token_hash = hash_token(token)
    conn = _get_connection(db_path)
    try:
        rows = conn.execute("SELECT client_id, label, token_hash FROM clients").fetchall()
    finally:
        conn.close()
    for client_id, label, stored_hash in rows:
        if hmac.compare_digest(token_hash, stored_hash):
            return ClientIdentity(client_id=client_id, label=label)
    return None


def get_current_client(authorization: str | None = Header(default=None)) -> ClientIdentity:
    if AUTH_DISABLED:
        # Same dependency, same downstream code — just a different resolution
        # path. No token validation at all while this flag is set; see
        # serving/config.py's docstring on why this must default to false.
        return INTERNAL_REVIEW_IDENTITY

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization[len("Bearer ") :]
    identity = _lookup_by_token(token, DB_PATH)
    if identity is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return identity
