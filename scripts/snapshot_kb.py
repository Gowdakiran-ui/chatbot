"""Read-only snapshot of both Qdrant collections (payloads + dense + sparse vectors) to
data/snapshots/<name>.jsonl, so audits and experiments can run offline against a frozen copy.

Usage: python -m scripts.snapshot_kb [--out data/snapshots]
Only reads from the cluster (scroll); never writes to it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from db.config import CHANAKYA_COLLECTION_BASE, CRISIS_COLLECTION_BASE, DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME
from db.crisis_qdrant_client import get_client as get_crisis_client
from db.qdrant_client import get_client as get_chanakya_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def snapshot(client, alias: str, out_path: Path) -> int:
    count, offset = 0, None
    with out_path.open("w", encoding="utf-8") as fh:
        while True:
            points, offset = client.scroll(alias, limit=128, offset=offset, with_payload=True, with_vectors=True)
            for p in points:
                sparse = p.vector.get(SPARSE_VECTOR_NAME)
                fh.write(json.dumps({
                    "point_id": str(p.id),
                    "payload": p.payload,
                    "dense": p.vector.get(DENSE_VECTOR_NAME),
                    "sparse": {"indices": sparse.indices, "values": sparse.values} if sparse else None,
                }, ensure_ascii=False) + "\n")
                count += 1
            if offset is None:
                break
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "snapshots"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for alias, getter in ((CHANAKYA_COLLECTION_BASE, get_chanakya_client), (CRISIS_COLLECTION_BASE, get_crisis_client)):
        client = getter()
        info = client.get_collection(alias)
        n = snapshot(client, alias, out / f"{alias}.jsonl")
        print(f"{alias}: {n} points written (cluster reports {info.points_count}; status {info.status})")


if __name__ == "__main__":
    main()
