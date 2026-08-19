"""Orchestrator for the crisis case-study KB (Steps 1-5 of task.md).

Incremental/idempotent by batch filename: each raw .md file is parsed+chunked into its
own cached per-batch JSONL, keyed by a content hash. A batch is only reprocessed if it's
new or its content changed; unchanged batches are read from cache. crisis_kb.jsonl and
parse_errors.jsonl are always rebuilt by concatenating the (possibly-cached) per-batch
files, which is cheap.

Usage:
    python build_crisis_kb.py
    python build_crisis_kb.py --region india   # override inference for all input files
    python build_crisis_kb.py --force          # ignore cache, reprocess every batch
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from crisis_chunk import build_case_chunks
from crisis_config import (
    CRISIS_BATCH_CACHE_DIR,
    CRISIS_BATCH_MANIFEST_PATH,
    CRISIS_KB_PATH,
    CRISIS_PARSE_ERRORS_PATH,
    CRISIS_PROCESSED_DIR,
    CRISIS_RAW_DIR,
    Region,
    infer_region,
)
from crisis_parse import parse_batch_file
from manifest import content_hash as _content_hash
from manifest import is_unchanged, load_manifest, make_entry, save_manifest


def _batch_cache_paths(stem: str) -> tuple[Path, Path]:
    return (
        CRISIS_BATCH_CACHE_DIR / f"{stem}.chunks.jsonl",
        CRISIS_BATCH_CACHE_DIR / f"{stem}.errors.jsonl",
    )


def process_batch_file(path: Path, region_override: Region | None) -> tuple[int, int]:
    """Parses+chunks one batch file and writes its per-batch cache. Returns
    (n_cases, n_errors)."""
    region = region_override or infer_region(path.name)
    if region is None:
        raise ValueError(
            f"Could not infer region for {path.name}; pass --region india|europe|america"
        )

    text = path.read_text(encoding="utf-8")
    cases, errors = parse_batch_file(text, region, path.name)

    chunks_path, errors_path = _batch_cache_paths(path.stem)
    with open(chunks_path, "w", encoding="utf-8") as f:
        for case in cases:
            for chunk in build_case_chunks(case):
                f.write(json.dumps(chunk.to_jsonl_dict(), ensure_ascii=False) + "\n")
    with open(errors_path, "w", encoding="utf-8") as f:
        for err in errors:
            f.write(json.dumps(err.to_jsonl_dict(), ensure_ascii=False) + "\n")

    return len(cases), len(errors)


def run(region_override: Region | None = None, force: bool = False) -> None:
    CRISIS_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    CRISIS_BATCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(CRISIS_BATCH_MANIFEST_PATH)
    batch_files = sorted(CRISIS_RAW_DIR.glob("*.md"))
    if not batch_files:
        print(f"No batch files found in {CRISIS_RAW_DIR}")
        return

    for path in batch_files:
        text = path.read_text(encoding="utf-8")
        h = _content_hash(text)
        chunks_path, _ = _batch_cache_paths(path.stem)
        # embed_model=None: this manifest only gates parse+chunk caching (Step 1-2),
        # not embedding — crisis_kb has no incremental-embed path yet (see Piece 1 report).
        cached = is_unchanged(manifest, path.name, h, embed_model=None) and chunks_path.exists()

        if cached and not force:
            print(f"  {path.name}: unchanged, using cache")
            continue

        n_cases, n_errors = process_batch_file(path, region_override)
        chunk_ids = [
            json.loads(l)["id"] for l in chunks_path.read_text(encoding="utf-8").splitlines() if l
        ]
        manifest[path.name] = make_entry(chunk_ids, h, embed_model=None)
        print(f"  {path.name}: parsed {n_cases} case(s), {n_errors} field error(s)")

    save_manifest(CRISIS_BATCH_MANIFEST_PATH, manifest)

    # Rebuild the combined outputs from (cached + freshly processed) per-batch files.
    all_chunks: list[dict] = []
    all_errors: list[dict] = []
    for path in batch_files:
        chunks_path, errors_path = _batch_cache_paths(path.stem)
        if chunks_path.exists():
            all_chunks.extend(json.loads(l) for l in chunks_path.read_text(encoding="utf-8").splitlines() if l)
        if errors_path.exists():
            all_errors.extend(json.loads(l) for l in errors_path.read_text(encoding="utf-8").splitlines() if l)

    with open(CRISIS_KB_PATH, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(CRISIS_PARSE_ERRORS_PATH, "w", encoding="utf-8") as f:
        for e in all_errors:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(all_chunks)} chunks to {CRISIS_KB_PATH}")
    print(f"Wrote {len(all_errors)} parse errors to {CRISIS_PARSE_ERRORS_PATH}")

    print_validation_stats(all_chunks, all_errors)


def print_validation_stats(all_chunks: list[dict], all_errors: list[dict]) -> None:
    print("\n=== Step 5: Validation ===")

    by_case: dict[str, int] = defaultdict(int)
    by_region: Counter[str] = Counter()
    by_crisis_type: Counter[str] = Counter()
    for c in all_chunks:
        meta = c["metadata"]
        by_case[meta["case_id"]] += 1
        by_region[meta["region"]] += 1
        by_crisis_type[meta["crisis_type"]] += 1

    print(f"Total cases parsed: {len(by_case)}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Parse errors (fields missing): {len(all_errors)}")

    print("Chunks per region:")
    for region, count in by_region.items():
        print(f"  {region}: {count}")

    print("Chunks per crisis_type:")
    for ct, count in sorted(by_crisis_type.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {ct}: {count}")

    under_5 = {cid: n for cid, n in by_case.items() if n < 5}
    if under_5:
        print(f"\nCases with FEWER than 5 chunks (flagged): {under_5}")
    else:
        print("\nAll parsed cases produced >=5 chunks (1 summary + >=4 section).")

    if all_chunks:
        print("\n--- Spot-check: 3 random chunks ---")
        for c in random.sample(all_chunks, min(3, len(all_chunks))):
            print(f"\n[{c['id']}] chunk_type={c['chunk_type']}")
            print("metadata:", json.dumps(c["metadata"], ensure_ascii=False))
            print("text:", c["text"][:400])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=[r.value for r in Region], default=None)
    parser.add_argument("--force", action="store_true", help="Ignore cache, reprocess all batches")
    args = parser.parse_args()
    run(region_override=Region(args.region) if args.region else None, force=args.force)
