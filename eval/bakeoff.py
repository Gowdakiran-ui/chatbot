"""Model bake-off on frozen retrieval: same system prompts, same context, only the model changes.

    python -m eval.bakeoff results/bakeoff --models deepseek/deepseek-v4-pro,anthropic/claude-haiku-5.5,anthropic/claude-sonnet-5.5

Contexts come from results/trace.jsonl (offline retrieval), so retrieval variance is removed. Each model
is called through the app's own OpenRouterProvider (streaming) so TTFT/total/usage are measured the same way.
Scores: leak phrases, raw chunk-id echo (before the output filter), unsupported quotes, numbers that are not in the
context, length, TTFT, total, and real cost from OpenRouter's listed prices. Persona/usefulness are for a human:
a blind side-by-side file is written for manual rating.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

from eval.metrics import load_trace
from providers.openrouter import OpenRouterProvider
from scripts.regression_run import CHUNK_ID_RE, LEAK_PATTERNS, QUOTE_RES, _norm
from serving.mode_config import MODE_CONFIG, Mode

NUMBER_RE = re.compile(r"[$€£₹]?\d[\d,]*(?:\.\d+)?\s?(?:%|billion|million|crore|lakh|bn|m)?", re.I)
# USD per million tokens, from https://openrouter.ai/api/v1/models (checked when this file was written).
PRICES = {
    "deepseek/deepseek-v4-pro": (0.96, 1.91),
    "anthropic/claude-haiku-5.5": (0.10, 0.50),
    "anthropic/claude-sonnet-5.5": (2.00, 10.00),
}
DEFAULT_QUERIES = (
    "c01 c05 c09 c13 c17 c20 c23 c27 c31 c34 c37 c12 c24 c35 c06 c04 "
    "r01 r04 r07 r10 r13 r16 r18 r21 r23 r26 r28 r32 r33 r36 r38 r40 "
    "o03 o09 o17 o20 e04 e05 e11 e12"
).split()


def build_prompt_from_trace(row: dict) -> str:
    block = "\n\n---\n\n".join(f"[{c['id']}]\n{c['text']}" for c in row["context"])
    return f"Retrieved context:\n\n{block}\n\nQuestion: {row['query']}"


def run_one(model: str, row: dict) -> dict:
    cfg = MODE_CONFIG[Mode(row["mode"])]
    system = cfg.system_prompt_path.read_text(encoding="utf-8")
    provider = OpenRouterProvider(model=model)
    start, first, text, error = time.monotonic(), None, "", None
    try:
        for tok in provider.generate(build_prompt_from_trace(row), system, stream=True, max_tokens=cfg.max_tokens):
            first = first if first is not None else time.monotonic() - start
            text += tok
    except Exception as exc:
        error = repr(exc)
    usage = provider.usage_log[-1] if provider.usage_log else {"input_tokens": 0, "output_tokens": 0}
    pin, pout = PRICES.get(model, (0, 0))
    context = "\n".join(c["text"] for c in row["context"])
    ctx_norm, ctx_numbers = _norm(context), {re.sub(r"[^\d.]", "", n) for n in NUMBER_RE.findall(context)}
    answer_numbers = {re.sub(r"[^\d.]", "", n) for n in NUMBER_RE.findall(text)} - {""}
    plain = text.replace("**", "")
    quotes = [q for rx in QUOTE_RES for q in rx.findall(plain) if len(_norm(q).split()) >= 6]
    return {
        "model": model, "id": row["id"], "mode": row["mode"], "query": row["query"], "text": text, "error": error,
        "ttft": first, "total": time.monotonic() - start, "finish": provider.last_finish_reason,
        "in_tokens": usage["input_tokens"], "out_tokens": usage["output_tokens"],
        "cost": usage["input_tokens"] / 1e6 * pin + usage["output_tokens"] / 1e6 * pout,
        "leaks": sorted({m.group(0).lower() for p in LEAK_PATTERNS for m in re.finditer(p, text, re.I)}),
        "id_echo": sorted(set(CHUNK_ID_RE.findall(text))),
        "unsupported_quotes": [q[:80] for q in quotes if _norm(q) not in ctx_norm],
        "numbers_not_in_context": sorted(n for n in answer_numbers if n not in ctx_numbers and len(n) > 1)[:12],
        "words": len(text.split()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--models", default=",".join(PRICES))
    ap.add_argument("--only", default=" ".join(DEFAULT_QUERIES))
    ap.add_argument("--trace", default="results/trace.jsonl")
    args = ap.parse_args()
    ids = args.only.replace(",", " ").split()
    rows = [r for r in load_trace(args.trace) if r["id"] in ids]
    models = args.models.split(",")
    out = Path(args.label + "_runs.jsonl").open("w", encoding="utf-8")
    results = []
    for row in rows:
        for model in models:
            res = run_one(model, row)
            results.append(res)
            out.write(json.dumps(res, ensure_ascii=False) + "\n"); out.flush()
            print(f"{row['id']} {model:<30} ttft={res['ttft'] and round(res['ttft'], 1)} total={res['total']:.1f} cost=${res['cost']:.4f} "
                  f"leaks={res['leaks']} idecho={len(res['id_echo'])} uq={len(res['unsupported_quotes'])} nums={len(res['numbers_not_in_context'])}", flush=True)
    # summary table
    lines = [f"# {args.label}", "", "| model | n | errors | median TTFT | median total | mean cost/answer | leak answers | id-echo answers | unsupported-quote answers | answers with numbers not in context | mean words |", "|" + "---|" * 11]
    for model in models:
        rs = [r for r in results if r["model"] == model]
        ok = [r for r in rs if not r["error"] and r["text"]]
        med = lambda xs: sorted(xs)[len(xs) // 2] if xs else float("nan")  # noqa: E731
        lines.append(f"| {model} | {len(rs)} | {len(rs) - len(ok)} | {med([r['ttft'] for r in ok if r['ttft']]):.1f}s | {med([r['total'] for r in ok]):.1f}s | "
                     f"${sum(r['cost'] for r in rs) / max(len(rs), 1):.4f} | {sum(bool(r['leaks']) for r in ok)} | {sum(bool(r['id_echo']) for r in ok)} | "
                     f"{sum(bool(r['unsupported_quotes']) for r in ok)} | {sum(bool(r['numbers_not_in_context']) for r in ok)} | {sum(r['words'] for r in ok) / max(len(ok), 1):.0f} |")
    lines.append(f"\nTotal spend this run: ${sum(r['cost'] for r in results):.3f}")
    Path(args.label + ".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # blind side-by-side for human rating (model order shuffled per query, key kept separately)
    rng, blind, key = random.Random(7), [], {}
    for row in rows:
        group = [r for r in results if r["id"] == row["id"]]
        rng.shuffle(group)
        blind.append(f"\n\n## {row['id']} [{row['mode']}] {row['query'][:200]}\n")
        for letter, r in zip("ABC", group):
            key[f"{row['id']}:{letter}"] = r["model"]
            blind.append(f"\n### Answer {letter}\n\n{r['text']}\n")
    Path(args.label + "_blind.md").write_text("".join(blind), encoding="utf-8")
    Path(args.label + "_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print("wrote", args.label + ".md")


if __name__ == "__main__":
    main()
