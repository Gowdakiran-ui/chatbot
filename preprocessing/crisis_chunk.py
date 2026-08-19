"""Step 2-4 — hierarchical chunking (summary + section chunks) for a parsed crisis case.

Pure functions: no file I/O, no network calls.
"""
from __future__ import annotations

import re

from crisis_config import SECTION_MAX_TOKENS, CrisisChunkType
from crisis_schema import CrisisChunkMetadata, CrisisChunkRecord, ParsedCase
from tokens import count_tokens


def _build_metadata(case: ParsedCase, chunk_type: CrisisChunkType) -> CrisisChunkMetadata:
    return CrisisChunkMetadata(
        case_id=case.case_id,
        company=case.company,
        industry=case.industry,
        crisis_type=case.crisis_type,
        region=case.region,
        year=case.year,
        response_speed_score=case.response_speed_score,
        transparency_score=case.transparency_score,
        resolution_status=case.resolution_status,
        onlyne_relevance=case.onlyne_relevance,
        chunk_type=chunk_type,
    )


def build_summary_chunk(case: ParsedCase) -> CrisisChunkRecord:
    text = (
        f"Company: {case.company}\n"
        f"Industry: {case.industry}\n"
        f"Year: {case.year_raw}\n"
        f"Crisis Type: {case.crisis_type}\n"
        f"Trigger Event: {case.trigger_event}\n"
        f"Resolution Status: {case.resolution_status_raw}\n"
        f"Estimated Impact: {case.estimated_impact}"
    )
    return CrisisChunkRecord(
        id=f"{case.case_id}_{CrisisChunkType.SUMMARY.value}",
        text=text,
        chunk_type=CrisisChunkType.SUMMARY,
        metadata=_build_metadata(case, CrisisChunkType.SUMMARY),
    )


_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")


def split_section_if_too_long(text: str, max_tokens: int = SECTION_MAX_TOKENS) -> list[str]:
    """Sections are kept as one chunk unless they exceed max_tokens (rare per task.md);
    only then fall back to paragraph-level (or line-level, for bullet lists) splitting."""
    if count_tokens(text) <= max_tokens:
        return [text]

    paragraphs = [p for p in _PARAGRAPH_SPLIT_RE.split(text) if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [l for l in text.split("\n") if l.strip()]
    if len(paragraphs) <= 1:
        return [text]  # nothing to split on; keep whole rather than break mid-sentence

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for p in paragraphs:
        p_tokens = count_tokens(p)
        if current and current_tokens + p_tokens > max_tokens:
            chunks.append("\n\n".join(current))
            current, current_tokens = [], 0
        current.append(p)
        current_tokens += p_tokens
    if current:
        chunks.append("\n\n".join(current))
    return chunks


_SECTION_FIELDS: list[tuple[CrisisChunkType, str]] = [
    (CrisisChunkType.TRIGGER_EVENT, "trigger_event"),
    (CrisisChunkType.WENT_RIGHT, "went_right"),
    (CrisisChunkType.WENT_WRONG, "went_wrong"),
    (CrisisChunkType.BEST_PRACTICE, "best_practice"),
]


def build_section_chunks(case: ParsedCase) -> list[CrisisChunkRecord]:
    records: list[CrisisChunkRecord] = []
    for chunk_type, attr in _SECTION_FIELDS:
        text = getattr(case, attr)
        parts = split_section_if_too_long(text)
        metadata = _build_metadata(case, chunk_type)
        if len(parts) == 1:
            records.append(
                CrisisChunkRecord(
                    id=f"{case.case_id}_{chunk_type.value}",
                    text=parts[0],
                    chunk_type=chunk_type,
                    metadata=metadata,
                )
            )
        else:
            for i, part in enumerate(parts, start=1):
                records.append(
                    CrisisChunkRecord(
                        id=f"{case.case_id}_{chunk_type.value}_{i}",
                        text=part,
                        chunk_type=chunk_type,
                        metadata=metadata,
                    )
                )
    return records


def build_case_chunks(case: ParsedCase) -> list[CrisisChunkRecord]:
    return [build_summary_chunk(case), *build_section_chunks(case)]
