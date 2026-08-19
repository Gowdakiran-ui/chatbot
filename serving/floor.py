"""Piece 4 — retrieval floor (refusal path).

If the top hit's dense score doesn't clear config.min_score, the generation model is
never called: a direct, honest refusal in the mode's voice is returned instead, and
the check is logged with the query, mode, and score regardless of outcome. Kept
deliberately decoupled from the generation layer (Piece 5) — retrieval, the floor
gate, and generation stay distinct per CLAUDE.md's "retrieval, generation, and
routing are distinct layers" rule. Piece 6's endpoint wires this gate in front of
the real generate() call; `GenerateFn` stands in for that until Piece 5 exists.

Per serving/mode_config.py's docstring and serving/retrieval.py: the floor is
checked against `top_dense_score` (cosine similarity), not `top_score` (the fused
RRF score) — the RRF score doesn't discriminate relevant from irrelevant queries.
"""
from __future__ import annotations

import logging
from typing import Callable

from pydantic import BaseModel

from serving.disclaimer import NOT_LEGAL_ADVICE_LINE
from serving.mode_config import Mode, ModeConfig
from serving.retrieval import RetrievalResult, retrieve_context

logger = logging.getLogger("serving.floor")

# Stands in for Piece 5's real GenerationProvider.generate() — kept generic so this
# module has no dependency on Piece 5, and so "the floor blocks generation" is
# testable with a plain mock before a real provider exists.
GenerateFn = Callable[[RetrievalResult], str]

_REFUSAL_TEXT: dict[Mode, str] = {
    Mode.CHANAKYA: (
        "I do not have a teaching among my retrieved texts that speaks directly to this. "
        "I would rather tell you plainly that I lack a grounded source here than offer "
        "counsel I cannot trace back to the Arthashastra or Chanakya Niti."
    ),
    Mode.CRISIS: (
        "I don't have a documented precedent among the retrieved crisis cases that "
        "matches this situation closely enough to advise from. Rather than generalize "
        "past what's grounded, I'm flagging this for human review. "
        f"{NOT_LEGAL_ADVICE_LINE}"
    ),
}


class FloorCheckResult(BaseModel):
    mode: Mode
    query: str
    passed: bool
    top_score: float
    top_dense_score: float
    min_score: float
    refusal_text: str | None = None


def passes_floor(result: RetrievalResult, config: ModeConfig) -> bool:
    return result.top_dense_score >= config.min_score


def refusal_text_for(mode: Mode) -> str:
    return _REFUSAL_TEXT[mode]


def check_floor(result: RetrievalResult, config: ModeConfig) -> FloorCheckResult:
    passed = passes_floor(result, config)
    log_fn = logger.info if passed else logger.warning
    log_fn(
        "retrieval_floor_check mode=%s query=%r top_score=%.4f top_dense_score=%.4f "
        "min_score=%.4f passed=%s",
        result.mode.value,
        result.query,
        result.top_score,
        result.top_dense_score,
        config.min_score,
        passed,
    )
    return FloorCheckResult(
        mode=result.mode,
        query=result.query,
        passed=passed,
        top_score=result.top_score,
        top_dense_score=result.top_dense_score,
        min_score=config.min_score,
        refusal_text=None if passed else refusal_text_for(result.mode),
    )


def answer_with_floor(query: str, config: ModeConfig, mode: Mode, generate_fn: GenerateFn) -> str:
    """Retrieval + floor check + generation, in one call: generate_fn is only ever
    invoked if the floor passes. This is the seam Piece 6's endpoint calls once
    Piece 5's real generate() exists."""
    result = retrieve_context(query, config, mode)
    check = check_floor(result, config)
    if not check.passed:
        return check.refusal_text
    return generate_fn(result)
