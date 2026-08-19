import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root, for `db.*`/`serving.*`

from db.parent_expansion import expand_chanakya_chunk, expand_crisis_chunk
from serving.mode_config import MODE_CONFIG, Mode, resolve_mode


def test_both_modes_configured():
    assert set(MODE_CONFIG) == {Mode.CHANAKYA, Mode.CRISIS}


def test_resolve_mode_returns_matching_config():
    assert resolve_mode(Mode.CHANAKYA) is MODE_CONFIG[Mode.CHANAKYA]
    assert resolve_mode(Mode.CRISIS) is MODE_CONFIG[Mode.CRISIS]


def test_collection_aliases_are_distinct_and_correct():
    assert MODE_CONFIG[Mode.CHANAKYA].collection_alias == "chanakya_kb"
    assert MODE_CONFIG[Mode.CRISIS].collection_alias == "crisis_kb"


def test_expand_fn_matches_mode():
    assert MODE_CONFIG[Mode.CHANAKYA].expand_fn is expand_chanakya_chunk
    assert MODE_CONFIG[Mode.CRISIS].expand_fn is expand_crisis_chunk


def test_crisis_requires_disclaimer_chanakya_does_not():
    assert MODE_CONFIG[Mode.CRISIS].requires_disclaimer is True
    assert MODE_CONFIG[Mode.CHANAKYA].requires_disclaimer is False


def test_crisis_min_score_stricter_than_chanakya():
    assert MODE_CONFIG[Mode.CRISIS].min_score > MODE_CONFIG[Mode.CHANAKYA].min_score


def test_client_factories_point_at_separate_clusters():
    from db.crisis_qdrant_client import get_client as crisis_get_client
    from db.qdrant_client import get_client as chanakya_get_client

    assert MODE_CONFIG[Mode.CHANAKYA].get_client is chanakya_get_client
    assert MODE_CONFIG[Mode.CRISIS].get_client is crisis_get_client
    assert MODE_CONFIG[Mode.CHANAKYA].get_client is not MODE_CONFIG[Mode.CRISIS].get_client


def test_system_prompt_paths_are_distinct_and_named_per_mode():
    chanakya_path = MODE_CONFIG[Mode.CHANAKYA].system_prompt_path
    crisis_path = MODE_CONFIG[Mode.CRISIS].system_prompt_path
    assert chanakya_path != crisis_path
    assert chanakya_path.name == "chanakya_system.md"
    assert crisis_path.name == "crisis_system.md"
