"""Shared content-hash manifest — one pattern, used by both the Chanakya and Crisis
ingestion pipelines, so re-running ingestion only reprocesses source documents that
actually changed.

`content_hash` is computed over cleaned/normalized text, never raw file bytes — a
whitespace- or encoding-only re-read of the same source must not look "changed".
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_manifest(path: Path) -> dict[str, dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_manifest(path: Path, manifest: dict[str, dict]) -> None:
    """Atomic write — a crash mid-save must never leave a half-written manifest that
    would make every doc look changed (or worse, silently unchanged) on the next run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(manifest, indent=2, ensure_ascii=False))
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def make_entry(chunk_ids: list[str], content_hash_value: str, embed_model: str | None) -> dict:
    return {
        "content_hash": content_hash_value,
        "chunk_ids": chunk_ids,
        "embed_model": embed_model,
        "last_ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def is_unchanged(
    manifest: dict[str, dict], doc_id: str, content_hash_value: str, embed_model: str | None
) -> bool:
    """A doc counts as unchanged only if its content hash *and* the embed model used
    to produce its current vectors both match — an embed-model swap must force a
    re-embed even when the text itself didn't move."""
    entry = manifest.get(doc_id)
    if not isinstance(entry, dict):
        # Missing, or a pre-migration manifest entry in an older format (e.g. crisis_kb's
        # original {filename: hash_string} shape) — treat as a cache miss rather than
        # crashing, so a format upgrade just costs one full reprocess, not a hard failure.
        return False
    return entry.get("content_hash") == content_hash_value and entry.get("embed_model") == embed_model
