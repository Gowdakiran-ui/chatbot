"""Qdrant connection module for the Crisis case-study knowledge base.

This is a SEPARATE Qdrant Cloud cluster from db/qdrant_client.py (Chanakya) — confirmed
by checking .env: `crisis_planer_qdrant_url` / `crisis_planer_api_key` point at a
different cluster id and a different AWS region (eu-west-1) than Chanakya's
(sa-east-1). Per CLAUDE.md's "keep the two KBs genuinely separate" rule and task.md's
explicit instruction not to assume, this module exists instead of reusing
db/qdrant_client.py — crisis_kb and chanakya_kb must never share a client, a
collection, or get queried together.

Env vars (loaded from the project-root `.env`):
    crisis_planer_qdrant_url      - Qdrant Cloud cluster URL (crisis cluster)
    crisis_planer_api_key         - Qdrant Cloud API key (crisis cluster)
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType, VectorParams

from db.config import CRISIS_COLLECTION_BASE, CRISIS_FILTERABLE_FIELDS, DISTANCE_METRIC, QDRANT_TIMEOUT

# --- Environment -----------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_QDRANT_URL_ENV_VAR = "crisis_planer_qdrant_url"
_QDRANT_API_KEY_ENV_VAR = "crisis_planer_api_key"


def _get_qdrant_url() -> str:
    value = os.environ.get(_QDRANT_URL_ENV_VAR)
    if not value:
        raise RuntimeError(f"Qdrant URL not found in .env (expected '{_QDRANT_URL_ENV_VAR}')")
    return value


def _get_qdrant_api_key() -> str:
    value = os.environ.get(_QDRANT_API_KEY_ENV_VAR)
    if not value:
        raise RuntimeError(f"Qdrant API key not found in .env (expected '{_QDRANT_API_KEY_ENV_VAR}')")
    return value


# --- Crisis KB collection config -------------------------------------------------

# COLLECTION_NAME is the alias clients read/write through (see db/versioning.py, Piece 2
# of the hardening task) — always resolves to whichever "crisis_kb_v{n}" version is
# currently live. Never hardcode a literal "_v{n}" suffix outside versioning.py or a
# version-bump script.
COLLECTION_NAME = CRISIS_COLLECTION_BASE

# Only used as a fallback if the vector size can't be detected from the data being
# uploaded — always pass vector_size explicitly (upload_crisis_kb.py does).
DEFAULT_VECTOR_SIZE = 768  # nomic-embed-text-v1.5, the model this project already uses

# Fields the retrieval layer needs to filter *before* semantic search. Qdrant Cloud
# requires an explicit index per field before it will accept a filter on it — without
# this, filtered queries 400 with "Index required but not found."
FILTERABLE_FIELDS = CRISIS_FILTERABLE_FIELDS


def get_client(timeout: int = QDRANT_TIMEOUT) -> QdrantClient:
    """Returns a connected QdrantClient for the Crisis KB Qdrant Cloud cluster
    (separate from Chanakya's). `timeout` (seconds) is raised above the library
    default — a large batch write over a home connection can otherwise time out."""
    return QdrantClient(url=_get_qdrant_url(), api_key=_get_qdrant_api_key(), timeout=timeout)


def ensure_collection(client: QdrantClient, vector_size: int | None = None) -> int:
    """Creates the `crisis_kb` collection if it doesn't already exist. Returns the
    vector size the collection is configured with. Never recreates an existing
    collection — see check_before_recreate() for the "don't silently overwrite" guard."""
    if client.collection_exists(COLLECTION_NAME):
        info = client.get_collection(COLLECTION_NAME)
        ensure_payload_indexes(client)  # collection may predate the indexing requirement
        return info.config.params.vectors.size

    size = vector_size or DEFAULT_VECTOR_SIZE
    if vector_size is None:
        print(f"WARNING: no vector_size given, defaulting to {DEFAULT_VECTOR_SIZE}.")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=size, distance=DISTANCE_METRIC),
    )
    print(f"Created collection '{COLLECTION_NAME}' (size={size}, distance={DISTANCE_METRIC.value})")

    ensure_payload_indexes(client)
    return size


def ensure_payload_indexes(client: QdrantClient) -> None:
    """Creates a keyword index on each field in FILTERABLE_FIELDS if it doesn't already
    exist — idempotent, safe to call every run. Required by Qdrant Cloud before those
    fields can be used in a query_filter."""
    existing = client.get_collection(COLLECTION_NAME).payload_schema
    for field in FILTERABLE_FIELDS:
        if field in existing:
            continue
        client.create_payload_index(
            collection_name=COLLECTION_NAME, field_name=field, field_schema=PayloadSchemaType.KEYWORD
        )
        print(f"Created payload index on '{field}'")


if __name__ == "__main__":
    # Quick connectivity smoke test: `python -m db.crisis_qdrant_client`
    c = get_client()
    print("Connected. Existing collections:", [col.name for col in c.get_collections().collections])
