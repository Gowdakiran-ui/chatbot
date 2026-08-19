"""Step 3 — multi-label domain classification via a batched LLM call.

The only impure function is `classify_batch_via_llm` (makes the actual API call). Prompt
building and response parsing are pure and unit-testable without hitting the network.
"""
from __future__ import annotations

import json
import os

from config import CLASSIFICATION_CONFIDENCE_THRESHOLD, CLASSIFICATION_MODEL, DOMAIN_TAGS

_FEW_SHOT_EXAMPLES = [
    (
        "career",
        "A wise minister once said: choose the employer who tests your counsel before "
        "rewarding it, for such a master builds careers, not just fills posts.",
    ),
    (
        "leadership",
        "The king who listens to no one but himself will soon find himself surrounded by "
        "flatterers instead of advisors; true leadership is the discipline of seeking dissent.",
    ),
    (
        "ethics",
        "Wealth gained through deceit is a debt owed to one's own conscience, and it is repaid "
        "with interest in the currency of reputation.",
    ),
    (
        "general",
        "In those days, the kingdom was divided into provinces, each governed by an officer "
        "appointed directly by the crown.",
    ),
]

_SYSTEM_PROMPT = f"""You are a domain-tagging assistant for a knowledge base of Chanakya/Arthashastra
content that has been paraphrased into modern business advice.

For each numbered chunk of text, assign 1-2 tags from this fixed set: {DOMAIN_TAGS}.
- "career": individual professional growth, job/employer choice, skill-building, promotion.
- "leadership": managing others, decision-making authority, organizational influence.
- "ethics": moral conduct, integrity, honesty, right vs wrong.
- "general": historical/narrative content with no clear modern business-advice angle.

A chunk may honestly need 2 tags (e.g. leadership + ethics). Do not force a tag that doesn't fit.

Respond with ONLY a JSON array, one object per input chunk in the same order, no prose:
[{{"tags": ["leadership"], "confidence": 0.9}}, ...]
confidence is your overall confidence (0.0-1.0) in the tag assignment for that chunk.
If you cannot confidently assign any tag, return {{"tags": [], "confidence": 0.0}}.
"""


def build_few_shot_prefix() -> str:
    lines = ["Examples:"]
    for tag, example in _FEW_SHOT_EXAMPLES:
        lines.append(f'- tags=["{tag}"] :: "{example}"')
    return "\n".join(lines)


def build_batch_prompt(texts: list[str]) -> str:
    prefix = build_few_shot_prefix()
    body_lines = [f"{i + 1}. {t}" for i, t in enumerate(texts)]
    return f"{prefix}\n\nClassify these {len(texts)} chunks:\n\n" + "\n\n".join(body_lines)


def parse_classification_response(raw_text: str, expected_count: int) -> list[dict]:
    """Parse the model's JSON array response. Pads/truncates defensively so a malformed
    or short response never desyncs chunk<->tag alignment; short entries are marked as
    zero-confidence so they get flagged for review rather than silently mis-tagged."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = []

    if not isinstance(parsed, list):
        parsed = []

    results: list[dict] = []
    for i in range(expected_count):
        if i < len(parsed) and isinstance(parsed[i], dict):
            tags = parsed[i].get("tags", [])
            confidence = parsed[i].get("confidence", 0.0)
            tags = [t for t in tags if t in DOMAIN_TAGS]
            results.append({"tags": tags, "confidence": float(confidence)})
        else:
            results.append({"tags": [], "confidence": 0.0})
    return results


def classify_batch_via_llm(texts: list[str], model: str = CLASSIFICATION_MODEL) -> list[dict]:
    """Impure: makes one Anthropic API call to classify a batch of chunk texts."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    prompt = build_batch_prompt(texts)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = "".join(block.text for block in response.content if block.type == "text")
    return parse_classification_response(raw_text, expected_count=len(texts))


def needs_review(result: dict, threshold: float = CLASSIFICATION_CONFIDENCE_THRESHOLD) -> bool:
    return not result["tags"] or result["confidence"] < threshold
