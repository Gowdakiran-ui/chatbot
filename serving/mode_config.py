"""Piece 1 — mode config resolver.

`Mode` is resolved once per request into a `ModeConfig`, threaded through every
downstream call (retrieval, floor check, prompt selection, generation). No
`if mode == "crisis"` branching should appear anywhere else in the codebase — any
mode-dependent behavior belongs in this file, as a new field or a new MODE_CONFIG
entry, not as a conditional at the call site.

Note on `min_score`: this is expressed on the *dense cosine similarity* scale
(0-1), not Qdrant's raw RRF fusion score. Spot-checked against both live clusters:
hybrid_search()'s fused RRF score is purely rank-based (sum of 1/(k+rank+1) across
the dense/sparse prefetch lists) and does NOT discriminate relevant from irrelevant
queries — a nonsense query ("xyzzy quantum toaster...") got the same top RRF score
(0.5) as a genuinely relevant one on chanakya_kb, because Qdrant always returns
*something* as the nearest neighbor regardless of how far away it actually is.
Dense cosine similarity does discriminate cleanly on the same queries (relevant
~0.72-0.76 vs irrelevant ~0.49-0.53 on chanakya_kb; ~0.66-0.71 vs ~0.49-0.51 on
crisis_kb). So Piece 3/4's floor check must compare against a dense similarity
score attached per-hit, not the raw fused score hybrid_search() returns today —
flagging this now so it isn't built on the wrong number later.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict
from qdrant_client import QdrantClient

from db.crisis_qdrant_client import get_client as get_crisis_client
from db.parent_expansion import expand_chanakya_chunk, expand_crisis_chunk
from db.qdrant_client import get_client as get_chanakya_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"

ExpandFn = Callable[[QdrantClient, str, dict], str]
ClientFactory = Callable[[], QdrantClient]


class Mode(str, Enum):
    CHANAKYA = "chanakya"
    CRISIS = "crisis"


class ModeConfig(BaseModel):
    """Everything downstream serving code needs for one mode. Static, resolved
    once per request from MODE_CONFIG — never mutated at request time."""

    model_config = ConfigDict(arbitrary_types_allowed=True)  # for expand_fn/get_client callables

    collection_alias: str
    system_prompt_path: Path
    top_k: int
    min_score: float
    expand_fn: ExpandFn
    # chanakya_kb and crisis_kb live on separate Qdrant Cloud clusters (see
    # db/crisis_qdrant_client.py) — retrieval needs the right client per mode, not
    # just the right collection name.
    get_client: ClientFactory
    requires_disclaimer: bool
    # Per-mode generation cap, threaded into provider.generate()'s max_tokens.
    # Not a single global default (see providers/openrouter.py) — the
    # generation-quality fix task found crisis-mode answers, which cite several
    # retrieved cases per turn, need real headroom over chanakya's simpler,
    # single-passage answers; paying for that headroom on every chanakya call
    # would be wasted cost with no quality benefit (the eval never needed more
    # than ~500 output tokens there).
    max_tokens: int


MODE_CONFIG: dict[Mode, ModeConfig] = {
    Mode.CHANAKYA: ModeConfig(
        collection_alias="chanakya_kb",
        system_prompt_path=PROMPTS_DIR / "chanakya_system.md",
        top_k=5,
        min_score=0.60,
        expand_fn=expand_chanakya_chunk,
        get_client=get_chanakya_client,
        requires_disclaimer=False,
        max_tokens=800,
    ),
    Mode.CRISIS: ModeConfig(
        collection_alias="crisis_kb",
        system_prompt_path=PROMPTS_DIR / "crisis_system.md",
        top_k=5,
        # Stricter than chanakya: a missed precedent is a worse failure than a
        # missed leadership quote (task.md). Real crisis hits score ~0.66-0.71
        # dense; irrelevant queries top out ~0.51 — 0.65 sits close under the
        # weakest real hit while staying well clear of noise.
        min_score=0.65,
        expand_fn=expand_crisis_chunk,
        get_client=get_crisis_client,
        requires_disclaimer=True,
        max_tokens=1400,
    ),
}


def resolve_mode(mode: Mode) -> ModeConfig:
    return MODE_CONFIG[mode]
