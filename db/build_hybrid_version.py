"""Builds the hybrid dense+sparse "_v2" collection for a KB and (with no gate wired in
yet — Piece 4 does that) leaves the alias pointed at "_v1" for manual review.

Usage:
    python -m db.build_hybrid_version chanakya
    python -m db.build_hybrid_version crisis
"""
from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from db.config import CHANAKYA_COLLECTION_BASE, CRISIS_COLLECTION_BASE, VECTOR_SIZE
from db.embedding import embed_documents
from db.golden_gate import make_golden_gate
from db.sparse_embedding import embed_documents_sparse
from db.version_bump import bump_version, hybrid_build_fn

_ID_NAMESPACE = uuid.NAMESPACE_DNS

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _chanakya_build_fn(client):
    jsonl_path = PROJECT_ROOT / "data" / "processed" / "chanakya_kb.jsonl"
    return hybrid_build_fn(
        client,
        jsonl_path,
        embed_dense_fn=embed_documents,
        embed_sparse_fn=embed_documents_sparse,
        id_fn=lambda row: str(uuid.uuid5(_ID_NAMESPACE, row["id"])),
        payload_fn=lambda row: dict(row),
        vector_size=VECTOR_SIZE,
    )


def _crisis_build_fn(client):
    jsonl_path = PROJECT_ROOT / "data" / "processed" / "crisis_kb.jsonl"
    return hybrid_build_fn(
        client,
        jsonl_path,
        embed_dense_fn=embed_documents,
        embed_sparse_fn=embed_documents_sparse,
        id_fn=lambda row: str(uuid.uuid5(_ID_NAMESPACE, row["id"])),
        payload_fn=lambda row: {**row["metadata"], "id": row["id"], "text": row["text"]},
        vector_size=VECTOR_SIZE,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kb", choices=["chanakya", "crisis"])
    args = parser.parse_args()

    if args.kb == "chanakya":
        from db.qdrant_client import COLLECTION_NAME, get_client

        client = get_client()
        build_fn = _chanakya_build_fn(client)
        gate = make_golden_gate("chanakya", CHANAKYA_COLLECTION_BASE)
    else:
        from db.crisis_qdrant_client import COLLECTION_NAME, get_client

        client = get_client()
        build_fn = _crisis_build_fn(client)
        gate = make_golden_gate("crisis", CRISIS_COLLECTION_BASE)

    bump_version(client, COLLECTION_NAME, build_fn, gate_fn=gate)


if __name__ == "__main__":
    main()
