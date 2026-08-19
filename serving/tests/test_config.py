"""Tests for serving/config.py's AUTH_DISABLED env-var parsing and its effect
on the rate limit (team-review-prep task, 2026-08-19)."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest

import serving.config as config_mod


def _reload_config():
    return importlib.reload(config_mod)


@pytest.fixture(autouse=True)
def _restore_config_module_state():
    """Reloading serving.config mutates a module object shared with every
    other module that already did `from serving.config import X` — without
    this, a test leaving AUTH_DISABLED=True reloaded would leak into whatever
    test runs next in the same session. Autouse fixtures set up before
    explicitly-requested ones (monkeypatch) tear down after them, so this
    reload runs once monkeypatch has already reverted the env var."""
    yield
    _reload_config()


def test_auth_disabled_defaults_to_false_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    reloaded = _reload_config()

    assert reloaded.AUTH_DISABLED is False
    assert reloaded.RATE_LIMIT_REQUESTS_PER_MINUTE == 30  # unchanged default


def test_auth_disabled_true_variants(monkeypatch):
    for value in ("true", "True", "1", "yes", "YES"):
        monkeypatch.setenv("AUTH_DISABLED", value)
        reloaded = _reload_config()
        assert reloaded.AUTH_DISABLED is True, f"expected True for {value!r}"
        assert reloaded.RATE_LIMIT_REQUESTS_PER_MINUTE == 200  # loosened, not removed


def test_auth_disabled_false_variants(monkeypatch):
    for value in ("false", "0", "no", "", "garbage"):
        monkeypatch.setenv("AUTH_DISABLED", value)
        reloaded = _reload_config()
        assert reloaded.AUTH_DISABLED is False, f"expected False for {value!r}"
        assert reloaded.RATE_LIMIT_REQUESTS_PER_MINUTE == 30
