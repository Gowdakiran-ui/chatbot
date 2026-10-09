"""Retrieval tracing and metrics over the offline KBs (no network, no LLM).

Runs the production `serving.retrieval.retrieve_context` unchanged (so the numbers describe what the
app really does) and, next to it, the dense-only and sparse-only candidate lists so the effect of
fusion, the floor and parent expansion can be inspected.

    python -m eval.retrieval_trace results/trace.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from db.config import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME
from db.embedding import embed_query
from db.sparse_embedding import embed_query_sparse
from eval.offline_kb import build_offline_clients
from serving.floor import passes_floor
from serving.mode_config import MODE_CONFIG, Mode
from serving.retrieval import retrieve_context

EVAL_DIR = Path(__file__).resolve().parent
LIST_DEPTH = 20


def load_queries(path: Path = EVAL_DIR / "queries.jsonl") -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def offline_config(mode: Mode, clients: dict):
    base = MODE_CONFIG[mode]
    return base.model_copy(update={"get_client": lambda: clients[base.collection_alias]})


def trace_query(query: str, mode: Mode, clients: dict) -> dict:
    config = offline_config(mode, clients)
    client = clients[config.collection_alias]
    dense = client.query_points(config.collection_alias, query=embed_query(query), using=DENSE_VECTOR_NAME,
                                limit=LIST_DEPTH, with_payload=["id", "case_id"]).points
    sparse = client.query_points(config.collection_alias, query=embed_query_sparse(query), using=SPARSE_VECTOR_NAME,
                                 limit=LIST_DEPTH, with_payload=["id", "case_id"]).points
    result = retrieve_context(query, config, mode)
    return {
        "dense_list": [(p.payload["id"], round(p.score, 4)) for p in dense],
        "sparse_list": [(p.payload["id"], round(p.score, 4)) for p in sparse],
        "fused": [
            {"rank": i + 1, "id": h.chunk_id, "rrf": round(h.score, 4), "dense": round(h.dense_score, 4)}
            for i, h in enumerate(result.raw_hits)
        ],
        "context": [{"id": c.chunk_id, "chars": len(c.text), "text": c.text} for c in result.chunks],
        "prod_best_dense": round(result.top_dense_score, 4),
        "prod_floor": config.min_score,
        "prod_passes_floor": passes_floor(result, config),
        "dense_top1_overall": round(dense[0].score, 4) if dense else 0.0,
    }


def case_of(chunk_id: str) -> str:
    """crisis ids are <case_id>_<chunk_type>; chanakya ids are returned unchanged."""
    for suffix in ("_summary", "_trigger_event", "_went_right", "_went_wrong", "_best_practice"):
        if chunk_id.endswith(suffix):
            return chunk_id[: -len(suffix)]
    return chunk_id


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "results/trace.jsonl")
    out.parent.mkdir(exist_ok=True)
    clients = build_offline_clients()
    rows = load_queries()
    with out.open("w", encoding="utf-8") as fh:
        for i, q in enumerate(rows, 1):
            t = trace_query(q["query"], Mode(q["mode"]), clients)
            fh.write(json.dumps({**q, **t}, ensure_ascii=False) + "\n")
            if i % 20 == 0:
                print(f"{i}/{len(rows)}", flush=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
