"""Piece 4 of the security/auth hardening task — lightweight prompt-injection
pre-check.

The first and most load-bearing defense is structural, not this module: the user
`message` is passed as a genuinely separate `user`-role turn from the `system`
prompt — never concatenated into one string — all the way to the OpenRouter
request body. See serving/prompt.py (builds only the user-turn text) and
providers/openrouter.py's `_messages()` (system and user are distinct dict
entries in the request). That's verified directly in
serving/tests/test_prompt_injection.py, not just asserted here in a comment.

This module is a second, softer layer: a keyword/pattern pre-check on the
incoming message. It deliberately does NOT block — false positives are likely
(a legitimate client asking "how do we handle a competitor who wants us to
ignore prior commitments" would trip a naive filter), and silently dropping a
real client question is worse than logging a false alarm. Every match is logged
with the full message for review, and `flagged` is surfaced in serving/app.py's
per-turn structured log line so this is a real, queryable signal from day one.
"""
from __future__ import annotations

import re

_INJECTION_PATTERNS = [
    re.compile(r"ignore (all|any|the)?\s*(previous|prior|above)\s*instructions", re.IGNORECASE),
    re.compile(r"disregard (all|any|the)?\s*(previous|prior|above)\s*instructions", re.IGNORECASE),
    re.compile(r"forget (all|everything)\s*(you (were|are) told|your instructions)", re.IGNORECASE),
    re.compile(r"you are now\b", re.IGNORECASE),
    re.compile(r"act as (if you are|a)\b", re.IGNORECASE),
    re.compile(r"reveal (your|the)\s*(system prompt|instructions)", re.IGNORECASE),
    re.compile(r"(show|print|repeat|output)\s*(me\s*)?(your|the)\s*(system prompt|instructions)", re.IGNORECASE),
    re.compile(r"new instructions\s*:", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\bDAN\b"),  # "Do Anything Now" jailbreak persona — common enough to be a distinct signal
]


def check_for_injection(message: str) -> bool:
    """Returns True if `message` matches a common prompt-injection pattern. A
    detection signal only — callers must not use this to block, alter, or drop
    the message, only to flag and log it for review."""
    return any(pattern.search(message) for pattern in _INJECTION_PATTERNS)
