import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root, for `serving.*`

from serving.mode_config import MODE_CONFIG, Mode
from serving.sources import build_sources, chanakya_source_info, crisis_source_info, make_snippet


def test_snippet_short_text_is_unchanged_but_whitespace_collapsed():
    assert make_snippet("a  b\n\nc") == "a b c"


def test_snippet_drops_leading_bullet_marker():
    assert make_snippet("- The gap was long") == "The gap was long"


def test_snippet_cuts_at_word_boundary_with_ellipsis():
    text = "word " * 100
    snippet = make_snippet(text)
    assert snippet.endswith("…")
    assert len(snippet) <= 201
    assert "wor…" not in snippet  # never ends mid-word


def test_snippet_exact_boundary_cut():
    text = ("x" * 195) + " tail-word-that-overflows"
    assert make_snippet(text) == ("x" * 195) + "…"


def test_chanakya_label_uses_source_name_and_real_reference():
    info = chanakya_source_info({"source": "arthashastra", "reference": "Book IV, Chapter II", "domain_tags": ["ethics"]})
    assert info.label == "Arthashastra, Book IV, Chapter II"
    assert info.metadata == {"domain_tags": ["ethics"]}


def test_chanakya_label_drops_segment_artifact_and_handles_unknown_slug():
    assert chanakya_source_info({"source": "7_secrets_of_leadership", "reference": "segment 61"}).label == "7 Secrets of Leadership"
    assert chanakya_source_info({"source": "some_new_book"}).label == "Some New Book"
    assert chanakya_source_info({"source": "arthashastra"}).metadata == {"domain_tags": []}


def test_crisis_label_and_chips():
    info = crisis_source_info(
        {"company": "Byju's (Think & Learn Pvt. Ltd.)", "year": 2022, "crisis_type": "Governance", "industry": "Edtech",
         "resolution_status": "Unresolved", "onlyne_relevance": ["internal"], "transparency_score": 1}
    )
    assert info.label == "Byju's (2022)"
    assert info.metadata == {"crisis_type": "Governance", "industry": "Edtech", "resolution_status": "Unresolved"}


def test_build_sources_never_exposes_scores_and_leads_crisis_summary_with_trigger():
    chunk = SimpleNamespace(
        chunk_id="america_case_021_summary",
        score=0.9,
        dense_score=0.8,
        payload={"company": "Wells Fargo", "year": 2016, "chunk_type": "summary",
                 "text": "Company: Wells Fargo\nIndustry: Banking\nTrigger Event: Regulators announced fines.\nResolution Status: x"},
    )
    (ref,) = build_sources([chunk], MODE_CONFIG[Mode.CRISIS].source_info_fn)
    dumped = ref.model_dump()
    assert dumped["id"] == "america_case_021_summary"
    assert dumped["snippet"] == "Regulators announced fines."
    assert "score" not in str(dumped).lower()


def test_each_mode_has_its_own_source_info_fn():
    assert MODE_CONFIG[Mode.CHANAKYA].source_info_fn is chanakya_source_info
    assert MODE_CONFIG[Mode.CRISIS].source_info_fn is crisis_source_info
