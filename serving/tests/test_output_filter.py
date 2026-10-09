"""Pure-function tests for serving/output_filter.py and sources.select_used_chunks."""
from __future__ import annotations

from types import SimpleNamespace

from serving.output_filter import ChunkIdStripper, strip_chunk_ids, verse_refs_not_in_context
from serving.sources import crisis_source_info, select_used_chunks

IDS = ["america_case_009_went_right", "america_case_033_went_right"]


def _stream(tokens: list[str], ids: list[str] = IDS) -> str:
    stripper = ChunkIdStripper(ids)
    return "".join(stripper.feed(t) for t in tokens) + stripper.flush()


def test_strips_bracketed_known_ids():
    out = strip_chunk_ids("Starbucks [america_case_009_went_right] acted fast.", IDS)
    assert "america_case" not in out
    assert out == "Starbucks acted fast."


def test_strips_unknown_but_id_shaped_tokens():
    assert "segment_61_001" not in strip_chunk_ids("As in (7_secrets_of_leadership_segment_61_001) shows.")


def test_tidies_separator_left_between_removed_ids():
    out = strip_chunk_ids("Starbucks (2018) / [america_case_009_went_right] and [america_case_033_went_right]: speed.", IDS)
    assert "america_case" not in out and "/ and" not in out


def test_plain_text_untouched():
    text = "Look to the treasury first (Book 2, Chapter 8). Verse 2.8.1 says so."
    assert strip_chunk_ids(text, IDS) == text


def test_stream_handles_id_split_across_tokens():
    out = _stream(["Starbucks [america_", "case_009_went", "_right] acted", " fast."])
    assert out == "Starbucks acted fast."


def test_stream_flushes_trailing_partial_word():
    assert _stream(["Hello wor", "ld"]) == "Hello world"


def test_verse_refs_flags_only_unsupported():
    context = ["...Arthashastra 7.5.19 says ..."]
    assert verse_refs_not_in_context("See 7.5.19 and 1.8.25.", context) == ["1.8.25"]
    assert verse_refs_not_in_context("No refs here.", context) == []


def _chunk(chunk_id: str, text: str, company: str = "") -> SimpleNamespace:
    return SimpleNamespace(chunk_id=chunk_id, text=text, payload={"company": company, "year": 2017})


def test_select_used_chunks_by_shared_wording():
    used = _chunk("a", "A leader must trust his managers and treat them as equals in every decision")
    unused = _chunk("b", "Dowry is illegal even though the bridegroom's party asked for it")
    answer = "You must trust his managers and treat them as equals in every decision you make."
    got = select_used_chunks(answer, [used, unused], crisis_source_info, match_label=False)
    assert [c.chunk_id for c in got] == ["a"]


def test_select_used_chunks_by_label_only_when_enabled():
    chunk = _chunk("c", "unrelated text body here", company="Equifax")
    answer = "The Equifax case shows delay is costly."
    assert select_used_chunks(answer, [chunk], crisis_source_info, match_label=True) == [chunk]
    assert select_used_chunks(answer, [chunk], crisis_source_info, match_label=False) == []
