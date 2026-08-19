"""Versioned collections + alias management — shared by both the Chanakya and Crisis
KBs (Piece 2 of the hardening task).

Data lives in "{base}_v{n}" collections; clients (ingestion scripts, queries) read/write
through a plain alias ("chanakya_kb", "crisis_kb") that always points at whichever
version is currently live. A version bump populates a brand new "{base}_v{n+1}"
collection in full, gates it (Piece 4), and only then atomically repoints the alias —
so a bad ingest run can never corrupt what's currently being served. Old versions are
never deleted here; they're the rollback target.
"""
from __future__ import annotations

import re

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    Distance,
    VectorParams,
)

_VERSION_RE = re.compile(r"^(?P<base>.+)_v(?P<version>\d+)$")


def collection_name(base: str, version: int) -> str:
    return f"{base}_v{version}"


def parse_version(name: str, base: str) -> int | None:
    m = _VERSION_RE.match(name)
    if not m or m.group("base") != base:
        return None
    return int(m.group("version"))


def list_versions(client: QdrantClient, base: str) -> list[int]:
    """All existing "{base}_v{n}" collection versions, sorted ascending."""
    all_collections = [c.name for c in client.get_collections().collections]
    versions = [v for name in all_collections if (v := parse_version(name, base)) is not None]
    return sorted(versions)


def current_alias_target(client: QdrantClient, alias: str) -> str | None:
    """The collection an alias currently points at, or None if the alias doesn't exist."""
    for a in client.get_aliases().aliases:
        if a.alias_name == alias:
            return a.collection_name
    return None


def flip_alias(client: QdrantClient, alias: str, target_collection: str) -> None:
    """Atomically repoints `alias` at `target_collection` — a single
    update_collection_aliases call with delete+create, so there's no window where the
    alias resolves to nothing. If the alias doesn't exist yet, this just creates it."""
    if not client.collection_exists(target_collection):
        raise RuntimeError(f"Cannot point alias '{alias}' at nonexistent collection '{target_collection}'")

    operations = []
    if current_alias_target(client, alias) is not None:
        operations.append(DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=alias)))
    operations.append(
        CreateAliasOperation(create_alias=CreateAlias(collection_name=target_collection, alias_name=alias))
    )
    client.update_collection_aliases(change_aliases_operations=operations)


def clone_collection_to_version(
    client: QdrantClient, source_collection: str, base: str, version: int, batch_size: int = 500
) -> str:
    """Copies every point (vector + payload, unchanged) from `source_collection` into a
    brand-new "{base}_v{version}" collection, without re-embedding — used once, to turn
    the original un-versioned "chanakya_kb"/"crisis_kb" collection into "_v1" before it
    becomes an alias. Verifies the point count matches before returning."""
    new_name = collection_name(base, version)
    if client.collection_exists(new_name):
        raise RuntimeError(f"'{new_name}' already exists — refusing to overwrite")

    src_info = client.get_collection(source_collection)
    client.create_collection(
        collection_name=new_name,
        vectors_config=VectorParams(
            size=src_info.config.params.vectors.size, distance=src_info.config.params.vectors.distance
        ),
    )

    total = 0
    offset = None
    while True:
        points, offset = client.scroll(
            source_collection, limit=batch_size, offset=offset, with_payload=True, with_vectors=True
        )
        if points:
            client.upload_points(collection_name=new_name, points=points, wait=True)
            total += len(points)
        if offset is None:
            break

    src_count = client.count(source_collection).count
    new_count = client.count(new_name).count
    if new_count != src_count:
        raise RuntimeError(
            f"Clone count mismatch: '{source_collection}' has {src_count} points, "
            f"'{new_name}' has {new_count} after clone — not deleting the source."
        )
    print(f"Cloned {new_count} points from '{source_collection}' to '{new_name}'")
    return new_name


def bootstrap_alias(client: QdrantClient, base: str) -> str:
    """One-time migration: turns a plain, un-versioned collection named `base`
    (e.g. "chanakya_kb") into "{base}_v1" plus an alias `base` pointing at it. Idempotent
    — if `base` is already an alias, this is a no-op and just returns the current target.

    Returns the version-1 collection name.
    """
    existing_alias_target = current_alias_target(client, base)
    if existing_alias_target is not None:
        print(f"'{base}' is already an alias -> '{existing_alias_target}'; nothing to bootstrap.")
        return existing_alias_target

    if not client.collection_exists(base):
        raise RuntimeError(f"Neither a collection nor an alias named '{base}' exists — nothing to bootstrap from.")

    v1_name = clone_collection_to_version(client, base, base, version=1)

    # Free the plain name so it can become the alias. Only reached after clone_collection_to_version
    # has already verified the point counts match, so this never risks losing data.
    client.delete_collection(base)
    flip_alias(client, base, v1_name)
    print(f"'{base}' is now an alias -> '{v1_name}'")
    return v1_name
