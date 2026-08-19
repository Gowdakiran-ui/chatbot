"""Closes the embedding-path coverage gap the forensics audit flagged: a wrong or
missing search_document:/search_query: prefix silently degrades every retrieval score
without raising an error — the audit could only catch this by manually tracing call
sites. This asserts it directly, with a fake model (no model load) recording exactly
what text reaches `.encode()`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root, for `db.*`

import db.embedding as embedding_module


class _FakeModel:
    def __init__(self):
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append(list(texts) if isinstance(texts, list) else [texts])
        import numpy as np

        n = len(texts) if isinstance(texts, list) else 1
        return np.zeros((n, 4))


def test_embed_documents_applies_document_prefix(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(embedding_module, "_model", fake)

    embedding_module.embed_documents(["alpha text", "beta text"])

    assert len(fake.calls) == 1
    sent_texts = fake.calls[0]
    assert sent_texts == [
        embedding_module.DOCUMENT_PREFIX + "alpha text",
        embedding_module.DOCUMENT_PREFIX + "beta text",
    ]
    # The query prefix must never leak into the document path.
    assert not any(t.startswith(embedding_module.QUERY_PREFIX) for t in sent_texts)


def test_embed_query_applies_query_prefix_not_document_prefix(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(embedding_module, "_model", fake)

    embedding_module.embed_query("what should a leader do")

    assert len(fake.calls) == 1
    sent_texts = fake.calls[0]
    assert sent_texts == [embedding_module.QUERY_PREFIX + "what should a leader do"]
    assert not sent_texts[0].startswith(embedding_module.DOCUMENT_PREFIX)


def test_document_and_query_prefixes_are_distinct():
    # A regression here (e.g. someone "simplifying" both to the same string) would
    # silently degrade retrieval without any test above catching it structurally.
    assert embedding_module.DOCUMENT_PREFIX != embedding_module.QUERY_PREFIX
    assert embedding_module.DOCUMENT_PREFIX.strip()
    assert embedding_module.QUERY_PREFIX.strip()
