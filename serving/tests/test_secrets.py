import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

from serving.secrets import REDACTED, redact_secrets


def test_redacts_openrouter_api_key(monkeypatch):
    monkeypatch.setenv("openrouter_api_key", "sk-or-super-secret-value-123")

    text = redact_secrets("request failed with key sk-or-super-secret-value-123 in header")

    assert "sk-or-super-secret-value-123" not in text
    assert REDACTED in text


def test_redacts_chanakya_qdrant_api_key(monkeypatch):
    monkeypatch.setenv("chanakya_qdrant_api_key", "qdrant-secret-abc")

    text = redact_secrets("error: qdrant-secret-abc rejected")

    assert "qdrant-secret-abc" not in text


def test_redacts_crisis_qdrant_api_key(monkeypatch):
    monkeypatch.setenv("crisis_planer_api_key", "crisis-secret-xyz")

    text = redact_secrets("error: crisis-secret-xyz rejected")

    assert "crisis-secret-xyz" not in text


def test_redacts_multiple_secrets_in_same_text(monkeypatch):
    monkeypatch.setenv("openrouter_api_key", "secret-one")
    monkeypatch.setenv("chanakya_qdrant_api_key", "secret-two")

    text = redact_secrets("first secret-one then secret-two")

    assert "secret-one" not in text
    assert "secret-two" not in text


def test_leaves_ordinary_text_unchanged_when_no_secret_present(monkeypatch):
    monkeypatch.setenv("openrouter_api_key", "sk-or-super-secret-value-123")

    text = redact_secrets("a completely unrelated error message")

    assert text == "a completely unrelated error message"


def test_missing_env_var_does_not_error(monkeypatch):
    monkeypatch.delenv("openrouter_api_key", raising=False)

    text = redact_secrets("some error text")

    assert text == "some error text"
