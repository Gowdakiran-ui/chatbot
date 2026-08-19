"""Piece 5 — parent-child chunk expansion.

Retrieval matches on small, precise chunks; these functions expand a retrieved chunk to
its fuller context before handing that text to the generation layer. This is a
serving-side operation (it runs *after* retrieval, on whatever chunk(s) came back) but
lives here because it operates on the exact payload schema this task defines
(`parent_id`, `case_id`) — it's meant to be called from the serving code being built
separately, not wired into anything in this repo yet.
"""
from __future__ import annotations

import re
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

_ID_NAMESPACE = uuid.NAMESPACE_DNS
_TRAILING_SEQ_RE = re.compile(r"_(\d+)$")
_SEGMENT_NUM_RE = re.compile(r"_segment_(\d+)_\d+$")

# A verse-chapter parent group can have many siblings (up to several dozen for a long
# Arthashastra chapter) — cap how much concatenated text goes to the LLM in one shot.
MAX_EXPANDED_CHARS = 8000


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, chunk_id))


def _seq_number(chunk_id: str) -> int:
    m = _TRAILING_SEQ_RE.search(chunk_id)
    return int(m.group(1)) if m else 0


def _segment_number(chunk_id: str) -> int | None:
    """Extracts the "N" from a prose chunk id like "corporate_chanakya_segment_N_001" —
    distinct from _seq_number(), which reads the trailing "_001" (always 1 for prose,
    since chunk_prose_style gives every chunk a unique "segment N" reference)."""
    m = _SEGMENT_NUM_RE.search(chunk_id)
    return int(m.group(1)) if m else None


def expand_chanakya_chunk(client: QdrantClient, collection: str, payload: dict) -> str:
    """Expands a retrieved Chanakya chunk to its fuller context:
    - verse-type chunks (Arthashastra, Chanakya Neeti) with a parent_id: concatenates
      every sibling chunk sharing that book/chapter group key, in original order.
    - prose-type chunks (Corporate Chanakya, 7 Secrets, chanakya_info bio) or any chunk
      with no parent_id: falls back to a neighbor window — the adjacent segment(s) in
      the same source, since these chunks already carry ~15% overlap and there's no
      larger structural unit in the source to group by.
    Falls back to the chunk's own text if no expansion is available (e.g. it's the only
    chunk in its group, or a neighbor doesn't exist at a source boundary).
    """
    parent_id = payload.get("parent_id")

    if parent_id:
        results, _ = client.scroll(
            collection_name=collection,
            scroll_filter=Filter(must=[FieldCondition(key="parent_id", match=MatchValue(value=parent_id))]),
            limit=200,
            with_payload=True,
            with_vectors=False,
        )
        siblings = sorted(results, key=lambda p: _seq_number(p.payload["id"]))
        text = "\n\n".join(s.payload["text"] for s in siblings)
        if text:
            return text[:MAX_EXPANDED_CHARS]

    # Prose fallback: pull in the immediately preceding/following segment, if any.
    source = payload["source"]
    seg = _segment_number(payload["id"])
    if seg is None:
        return payload["text"]
    neighbor_ids = [f"{source}_segment_{seg - 1}_001", payload["id"], f"{source}_segment_{seg + 1}_001"]
    points = client.retrieve(collection, ids=[_point_id(cid) for cid in neighbor_ids], with_payload=True)
    if not points:
        return payload["text"]
    ordered = sorted(points, key=lambda p: _segment_number(p.payload["id"]) or 0)
    return "\n\n".join(p.payload["text"] for p in ordered)[:MAX_EXPANDED_CHARS]


def expand_crisis_chunk(client: QdrantClient, collection: str, payload: dict) -> str:
    """Expands a retrieved Crisis section chunk (trigger_event/went_right/went_wrong/
    best_practice) to its case's summary — the case's `case_id` field already makes the
    parent derivable (f"{case_id}_summary") without a separate parent_id field, so
    that's what this constructs rather than reading a stored parent_id. Summary chunks
    themselves have no parent to expand to; returns their own text unchanged."""
    if payload.get("chunk_type") == "summary":
        return payload["text"]

    parent_chunk_id = f"{payload['case_id']}_summary"
    points = client.retrieve(collection, ids=[_point_id(parent_chunk_id)], with_payload=True)
    if not points:
        return payload["text"]
    return points[0].payload["text"]
