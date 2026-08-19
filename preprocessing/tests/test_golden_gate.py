"""Tests for db/golden_gate.py and its wiring into db/version_bump.bump_version() —
in-memory Qdrant, a fake deterministic embed_query (no model load)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root, for `db.*`

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

import db.golden_gate as golden_gate_module
import db.run_golden_eval as run_golden_eval_module
from db.golden_gate import make_golden_gate
from db.version_bump import bump_version
from db.versioning import current_alias_target, flip_alias

# Three "documents" and three queries whose fake embeddings are engineered to match
# exactly one document each — recall is fully controllable this way.
_VECTORS = {
    "doc_a": [1.0, 0.0],
    "doc_b": [0.0, 1.0],
    "doc_c": [-1.0, 0.0],
}
_GOLDEN = [
    {"query": "find a", "expected_chunk_ids": ["doc_a"]},
    {"query": "find b", "expected_chunk_ids": ["doc_b"]},
    {"query": "find c", "expected_chunk_ids": ["doc_c"]},
]
_QUERY_VECTOR = {"find a": [1.0, 0.0], "find b": [0.0, 1.0], "find c": [-1.0, 0.0]}


@pytest.fixture
def client():
    return QdrantClient(":memory:")


@pytest.fixture(autouse=True)
def _patch_embed_and_golden(monkeypatch):
    monkeypatch.setattr(run_golden_eval_module, "embed_query", lambda text: _QUERY_VECTOR[text])
    monkeypatch.setattr(golden_gate_module, "load_golden_queries", lambda kb: _GOLDEN)


def _seed(client, name, doc_ids):
    client.create_collection(name, vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    points = [PointStruct(id=i, vector=_VECTORS[d], payload={"id": d}) for i, d in enumerate(doc_ids)]
    client.upload_points(collection_name=name, points=points, wait=True)


def test_gate_passes_when_candidate_matches_baseline(client):
    _seed(client, "foo_v1", ["doc_a", "doc_b", "doc_c"])
    _seed(client, "foo_v2", ["doc_a", "doc_b", "doc_c"])

    gate = make_golden_gate("foo", "foo", floor=0.5)
    passed, detail = gate(client, "foo_v2")

    assert passed
    assert "100.0%" in detail


def test_gate_fails_when_candidate_regresses_below_baseline(client):
    _seed(client, "foo_v1", ["doc_a", "doc_b", "doc_c"])
    # Candidate only has doc_a and doc_c — "find b" can't recall doc_b at all.
    _seed(client, "foo_v2", ["doc_a", "doc_c"])

    gate = make_golden_gate("foo", "foo", floor=0.5)
    passed, detail = gate(client, "foo_v2")

    assert not passed
    assert "find b" in detail


def test_gate_uses_the_stricter_of_baseline_or_floor(client):
    # Baseline itself only recalls 1/3 (doc_a present, doc_b/doc_c missing) — floor
    # should still block a candidate that merely matches that weak baseline.
    _seed(client, "foo_v1", ["doc_a"])
    _seed(client, "foo_v2", ["doc_a"])

    gate = make_golden_gate("foo", "foo", floor=0.90)
    passed, detail = gate(client, "foo_v2")

    assert not passed
    assert "floor=90.0%" in detail


def test_bump_version_promotes_only_when_golden_gate_passes(client):
    _seed(client, "foo_v1", ["doc_a", "doc_b", "doc_c"])
    flip_alias(client, "foo", "foo_v1")
    gate = make_golden_gate("foo", "foo", floor=0.5)

    # A bad rebuild: gate should block promotion.
    def bad_build_fn(new_name):
        _seed(client, new_name, ["doc_a"])  # missing doc_b, doc_c
        return client.count(new_name).count

    bump_version(client, "foo", bad_build_fn, gate_fn=gate)
    assert current_alias_target(client, "foo") == "foo_v1"  # unchanged

    # A good rebuild: gate should promote it.
    def good_build_fn(new_name):
        _seed(client, new_name, ["doc_a", "doc_b", "doc_c"])
        return client.count(new_name).count

    result_name = bump_version(client, "foo", good_build_fn, gate_fn=gate)
    assert current_alias_target(client, "foo") == result_name
