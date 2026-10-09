"""Offline copy of both knowledge bases, rebuilt in an in-memory Qdrant from data/snapshots/*.jsonl.

Same vectors, payloads, distance metric and RRF fusion as the cloud collections, so retrieval
behaves identically, but nothing here ever touches the live cluster. Build snapshots first with
`python -m scripts.snapshot_kb`.
"""
from __future__ import annotations

import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, SparseVector, SparseVectorParams, VectorParams

from db.config import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME, VECTOR_SIZE

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "snapshots"


def load_collection(client: QdrantClient, name: str) -> int:
    client.create_collection(
        name,
        vectors_config={DENSE_VECTOR_NAME: VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)},
        sparse_vectors_config={SPARSE_VECTOR_NAME: SparseVectorParams()},
    )
    batch, total = [], 0
    for line in (SNAPSHOT_DIR / f"{name}.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        sparse = row["sparse"]
        batch.append(PointStruct(
            id=row["point_id"],
            payload=row["payload"],
            vector={
                DENSE_VECTOR_NAME: row["dense"],
                SPARSE_VECTOR_NAME: SparseVector(indices=sparse["indices"], values=sparse["values"]),
            },
        ))
        if len(batch) == 256:
            client.upsert(name, batch); total += len(batch); batch = []
    if batch:
        client.upsert(name, batch); total += len(batch)
    return total


def build_offline_clients() -> dict[str, QdrantClient]:
    """One in-memory client per KB, mirroring the two-cluster production layout."""
    clients = {}
    for name in ("chanakya_kb", "crisis_kb"):
        c = QdrantClient(":memory:")
        load_collection(c, name)
        clients[name] = c
    return clients
