"""Tests for db/versioning.py and db/version_bump.py — run against an in-memory Qdrant
instance (":memory:"), not Cloud. This is test infrastructure only; the project's "no
local embedded Qdrant" constraint is about production storage, not test isolation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root, for `db.*`

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from db.version_bump import bump_version, next_version
from db.versioning import (
    bootstrap_alias,
    clone_collection_to_version,
    collection_name,
    current_alias_target,
    flip_alias,
    list_versions,
    parse_version,
)


@pytest.fixture
def client():
    return QdrantClient(":memory:")


def _seed_collection(client, name, n_points=5, size=4):
    client.create_collection(name, vectors_config=VectorParams(size=size, distance=Distance.COSINE))
    points = [
        PointStruct(id=i, vector=[float(i)] * size, payload={"n": i}) for i in range(n_points)
    ]
    client.upload_points(collection_name=name, points=points, wait=True)


def test_collection_name_and_parse_version_roundtrip():
    assert collection_name("chanakya_kb", 3) == "chanakya_kb_v3"
    assert parse_version("chanakya_kb_v3", "chanakya_kb") == 3
    assert parse_version("chanakya_kb_v3", "crisis_kb") is None
    assert parse_version("chanakya_kb", "chanakya_kb") is None  # no _vN suffix


def test_list_versions_sorted(client):
    _seed_collection(client, "foo_v2")
    _seed_collection(client, "foo_v1")
    _seed_collection(client, "foo_v10")
    _seed_collection(client, "bar_v1")  # different base, must not leak in
    assert list_versions(client, "foo") == [1, 2, 10]


def test_bootstrap_alias_migrates_plain_collection(client):
    _seed_collection(client, "foo", n_points=7)
    assert current_alias_target(client, "foo") is None

    v1 = bootstrap_alias(client, "foo")

    assert v1 == "foo_v1"
    assert current_alias_target(client, "foo") == "foo_v1"
    assert client.count("foo").count == 7
    assert client.count("foo_v1").count == 7
    assert not client.collection_exists("foo") or current_alias_target(client, "foo") == "foo_v1"


def test_bootstrap_alias_is_idempotent(client):
    _seed_collection(client, "foo", n_points=3)
    v1_first = bootstrap_alias(client, "foo")
    v1_second = bootstrap_alias(client, "foo")
    assert v1_first == v1_second == "foo_v1"


def test_flip_alias_atomically_repoints(client):
    _seed_collection(client, "foo_v1", n_points=3)
    _seed_collection(client, "foo_v2", n_points=9)
    flip_alias(client, "foo", "foo_v1")
    assert current_alias_target(client, "foo") == "foo_v1"
    assert client.count("foo").count == 3

    flip_alias(client, "foo", "foo_v2")
    assert current_alias_target(client, "foo") == "foo_v2"
    assert client.count("foo").count == 9


def test_flip_alias_rejects_nonexistent_target(client):
    with pytest.raises(RuntimeError):
        flip_alias(client, "foo", "foo_v99")


def test_clone_collection_verifies_count(client):
    _seed_collection(client, "foo", n_points=6)
    new_name = clone_collection_to_version(client, "foo", "foo", version=1)
    assert new_name == "foo_v1"
    assert client.count("foo_v1").count == 6


def test_bump_version_without_gate_does_not_flip_alias(client):
    _seed_collection(client, "foo_v1", n_points=3)
    flip_alias(client, "foo", "foo_v1")

    def build_fn(new_name):
        _seed_collection(client, new_name, n_points=8)
        return 8

    result_name = bump_version(client, "foo", build_fn, gate_fn=None)

    assert result_name == "foo_v2"
    assert client.collection_exists("foo_v2")
    # No gate configured -> alias must NOT move automatically.
    assert current_alias_target(client, "foo") == "foo_v1"


def test_bump_version_flips_alias_only_when_gate_passes(client):
    _seed_collection(client, "foo_v1", n_points=3)
    flip_alias(client, "foo", "foo_v1")

    def build_fn(new_name):
        _seed_collection(client, new_name, n_points=8)
        return 8

    def failing_gate(client_, candidate):
        return False, "recall@5 regressed"

    bump_version(client, "foo", build_fn, gate_fn=failing_gate)
    assert current_alias_target(client, "foo") == "foo_v1"  # unchanged on failure

    def passing_gate(client_, candidate):
        return True, "recall@5 ok"

    result_name = bump_version(client, "foo", build_fn, gate_fn=passing_gate)
    assert result_name == "foo_v3"  # v2 already exists from the failed-gate attempt
    assert current_alias_target(client, "foo") == "foo_v3"


def test_bump_version_refuses_to_overwrite_existing_version(client, monkeypatch):
    # next_version() always picks a fresh slot dynamically, so a same-process collision
    # can't happen in single-threaded use — the guard exists for a genuine TOCTOU race
    # (two concurrent bump_version calls). Simulate that race by forcing next_version()
    # to return an already-taken number.
    import db.version_bump as version_bump_module

    _seed_collection(client, "foo_v1", n_points=3)
    flip_alias(client, "foo", "foo_v1")
    _seed_collection(client, "foo_v2", n_points=1)  # the "other concurrent call" already landed

    monkeypatch.setattr(version_bump_module, "next_version", lambda client_, base: 2)

    with pytest.raises(RuntimeError):
        bump_version(client, "foo", lambda new_name: 0, gate_fn=None)


def test_next_version_starts_at_one(client):
    assert next_version(client, "brand_new_base") == 1
    _seed_collection(client, "brand_new_base_v1")
    assert next_version(client, "brand_new_base") == 2
