"""Paths/config for the crisis case-study KB pipeline. Fully separate from config.py
(the Chanakya KB config) — different collection, different schema, per CLAUDE.md's
"two collections, not two apps" rule: shared plumbing (tokens.py), separate config."""
from __future__ import annotations

import os
import re
from enum import Enum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CRISIS_RAW_DIR = Path(
    os.environ.get("CRISIS_RAW_DIR", PROJECT_ROOT / "data" / "raw" / "crisis_cases")
)
CRISIS_PROCESSED_DIR = Path(
    os.environ.get("CRISIS_PROCESSED_DIR", PROJECT_ROOT / "data" / "processed")
)
# Per-batch cache used for idempotent/incremental ingestion (see build_crisis_kb.py).
CRISIS_BATCH_CACHE_DIR = CRISIS_PROCESSED_DIR / "crisis_batches"
CRISIS_BATCH_MANIFEST_PATH = CRISIS_BATCH_CACHE_DIR / ".manifest.json"

CRISIS_KB_PATH = CRISIS_PROCESSED_DIR / "crisis_kb.jsonl"
CRISIS_PARSE_ERRORS_PATH = CRISIS_PROCESSED_DIR / "parse_errors.jsonl"


class Region(str, Enum):
    INDIA = "india"
    EUROPE = "europe"
    AMERICA = "america"


class CrisisChunkType(str, Enum):
    SUMMARY = "summary"
    TRIGGER_EVENT = "trigger_event"
    WENT_RIGHT = "went_right"
    WENT_WRONG = "went_wrong"
    BEST_PRACTICE = "best_practice"


# Two early batch files predate the region-in-filename convention adopted by later
# batches; both are confirmed (by content) to be U.S. corporate cases.
REGION_FILENAME_OVERRIDES: dict[str, Region] = {
    "crisis-case-studies-batch1.md": Region.AMERICA,
    "crisis-case-studies-batch2.md": Region.AMERICA,
}

_US_TOKEN_RE = re.compile(r"(^|[-_ ])us([-_ .]|$)", re.IGNORECASE)


def infer_region(filename: str) -> Region | None:
    """Region comes from filename (task.md Step 1.3). Returns None if it can't be
    inferred — caller should fall back to an explicit --region arg or log an error."""
    if filename in REGION_FILENAME_OVERRIDES:
        return REGION_FILENAME_OVERRIDES[filename]

    lower = filename.lower()
    if "india" in lower:
        return Region.INDIA
    if "europe" in lower or "european" in lower:
        return Region.EUROPE
    if _US_TOKEN_RE.search(lower) or "america" in lower or "u.s" in lower:
        return Region.AMERICA
    return None


# Section chunks longer than this fall back to paragraph-level splitting (Step 2.B).
SECTION_MAX_TOKENS = 800
