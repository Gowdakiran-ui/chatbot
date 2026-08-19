"""Step 1 — deterministic, regex-based parsing of crisis case-study batch files.

No LLM calls (task.md constraint). Pure functions: `split_cases` and `parse_case_block`
work on plain strings and are unit-testable against a small sample file.

Source files are not perfectly uniform (confirmed by inspecting all 21 real batch files):
- Case headings appear as "## Case 001", "## CASE-001", "Case 13", or "Case ID: 30".
- Fields appear as either "**Label:** value on the same line" or plain "Label: value",
  and some values (Response Speed Score, Resolution Status) carry an explanatory
  sentence/paragraph after the short value, either inline or on a following italic line.
The parser is written to handle all of these without per-file special-casing.
"""
from __future__ import annotations

import re

from crisis_schema import ParsedCase, ParseError

# --- Case boundary -----------------------------------------------------------------

_CASE_HEADING_RE = re.compile(
    r"^#{0,3}\s*CASE(?:\s*ID)?\s*[:\-]?\s*0*(\d+)\b",
    re.IGNORECASE | re.MULTILINE,
)


def split_cases(text: str) -> list[tuple[int, str]]:
    """Split a batch file's text into (case_number, block_text) pairs. Case boundaries
    are detected from heading lines rather than the literal '---' separator, since not
    every source file uses '## Case NNN' headings consistently."""
    matches = list(_CASE_HEADING_RE.finditer(text))
    cases: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        cases.append((int(m.group(1)), text[start:end]))
    return cases


# --- Field extraction ----------------------------------------------------------------

# canonical_key -> regex fragment matching the label text (case-insensitive)
_FIELD_LABEL_PATTERNS: dict[str, str] = {
    "company": r"Company",
    "industry": r"Industry",
    "year": r"Year",
    "crisis_type": r"Crisis Type",
    "trigger_event": r"Trigger Event",
    "response_type": r"Response Type",
    "response_speed_score": r"Response Speed Score",
    "transparency_score": r"Transparency Score",
    "legal_framework": r"Legal\s*/\s*Regulatory Framework(?:\s*Triggered)?",
    "resolution_status": r"Resolution Status",
    "went_right": r"What Went Right",
    "went_wrong": r"What Went Wrong",
    "best_practice": r"Best Practice\s*/\s*What Should Have Happened",
    "estimated_impact": r"Estimated Impact",
    "onlyne_relevance": r"Onlyne Relevance",
    "key_sources": r"Key Sources",
}

# Fields required by task.md's Input field list; a case missing any of these is logged
# to parse_errors.jsonl and excluded from chunk output.
REQUIRED_FIELDS = tuple(_FIELD_LABEL_PATTERNS.keys())

_FIELD_LABEL_RES: dict[str, re.Pattern] = {
    key: re.compile(rf"^\*{{0,2}}{pattern}\*{{0,2}}\s*:\s*\*{{0,2}}\s*", re.IGNORECASE | re.MULTILINE)
    for key, pattern in _FIELD_LABEL_PATTERNS.items()
}


def parse_case_block(block: str) -> dict[str, str]:
    """Extract every recognized field from one case block. Returns {key: raw_text}
    for only the fields actually found — callers check REQUIRED_FIELDS for gaps."""
    positions: list[tuple[int, int, str]] = []  # (label_start, value_start, key)
    for key, label_re in _FIELD_LABEL_RES.items():
        m = label_re.search(block)
        if m:
            positions.append((m.start(), m.end(), key))

    positions.sort(key=lambda p: p[0])

    fields: dict[str, str] = {}
    for i, (_, value_start, key) in enumerate(positions):
        value_end = positions[i + 1][0] if i + 1 < len(positions) else len(block)
        fields[key] = block[value_start:value_end].strip()
    return fields


# --- Derived/typed values from raw field text ----------------------------------------

_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_LEADING_INT_RE = re.compile(r"\s*(\d+)")


def _first_line(text: str) -> str:
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def extract_year(raw: str) -> int | None:
    m = _YEAR_RE.search(raw)
    return int(m.group(1)) if m else None


def extract_leading_score(raw: str) -> int | None:
    m = _LEADING_INT_RE.match(_first_line(raw))
    return int(m.group(1)) if m else None


def extract_short_status(raw: str) -> str:
    return _first_line(raw)


def parse_onlyne_relevance(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.replace("\n", " ").split("/")]
    return [p for p in parts if p]


# --- Case assembly ---------------------------------------------------------------------


def build_case(
    case_number: int, block: str, region, source_file: str
) -> tuple[ParsedCase | None, list[ParseError]]:
    """Returns (ParsedCase, []) on success, or (None, [ParseError, ...]) if any
    required field is missing — the case is then excluded from chunk output.

    case_id is prefixed with region because case numbering restarts at 001
    independently per source file/region (confirmed across the real batch files —
    e.g. an India "Case 001" and a US "Case 001" both exist), so the region prefix
    is required for global uniqueness, not just readability."""
    case_id = f"{region.value}_case_{case_number:03d}"
    fields = parse_case_block(block)

    missing = [f for f in REQUIRED_FIELDS if f not in fields or not fields[f]]
    if missing:
        return None, [
            ParseError(source_file=source_file, case_id=case_id, missing_field=f)
            for f in missing
        ]

    case = ParsedCase(
        case_id=case_id,
        region=region,
        source_file=source_file,
        company=fields["company"],
        industry=fields["industry"],
        year_raw=fields["year"],
        year=extract_year(fields["year"]),
        crisis_type=fields["crisis_type"],
        trigger_event=fields["trigger_event"],
        response_type=fields["response_type"],
        response_speed_score_raw=fields["response_speed_score"],
        response_speed_score=extract_leading_score(fields["response_speed_score"]),
        transparency_score_raw=fields["transparency_score"],
        transparency_score=extract_leading_score(fields["transparency_score"]),
        legal_framework=fields["legal_framework"],
        resolution_status_raw=fields["resolution_status"],
        resolution_status=extract_short_status(fields["resolution_status"]),
        went_right=fields["went_right"],
        went_wrong=fields["went_wrong"],
        best_practice=fields["best_practice"],
        estimated_impact=fields["estimated_impact"],
        onlyne_relevance=parse_onlyne_relevance(fields["onlyne_relevance"]),
        key_sources=fields["key_sources"],
    )
    return case, []


def parse_batch_file(text: str, region, source_file: str) -> tuple[list[ParsedCase], list[ParseError]]:
    cases: list[ParsedCase] = []
    errors: list[ParseError] = []
    for case_number, block in split_cases(text):
        case, case_errors = build_case(case_number, block, region, source_file)
        if case:
            cases.append(case)
        errors.extend(case_errors)
    return cases, errors
