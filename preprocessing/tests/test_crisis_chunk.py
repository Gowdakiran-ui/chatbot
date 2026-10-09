from crisis_chunk import build_case_chunks, build_section_chunks, build_summary_chunk, split_section_if_too_long
from crisis_config import CrisisChunkType, Region
from crisis_schema import ParsedCase


def _sample_case(**overrides) -> ParsedCase:
    defaults = dict(
        case_id="india_case_001",
        region=Region.INDIA,
        source_file="sample.md",
        company="Satyam Computer Services",
        industry="IT Services",
        year_raw="2009",
        year=2009,
        crisis_type="Accounting Fraud",
        trigger_event="Founder-chairman confessed to inflating profits.",
        response_type="Reactive",
        response_speed_score_raw="2",
        response_speed_score=2,
        transparency_score_raw="2",
        transparency_score=2,
        legal_framework="SEBI investigation",
        resolution_status_raw="Resolved (company survived)",
        resolution_status="Resolved (company survived)",
        went_right="Government intervened within days.",
        went_wrong="Fraud went undetected for 7 years.",
        best_practice="Independent directors should have insisted on a forensic audit.",
        estimated_impact="₹7,800 crore fraud.",
        onlyne_relevance=["ORM", "Crisis Comms"],
        key_sources="SEC.gov",
    )
    defaults.update(overrides)
    return ParsedCase(**defaults)


def test_build_summary_chunk_concatenates_expected_fields():
    case = _sample_case()
    chunk = build_summary_chunk(case)
    assert chunk.id == "india_case_001_summary"
    assert chunk.chunk_type == CrisisChunkType.SUMMARY
    for field in [case.company, case.industry, case.crisis_type, case.trigger_event, case.estimated_impact]:
        assert field in chunk.text
    assert chunk.metadata.case_id == "india_case_001"
    assert chunk.metadata.region == Region.INDIA


def test_build_section_chunks_produces_four_chunks():
    case = _sample_case()
    chunks = build_section_chunks(case)
    assert len(chunks) == 4
    ids = {c.id for c in chunks}
    assert ids == {
        "india_case_001_trigger_event",
        "india_case_001_went_right",
        "india_case_001_went_wrong",
        "india_case_001_best_practice",
    }


def test_build_case_chunks_yields_seven_total():
    case = _sample_case()
    chunks = build_case_chunks(case)
    assert len(chunks) == 7
    assert chunks[0].chunk_type == CrisisChunkType.SUMMARY
    assert {c.chunk_type for c in chunks[-2:]} == {CrisisChunkType.RESPONSE_ASSESSMENT, CrisisChunkType.LEGAL_FRAMEWORK}


def test_assessment_chunk_carries_type_and_both_rationales():
    case = _sample_case(response_type="Delayed, then Reactive", response_speed_score_raw="1/5 - disclosed 40 days late", transparency_score_raw="2/5 - partial")
    chunk = build_case_chunks(case)[-2]
    assert chunk.id == "india_case_001_response_assessment"
    for needle in ("Delayed, then Reactive", "disclosed 40 days late", "partial"):
        assert needle in chunk.text


def test_legal_chunk_and_sources_metadata():
    case = _sample_case(legal_framework="SEBI probe and SFIO investigation", key_sources="SEC.gov")
    legal = build_case_chunks(case)[-1]
    assert legal.id == "india_case_001_legal_framework" and legal.text == "SEBI probe and SFIO investigation"
    assert legal.metadata.key_sources == "SEC.gov"


def test_metadata_shared_across_all_chunks():
    case = _sample_case()
    chunks = build_case_chunks(case)
    for c in chunks:
        assert c.metadata.company == "Satyam Computer Services"
        assert c.metadata.onlyne_relevance == ["ORM", "Crisis Comms"]


def test_split_section_if_too_long_keeps_short_text_whole():
    text = "A short section that doesn't need splitting."
    assert split_section_if_too_long(text, max_tokens=800) == [text]


def test_split_section_if_too_long_splits_long_paragraphs():
    paragraph = "This is a sentence about the crisis response. " * 40
    text = "\n\n".join([paragraph] * 5)  # well over 800 tokens total
    parts = split_section_if_too_long(text, max_tokens=200)
    assert len(parts) > 1
    # Nothing lost: every paragraph's distinctive content survives across parts.
    assert "".join(parts).count("crisis response") == 5 * paragraph.count("crisis response")


def test_build_section_chunks_splits_oversized_section_with_suffixed_ids():
    long_text = ("This is a long went_wrong section. " * 60 + "\n\n") * 5
    case = _sample_case(went_wrong=long_text)
    chunks = build_section_chunks(case)
    went_wrong_chunks = [c for c in chunks if c.chunk_type == CrisisChunkType.WENT_WRONG]
    assert len(went_wrong_chunks) > 1
    assert went_wrong_chunks[0].id == "india_case_001_went_wrong_1"
    assert went_wrong_chunks[1].id == "india_case_001_went_wrong_2"
