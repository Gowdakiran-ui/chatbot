"""Piece 5 of the security/auth hardening task — secrets hygiene.

The real defense is that no code path should ever embed a credential in an
exception message, log line, or client-facing error in the first place (checked
directly in providers/openrouter.py and db/*_qdrant_client.py — none of them
interpolate the API key/URL into anything that gets logged or raised). This
module is the belt-and-suspenders layer: `redact_secrets()` strips every known
credential value out of arbitrary text before it's logged or sent to a client, so
a future bug that accidentally embeds a secret in an error string still can't
leak it.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Every env var this project loads a credential from — see providers/openrouter.py,
# db/qdrant_client.py, db/crisis_qdrant_client.py.
_SECRET_ENV_VARS = (
    "openrouter_api_key",
    "chanakya_qdrant_api_key",
    "crisis_planer_api_key",
)

REDACTED = "[REDACTED]"


def redact_secrets(text: str) -> str:
    """Replaces every occurrence of any currently-configured secret value in
    `text` with a redaction marker. Reads current env values each call (not
    cached at import time) so tests can monkeypatch a secret and see it redacted
    without reloading this module."""
    for var in _SECRET_ENV_VARS:
        value = os.environ.get(var)
        if value:
            text = text.replace(value, REDACTED)
    return text
