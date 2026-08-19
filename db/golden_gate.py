"""Piece 4 — wires the golden-query regression set into Piece 2's version-bump flow as
a hard gate: a candidate version only gets promoted if its recall@5 is at least as good
as the current "_v1" baseline, and at least a fixed floor. Whichever is stricter wins.
"""
from __future__ import annotations

from typing import Callable

from qdrant_client import QdrantClient

from db.run_golden_eval import evaluate, load_golden_queries
from db.version_bump import GateFn
from db.versioning import collection_name

DEFAULT_FLOOR = 0.90


def make_golden_gate(
    kb: str,
    base: str,
    floor: float = DEFAULT_FLOOR,
    baseline_version: int = 1,
) -> GateFn:
    """`kb` selects the golden query set ("chanakya" or "crisis"); `base` is the
    collection base name ("chanakya_kb" or "crisis_kb") the "_v1" baseline is read from.
    Returns a gate_fn(client, candidate_collection) -> (passed, detail) suitable for
    db.version_bump.bump_version()."""
    golden_queries = load_golden_queries(kb)
    baseline_name = collection_name(base, baseline_version)

    def gate_fn(client: QdrantClient, candidate_collection: str) -> tuple[bool, str]:
        baseline = evaluate(client, baseline_name, golden_queries)
        candidate = evaluate(client, candidate_collection, golden_queries)
        threshold = max(baseline["recall_at_k"], floor)
        passed = candidate["recall_at_k"] >= threshold

        detail = (
            f"candidate recall@5={candidate['recall_at_k']:.1%} vs "
            f"baseline({baseline_name})={baseline['recall_at_k']:.1%}, floor={floor:.1%} "
            f"(required >= {threshold:.1%})"
        )
        if not passed:
            failing = [row["query"] for row in candidate["rows"] if not row["hit"]]
            detail += f" — regressed on: {failing}"
        return passed, detail

    return gate_fn
