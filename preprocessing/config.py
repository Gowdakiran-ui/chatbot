"""Central configuration: paths, enums, tunables. No hardcoded paths outside this file."""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = Path(os.environ.get("CHANAKYA_RAW_DIR", PROJECT_ROOT / "data" / "raw"))
CLEANED_DIR = Path(os.environ.get("CHANAKYA_CLEANED_DIR", PROJECT_ROOT / "data" / "cleaned"))
PROCESSED_DIR = Path(os.environ.get("CHANAKYA_PROCESSED_DIR", PROJECT_ROOT / "data" / "processed"))

CHANAKYA_KB_PATH = PROCESSED_DIR / "chanakya_kb.jsonl"
NEEDS_REVIEW_PATH = PROCESSED_DIR / "needs_review.jsonl"


class ChunkType(str, Enum):
    VERSE = "verse"
    PROSE = "prose"


class DomainTag(str, Enum):
    CAREER = "career"
    LEADERSHIP = "leadership"
    ETHICS = "ethics"
    GENERAL = "general"


class SourceName(str, Enum):
    ARTHASHASTRA = "arthashastra"
    CHANAKYA_NEETI = "chanakya_neeti"
    CORPORATE_CHANAKYA = "corporate_chanakya"
    SEVEN_SECRETS = "7_secrets_of_leadership"
    CHANAKYA_INFO = "chanakya_info"


# Which chunking strategy each source uses.
SOURCE_CHUNK_TYPE: dict[SourceName, ChunkType] = {
    SourceName.ARTHASHASTRA: ChunkType.VERSE,
    SourceName.CHANAKYA_NEETI: ChunkType.VERSE,
    SourceName.CORPORATE_CHANAKYA: ChunkType.PROSE,
    SourceName.SEVEN_SECRETS: ChunkType.PROSE,
    SourceName.CHANAKYA_INFO: ChunkType.PROSE,
}

# Raw input filenames (relative to RAW_DIR) per source. Must match the actual files in
# data/raw/ exactly — these previously referenced placeholder names (e.g.
# "arthashastra.pdf") that never matched what's actually on disk, which meant
# load_source_text() could never succeed for a real re-run (see forensics_report.md).
SOURCE_FILENAMES: dict[SourceName, str] = {
    SourceName.ARTHASHASTRA: "R. Shamasastry-Kautilya's Arthashastra   (1915).pdf",
    SourceName.CHANAKYA_NEETI: "chanakya-neeti-startegies-for-success-radhakrishnan-pillai_compress.pdf",
    SourceName.CORPORATE_CHANAKYA: "[Studycrux.com] Corporate Chanakya-X.pdf",
    SourceName.SEVEN_SECRETS: "chanakyas-7-secrets-of-leadership-radhakrishnan-pillai-d-sivanandhan_compress.pdf",
    SourceName.CHANAKYA_INFO: "chanakya info.txt",
}

# --- PDF cleaning tunables ---
HEADER_FOOTER_FREQUENCY_THRESHOLD = 0.30  # line appearing on >30% of pages -> strip
NON_ALPHA_PAGE_THRESHOLD = 0.80  # drop pages that are >80% non-alphabetic chars
FRONT_BACK_MATTER_WORD_THRESHOLD = 200  # first/last page with >200 words of prose

# --- Chunking tunables ---
MIN_VERSE_TOKENS = 50  # verses smaller than this get merged with neighbors
PROSE_TARGET_MIN_TOKENS = 300
PROSE_TARGET_MAX_TOKENS = 500
PROSE_OVERLAP_RATIO = 0.15

# --- Classification tunables ---
DOMAIN_TAGS = [t.value for t in DomainTag]
CLASSIFICATION_BATCH_SIZE = 20
CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.5
CLASSIFICATION_MODEL = os.environ.get("CHANAKYA_CLASSIFY_MODEL", "claude-sonnet-5")
