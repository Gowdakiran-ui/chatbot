"""Client-facing description of the chunks an answer was grounded in.

The `final` SSE event carries `sources: [{id, label, snippet, metadata}]` for the cited chunks only. Raw
retrieval scores are deliberately not included. Mode-specific label/metadata rules live in the per-mode
`source_info_fn` on ModeConfig (serving/mode_config.py), not as conditionals at the call site.
"""
from __future__ import annotations

import re
from typing import Callable

from pydantic import BaseModel

SNIPPET_MAX_CHARS = 200


class SourceInfo(BaseModel):
    label: str
    metadata: dict


class SourceRef(BaseModel):
    id: str
    label: str
    snippet: str
    metadata: dict


SourceInfoFn = Callable[[dict], SourceInfo]

_CHANAKYA_SOURCE_NAMES = {
    "arthashastra": "Arthashastra",
    "chanakya_neeti": "Chanakya Niti",
    "7_secrets_of_leadership": "7 Secrets of Leadership",
    "corporate_chanakya": "Corporate Chanakya",
    "chanakya_info": "Chanakya Info",
}


def make_snippet(text: str, max_chars: int = SNIPPET_MAX_CHARS) -> str:
    """Whitespace-collapsed excerpt of at most ~max_chars, cut at a word boundary with an ellipsis."""
    flat = " ".join(text.split()).lstrip("-*• ")  # drop a leading markdown bullet
    if len(flat) <= max_chars:
        return flat
    cut = flat[:max_chars]
    if flat[max_chars] != " ":  # we cut mid-word: back up to the last space
        space = cut.rfind(" ")
        if space > 0:
            cut = cut[:space]
    return cut.rstrip(" ,;:.-") + "…"


def chanakya_source_info(payload: dict) -> SourceInfo:
    slug = str(payload.get("source", ""))
    name = _CHANAKYA_SOURCE_NAMES.get(slug) or slug.replace("_", " ").title() or "Chanakya"
    reference = str(payload.get("reference") or "").strip()
    # "segment 47" is an ingestion artifact, not a citation a reader can use
    label = f"{name}, {reference}" if reference and not reference.lower().startswith("segment") else name
    return SourceInfo(label=label, metadata={"domain_tags": list(payload.get("domain_tags") or [])})


def crisis_source_info(payload: dict) -> SourceInfo:
    company = re.sub(r"\s*\([^)]*\)\s*$", "", str(payload.get("company", "")).strip()) or "Unknown company"
    year = payload.get("year")
    return SourceInfo(
        label=f"{company} ({year})" if year else company,
        metadata={key: payload.get(key) for key in ("crisis_type", "industry", "resolution_status") if payload.get(key)},
    )


def generic_source_info(payload: dict) -> SourceInfo:
    return SourceInfo(label=str(payload.get("source") or payload.get("id") or "Source"), metadata={})


_CRISIS_TRIGGER_RE = re.compile(r"Trigger Event:\s*(.+)")


def snippet_text(payload: dict) -> str:
    """The matched passage itself. Crisis summary chunks open with a Company/Industry/... header, so lead with
    the trigger event instead when there is one."""
    text = str(payload.get("text", ""))
    match = _CRISIS_TRIGGER_RE.search(text) if payload.get("chunk_type") == "summary" else None
    return match.group(1) if match else text


def build_sources(chunks, info_fn: SourceInfoFn) -> list[SourceRef]:
    refs: list[SourceRef] = []
    for chunk in chunks:
        info = info_fn(chunk.payload)
        refs.append(
            SourceRef(id=chunk.chunk_id, label=info.label, snippet=make_snippet(snippet_text(chunk.payload)), metadata=info.metadata)
        )
    return refs
