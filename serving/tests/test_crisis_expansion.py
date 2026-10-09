"""expand_crisis_case keeps the matched advice sections instead of swapping them for the summary."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from db.parent_expansion import expand_crisis_case

NS = uuid.NAMESPACE_DNS


def _payload(case: str, kind: str, text: str) -> dict:
    return {"id": f"{case}_{kind}", "case_id": case, "chunk_type": kind, "text": text}


class _FakeClient:
    def __init__(self, rows: list[dict]):
        self._by_point = {str(uuid.uuid5(NS, r["id"])): r for r in rows}

    def retrieve(self, collection, ids, with_payload=True):
        return [SimpleNamespace(payload=self._by_point[i]) for i in ids if i in self._by_point]


def _case(case: str = "america_case_004") -> list[dict]:
    return [_payload(case, k, f"{k} text") for k in ("summary", "trigger_event", "went_right", "went_wrong", "best_practice")]


def test_matched_section_text_reaches_the_context():
    rows = _case()
    out = expand_crisis_case(_FakeClient(rows), "crisis_kb", [rows[3]])  # only went_wrong matched
    assert "went_wrong text" in out
    assert out.startswith("summary text")


def test_best_practice_is_always_added_even_when_not_matched():
    rows = _case()
    out = expand_crisis_case(_FakeClient(rows), "crisis_kb", [rows[2]])  # only went_right matched
    assert "Lesson / best practice:\nbest_practice text" in out
    assert "went_wrong text" not in out  # unmatched sections other than best_practice stay out


def test_multiple_hits_of_one_case_merge_in_a_stable_order():
    rows = _case()
    out = expand_crisis_case(_FakeClient(rows), "crisis_kb", [rows[3], rows[2]])
    assert out.index("What went right") < out.index("What went wrong") < out.index("Lesson / best practice")


def test_summary_hit_alone_still_gets_best_practice():
    rows = _case()
    out = expand_crisis_case(_FakeClient(rows), "crisis_kb", [rows[0]])
    assert out.count("summary text") == 1 and "best_practice text" in out
