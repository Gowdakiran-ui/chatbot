from classify_local import classify_batch, classify_chunk, scores_to_tags


def test_scores_to_tags_single_label_above_threshold():
    scores = {"career": 0.1, "leadership": 0.92, "ethics": 0.2, "general": 0.05}
    assert scores_to_tags(scores, threshold=0.5) == ["leadership"]


def test_scores_to_tags_multi_label_above_threshold():
    scores = {"career": 0.6, "leadership": 0.7, "ethics": 0.2, "general": 0.05}
    tags = scores_to_tags(scores, threshold=0.5)
    assert set(tags) == {"career", "leadership"}


def test_scores_to_tags_falls_back_to_general_when_nothing_crosses_threshold():
    scores = {"career": 0.2, "leadership": 0.3, "ethics": 0.1, "general": 0.05}
    assert scores_to_tags(scores, threshold=0.5) == ["general"]


def test_scores_to_tags_missing_label_treated_as_zero():
    scores = {"career": 0.9}  # leadership/ethics/general absent
    assert scores_to_tags(scores, threshold=0.5) == ["career"]


def test_scores_to_tags_never_returns_empty():
    assert scores_to_tags({}, threshold=0.5) == ["general"]


def _fake_classifier(texts: list[str], labels: list[str], **kwargs) -> list[dict]:
    # Deterministic stand-in for the real HF pipeline: first label always "wins".
    results = []
    for _ in texts:
        results.append({"labels": labels, "scores": [0.9] + [0.1] * (len(labels) - 1)})
    return results


def test_classify_batch_uses_injected_classifier_without_loading_model():
    texts = ["some chunk text", "another chunk text"]
    results = classify_batch(texts, classifier=_fake_classifier, labels=["career", "leadership", "ethics", "general"])
    assert len(results) == 2
    for tags, scores in results:
        assert tags == ["career"]
        assert scores["career"] == 0.9


def test_classify_batch_empty_input_returns_empty_list():
    assert classify_batch([], classifier=_fake_classifier) == []


def test_classify_chunk_single_text():
    tags, scores = classify_chunk("some text", classifier=_fake_classifier, labels=["career", "leadership", "ethics", "general"])
    assert tags == ["career"]
    assert isinstance(scores, dict)
