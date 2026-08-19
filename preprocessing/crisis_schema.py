"""Pydantic models for the crisis case-study KB pipeline."""
from __future__ import annotations

from pydantic import BaseModel, Field

from crisis_config import CrisisChunkType, Region


class ParsedCase(BaseModel):
    """A single case, fully parsed from its markdown block (Step 1 output)."""

    case_id: str  # "case_001"
    region: Region
    source_file: str

    company: str
    industry: str
    year_raw: str
    year: int | None
    crisis_type: str
    trigger_event: str
    response_type: str
    response_speed_score_raw: str
    response_speed_score: int | None
    transparency_score_raw: str
    transparency_score: int | None
    legal_framework: str
    resolution_status_raw: str
    resolution_status: str  # short form, used in metadata
    went_right: str
    went_wrong: str
    best_practice: str
    estimated_impact: str
    onlyne_relevance: list[str]
    key_sources: str


class ParseError(BaseModel):
    """Logged when a case is missing a required field — the case is excluded from
    chunk output entirely rather than silently emitting a chunk with a blank field."""

    source_file: str
    case_id: str
    missing_field: str

    def to_jsonl_dict(self) -> dict:
        return self.model_dump()


class CrisisChunkMetadata(BaseModel):
    case_id: str
    company: str
    industry: str
    crisis_type: str
    region: Region
    year: int | None
    response_speed_score: int | None
    transparency_score: int | None
    resolution_status: str
    onlyne_relevance: list[str]
    chunk_type: CrisisChunkType

    def to_dict(self) -> dict:
        d = self.model_dump()
        d["region"] = self.region.value
        d["chunk_type"] = self.chunk_type.value
        return d


class CrisisChunkRecord(BaseModel):
    id: str
    text: str
    chunk_type: CrisisChunkType
    metadata: CrisisChunkMetadata

    def to_jsonl_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "chunk_type": self.chunk_type.value,
            "metadata": self.metadata.to_dict(),
        }
