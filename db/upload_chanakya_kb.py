"""Embed chanakya_kb.jsonl locally and upload it to the existing Qdrant Cloud
`chanakya_kb` collection, then run a test search.

Scope (deliberately narrow per current instructions): embedding + upload + search
verification only. Domain classification is skipped for now — `domain_tags` is
uploaded as-is (currently empty on every row) and can be backfilled into the payload
later without re-embedding.

Usage:
    python -m db.upload_chanakya_kb
    python -m db.upload_chanakya_kb --query "how should a leader handle betrayal"
    python -m db.upload_chanakya_kb --payload-only   # update payload (e.g. domain_tags)
                                                       # for existing points, no re-embed
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from qdrant_client.models import PointStruct, SetPayloadOperation, SetPayload

from db.embedding import VECTOR_SIZE, embed_documents, embed_query
from db.qdrant_client import COLLECTION_NAME, ensure_collection, get_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANAKYA_KB_PATH = PROJECT_ROOT / "data" / "processed" / "chanakya_kb.jsonl"

# Qdrant point IDs must be an unsigned int or a UUID — chunk ids like
# "arthashastra_book_iii_001" are neither, so we derive a stable UUID5 from each one
# and keep the original string id in the payload for human traceability.
_ID_NAMESPACE = uuid.NAMESPACE_DNS

UPLOAD_BATCH_SIZE = 100
PAYLOAD_BATCH_SIZE = 25  # smaller than UPLOAD_BATCH_SIZE — payload-only batches carry
# per-point distinct operations (not one shared vector op), so keep requests smaller
# to avoid write timeouts over a home connection.
EMBED_BATCH_SIZE = 32  # CPU-only, 16GB RAM: keep modest, don't blow up memory.


def load_rows(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_points(rows: list[dict], vectors: list[list[float]]) -> list[PointStruct]:
    points = []
    for row, vector in zip(rows, vectors):
        point_id = str(uuid.uuid5(_ID_NAMESPACE, row["id"]))
        payload = {**row}  # includes original string "id" plus all other fields
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))
    return points


def upload_in_batches(client, points: list[PointStruct], batch_size: int = UPLOAD_BATCH_SIZE) -> None:
    total = len(points)
    for start in range(0, total, batch_size):
        batch = points[start : start + batch_size]
        client.upload_points(collection_name=COLLECTION_NAME, points=batch, wait=True)
        done = min(start + batch_size, total)
        print(f"Upserted {done}/{total}")


def update_payloads_only(client, rows: list[dict], batch_size: int = PAYLOAD_BATCH_SIZE) -> None:
    """Updates payload (e.g. domain_tags) on already-embedded points without touching
    their vectors — for when only metadata changed, not the text. Point ids are
    recomputed the same deterministic way as build_points, so this targets the exact
    same points a full re-upload would. One batch_update_points call per batch (each
    point gets its own SetPayloadOperation with its own payload) — no per-point network
    round trips, and no re-embedding."""
    total = len(rows)
    for start in range(0, total, batch_size):
        batch = rows[start : start + batch_size]
        operations = [
            SetPayloadOperation(
                set_payload=SetPayload(
                    payload={**row},
                    points=[str(uuid.uuid5(_ID_NAMESPACE, row["id"]))],
                )
            )
            for row in batch
        ]
        client.batch_update_points(collection_name=COLLECTION_NAME, update_operations=operations, wait=True)
        done = min(start + batch_size, total)
        print(f"Updated payload {done}/{total}")


def run_test_queries(client, queries: list[str], top_k: int = 3, score_floor: float = 0.3) -> None:
    print("\n=== Test queries ===")
    for query in queries:
        vector = embed_query(query)
        results = client.query_points(
            collection_name=COLLECTION_NAME, query=vector, limit=top_k
        ).points

        print(f"\nQuery: {query!r}")
        if not results or results[0].score < score_floor:
            print(f"  WARNING: No result above score threshold {score_floor} — flagging for review.")

        for r in results:
            snippet = r.payload.get("text", "")[:150].replace("\n", " ")
            print(f"  [{r.score:.3f}] id={r.payload.get('id')} ({r.payload.get('reference')})")
            print(f"      {snippet}...")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", help="Custom test query (repeatable)")
    parser.add_argument(
        "--payload-only",
        action="store_true",
        help="Update payload (e.g. domain_tags) on existing points only — skips embedding entirely.",
    )
    args = parser.parse_args()

    print(f"Loading {CHANAKYA_KB_PATH} ...")
    rows = load_rows(CHANAKYA_KB_PATH)
    print(f"Loaded {len(rows)} rows")

    client = get_client()

    if args.payload_only:
        if not client.collection_exists(COLLECTION_NAME):
            raise RuntimeError(f"Collection '{COLLECTION_NAME}' doesn't exist — run a full upload first.")
        print(f"\n--payload-only: updating payload for {len(rows)} existing points, no re-embedding ...")
        update_payloads_only(client, rows)
    else:
        print(f"Embedding {len(rows)} chunks with nomic-embed-text-v1.5 (CPU, batch_size={EMBED_BATCH_SIZE}) ...")
        texts = [row["text"] for row in rows]
        vectors = embed_documents(texts, batch_size=EMBED_BATCH_SIZE)

        actual_dim = len(vectors[0])
        if actual_dim != VECTOR_SIZE:
            raise RuntimeError(
                f"Embedding dimension mismatch: got {actual_dim}, expected {VECTOR_SIZE}. "
                "Aborting before touching Qdrant."
            )
        print(f"Embedded OK — {actual_dim}-dim vectors, normalized.")

        if client.collection_exists(COLLECTION_NAME):
            existing_count = client.count(COLLECTION_NAME).count
            print(f"Collection '{COLLECTION_NAME}' already exists with {existing_count} point(s) — upserting by id (idempotent), not recreating.")
        ensure_collection(client, vector_size=actual_dim)

        points = build_points(rows, vectors)
        print(f"\nUploading {len(points)} points in batches of {UPLOAD_BATCH_SIZE} ...")
        upload_in_batches(client, points)

    final_count = client.count(COLLECTION_NAME).count
    print(f"\nCollection '{COLLECTION_NAME}' now has {final_count} point(s) (input had {len(rows)} rows).")
    if final_count != len(rows):
        print("WARNING: Point count does not match input row count — investigate before trusting retrieval.")

    default_queries = [
        "how should a leader handle betrayal by a trusted advisor",
        "what makes a good minister or advisor to a king",
        "how to build wealth ethically",
    ]
    run_test_queries(client, args.query or default_queries)


if __name__ == "__main__":
    main()
