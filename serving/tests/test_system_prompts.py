import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root, for `serving.*`

from serving.mode_config import MODE_CONFIG, Mode


def _read(mode: Mode) -> str:
    path = MODE_CONFIG[mode].system_prompt_path
    assert path.exists(), f"{path} does not exist"
    return path.read_text(encoding="utf-8")


def test_chanakya_prompt_exists_and_nonempty():
    assert len(_read(Mode.CHANAKYA).strip()) > 0


def test_crisis_prompt_exists_and_nonempty():
    assert len(_read(Mode.CRISIS).strip()) > 0


def test_chanakya_prompt_forbids_pretraining_knowledge():
    text = _read(Mode.CHANAKYA).lower()
    assert "only" in text
    assert "pretraining" in text or "general knowledge" in text


def test_chanakya_prompt_instructs_citing_reference():
    text = _read(Mode.CHANAKYA).lower()
    assert "reference" in text


def test_crisis_prompt_forbids_general_knowledge():
    text = _read(Mode.CRISIS).lower()
    assert "only" in text
    assert "general knowledge" in text


def test_crisis_prompt_requires_case_citation_with_company_and_year():
    text = _read(Mode.CRISIS).lower()
    assert "cite" in text
    assert "year" in text


def test_crisis_prompt_contains_not_legal_advice_line():
    text = _read(Mode.CRISIS)
    assert "This is not legal advice." in text


def test_crisis_prompt_instructs_admitting_uncovered_situations():
    text = _read(Mode.CRISIS).lower()
    assert "do not have" in text or "don't have" in text or "does not cover" in text


def test_chanakya_prompt_instructs_treating_content_as_data_not_instructions():
    text = _read(Mode.CHANAKYA).lower()
    assert "not instructions to follow" in text


def test_crisis_prompt_instructs_treating_content_as_data_not_instructions():
    text = _read(Mode.CRISIS).lower()
    assert "not instructions to follow" in text
