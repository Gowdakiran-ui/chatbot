import json

import incremental_ingest as inc
from config import SourceName


class _FakeChunkType:
    value = "prose"


class _FakeChunk:
    def __init__(self, id_, source, text):
        self.id = id_
        self.source = source
        self.text = text
        self.chunk_type = _FakeChunkType()
        self.reference = "fake"
        self.token_count = 10


def _patch_pipeline(monkeypatch, texts_by_source: dict):
    """Fakes load_source_text/chunk_source/build_raw_chunks/classify_batch so the real
    5-source pipeline (real PDFs, real HF model) never runs — one fake single-chunk
    "document" per SourceName, content controlled by the test."""

    def fake_load_source_text(source):
        return texts_by_source[source], False

    def fake_chunk_source(source, text):
        return [text]

    def fake_build_raw_chunks(source, text_chunks):
        return [_FakeChunk(f"{source.value}_chunk_001", source, text_chunks[0])]

    def fake_classify_batch(texts):
        return [(["general"], {"general": 0.9}) for _ in texts]

    monkeypatch.setattr(inc, "load_source_text", fake_load_source_text)
    monkeypatch.setattr(inc, "chunk_source", fake_chunk_source)
    monkeypatch.setattr(inc, "build_raw_chunks", fake_build_raw_chunks)
    monkeypatch.setattr(inc, "classify_batch", fake_classify_batch)


def _spies():
    embed_calls: list[list[str]] = []
    uploaded: list[tuple] = []
    deleted: list[list[str]] = []

    def embed_fn(texts):
        embed_calls.append(list(texts))
        return [[0.0, 0.0, 0.0] for _ in texts]

    def upload_fn(rows, vectors):
        uploaded.append((rows, vectors))

    def delete_fn(ids):
        deleted.append(ids)

    return embed_calls, uploaded, deleted, embed_fn, upload_fn, delete_fn


def test_first_run_treats_every_source_as_changed(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    kb_path = tmp_path / "chanakya_kb.jsonl"
    texts = {s: f"original text for {s.value}" for s in SourceName}
    _patch_pipeline(monkeypatch, texts)
    embed_calls, uploaded, deleted, embed_fn, upload_fn, delete_fn = _spies()

    result = inc.run_incremental("fake-model", embed_fn, upload_fn, delete_fn, manifest_path, kb_path)

    assert sorted(result["changed"]) == sorted(s.value for s in SourceName)
    assert result["unchanged"] == []
    assert len(embed_calls) == 5  # one embed call per source, all new
    assert len(uploaded) == 5
    assert deleted == []  # nothing pre-existing to remove


def test_touching_one_source_only_reembeds_that_source(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    kb_path = tmp_path / "chanakya_kb.jsonl"
    texts = {s: f"original text for {s.value}" for s in SourceName}
    _patch_pipeline(monkeypatch, texts)
    embed_calls, uploaded, deleted, embed_fn, upload_fn, delete_fn = _spies()

    inc.run_incremental("fake-model", embed_fn, upload_fn, delete_fn, manifest_path, kb_path)
    embed_calls.clear()
    uploaded.clear()

    touched = SourceName.ARTHASHASTRA
    texts[touched] = "CHANGED text for arthashastra"
    _patch_pipeline(monkeypatch, texts)

    result = inc.run_incremental("fake-model", embed_fn, upload_fn, delete_fn, manifest_path, kb_path)

    assert result["changed"] == [touched.value]
    assert sorted(result["unchanged"]) == sorted(s.value for s in SourceName if s != touched)

    # The core assertion: embed_fn was invoked exactly once, and only with the
    # touched source's chunk text — every other source's text never reached it.
    assert len(embed_calls) == 1
    assert embed_calls[0] == ["CHANGED text for arthashastra"]
    assert len(uploaded) == 1

    rows = [json.loads(l) for l in kb_path.read_text(encoding="utf-8").splitlines() if l]
    assert len(rows) == 5
    assert {r["source"] for r in rows} == {s.value for s in SourceName}
    changed_row = next(r for r in rows if r["source"] == touched.value)
    assert changed_row["text"] == "CHANGED text for arthashastra"


def test_rerun_with_no_changes_embeds_nothing(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    kb_path = tmp_path / "chanakya_kb.jsonl"
    texts = {s: f"stable text for {s.value}" for s in SourceName}
    _patch_pipeline(monkeypatch, texts)
    embed_calls, uploaded, deleted, embed_fn, upload_fn, delete_fn = _spies()

    inc.run_incremental("fake-model", embed_fn, upload_fn, delete_fn, manifest_path, kb_path)
    embed_calls.clear()
    uploaded.clear()

    result = inc.run_incremental("fake-model", embed_fn, upload_fn, delete_fn, manifest_path, kb_path)

    assert result["changed"] == []
    assert sorted(result["unchanged"]) == sorted(s.value for s in SourceName)
    assert embed_calls == []
    assert uploaded == []


def test_embed_model_change_forces_reembed_even_if_text_unchanged(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    kb_path = tmp_path / "chanakya_kb.jsonl"
    texts = {s: f"stable text for {s.value}" for s in SourceName}
    _patch_pipeline(monkeypatch, texts)
    embed_calls, uploaded, deleted, embed_fn, upload_fn, delete_fn = _spies()

    inc.run_incremental("model-v1", embed_fn, upload_fn, delete_fn, manifest_path, kb_path)
    embed_calls.clear()

    result = inc.run_incremental("model-v2", embed_fn, upload_fn, delete_fn, manifest_path, kb_path)

    assert sorted(result["changed"]) == sorted(s.value for s in SourceName)
    assert len(embed_calls) == 5


def test_shrinking_source_deletes_stale_chunk_ids(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    kb_path = tmp_path / "chanakya_kb.jsonl"
    texts = {s: f"original text for {s.value}" for s in SourceName}
    _patch_pipeline(monkeypatch, texts)
    embed_calls, uploaded, deleted, embed_fn, upload_fn, delete_fn = _spies()

    inc.run_incremental("fake-model", embed_fn, upload_fn, delete_fn, manifest_path, kb_path)

    # Re-chunking a changed source under a *different* fake id simulates a chunk
    # boundary shift — the old chunk id must be deleted, not silently orphaned.
    touched = SourceName.CHANAKYA_NEETI

    def fake_build_raw_chunks_renumbered(source, text_chunks):
        if source == touched:
            return [_FakeChunk(f"{source.value}_chunk_999", source, text_chunks[0])]
        return [_FakeChunk(f"{source.value}_chunk_001", source, text_chunks[0])]

    texts[touched] = "CHANGED text, re-chunked under a new id"
    monkeypatch.setattr(inc, "load_source_text", lambda s: (texts[s], False))
    monkeypatch.setattr(inc, "chunk_source", lambda s, t: [t])
    monkeypatch.setattr(inc, "build_raw_chunks", fake_build_raw_chunks_renumbered)
    monkeypatch.setattr(inc, "classify_batch", lambda texts: [(["general"], {"general": 0.9}) for _ in texts])

    result = inc.run_incremental("fake-model", embed_fn, upload_fn, delete_fn, manifest_path, kb_path)

    assert result["changed"] == [touched.value]
    assert deleted == [[f"{touched.value}_chunk_001"]]
