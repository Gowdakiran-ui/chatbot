"""Metrics over a retrieval trace (see eval/retrieval_trace.py). Pure functions, no I/O except main().

    python -m eval.metrics results/trace.jsonl results/baseline_retrieval.md
"""
from __future__ import annotations

import collections
import json
import statistics as st
import sys
from pathlib import Path

from eval.retrieval_trace import case_of, load_queries

K = 5


def _key(mode: str, chunk_id: str) -> str:
    """Gold labels are case ids for crisis (any chunk of the case counts) and chunk ids for chanakya."""
    return case_of(chunk_id) if mode == "crisis" else chunk_id


def ranked(row: dict, source: str) -> list[str]:
    if source == "fused":
        ids = [h["id"] for h in row["fused"]]
    else:
        ids = [i for i, _ in row[f"{source}_list"]]
    out: list[str] = []
    for i in ids:
        k = _key(row["mode"], i)
        if k not in out:
            out.append(k)
    return out


def retrieval_metrics(rows: list[dict], source: str, k: int = K) -> dict:
    scored = [r for r in rows if r["expected_ids"]]
    if not scored:
        return {"n": 0}
    hit = recall = rr = 0.0
    for r in scored:
        gold = set(r["expected_ids"])
        got = ranked(r, source)[:k]
        found = [g for g in got if g in gold]
        hit += bool(found)
        recall += len(set(found)) / len(gold)
        first = next((i for i, g in enumerate(got, 1) if g in gold), None)
        rr += 1 / first if first else 0
    n = len(scored)
    return {"n": n, "hit@k": hit / n, "recall@k": recall / n, "mrr": rr / n}


def context_hit(rows: list[dict]) -> float:
    """Share of answerable queries whose *model-visible context* (after expansion) contains a gold item."""
    scored = [r for r in rows if r["expected_ids"]]
    ok = 0
    for r in scored:
        gold = set(r["expected_ids"])
        ctx = {_key(r["mode"], c["id"]) for c in r["context"]}
        ok += bool(ctx & gold)
    return ok / len(scored) if scored else 0.0


def refusal_metrics(rows: list[dict]) -> dict:
    """Production floor decision vs expectation. 'either'/'safe' edge cases are excluded."""
    answerable = [r for r in rows if r["expect"] == "answer"]
    offtopic = [r for r in rows if r["expect"] == "refuse"]
    refused_ans = sum(not r["prod_passes_floor"] for r in answerable)
    refused_off = sum(not r["prod_passes_floor"] for r in offtopic)
    tp, fp, fn = refused_off, refused_ans, len(offtopic) - refused_off
    return {
        "answerable": len(answerable), "answered": len(answerable) - refused_ans,
        "offtopic": len(offtopic), "refused_offtopic": refused_off,
        "refusal_precision": tp / (tp + fp) if tp + fp else 1.0,
        "refusal_recall": tp / (tp + fn) if tp + fn else 1.0,
    }


def separability(rows: list[dict], mode: str) -> dict:
    ins = [r["prod_best_dense"] for r in rows if r["mode"] == mode and r["expect"] == "answer"]
    out = [r["prod_best_dense"] for r in rows if r["mode"] == mode and r["expect"] == "refuse"]
    if not ins or not out:
        return {}
    pairs = [(a > b) + 0.5 * (a == b) for a in ins for b in out]
    return {"in_min": min(ins), "in_median": st.median(ins), "off_median": st.median(out), "off_max": max(out),
            "auc": sum(pairs) / len(pairs)}


def hubs(rows: list[dict], top: int = 8) -> list[tuple[str, int]]:
    c = collections.Counter(h["id"] for r in rows for h in r["fused"])
    return c.most_common(top)


def render(rows: list[dict]) -> str:
    out = ["# Retrieval baseline (offline snapshot, production retrieval code)", ""]
    for split, label in (("chanakya_in", "Chanakya in-scope"), ("crisis_in", "Crisis in-scope")):
        sub = [r for r in rows if r["split"] == split]
        out += [f"## {label} ({len(sub)} queries; {sum(bool(r['expected_ids']) for r in sub)} with gold labels)", "",
                "| list | hit@5 | recall@5 | MRR | hit@20 |", "|---|---|---|---|---|"]
        for src in ("fused", "dense", "sparse"):
            m, m20 = retrieval_metrics(sub, src, K), retrieval_metrics(sub, src, 20)
            if m["n"]:
                out.append(f"| {src} | {m['hit@k']:.2f} | {m['recall@k']:.2f} | {m['mrr']:.2f} | {m20['hit@k']:.2f} |")
        out += ["", f"Model-visible context contains a gold item: {context_hit(sub):.2f}", ""]
    out += ["## Refusal behaviour of the production floor", ""]
    for scope, sub in (("all modes", rows), ("chanakya", [r for r in rows if r["mode"] == "chanakya"]),
                       ("crisis", [r for r in rows if r["mode"] == "crisis"])):
        m = refusal_metrics(sub)
        out.append(f"- {scope}: answered {m['answered']}/{m['answerable']} answerable; refused {m['refused_offtopic']}/{m['offtopic']} "
                   f"off-topic; precision {m['refusal_precision']:.2f}, recall {m['refusal_recall']:.2f}")
    out += ["", "## Best-dense-score separability (answer vs refuse expected)", ""]
    for mode in ("chanakya", "crisis"):
        s = separability(rows, mode)
        if s:
            out.append(f"- {mode}: in-scope min {s['in_min']:.3f}, median {s['in_median']:.3f}; off-topic median {s['off_median']:.3f}, "
                       f"max {s['off_max']:.3f}; AUC {s['auc']:.3f}")
    out += ["", "## Hub chunks (appear in top-5 for the most queries)", ""]
    out += [f"- {cid}: {n} queries" for cid, n in hubs(rows)]
    return "\n".join(out) + "\n"


def load_trace(path: str) -> list[dict]:
    queries = {q["id"]: q for q in load_queries()}
    rows = []
    for line in Path(path).open(encoding="utf-8"):
        t = json.loads(line)
        rows.append({**t, **{k: queries[t["id"]][k] for k in ("expected_ids", "expect", "kb_gap", "note")}})
    return rows


if __name__ == "__main__":
    trace_path = sys.argv[1] if len(sys.argv) > 1 else "results/trace.jsonl"
    text = render(load_trace(trace_path))
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text, encoding="utf-8")
    print(text)
