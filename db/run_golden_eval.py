"""Golden query regression eval (Piece 4) — runs every golden query against a given
collection/version, computes recall@5, prints a per-query pass/fail table.

Usage:
    python -m db.run_golden_eval chanakya chanakya_kb_v1
    python -m db.run_golden_eval crisis crisis_kb_v2
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qdrant_client import QdrantClient

from db.config import DENSE_VECTOR_NAME
from db.embedding import embed_query

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = PROJECT_ROOT / "preprocessing" / "tests"

GOLDEN_PATHS = {
    "chanakya": GOLDEN_DIR / "golden_queries_chanakya.jsonl",
    "crisis": GOLDEN_DIR / "golden_queries_crisis.jsonl",
}


def load_golden_queries(kb: str) -> list[dict]:
    path = GOLDEN_PATHS[kb]
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def _has_named_dense_vector(client: QdrantClient, collection: str) -> bool:
    info = client.get_collection(collection)
    vectors = info.config.params.vectors
    return isinstance(vectors, dict) and DENSE_VECTOR_NAME in vectors


def query_top_k(client: QdrantClient, collection: str, query_text: str, top_k: int = 5) -> list[str]:
    """Dense-vector recall — the baseline metric the gate compares across versions.
    Auto-detects whether the target collection uses a named "dense" vector (hybrid
    "_v2"+) or the unnamed default (dense-only "_v1"), so the same eval works on both."""
    vector = embed_query(query_text)
    if _has_named_dense_vector(client, collection):
        results = client.query_points(collection_name=collection, query=vector, using=DENSE_VECTOR_NAME, limit=top_k).points
    else:
        results = client.query_points(collection_name=collection, query=vector, limit=top_k).points
    return [r.payload.get("id") for r in results]


def evaluate(client: QdrantClient, collection: str, golden_queries: list[dict], top_k: int = 5) -> dict:
    rows = []
    hits = 0
    for gq in golden_queries:
        got_ids = query_top_k(client, collection, gq["query"], top_k)
        hit = any(eid in got_ids for eid in gq["expected_chunk_ids"])
        hits += hit
        rows.append({"query": gq["query"], "expected": gq["expected_chunk_ids"], "got": got_ids, "hit": hit})

    recall_at_k = hits / len(golden_queries) if golden_queries else 0.0
    return {"collection": collection, "recall_at_k": recall_at_k, "top_k": top_k, "rows": rows}


def print_report(result: dict) -> None:
    print(f"\n=== Golden eval: '{result['collection']}' — recall@{result['top_k']} = {result['recall_at_k']:.1%} ===")
    for row in result["rows"]:
        status = "PASS" if row["hit"] else "FAIL"
        print(f"  [{status}] {row['query']!r}")
        if not row["hit"]:
            print(f"         expected one of {row['expected']}, got {row['got']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kb", choices=["chanakya", "crisis"])
    parser.add_argument("collection", help="Collection name to evaluate, e.g. chanakya_kb_v1 or chanakya_kb_v2")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    if args.kb == "chanakya":
        from db.qdrant_client import get_client
    else:
        from db.crisis_qdrant_client import get_client

    client = get_client()
    golden_queries = load_golden_queries(args.kb)
    result = evaluate(client, args.collection, golden_queries, args.top_k)
    print_report(result)


if __name__ == "__main__":
    main()
