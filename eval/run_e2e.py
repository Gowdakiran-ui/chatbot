"""End-to-end eval: send every query in eval/queries.jsonl to a running app and score the answers.

    python -m uvicorn eval.offline_app:app --port 8001        # offline KB, real prompts/model
    python -m eval.run_e2e results/baseline --base-url http://127.0.0.1:8001 [--only c01,r05] [--splits crisis_in,edge]

Writes <label>.md (aggregates + per-query table) and <label>_answers.jsonl (full answers and sources).
Needs results/trace.jsonl (eval.retrieval_trace) for the context the model was given.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

from eval.metrics import load_trace
from eval.retrieval_trace import case_of
from scripts.regression_run import CHUNK_ID_RE, LEAK_PATTERNS, QUOTE_RES, VERSE_REF_RE, _norm

# Phrases that only appear in our own system prompts: seeing them in an answer means the prompt leaked.
PROMPT_MARKERS = [r"never expose the machinery", r"grounding\s*[—-]\s*read carefully", r"retrieved passages",
                  r"quote only what is there", r"not legal advice\.? for regulatory"]
DISCLAIMER = "This is not legal advice"


def ask(base_url: str, mode: str, message: str) -> dict:
    body = json.dumps({"message": message, "mode": mode}).encode("utf-8")
    req = urllib.request.Request(f"{base_url}/chat", body, {"content-type": "application/json"})
    start, first, text, final, error = time.monotonic(), None, "", {}, None
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                ev = json.loads(line[5:])
                if ev["type"] == "token":
                    first = first if first is not None else time.monotonic() - start
                    text += ev["text"]
                elif ev["type"] == "final":
                    final = ev
                elif ev["type"] == "error":
                    error = ev.get("message")
    except urllib.error.HTTPError as exc:
        error = f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}"
    except Exception as exc:  # network / timeout
        error = repr(exc)
    return {"text": text, "final": final, "ttft": first, "total": time.monotonic() - start, "error": error}


def score(row: dict, res: dict) -> dict:
    text, final = res["text"], res["final"]
    refused = bool(final.get("refused")) if final else None
    supplied = "\n".join(c["text"] for c in row["context"])
    supplied_norm = _norm(supplied)
    plain = text.replace("**", "")
    quotes = [q for rx in QUOTE_RES for q in rx.findall(plain) if len(_norm(q).split()) >= 6]
    shown = [s["id"] for s in final.get("sources", [])] if final else []
    gold = set(row["expected_ids"])
    shown_keys = [case_of(i) if row["mode"] == "crisis" else i for i in shown]
    return {
        "refused": refused,
        "leaks": sorted({m.group(0).lower() for p in LEAK_PATTERNS for m in re.finditer(p, text, re.I)}) if not refused else [],
        "chunk_ids": sorted(set(CHUNK_ID_RE.findall(text))),
        "prompt_leak": sorted({m for p in PROMPT_MARKERS for m in [p] if re.search(p, text, re.I)}) if not refused else [],
        "unsupported_quotes": [q[:80] for q in quotes if _norm(q) not in supplied_norm] if not refused else [],
        "unsupported_refs": [r for r in dict.fromkeys(VERSE_REF_RE.findall(text)) if r.split("-")[0] not in supplied] if not refused else [],
        "sources": shown,
        "source_precision": (sum(k in gold for k in shown_keys) / len(shown_keys)) if (gold and shown_keys) else None,
        "disclaimer": (DISCLAIMER in text) if row["mode"] == "crisis" and refused is False else None,
        "ttft": res["ttft"], "total": res["total"], "error": res["error"],
    }


def verdict(row: dict, s: dict) -> str:
    if s["error"]:
        return "ERROR"
    exp, refused = row["expect"], s["refused"]
    if exp == "answer":
        return "ok" if refused is False else "WRONG(refused)"
    if exp == "refuse":
        return "ok" if refused else "WRONG(answered)"
    return "n/a"


def aggregate(results: list[tuple[dict, dict]]) -> list[str]:
    out = ["| split | n | verdict ok | answered | leak phrases | chunk ids | prompt leak | unsupported quote/ref | mean TTFT | mean total |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for split in ("chanakya_in", "crisis_in", "offtopic", "edge"):
        sub = [(r, s) for r, s in results if r["split"] == split]
        if not sub:
            continue
        n = len(sub)
        ok = sum(verdict(r, s) == "ok" for r, s in sub)
        graded = sum(verdict(r, s) != "n/a" for r, s in sub)
        answered = [(r, s) for r, s in sub if s["refused"] is False]
        mean = lambda xs: (sum(xs) / len(xs)) if xs else float("nan")  # noqa: E731
        out.append(f"| {split} | {n} | {ok}/{graded} | {len(answered)} | {sum(bool(s['leaks']) for _, s in answered)} | "
                   f"{sum(bool(s['chunk_ids']) for _, s in answered)} | {sum(bool(s['prompt_leak']) for _, s in answered)} | "
                   f"{sum(bool(s['unsupported_quotes'] or s['unsupported_refs']) for _, s in answered)} | "
                   f"{mean([s['ttft'] for _, s in sub if s['ttft']]):.1f}s | {mean([s['total'] for _, s in sub]):.1f}s |")
    prec = [s["source_precision"] for _, s in results if s["source_precision"] is not None]
    out += ["", f"Source precision (shown sources that are gold; labelled queries only): {sum(prec) / len(prec):.2f} over {len(prec)} answers" if prec else ""]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--only", default="")
    ap.add_argument("--splits", default="")
    ap.add_argument("--trace", default="results/trace.jsonl")
    ap.add_argument("--rescore", action="store_true", help="re-score saved answers instead of calling the app")
    args = ap.parse_args()
    rows = load_trace(args.trace)
    if args.only:
        rows = [r for r in rows if r["id"] in args.only.split(",")]
    if args.splits:
        rows = [r for r in rows if r["split"] in args.splits.split(",")]
    results, out_dir = [], Path(args.label)
    out_dir.parent.mkdir(exist_ok=True)
    saved = {}
    if args.rescore:
        # Read the saved answers fully BEFORE opening any output file, and never write over them.
        saved = {json.loads(l)["id"]: json.loads(l) for l in Path(args.label + "_answers.jsonl").open(encoding="utf-8")}
        answers = Path(args.label + "_rescored_answers.jsonl").open("w", encoding="utf-8")
    else:
        answers_path = out_dir.with_name(out_dir.name + "_answers.jsonl")
        if answers_path.exists() and answers_path.stat().st_size:
            answers_path.replace(answers_path.with_suffix(".jsonl.bak"))  # keep the previous run's answers
        answers = answers_path.open("w", encoding="utf-8")
    for i, row in enumerate(rows, 1):
        if args.rescore:
            old = saved[row["id"]]
            res = {"text": old["text"], "ttft": old["ttft"], "total": old["total"], "error": old["error"],
                   "final": {"refused": old["refused"], "sources": [{"id": x} for x in old["sources"]]} if old["refused"] is not None else {}}
        else:
            res = ask(args.base_url, row["mode"], row["query"])
        s = score(row, res)
        results.append((row, s))
        answers.write(json.dumps({"id": row["id"], "query": row["query"], "mode": row["mode"], "text": res["text"], **s}, ensure_ascii=False) + "\n")
        answers.flush()
        print(f"{i:>3}/{len(rows)} {row['id']} {verdict(row, s):<15} dense={row['prod_best_dense']:.3f} ttft={s['ttft'] and round(s['ttft'], 1)} "
              f"total={s['total']:.1f} leaks={s['leaks']} ids={len(s['chunk_ids'])} uq={len(s['unsupported_quotes'])}", flush=True)
    lines = [f"# {args.label}", ""] + aggregate(results) + ["", "## Per query", "",
             "| id | split | mode | expect | verdict | dense | ttft | total | leaks | ids | prompt | unsupp q/r | src prec | disclaimer |", "|" + "---|" * 14]
    for r, s in results:
        lines.append(f"| {r['id']} | {r['split']} | {r['mode']} | {r['expect']} | {verdict(r, s)} | {r['prod_best_dense']:.3f} | "
                     f"{(s['ttft'] or 0):.1f} | {s['total']:.1f} | {', '.join(s['leaks']) or '-'} | {len(s['chunk_ids']) or '-'} | "
                     f"{', '.join(s['prompt_leak']) or '-'} | {len(s['unsupported_quotes'])}/{len(s['unsupported_refs'])} | "
                     f"{'-' if s['source_precision'] is None else format(s['source_precision'], '.2f')} | {s['disclaimer'] if s['disclaimer'] is not None else '-'} |")
    Path(str(out_dir) + ".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", str(out_dir) + ".md")


if __name__ == "__main__":
    main()
