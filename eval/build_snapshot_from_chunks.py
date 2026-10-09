"""Build an offline KB snapshot from a rebuilt chunks file, reusing vectors for unchanged chunks.

    python -m eval.build_snapshot_from_chunks results/crisis_v2/crisis_kb.jsonl data/snapshots_v2/crisis_kb.jsonl

For every chunk whose id and text already exist in the base snapshot the stored dense and sparse vectors are
reused (so nothing existing is re-embedded or changes score); new or changed chunks are embedded locally with the
same model and prefixes as production. Only reads the base snapshot and writes the output file - no cluster access.
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from db.embedding import embed_documents
from db.sparse_embedding import embed_documents_sparse

BASE = Path(__file__).resolve().parent.parent / "data" / "snapshots" / "crisis_kb.jsonl"
NAMESPACE = uuid.NAMESPACE_DNS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("chunks")
    ap.add_argument("out")
    ap.add_argument("--base", default=str(BASE))
    args = ap.parse_args()

    base = {}
    for line in Path(args.base).open(encoding="utf-8"):
        row = json.loads(line)
        base[row["payload"]["id"]] = row
    chunks = [json.loads(line) for line in Path(args.chunks).open(encoding="utf-8")]

    reuse, fresh = [], []
    for c in chunks:
        old = base.get(c["id"])
        (reuse if old and old["payload"]["text"] == c["text"] else fresh).append(c)
    print(f"reusing vectors for {len(reuse)} chunks; embedding {len(fresh)} new/changed chunks")

    dense = embed_documents([c["text"] for c in fresh], batch_size=16) if fresh else []
    sparse = embed_documents_sparse([c["text"] for c in fresh]) if fresh else []
    fresh_vecs = {c["id"]: (d, s) for c, d, s in zip(fresh, dense, sparse)}

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out).open("w", encoding="utf-8") as fh:
        for c in chunks:
            payload = {**c["metadata"], "id": c["id"], "text": c["text"]}
            if c["id"] in fresh_vecs:
                d, s = fresh_vecs[c["id"]]
                dense_vec, sparse_vec = d, {"indices": list(s.indices), "values": list(s.values)}
            else:
                old = base[c["id"]]
                dense_vec, sparse_vec = old["dense"], old["sparse"]
            fh.write(json.dumps({"point_id": str(uuid.uuid5(NAMESPACE, c["id"])), "payload": payload,
                                 "dense": dense_vec, "sparse": sparse_vec}, ensure_ascii=False) + "\n")
    print("wrote", args.out, f"({len(chunks)} points)")


if __name__ == "__main__":
    main()
