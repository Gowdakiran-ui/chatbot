"""Embed crisis_kb.jsonl locally and upload it to the (separate) Crisis Qdrant Cloud
`crisis_kb` collection, then run test searches including a metadata-filtered one.

Same pattern as upload_chanakya_kb.py: local nomic-embed-text-v1.5 embeddings, UUID5
point ids derived from each chunk's string id, batched upload. No LLM, no classification
step — crisis_kb's tags/metadata came from deterministic regex parsing already.

Usage:
    python -m db.upload_crisis_kb
    python -m db.upload_crisis_kb --query "how to respond to a data breach"
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

from db.embedding import VECTOR_SIZE, embed_documents, embed_query
from db.crisis_qdrant_client import COLLECTION_NAME, ensure_collection, get_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CRISIS_KB_PATH = PROJECT_ROOT / "data" / "processed" / "crisis_kb.jsonl"

# Same UUID5 pattern as upload_chanakya_kb.py — Qdrant point ids must be an unsigned
# int or a UUID; chunk ids like "america_case_001_summary" are neither, so derive a
# stable UUID5 and keep the original string id in the payload.
_ID_NAMESPACE = uuid.NAMESPACE_DNS

# Same batch size/timeout tuning already learned from the Chanakya upload (60s client
# timeout is set in db/crisis_qdrant_client.py's get_client()).
UPLOAD_BATCH_SIZE = 100
EMBED_BATCH_SIZE = 32  # CPU-only, 16GB RAM: keep modest, don't blow up memory.

REQUIRED_TOP_FIELDS = ("id", "text", "chunk_type", "metadata")
REQUIRED_METADATA_FIELDS = (
    "case_id", "company", "industry", "crisis_type", "region", "year",
    "response_speed_score", "transparency_score", "resolution_status",
    "onlyne_relevance", "chunk_type",
)


def load_rows(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def validate_rows(rows: list[dict]) -> None:
    """Fails loudly (Step 1.2) rather than silently embedding incomplete data."""
    problems = []
    for row in rows:
        missing_top = [k for k in REQUIRED_TOP_FIELDS if k not in row]
        missing_meta = [k for k in REQUIRED_METADATA_FIELDS if k not in row.get("metadata", {})]
        if missing_top or missing_meta:
            problems.append((row.get("id", "<no id>"), missing_top, missing_meta))

    if problems:
        for row_id, missing_top, missing_meta in problems[:20]:
            print(f"  {row_id}: missing_top={missing_top} missing_metadata={missing_meta}")
        raise RuntimeError(
            f"{len(problems)} row(s) missing required fields — aborting before embedding. "
            "Check data/processed/parse_errors.jsonl for the corresponding parse-time gaps."
        )

    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise RuntimeError("Duplicate chunk ids found in crisis_kb.jsonl — aborting.")


def build_points(rows: list[dict], vectors: list[list[float]]) -> list[PointStruct]:
    points = []
    for row, vector in zip(rows, vectors):
        point_id = str(uuid.uuid5(_ID_NAMESPACE, row["id"]))
        # Flatten metadata to the top level of the payload (not nested under
        # "metadata") so Qdrant field filters like region=india work directly on
        # payload keys, e.g. FieldCondition(key="region", ...) rather than a dotted path.
        payload = {**row["metadata"], "id": row["id"], "text": row["text"]}
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))
    return points


def upload_in_batches(client, points: list[PointStruct], batch_size: int = UPLOAD_BATCH_SIZE) -> None:
    total = len(points)
    for start in range(0, total, batch_size):
        batch = points[start : start + batch_size]
        client.upload_points(collection_name=COLLECTION_NAME, points=batch, wait=True)
        done = min(start + batch_size, total)
        print(f"Upserted {done}/{total}")


def run_test_queries(client, queries: list[str], top_k: int = 3, score_floor: float = 0.3) -> None:
    print("\n=== Test queries ===")
    for query in queries:
        vector = embed_query(query)
        results = client.query_points(collection_name=COLLECTION_NAME, query=vector, limit=top_k).points

        print(f"\nQuery: {query!r}")
        if not results or results[0].score < score_floor:
            print(f"  WARNING: No result above score threshold {score_floor} — flagging for review.")

        for r in results:
            print(f"  [{r.score:.3f}] id={r.payload.get('id')} company={r.payload.get('company')} chunk_type={r.payload.get('chunk_type')}")


def run_filtered_query(client, query: str, region: str, top_k: int = 3) -> None:
    print(f"\n=== Metadata-filtered query: region={region!r} + {query!r} ===")
    vector = embed_query(query)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        query_filter=Filter(must=[FieldCondition(key="region", match=MatchValue(value=region))]),
        limit=top_k,
    ).points

    if not results:
        print("  WARNING: filtered query returned zero results.")
    for r in results:
        print(f"  [{r.score:.3f}] id={r.payload.get('id')} region={r.payload.get('region')} company={r.payload.get('company')} chunk_type={r.payload.get('chunk_type')}")
        if r.payload.get("region") != region:
            print(f"  WARNING: filter leaked a non-matching region ({r.payload.get('region')})!")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", help="Custom test query (repeatable)")
    args = parser.parse_args()

    print(f"Loading {CRISIS_KB_PATH} ...")
    rows = load_rows(CRISIS_KB_PATH)
    print(f"Loaded {len(rows)} rows")

    print("Validating required fields on every row ...")
    validate_rows(rows)
    print("All rows have required fields.")

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

    client = get_client()

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
        "how should we respond to a data breach in the first 48 hours",
        "example of a company that recovered reputation after executive scandal",
        "best practice for regulatory disclosure timing",
    ]
    run_test_queries(client, args.query or default_queries)
    run_filtered_query(client, "data breach", region="india")


if __name__ == "__main__":
    main()
