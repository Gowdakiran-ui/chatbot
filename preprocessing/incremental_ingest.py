"""Piece 1 — manifest-gated incremental ingestion for the Chanakya KB.

Unlike build_kb.py (full rebuild — used for fresh/versioned builds, see Piece 2), this
only reprocesses source documents whose cleaned-text hash changed since the last
successful run. Unchanged docs skip chunking, classification, and embedding entirely —
their existing rows are carried forward as-is from the current chanakya_kb.jsonl.

`embed_fn`/`upload_fn`/`delete_fn` are injectable (real Qdrant-backed callables in
`main()`, fakes in tests) — the same pattern classify_local.py already uses for its
classifier, so this stays testable without a model load or a live Qdrant connection.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Callable

from build_kb import build_raw_chunks, chunk_source, load_source_text
from classify_local import classify_batch
from config import CHANAKYA_KB_PATH, PROCESSED_DIR, SourceName
from manifest import content_hash, is_unchanged, load_manifest, make_entry, save_manifest

MANIFEST_PATH = PROCESSED_DIR / "chanakya_manifest.json"

EmbedFn = Callable[[list[str]], list[list[float]]]
UploadFn = Callable[[list[dict], list[list[float]]], None]
DeleteFn = Callable[[list[str]], None]


def _load_existing_rows_by_source(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    by_source: dict[str, list[dict]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                by_source.setdefault(row["source"], []).append(row)
    return by_source


def _write_rows_atomically(rows: list[dict], path: Path) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".jsonl.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def run_incremental(
    embed_model_name: str,
    embed_fn: EmbedFn,
    upload_fn: UploadFn,
    delete_fn: DeleteFn,
    manifest_path: Path = MANIFEST_PATH,
    kb_path: Path = CHANAKYA_KB_PATH,
) -> dict[str, list[str]]:
    """Returns {"changed": [source names...], "unchanged": [source names...]}."""
    manifest = load_manifest(manifest_path)
    existing_by_source = _load_existing_rows_by_source(kb_path)

    all_rows: list[dict] = []
    changed_sources: list[str] = []
    unchanged_sources: list[str] = []

    for source in SourceName:
        text, _ = load_source_text(source)
        h = content_hash(text)

        if is_unchanged(manifest, source.value, h, embed_model_name):
            unchanged_sources.append(source.value)
            all_rows.extend(existing_by_source.get(source.value, []))
            continue

        changed_sources.append(source.value)

        text_chunks = chunk_source(source, text)
        raw_chunks = build_raw_chunks(source, text_chunks)
        classified = classify_batch([c.text for c in raw_chunks])

        new_rows = [
            {
                "id": chunk.id,
                "source": chunk.source.value,
                "text": chunk.text,
                "domain_tags": tags,
                "chunk_type": chunk.chunk_type.value,
                "reference": chunk.reference,
                "token_count": chunk.token_count,
                "domain_tag_scores": scores,
            }
            for chunk, (tags, scores) in zip(raw_chunks, classified)
        ]

        # Chunk boundaries can shift on a re-chunk (e.g. source text edited); drop any
        # old points for this source whose id no longer exists in the new chunk set
        # before uploading — otherwise a shrinking doc leaves stale points behind.
        old_ids = {r["id"] for r in existing_by_source.get(source.value, [])}
        new_ids = {r["id"] for r in new_rows}
        stale_ids = sorted(old_ids - new_ids)
        if stale_ids:
            delete_fn(stale_ids)

        vectors = embed_fn([r["text"] for r in new_rows])
        upload_fn(new_rows, vectors)

        all_rows.extend(new_rows)
        manifest[source.value] = make_entry([r["id"] for r in new_rows], h, embed_model_name)

    _write_rows_atomically(all_rows, kb_path)
    save_manifest(manifest_path, manifest)

    return {"changed": changed_sources, "unchanged": unchanged_sources}


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root, for `db.*`

    from db.embedding import MODEL_NAME, embed_documents
    from db.qdrant_client import COLLECTION_NAME, get_client
    from db.upload_chanakya_kb import build_points

    client = get_client()

    def upload_fn(rows: list[dict], vectors: list[list[float]]) -> None:
        points = build_points(rows, vectors)
        client.upload_points(collection_name=COLLECTION_NAME, points=points, wait=True)

    def delete_fn(chunk_ids: list[str]) -> None:
        import uuid

        from qdrant_client.models import PointIdsList

        point_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, cid)) for cid in chunk_ids]
        client.delete(collection_name=COLLECTION_NAME, points_selector=PointIdsList(points=point_ids), wait=True)

    result = run_incremental(MODEL_NAME, embed_documents, upload_fn, delete_fn)
    print(f"Changed sources (reprocessed + re-embedded): {result['changed']}")
    print(f"Unchanged sources (skipped entirely): {result['unchanged']}")


if __name__ == "__main__":
    main()
