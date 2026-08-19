"""Version-bump orchestrator (Piece 2) — builds a brand-new "{base}_v{n+1}" collection
from scratch (a full re-embed, not a delta — Piece 1's manifest is for skipping
unchanged-doc work *within* a build, not for skipping whole-collection versioning) and
only flips the alias once a quality gate passes.

The gate is Piece 4's golden-query recall@5 check, wired in separately once that piece
exists. Until then, `gate_fn=None` means "no automated gate": bump_version() still
builds and count-verifies the new collection, but refuses to auto-flip the alias,
printing instructions for a manual review + rollback instead.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, SparseVector, SparseVectorParams, VectorParams

from db.config import DENSE_VECTOR_NAME, EMBED_BATCH_SIZE, SPARSE_VECTOR_NAME
from db.versioning import collection_name, current_alias_target, flip_alias, list_versions

# gate_fn(client, candidate_collection_name) -> (passed, human-readable detail)
GateFn = Callable[[QdrantClient, str], tuple[bool, str]]

# build_fn(new_collection_name) -> point count written
BuildFn = Callable[[str], int]


def next_version(client: QdrantClient, base: str) -> int:
    versions = list_versions(client, base)
    return (max(versions) + 1) if versions else 1


def bump_version(
    client: QdrantClient,
    base: str,
    build_fn: BuildFn,
    gate_fn: GateFn | None = None,
) -> str:
    """Never writes to `base` (the alias) directly — always builds into a fresh
    "{base}_v{n+1}" collection first, gates it, and only then flips the alias.
    Returns the new collection's name regardless of whether it got promoted."""
    new_version = next_version(client, base)
    new_name = collection_name(base, new_version)
    if client.collection_exists(new_name):
        raise RuntimeError(f"'{new_name}' already exists — refusing to overwrite")

    print(f"Building '{new_name}' ...")
    point_count = build_fn(new_name)
    print(f"Built '{new_name}': {point_count} points")

    if gate_fn is None:
        print(
            f"\nNo quality gate configured (Piece 4 not wired in yet) — '{new_name}' is built "
            f"and point-count-verified, but the alias was NOT flipped automatically.\n"
            f"Review it manually, then promote with:\n"
            f"  python -m db.rollback {base} {new_version}"
        )
        return new_name

    passed, detail = gate_fn(client, new_name)
    print(f"Gate result: {'PASS' if passed else 'FAIL'} - {detail}")
    if not passed:
        print(
            f"'{new_name}' built but NOT promoted — alias '{base}' still points at "
            f"'{current_alias_target(client, base)}'."
        )
        return new_name

    flip_alias(client, base, new_name)
    print(f"Gate passed — alias '{base}' now points at '{new_name}'")
    return new_name


def dense_only_build_fn(
    client: QdrantClient,
    jsonl_path: Path,
    embed_fn: Callable[[list[str]], list[list[float]]],
    id_fn: Callable[[dict], str],
    payload_fn: Callable[[dict], dict],
    vector_size: int,
    upload_batch_size: int = 100,
) -> BuildFn:
    """Reference build_fn: dense-vectors-only full rebuild from a source jsonl. Used to
    materialize "_v1" collections' schema for future version bumps that don't yet need
    Piece 3's sparse vectors. Piece 3 replaces/extends this with a hybrid build_fn when
    creating "_v2"."""

    def _build(new_collection_name: str) -> int:
        rows = [json.loads(l) for l in open(jsonl_path, encoding="utf-8") if l.strip()]

        client.create_collection(
            collection_name=new_collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

        for start in range(0, len(rows), upload_batch_size):
            batch = rows[start : start + upload_batch_size]
            vectors = embed_fn([r["text"] for r in batch])
            points = [
                PointStruct(id=id_fn(row), vector=vector, payload=payload_fn(row))
                for row, vector in zip(batch, vectors)
            ]
            client.upload_points(collection_name=new_collection_name, points=points, wait=True)

        return client.count(new_collection_name).count

    return _build


def hybrid_build_fn(
    client: QdrantClient,
    jsonl_path: Path,
    embed_dense_fn: Callable[[list[str]], list[list[float]]],
    embed_sparse_fn: Callable[[list[str]], list[SparseVector]],
    id_fn: Callable[[dict], str],
    payload_fn: Callable[[dict], dict],
    vector_size: int,
    dense_name: str = DENSE_VECTOR_NAME,
    sparse_name: str = SPARSE_VECTOR_NAME,
    batch_size: int = EMBED_BATCH_SIZE,
) -> BuildFn:
    """Piece 3: dense + sparse (BM25) hybrid build_fn — each point gets both a named
    dense vector and a named sparse vector, computed from the same `text` field. This is
    what creates a KB's "_v2" collection; "_v1" stays dense-only, per bump_version()
    never touching already-built versions."""

    def _build(new_collection_name: str) -> int:
        rows = [json.loads(l) for l in open(jsonl_path, encoding="utf-8") if l.strip()]

        client.create_collection(
            collection_name=new_collection_name,
            vectors_config={dense_name: VectorParams(size=vector_size, distance=Distance.COSINE)},
            sparse_vectors_config={sparse_name: SparseVectorParams()},
        )

        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            texts = [r["text"] for r in batch]
            dense_vectors = embed_dense_fn(texts)
            sparse_vectors = embed_sparse_fn(texts)
            points = [
                PointStruct(
                    id=id_fn(row),
                    vector={dense_name: dv, sparse_name: sv},
                    payload=payload_fn(row),
                )
                for row, dv, sv in zip(batch, dense_vectors, sparse_vectors)
            ]
            client.upload_points(collection_name=new_collection_name, points=points, wait=True)

        return client.count(new_collection_name).count

    return _build
