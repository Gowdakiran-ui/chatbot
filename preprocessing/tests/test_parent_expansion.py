import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root, for `db.*`

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from db.parent_expansion import MAX_EXPANDED_CHARS, expand_chanakya_chunk, expand_crisis_chunk

_NS = uuid.NAMESPACE_DNS


def _pid(chunk_id: str) -> str:
    return str(uuid.uuid5(_NS, chunk_id))


@pytest.fixture
def client():
    c = QdrantClient(":memory:")
    c.create_collection("kb", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    return c


def _put(client, chunk_id: str, payload: dict):
    payload = {"id": chunk_id, **payload}
    client.upload_points(
        "kb", points=[PointStruct(id=_pid(chunk_id), vector=[0.1, 0.2], payload=payload)], wait=True
    )


def test_expand_chanakya_verse_concatenates_siblings_in_order(client):
    _put(client, "arthashastra_book_ii_chapter_i_002", {
        "source": "arthashastra", "chunk_type": "verse", "parent_id": "arthashastra_book_ii_chapter_i", "text": "second"
    })
    _put(client, "arthashastra_book_ii_chapter_i_001", {
        "source": "arthashastra", "chunk_type": "verse", "parent_id": "arthashastra_book_ii_chapter_i", "text": "first"
    })
    _put(client, "arthashastra_book_ii_chapter_i_003", {
        "source": "arthashastra", "chunk_type": "verse", "parent_id": "arthashastra_book_ii_chapter_i", "text": "third"
    })
    # An unrelated chapter's chunk must not leak in.
    _put(client, "arthashastra_book_iii_chapter_i_001", {
        "source": "arthashastra", "chunk_type": "verse", "parent_id": "arthashastra_book_iii_chapter_i", "text": "unrelated"
    })

    payload = {"id": "arthashastra_book_ii_chapter_i_002", "parent_id": "arthashastra_book_ii_chapter_i",
               "source": "arthashastra", "text": "second"}
    result = expand_chanakya_chunk(client, "kb", payload)

    assert result == "first\n\nsecond\n\nthird"


def test_expand_chanakya_prose_uses_neighbor_window(client):
    _put(client, "corporate_chanakya_segment_9_001", {"source": "corporate_chanakya", "chunk_type": "prose", "parent_id": None, "text": "nine"})
    _put(client, "corporate_chanakya_segment_10_001", {"source": "corporate_chanakya", "chunk_type": "prose", "parent_id": None, "text": "ten"})
    _put(client, "corporate_chanakya_segment_11_001", {"source": "corporate_chanakya", "chunk_type": "prose", "parent_id": None, "text": "eleven"})

    payload = {"id": "corporate_chanakya_segment_10_001", "parent_id": None, "source": "corporate_chanakya", "text": "ten"}
    result = expand_chanakya_chunk(client, "kb", payload)

    assert result == "nine\n\nten\n\neleven"


def test_expand_chanakya_prose_at_source_boundary_has_no_previous(client):
    _put(client, "corporate_chanakya_segment_1_001", {"source": "corporate_chanakya", "chunk_type": "prose", "parent_id": None, "text": "one"})
    _put(client, "corporate_chanakya_segment_2_001", {"source": "corporate_chanakya", "chunk_type": "prose", "parent_id": None, "text": "two"})

    payload = {"id": "corporate_chanakya_segment_1_001", "parent_id": None, "source": "corporate_chanakya", "text": "one"}
    result = expand_chanakya_chunk(client, "kb", payload)

    assert result == "one\n\ntwo"


def test_expand_chanakya_falls_back_to_own_text_with_no_group_or_neighbors(client):
    _put(client, "chanakya_info_segment_5_001", {"source": "chanakya_info", "chunk_type": "prose", "parent_id": None, "text": "only chunk"})

    payload = {"id": "chanakya_info_segment_5_001", "parent_id": None, "source": "chanakya_info", "text": "only chunk"}
    result = expand_chanakya_chunk(client, "kb", payload)

    assert result == "only chunk"


def test_expand_chanakya_truncates_very_large_groups(client):
    for i in range(1, 30):
        _put(client, f"arthashastra_book_ii_chapter_i_{i:03d}", {
            "source": "arthashastra", "chunk_type": "verse", "parent_id": "arthashastra_book_ii_chapter_i",
            "text": "x" * 500,
        })

    payload = {"id": "arthashastra_book_ii_chapter_i_001", "parent_id": "arthashastra_book_ii_chapter_i",
               "source": "arthashastra", "text": "x" * 500}
    result = expand_chanakya_chunk(client, "kb", payload)

    assert len(result) == MAX_EXPANDED_CHARS


def test_expand_crisis_section_returns_summary_text(client):
    _put(client, "india_case_003_summary", {"case_id": "india_case_003", "chunk_type": "summary", "text": "full case summary"})
    _put(client, "india_case_003_trigger_event", {"case_id": "india_case_003", "chunk_type": "trigger_event", "text": "the trigger"})

    payload = {"id": "india_case_003_trigger_event", "case_id": "india_case_003", "chunk_type": "trigger_event", "text": "the trigger"}
    result = expand_crisis_chunk(client, "kb", payload)

    assert result == "full case summary"


def test_expand_crisis_summary_chunk_returns_itself(client):
    _put(client, "india_case_003_summary", {"case_id": "india_case_003", "chunk_type": "summary", "text": "full case summary"})

    payload = {"id": "india_case_003_summary", "case_id": "india_case_003", "chunk_type": "summary", "text": "full case summary"}
    result = expand_crisis_chunk(client, "kb", payload)

    assert result == "full case summary"


def test_expand_crisis_falls_back_when_parent_missing(client):
    _put(client, "india_case_099_trigger_event", {"case_id": "india_case_099", "chunk_type": "trigger_event", "text": "orphaned chunk"})

    payload = {"id": "india_case_099_trigger_event", "case_id": "india_case_099", "chunk_type": "trigger_event", "text": "orphaned chunk"}
    result = expand_crisis_chunk(client, "kb", payload)

    assert result == "orphaned chunk"
