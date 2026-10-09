"""Shared config for the serving/ layer — retrieval budgeting constants, per
CLAUDE.md's "config over hardcoding" principle. Mode-specific values (top_k,
min_score, collection_alias, ...) live in serving/mode_config.py instead, since
those vary per mode; these are global to the retrieval pipeline regardless of mode.
"""
from __future__ import annotations

import os

# How many candidates hybrid_search fetches per prefetch branch (dense, sparse)
# before RRF fusion — wider than the final top_k so fusion has real candidates to
# rank from, matching db/hybrid_query.py's own default.
PREFETCH_LIMIT = 20

# Total character budget across all expanded chunks handed to the generation
# model for one turn. Each expansion function already caps a single chunk at
# db.parent_expansion.MAX_EXPANDED_CHARS (8000) — this is the ceiling across all
# chunks combined, so a query that matches several large chapters doesn't blow
# past the model's context window. Chunks are added in retrieval-score order and
# dropped once this is exceeded, not concatenated unconditionally.
MAX_CONTEXT_CHARS = 12000

# --- Internal review mode (team-review-prep task, 2026-08-19) ----------------------
# A reversible dev-mode bypass, NOT a removal — auth code stays fully intact;
# this just routes around it (see serving/auth.py's get_current_client and
# serving/app.py's startup warning). Default unset/false. Must never be true
# in a real deployment — the startup warning exists specifically because this
# being left on by accident is the one real risk here.
AUTH_DISABLED = os.environ.get("AUTH_DISABLED", "").strip().lower() in ("1", "true", "yes")

# --- Rate limiting (Piece 2 of the security/auth hardening task) -------------------
# Per-client request rate, enforced before retrieval runs at all. Loosened
# (not removed) while AUTH_DISABLED is true: everyone on the team shares one
# identity in that mode (see serving/auth.py), so the normal per-client limit
# would let one teammate's testing 429 everyone else mid-demo.
RATE_LIMIT_REQUESTS_PER_MINUTE = 200 if AUTH_DISABLED else 30
RATE_LIMIT_WINDOW_SECONDS = 60.0

# Global (not per-client) cap on in-flight *generation* calls specifically —
# retrieval is cheap; generation is the slow, expensive part once the OpenRouter
# key is live, and the thing most likely to let one client's burst degrade
# everyone else's latency.
GENERATION_CONCURRENCY_LIMIT = 4
GENERATION_RETRY_AFTER_SECONDS = 5

# --- Input validation (Piece 3 of the security/auth hardening task) ----------------
# This is a chat message, not a document upload — a real ceiling, not a nominal one.
MAX_MESSAGE_LENGTH = 4000

# --- Secrets & transport hygiene (Piece 5 of the security/auth hardening task) -----
# Explicit allowlist, config-driven via env var (comma-separated origins) — never
# "*". Empty by default (fails closed: no browser origin is allowed) until an
# actual chat-interface domain exists and ALLOWED_ORIGINS is set in .env.
_raw_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [origin.strip() for origin in _raw_allowed_origins.split(",") if origin.strip()]

# ASGI-level cap on request body size, enforced before the body is even parsed —
# belt and suspenders alongside MAX_MESSAGE_LENGTH above (a Pydantic field check
# only runs *after* the body has already been read and JSON-decoded). Generous
# over MAX_MESSAGE_LENGTH (4000 chars) to leave room for JSON structure overhead.
MAX_BODY_BYTES = 32_768

# --- Retrieval floors (quality-fix plan, Step 2) -----------------------------------
# Minimum best dense cosine similarity for a query to be answered rather than refused,
# per mode. Env-overridable so tuning is a config change, not a deploy. Measured on the
# 130-query eval set (eval/): see results/audit_report.md for the trade-off table;
# out-of-scope ones <= 0.57 / <= 0.52.
CHANAKYA_MIN_SCORE = float(os.environ.get("CHANAKYA_MIN_SCORE", "0.64"))
CRISIS_MIN_SCORE = float(os.environ.get("CRISIS_MIN_SCORE", "0.65"))

# Load the embedding models when the app starts instead of on the first request (which otherwise
# takes ~12 s locally and ~60 s on the 1 GB VM). Set WARMUP_ON_STARTUP=false to skip, e.g. in tests.
WARMUP_ON_STARTUP = os.environ.get("WARMUP_ON_STARTUP", "true").strip().lower() not in ("0", "false", "no")
