"""Orchestrator: runs Steps 1-5 end to end and writes chanakya_kb.jsonl / needs_review.jsonl.

Usage:
    python build_kb.py            # full pipeline including LLM classification
    python build_kb.py --no-llm   # skip Step 3 (classification) — useful without an API key
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

from chunking import TextChunk, chunk_prose_style, chunk_verse_style
from classify import classify_batch_via_llm, needs_review
from config import (
    CHANAKYA_KB_PATH,
    CLASSIFICATION_BATCH_SIZE,
    CLEANED_DIR,
    NEEDS_REVIEW_PATH,
    PROCESSED_DIR,
    RAW_DIR,
    ChunkType,
    DomainTag,
    SOURCE_CHUNK_TYPE,
    SOURCE_FILENAMES,
    SourceName,
)
from pdf_clean import clean_pdf_file, write_cleaning_outputs
from schema import ClassifiedChunk, NeedsReviewChunk, RawChunk


def _slugify(reference: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", reference.lower()).strip("_")
    return slug[:max_len] or "loc"


def load_source_text(source: SourceName) -> tuple[str, bool]:
    """Returns (cleaned_text, was_pdf). Runs Step 1 for PDFs; the .txt source is already clean."""
    filename = SOURCE_FILENAMES[source]
    raw_path = RAW_DIR / filename

    if filename.endswith(".txt"):
        return raw_path.read_text(encoding="utf-8"), False

    cleaned_text, log = clean_pdf_file(raw_path)
    write_cleaning_outputs(source.value, cleaned_text, log, CLEANED_DIR)
    return cleaned_text, True


def chunk_source(source: SourceName, text: str) -> list[TextChunk]:
    chunk_type = SOURCE_CHUNK_TYPE[source]
    if chunk_type is ChunkType.VERSE:
        return chunk_verse_style(text)
    return chunk_prose_style(text)


def build_raw_chunks(source: SourceName, text_chunks: list[TextChunk]) -> list[RawChunk]:
    chunk_type = SOURCE_CHUNK_TYPE[source]
    seq_by_ref: Counter[str] = Counter()
    raw_chunks: list[RawChunk] = []
    for tc in text_chunks:
        slug = _slugify(tc.reference)
        seq_by_ref[slug] += 1
        chunk_id = f"{source.value}_{slug}_{seq_by_ref[slug]:03d}"
        raw_chunks.append(
            RawChunk(
                id=chunk_id,
                source=source,
                text=tc.text,
                chunk_type=chunk_type,
                reference=tc.reference,
                token_count=tc.token_count,
            )
        )
    return raw_chunks


def classify_all(raw_chunks: list[RawChunk], batch_size: int = CLASSIFICATION_BATCH_SIZE):
    classified: list[ClassifiedChunk] = []
    flagged: list[NeedsReviewChunk] = []

    for i in range(0, len(raw_chunks), batch_size):
        batch = raw_chunks[i : i + batch_size]
        results = classify_batch_via_llm([c.text for c in batch])
        for chunk, result in zip(batch, results):
            if needs_review(result):
                flagged.append(
                    NeedsReviewChunk(
                        id=chunk.id,
                        source=chunk.source,
                        text=chunk.text,
                        chunk_type=chunk.chunk_type,
                        reference=chunk.reference,
                        token_count=chunk.token_count,
                        proposed_tags=result["tags"],
                        confidence=result["confidence"],
                        reason="empty tags" if not result["tags"] else "low confidence",
                    )
                )
            else:
                classified.append(
                    ClassifiedChunk(
                        id=chunk.id,
                        source=chunk.source,
                        text=chunk.text,
                        domain_tags=[DomainTag(t) for t in result["tags"]],
                        chunk_type=chunk.chunk_type,
                        reference=chunk.reference,
                        token_count=chunk.token_count,
                    )
                )
    return classified, flagged


def print_validation_stats(classified: list[ClassifiedChunk], flagged: list[NeedsReviewChunk]) -> None:
    print("\n=== Step 5: Validation ===")
    by_source: Counter[str] = Counter(c.source.value for c in classified)
    by_tag: Counter[str] = Counter()
    for c in classified:
        for t in c.domain_tags:
            by_tag[t.value] += 1
    token_counts = [c.token_count for c in classified]
    avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0

    print(f"Total chunks: {len(classified)}  |  needs_review: {len(flagged)}")
    print("Chunks per source:")
    for source, count in by_source.items():
        print(f"  {source}: {count}")
    print("Chunks per domain tag:")
    for tag, count in by_tag.items():
        print(f"  {tag}: {count}")
    print(f"Average chunk token size: {avg_tokens:.1f}")

    if classified:
        print("\n--- Spot-check: 10 random chunks ---")
        sample = random.sample(classified, min(10, len(classified)))
        for c in sample:
            print(f"\n[{c.id}] tags={[t.value for t in c.domain_tags]} ref={c.reference}")
            print(c.text[:400])


def run(use_llm: bool = True) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    all_raw_chunks: list[RawChunk] = []
    for source in SourceName:
        print(f"Processing {source.value} ...")
        text, was_pdf = load_source_text(source)
        text_chunks = chunk_source(source, text)
        raw_chunks = build_raw_chunks(source, text_chunks)
        all_raw_chunks.extend(raw_chunks)
        print(f"  {'cleaned + ' if was_pdf else ''}chunked -> {len(raw_chunks)} chunks")

    if not use_llm:
        print("\n--no-llm: skipping Step 3 classification. Writing chunks with empty tags.")
        with open(CHANAKYA_KB_PATH, "w", encoding="utf-8") as f:
            for c in all_raw_chunks:
                record = {
                    "id": c.id,
                    "source": c.source.value,
                    "text": c.text,
                    "domain_tags": [],
                    "chunk_type": c.chunk_type.value,
                    "reference": c.reference,
                    "token_count": c.token_count,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"Wrote {len(all_raw_chunks)} unclassified chunks to {CHANAKYA_KB_PATH}")
        return

    print(f"\nClassifying {len(all_raw_chunks)} chunks via {CLASSIFICATION_BATCH_SIZE}-item batches...")
    classified, flagged = classify_all(all_raw_chunks)

    with open(CHANAKYA_KB_PATH, "w", encoding="utf-8") as f:
        for c in classified:
            f.write(json.dumps(c.to_jsonl_dict(), ensure_ascii=False) + "\n")

    with open(NEEDS_REVIEW_PATH, "w", encoding="utf-8") as f:
        for c in flagged:
            f.write(json.dumps(c.to_jsonl_dict(), ensure_ascii=False) + "\n")

    print(f"Wrote {len(classified)} chunks to {CHANAKYA_KB_PATH}")
    print(f"Wrote {len(flagged)} flagged chunks to {NEEDS_REVIEW_PATH}")

    print_validation_stats(classified, flagged)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="Skip Step 3 LLM classification")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    run(use_llm=not args.no_llm)
