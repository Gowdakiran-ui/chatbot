"""Tests for serving/auth.py (Piece 1) — unit tests against a temp SQLite DB, plus
FastAPI dependency-level tests for get_current_client."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
from fastapi import HTTPException

import serving.auth as auth_mod
from serving.auth import (
    INTERNAL_REVIEW_IDENTITY,
    ClientIdentity,
    _lookup_by_token,
    create_client,
    get_current_client,
    hash_token,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "auth_test.db"


def test_hash_token_is_deterministic_and_sha256():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert len(hash_token("abc")) == 64  # sha256 hex digest length


def test_create_client_then_lookup_by_correct_token_succeeds(db_path):
    create_client("client_a", "Client A", "raw-token-123", db_path=db_path)

    identity = _lookup_by_token("raw-token-123", db_path)

    assert identity == ClientIdentity(client_id="client_a", label="Client A")


def test_lookup_by_wrong_token_returns_none(db_path):
    create_client("client_a", "Client A", "raw-token-123", db_path=db_path)

    assert _lookup_by_token("wrong-token", db_path) is None


def test_lookup_scoped_correctly_across_multiple_clients(db_path):
    create_client("client_a", "Client A", "token-a", db_path=db_path)
    create_client("client_b", "Client B", "token-b", db_path=db_path)

    assert _lookup_by_token("token-a", db_path).client_id == "client_a"
    assert _lookup_by_token("token-b", db_path).client_id == "client_b"


def test_create_client_rejects_duplicate_client_id(db_path):
    create_client("client_a", "Client A", "token-1", db_path=db_path)
    with pytest.raises(Exception):
        create_client("client_a", "Client A (again)", "token-2", db_path=db_path)


def test_lookup_uses_hmac_compare_digest_not_equality(db_path):
    create_client("client_a", "Client A", "raw-token-123", db_path=db_path)

    with patch("serving.auth.hmac.compare_digest", wraps=__import__("hmac").compare_digest) as spy:
        _lookup_by_token("raw-token-123", db_path)

    assert spy.called  # every row comparison must go through compare_digest, never `==`


# --- get_current_client (FastAPI dependency) ----------------------------------------


def test_get_current_client_valid_token_returns_identity(monkeypatch, db_path):
    create_client("client_a", "Client A", "good-token", db_path=db_path)
    monkeypatch.setattr("serving.auth.DB_PATH", db_path)

    identity = get_current_client(authorization="Bearer good-token")

    assert identity == ClientIdentity(client_id="client_a", label="Client A")


def test_get_current_client_missing_header_raises_401(monkeypatch, db_path):
    monkeypatch.setattr("serving.auth.DB_PATH", db_path)

    with pytest.raises(HTTPException) as exc_info:
        get_current_client(authorization=None)

    assert exc_info.value.status_code == 401


def test_get_current_client_malformed_header_raises_401(monkeypatch, db_path):
    monkeypatch.setattr("serving.auth.DB_PATH", db_path)

    with pytest.raises(HTTPException) as exc_info:
        get_current_client(authorization="good-token-no-bearer-prefix")

    assert exc_info.value.status_code == 401


def test_get_current_client_invalid_token_raises_401(monkeypatch, db_path):
    create_client("client_a", "Client A", "good-token", db_path=db_path)
    monkeypatch.setattr("serving.auth.DB_PATH", db_path)

    with pytest.raises(HTTPException) as exc_info:
        get_current_client(authorization="Bearer tampered-token")

    assert exc_info.value.status_code == 401


def test_get_current_client_tampered_token_with_correct_prefix_raises_401(monkeypatch, db_path):
    """A token differing only in its last character must still fail cleanly —
    guards against any accidental prefix-matching logic creeping in later."""
    create_client("client_a", "Client A", "good-token-123456", db_path=db_path)
    monkeypatch.setattr("serving.auth.DB_PATH", db_path)

    with pytest.raises(HTTPException) as exc_info:
        get_current_client(authorization="Bearer good-token-123457")

    assert exc_info.value.status_code == 401


# --- AUTH_DISABLED (team-review-prep task, 2026-08-19) -------------------------------
# Piece 1's dev-mode bypass — a toggle, not a removal. Auth code stays fully
# intact (every test above still exercises it unchanged); these tests cover
# the second resolution path get_current_client takes when the flag is set,
# plus an explicit proof that the default (flag unset) path is untouched.


def test_default_auth_disabled_is_false_and_behavior_is_unchanged(monkeypatch, db_path):
    """Explicit proof, not an assumption: with AUTH_DISABLED at its real
    default (unset in this test process), get_current_client behaves exactly
    as every test above already demonstrates — missing header still 401s,
    the internal-review bypass is not silently active."""
    assert auth_mod.AUTH_DISABLED is False

    monkeypatch.setattr("serving.auth.DB_PATH", db_path)
    with pytest.raises(HTTPException) as exc_info:
        get_current_client(authorization=None)
    assert exc_info.value.status_code == 401


def test_auth_disabled_true_bypasses_token_validation_entirely(monkeypatch):
    monkeypatch.setattr("serving.auth.AUTH_DISABLED", True)

    identity = get_current_client(authorization=None)

    assert identity == INTERNAL_REVIEW_IDENTITY


def test_auth_disabled_true_ignores_a_present_but_bogus_header(monkeypatch):
    # Same dependency, same downstream code, different resolution path — the
    # header is never even inspected while the flag is set.
    monkeypatch.setattr("serving.auth.AUTH_DISABLED", True)

    identity = get_current_client(authorization="Bearer this-is-not-a-real-token")

    assert identity == INTERNAL_REVIEW_IDENTITY


def test_auth_disabled_true_never_touches_the_client_db(monkeypatch, tmp_path):
    # Point DB_PATH at a file that doesn't exist and was never created — if
    # AUTH_DISABLED's bypass ever touched the DB path, this would raise
    # (sqlite creates the file, so this alone doesn't prove much) — the real
    # proof is the identity returned came from the fixed constant, not a
    # lookup, which the other two tests above already show via a bogus token
    # that would 401 on the real lookup path.
    monkeypatch.setattr("serving.auth.AUTH_DISABLED", True)
    monkeypatch.setattr("serving.auth.DB_PATH", tmp_path / "does_not_exist" / "auth.db")

    identity = get_current_client(authorization=None)

    assert identity.client_id == "internal-review"
