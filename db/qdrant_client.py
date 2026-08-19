"""Qdrant connection module for the Chanakya knowledge base.

This is the single place that knows how to reach the `chanakya_kb` Qdrant collection.
Other scripts (upload, query, retrieval at request time) should import `get_client()`
and `COLLECTION_NAME` from here rather than constructing their own client — keeps the
connection config in one spot, per CLAUDE.md's "config over hardcoding" rule.

Env vars (loaded from the project-root `.env`):
    chanakya_qdrant_url      - Qdrant Cloud cluster URL
    chanakya_qdrant_api_key  - Qdrant Cloud API key

Note: the `.env` file currently spells the URL var "cahanakya_qdrant_url" (typo for
"chanakya"). We read it as-is rather than silently renaming a file we don't own; fix
the typo in `.env` if you'd rather standardize the name.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType, VectorParams

from db.config import CHANAKYA_COLLECTION_BASE, CHANAKYA_FILTERABLE_FIELDS, DISTANCE_METRIC, QDRANT_TIMEOUT

# --- Environment -----------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_QDRANT_URL_ENV_VARS = ("chanakya_qdrant_url", "cahanakya_qdrant_url")
_QDRANT_API_KEY_ENV_VAR = "chanakya_qdrant_api_key"


def _get_qdrant_url() -> str:
    for var in _QDRANT_URL_ENV_VARS:
        value = os.environ.get(var)
        if value:
            return value
    raise RuntimeError(
        f"Qdrant URL not found in .env. Expected one of: {', '.join(_QDRANT_URL_ENV_VARS)}"
    )


def _get_qdrant_api_key() -> str:
    value = os.environ.get(_QDRANT_API_KEY_ENV_VAR)
    if not value:
        raise RuntimeError(f"Qdrant API key not found in .env (expected '{_QDRANT_API_KEY_ENV_VAR}')")
    return value


# --- Chanakya KB collection config -------------------------------------------------

# COLLECTION_NAME is the alias clients read/write through (see db/versioning.py, Piece 2
# of the hardening task) — it always resolves to whichever "chanakya_kb_v{n}" version is
# currently live. Never hardcode a literal "_v{n}" suffix anywhere outside versioning.py
# or a version-bump script — that would bypass the alias and read/write a frozen version.
COLLECTION_NAME = CHANAKYA_COLLECTION_BASE

# Used only if the vector size can't be detected from the data being uploaded (see
# ensure_collection). Kept for backward compatibility with pre-Piece-2 callers; new code
# should pass vector_size explicitly (db.config.VECTOR_SIZE).
DEFAULT_VECTOR_SIZE = 1536


def get_client(timeout: int = QDRANT_TIMEOUT) -> QdrantClient:
    """Returns a connected QdrantClient for the Chanakya Qdrant Cloud cluster.
    `timeout` (seconds) is raised above the library default for batch writes over a
    home/laptop connection, where a large request can otherwise hit a write timeout."""
    return QdrantClient(url=_get_qdrant_url(), api_key=_get_qdrant_api_key(), timeout=timeout)


def ensure_collection(client: QdrantClient, vector_size: int | None = None) -> int:
    """Creates the `chanakya_kb` collection if it doesn't already exist. Returns the
    vector size the collection is configured with.

    If `vector_size` is not given, falls back to DEFAULT_VECTOR_SIZE and prints a clear
    warning — callers that know the real embedding dimension (e.g. detected from the
    first vector in the upload data) should always pass it explicitly.
    """
    if client.collection_exists(COLLECTION_NAME):
        info = client.get_collection(COLLECTION_NAME)
        ensure_payload_indexes(client)  # collection may predate the indexing requirement
        return info.config.params.vectors.size

    size = vector_size or DEFAULT_VECTOR_SIZE
    if vector_size is None:
        print(
            f"WARNING: no vector_size given, defaulting to {DEFAULT_VECTOR_SIZE} "
            "(OpenAI text-embedding-3-small dimension). Pass vector_size explicitly "
            "once your embedding provider is finalized."
        )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=size, distance=DISTANCE_METRIC),
    )
    print(f"Created collection '{COLLECTION_NAME}' (size={size}, distance={DISTANCE_METRIC.value})")

    ensure_payload_indexes(client)
    return size


def ensure_payload_indexes(client: QdrantClient) -> None:
    """Creates a keyword index on each field in CHANAKYA_FILTERABLE_FIELDS if it doesn't
    already exist — idempotent, safe to call every run. Required by Qdrant Cloud before
    those fields can be used in a query_filter (e.g. db/parent_expansion.py's parent_id
    sibling lookup)."""
    existing = client.get_collection(COLLECTION_NAME).payload_schema
    for field in CHANAKYA_FILTERABLE_FIELDS:
        if field in existing:
            continue
        client.create_payload_index(
            collection_name=COLLECTION_NAME, field_name=field, field_schema=PayloadSchemaType.KEYWORD
        )
        print(f"Created payload index on '{field}'")


if __name__ == "__main__":
    # Quick connectivity smoke test: `python db/qdrant_client.py`
    c = get_client()
    print("Connected. Existing collections:", [col.name for col in c.get_collections().collections])
