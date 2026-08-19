"""Local, zero-shot domain classification for the Chanakya KB — no LLM, no API call.

Replaces the Anthropic-based classify.py for this pass: `typeform/distilbert-base-
uncased-mnli` runs entirely on CPU via `transformers`' zero-shot-classification
pipeline. Model auto-downloads once from HuggingFace (~250MB), then runs offline.

`scores_to_tags` is the pure, unit-testable piece (thresholding + fallback logic, no
model). `classify_chunk`/`classify_batch` wrap it around an injectable classifier
callable so they're testable too, without needing to load the real model.
"""
from __future__ import annotations

from typing import Callable

from config import CLASSIFICATION_CONFIDENCE_THRESHOLD, DOMAIN_TAGS

# Signature matches a HuggingFace zero-shot-classification pipeline's return shape for
# one input: {"labels": [...], "scores": [...]} (both lists, same order, descending score).
ClassifierFn = Callable[[list[str], list[str]], list[dict]]

_MODEL_NAME = "typeform/distilbert-base-uncased-mnli"
_pipeline = None


def get_classifier() -> ClassifierFn:
    """Lazily loads and caches the local zero-shot pipeline (impure: loads model
    weights). First call downloads ~250MB from HuggingFace if not already cached."""
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline

        _pipeline = pipeline("zero-shot-classification", model=_MODEL_NAME)
    return _pipeline


def scores_to_tags(
    scores: dict[str, float], threshold: float = CLASSIFICATION_CONFIDENCE_THRESHOLD
) -> list[str]:
    """Pure function: label->score dict -> list of tags above threshold, multi-label.
    Falls back to ["general"] if nothing crosses the threshold — a chunk never ends up
    with empty domain_tags."""
    tags = [label for label in DOMAIN_TAGS if scores.get(label, 0.0) > threshold]
    return tags if tags else ["general"]


def classify_batch(
    texts: list[str],
    classifier: ClassifierFn | None = None,
    labels: list[str] = DOMAIN_TAGS,
    threshold: float = CLASSIFICATION_CONFIDENCE_THRESHOLD,
    batch_size: int = 16,
) -> list[tuple[list[str], dict[str, float]]]:
    """Classifies a batch of chunk texts. Returns a list of (tags, scores) pairs, one
    per input text, in order. `classifier` is injectable (real pipeline by default,
    a fake callable in tests) so this stays testable without loading the model."""
    if not texts:
        return []

    clf = classifier or get_classifier()
    raw_results = clf(texts, labels, multi_label=True, batch_size=batch_size)
    if isinstance(raw_results, dict):  # pipeline returns a single dict for one input
        raw_results = [raw_results]

    results = []
    for r in raw_results:
        scores = dict(zip(r["labels"], r["scores"]))
        results.append((scores_to_tags(scores, threshold), scores))
    return results


def classify_chunk(
    text: str,
    classifier: ClassifierFn | None = None,
    labels: list[str] = DOMAIN_TAGS,
    threshold: float = CLASSIFICATION_CONFIDENCE_THRESHOLD,
) -> tuple[list[str], dict[str, float]]:
    """Classifies a single chunk. Thin wrapper around classify_batch for a batch of 1."""
    return classify_batch([text], classifier, labels, threshold, batch_size=1)[0]
