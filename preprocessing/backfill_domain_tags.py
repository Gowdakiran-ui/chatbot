"""Backfill domain_tags on chanakya_kb.jsonl using the local zero-shot classifier
(classify_local.py) — no LLM, no API call. See task.md for the full spec.

Writes to a temp file and atomically replaces chanakya_kb.jsonl on success, so a crash
mid-run never leaves a half-written file. The jsonl has no embeddings in it (those are
computed at upload time in db/upload_chanakya_kb.py), so there's nothing to lose here.

Usage:
    python backfill_domain_tags.py
"""
from __future__ import annotations

import json
import os
import random
import tempfile
from collections import Counter

from classify_local import classify_batch
from config import CHANAKYA_KB_PATH, CLASSIFICATION_CONFIDENCE_THRESHOLD, DOMAIN_TAGS

OUTER_BATCH_SIZE = 100  # rows per progress-logged chunk
INNER_BATCH_SIZE = 16  # passed to the HF pipeline itself

FALLBACK_WARNING_RATIO = 0.20


def load_rows(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def classify_all(rows: list[dict]) -> None:
    """Classifies every row in place, setting domain_tags + domain_tag_scores."""
    total = len(rows)
    for start in range(0, total, OUTER_BATCH_SIZE):
        batch = rows[start : start + OUTER_BATCH_SIZE]
        results = classify_batch([r["text"] for r in batch], batch_size=INNER_BATCH_SIZE)
        for row, (tags, scores) in zip(batch, results):
            row["domain_tags"] = tags
            row["domain_tag_scores"] = scores
        done = min(start + OUTER_BATCH_SIZE, total)
        print(f"Classified {done}/{total}")


def write_rows_atomically(rows: list[dict], path) -> None:
    dir_ = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".jsonl.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def print_validation_stats(rows: list[dict], threshold: float = CLASSIFICATION_CONFIDENCE_THRESHOLD) -> None:
    print("\n=== Validation ===")
    per_label: Counter[str] = Counter()
    multi_label_count = 0
    fallback_general_count = 0

    for row in rows:
        tags = row["domain_tags"]
        scores = row["domain_tag_scores"]
        for t in tags:
            per_label[t] += 1
        if len(tags) > 1:
            multi_label_count += 1
        # Fallback was used iff nothing crossed the threshold (even if that
        # incidentally also results in tags == ["general"] "for real").
        if not any(scores.get(l, 0.0) > threshold for l in DOMAIN_TAGS):
            fallback_general_count += 1

    total = len(rows)
    print(f"Total chunks: {total}")
    print("Chunks per label:")
    for label in DOMAIN_TAGS:
        print(f"  {label}: {per_label.get(label, 0)}")
    print(f"Multi-label chunks: {multi_label_count}")
    print(f"Fallback-to-general (no label > {threshold}) chunks: {fallback_general_count} "
          f"({fallback_general_count / total:.1%})")

    if fallback_general_count / total > FALLBACK_WARNING_RATIO:
        print(
            f"\nFLAG: fallback rate exceeds {FALLBACK_WARNING_RATIO:.0%} - the "
            f"{threshold} threshold may be too strict for this content; consider "
            "lowering it (domain_tag_scores is stored per-chunk for this exact retuning)."
        )

    print("\n--- Spot-check: 10 random chunks ---")
    for row in random.sample(rows, min(10, total)):
        snippet = row["text"][:200].replace("\n", " ")
        print(f"\n[{row['id']}] tags={row['domain_tags']}")
        print(f"  scores={ {k: round(v, 3) for k, v in row['domain_tag_scores'].items()} }")
        print(f"  text: {snippet}...")


def main() -> None:
    print(f"Loading {CHANAKYA_KB_PATH} ...")
    rows = load_rows(CHANAKYA_KB_PATH)
    print(f"Loaded {len(rows)} rows")

    empty_before = sum(1 for r in rows if not r.get("domain_tags"))
    print(f"Rows with empty domain_tags before backfill: {empty_before}/{len(rows)}")

    classify_all(rows)

    still_empty = sum(1 for r in rows if not r.get("domain_tags"))
    assert still_empty == 0, f"{still_empty} rows still have empty domain_tags — fallback logic failed"

    write_rows_atomically(rows, CHANAKYA_KB_PATH)
    print(f"\nWrote {len(rows)} rows back to {CHANAKYA_KB_PATH}")

    print_validation_stats(rows)


if __name__ == "__main__":
    main()
