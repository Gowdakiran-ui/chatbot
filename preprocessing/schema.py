"""Pydantic models shared across the preprocessing pipeline."""
from __future__ import annotations

from pydantic import BaseModel, Field

from config import ChunkType, DomainTag, SourceName


class RawChunk(BaseModel):
    """Output of Step 2 (chunking), before domain classification."""

    id: str
    source: SourceName
    text: str
    chunk_type: ChunkType
    reference: str
    token_count: int


class ClassifiedChunk(BaseModel):
    """Final record written to chanakya_kb.jsonl (Step 4 schema)."""

    id: str
    source: SourceName
    text: str
    domain_tags: list[DomainTag]
    chunk_type: ChunkType
    reference: str
    token_count: int

    def to_jsonl_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source.value,
            "text": self.text,
            "domain_tags": [t.value for t in self.domain_tags],
            "chunk_type": self.chunk_type.value,
            "reference": self.reference,
            "token_count": self.token_count,
        }


class NeedsReviewChunk(BaseModel):
    """Written to needs_review.jsonl when classification confidence is low or empty."""

    id: str
    source: SourceName
    text: str
    chunk_type: ChunkType
    reference: str
    token_count: int
    proposed_tags: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reason: str

    def to_jsonl_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source.value,
            "text": self.text,
            "chunk_type": self.chunk_type.value,
            "reference": self.reference,
            "token_count": self.token_count,
            "proposed_tags": self.proposed_tags,
            "confidence": self.confidence,
            "reason": self.reason,
        }


class CleaningLogEntry(BaseModel):
    """One record of a trimming/removal decision made during PDF cleaning, for spot-check."""

    action: str  # "trim_front" | "trim_back" | "drop_page" | "strip_header_footer" | "strip_page_number"
    detail: str
    pages: list[int] = Field(default_factory=list)
