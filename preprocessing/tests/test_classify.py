from classify import build_batch_prompt, needs_review, parse_classification_response


def test_parse_classification_response_happy_path():
    raw = '[{"tags": ["career"], "confidence": 0.9}, {"tags": ["ethics", "leadership"], "confidence": 0.7}]'
    results = parse_classification_response(raw, expected_count=2)
    assert results[0]["tags"] == ["career"]
    assert results[1]["tags"] == ["ethics", "leadership"]


def test_parse_classification_response_strips_markdown_fence():
    raw = '```json\n[{"tags": ["general"], "confidence": 0.5}]\n```'
    results = parse_classification_response(raw, expected_count=1)
    assert results[0]["tags"] == ["general"]


def test_parse_classification_response_filters_unknown_tags():
    raw = '[{"tags": ["career", "not_a_real_tag"], "confidence": 0.8}]'
    results = parse_classification_response(raw, expected_count=1)
    assert results[0]["tags"] == ["career"]


def test_parse_classification_response_pads_short_response():
    raw = '[{"tags": ["career"], "confidence": 0.9}]'
    results = parse_classification_response(raw, expected_count=3)
    assert len(results) == 3
    assert results[1] == {"tags": [], "confidence": 0.0}
    assert results[2] == {"tags": [], "confidence": 0.0}


def test_parse_classification_response_malformed_json_returns_empty():
    results = parse_classification_response("not json at all", expected_count=2)
    assert all(r["tags"] == [] and r["confidence"] == 0.0 for r in results)


def test_needs_review_flags_empty_tags_or_low_confidence():
    assert needs_review({"tags": [], "confidence": 0.0})
    assert needs_review({"tags": ["career"], "confidence": 0.2}, threshold=0.5)
    assert not needs_review({"tags": ["career"], "confidence": 0.9}, threshold=0.5)


def test_build_batch_prompt_includes_all_chunks_in_order():
    prompt = build_batch_prompt(["first chunk", "second chunk"])
    assert "1. first chunk" in prompt
    assert "2. second chunk" in prompt
