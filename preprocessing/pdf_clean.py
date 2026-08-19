"""Step 1 — deterministic PDF cleaning. No LLM calls here (see CLAUDE.md / task.md constraints).

Pure functions operate on `List[str]` (one string per page) so they are unit-testable
without touching a real PDF. `extract_pages` is the only function that does file I/O.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import fitz  # PyMuPDF

from config import (
    FRONT_BACK_MATTER_WORD_THRESHOLD,
    HEADER_FOOTER_FREQUENCY_THRESHOLD,
    NON_ALPHA_PAGE_THRESHOLD,
)
from schema import CleaningLogEntry

_ROMAN_NUMERAL_RE = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(r"^[\-\s]*(\d+|[ivxlcdm]+)[\-\s]*$", re.IGNORECASE)


def extract_pages(pdf_path: Path) -> list[str]:
    """File I/O boundary: extract raw text per page from a PDF."""
    doc = fitz.open(pdf_path)
    try:
        return [page.get_text() for page in doc]
    finally:
        doc.close()


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def detect_repeated_lines(
    pages: list[str], threshold: float = HEADER_FOOTER_FREQUENCY_THRESHOLD
) -> set[str]:
    """Lines (normalized) appearing identically on more than `threshold` fraction of pages."""
    if not pages:
        return set()
    counts: dict[str, int] = {}
    for page in pages:
        seen_this_page = set()
        for raw_line in page.splitlines():
            line = _normalize_line(raw_line)
            if not line or line in seen_this_page:
                continue
            seen_this_page.add(line)
            counts[line] = counts.get(line, 0) + 1
    min_count = threshold * len(pages)
    # A line must recur on at least 2 pages to count as "repeated" at all — otherwise a
    # single-page occurrence can spuriously clear a fractional threshold on short inputs.
    return {line for line, count in counts.items() if count >= 2 and count > min_count}


def is_page_number_line(line: str) -> bool:
    """True for lines that are only digits/roman numerals, optionally with dashes."""
    stripped = _normalize_line(line)
    if not stripped:
        return False
    return bool(_PAGE_NUMBER_RE.match(stripped))


def strip_header_footer_and_page_numbers(
    pages: list[str], repeated_lines: set[str]
) -> tuple[list[str], list[CleaningLogEntry]]:
    cleaned_pages: list[str] = []
    stripped_repeated_pages: list[int] = []
    stripped_pagenum_pages: list[int] = []
    for i, page in enumerate(pages):
        kept_lines = []
        for raw_line in page.splitlines():
            norm = _normalize_line(raw_line)
            if norm in repeated_lines:
                stripped_repeated_pages.append(i)
                continue
            if is_page_number_line(raw_line):
                stripped_pagenum_pages.append(i)
                continue
            kept_lines.append(raw_line)
        cleaned_pages.append("\n".join(kept_lines))

    log: list[CleaningLogEntry] = []
    if repeated_lines:
        log.append(
            CleaningLogEntry(
                action="strip_header_footer",
                detail=f"Removed {len(repeated_lines)} repeated header/footer line(s): "
                f"{sorted(repeated_lines)[:10]}",
                pages=sorted(set(stripped_repeated_pages)),
            )
        )
    if stripped_pagenum_pages:
        log.append(
            CleaningLogEntry(
                action="strip_page_number",
                detail="Removed page-number-only lines",
                pages=sorted(set(stripped_pagenum_pages)),
            )
        )
    return cleaned_pages, log


def non_alpha_ratio(text: str) -> float:
    """Fraction of non-alphabetic characters among non-whitespace characters."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 1.0
    non_alpha = sum(1 for c in chars if not c.isalpha())
    return non_alpha / len(chars)


def drop_non_alpha_pages(
    pages: list[str], threshold: float = NON_ALPHA_PAGE_THRESHOLD
) -> tuple[list[str], list[int]]:
    """Returns (kept_pages, dropped_page_indices). Dropped pages become empty-string
    placeholders so page indices stay stable for logging; caller filters empties out."""
    dropped: list[int] = []
    kept: list[str] = []
    for i, page in enumerate(pages):
        if non_alpha_ratio(page) > threshold:
            dropped.append(i)
            kept.append("")
        else:
            kept.append(page)
    return kept, dropped


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]{2,}", text))


def find_front_matter_end(
    pages: list[str], word_threshold: int = FRONT_BACK_MATTER_WORD_THRESHOLD
) -> int:
    """Index of the first page with >word_threshold words of continuous prose/verse.
    Returns len(pages) if no such page exists."""
    for i, page in enumerate(pages):
        if _word_count(page) > word_threshold:
            return i
    return len(pages)


def find_back_matter_start(
    pages: list[str], word_threshold: int = FRONT_BACK_MATTER_WORD_THRESHOLD
) -> int:
    """Index one-past the last page with >word_threshold words of continuous prose/verse.
    Returns 0 if no such page exists."""
    for i in range(len(pages) - 1, -1, -1):
        if _word_count(pages[i]) > word_threshold:
            return i + 1
    return 0


def clean_pages(pages: list[str]) -> tuple[str, list[CleaningLogEntry]]:
    """Full deterministic cleaning pipeline over already-extracted page texts.
    Returns (cleaned_text, log_entries)."""
    log: list[CleaningLogEntry] = []

    repeated_lines = detect_repeated_lines(pages)
    stripped_pages, strip_log = strip_header_footer_and_page_numbers(pages, repeated_lines)
    log.extend(strip_log)

    non_empty_pages, dropped_indices = drop_non_alpha_pages(stripped_pages)
    if dropped_indices:
        log.append(
            CleaningLogEntry(
                action="drop_page",
                detail="Dropped pages >80% non-alphabetic (captions/decorative/blank scans)",
                pages=dropped_indices,
            )
        )

    front_end = find_front_matter_end(non_empty_pages)
    back_start = find_back_matter_start(non_empty_pages)
    if back_start < front_end:
        # Degenerate document (too short / no substantive page) — keep everything rather
        # than over-trimming to nothing.
        front_end, back_start = 0, len(non_empty_pages)

    if front_end > 0:
        log.append(
            CleaningLogEntry(
                action="trim_front",
                detail="Trimmed front matter (title/copyright/dedication/TOC)",
                pages=list(range(0, front_end)),
            )
        )
    if back_start < len(non_empty_pages):
        log.append(
            CleaningLogEntry(
                action="trim_back",
                detail="Trimmed back matter (index/about-author/appendix/ads)",
                pages=list(range(back_start, len(non_empty_pages))),
            )
        )

    body_pages = non_empty_pages[front_end:back_start]
    cleaned_text = "\n\n".join(p for p in body_pages if p.strip())
    return cleaned_text, log


def clean_pdf_file(pdf_path: Path) -> tuple[str, list[CleaningLogEntry]]:
    pages = extract_pages(pdf_path)
    return clean_pages(pages)


def write_cleaning_outputs(
    source_name: str, cleaned_text: str, log: list[CleaningLogEntry], cleaned_dir: Path
) -> None:
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    (cleaned_dir / f"{source_name}.txt").write_text(cleaned_text, encoding="utf-8")
    log_path = cleaned_dir / f"{source_name}_cleaning_log.json"
    log_path.write_text(
        json.dumps([entry.model_dump() for entry in log], indent=2), encoding="utf-8"
    )
