"""Piece 3 (live-verification task) — generation-quality eval.

Runs the real /chat pipeline end to end (real retrieval against production Qdrant,
real generation via OpenRouter) for a small, deliberately non-exhaustive sample: 8
queries per KB, drawn from the existing hand-verified golden query sets
(preprocessing/tests/golden_queries_*.jsonl) so retrieval quality is not a
confound here — these are known-good retrieval queries; this eval is about
generation quality specifically (citation presence, disclaimer presence,
groundedness), which the golden-query recall eval never checked.

NOT a pytest test — makes real, billed OpenRouter calls (see providers/openrouter.py's
cost safety rail: max_tokens capped, reasoning explicitly disabled). Run manually:

    python -m preprocessing.tests.eval_generation

Writes raw per-query records (query, retrieved context, full answer, latency, cost)
to preprocessing/tests/_eval_generation_raw.json for offline manual review — the
citation cross-check and groundedness read happen against that file afterward, not
inside this script, since groundedness judgment isn't scriptable.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from providers.openrouter import OpenRouterProvider
from serving.floor import check_floor
from serving.mode_config import MODE_CONFIG, Mode
from serving.prompt import build_prompt
from serving.retrieval import retrieve_context

RAW_OUTPUT_PATH = PROJECT_ROOT / "preprocessing" / "tests" / "_eval_generation_raw.json"

# Drawn from golden_queries_chanakya.jsonl — one per source type (arthashastra x2,
# chanakya_neeti x2, 7_secrets x2, corporate_chanakya x1, chanakya_info x1) so the
# sample isn't skewed toward one source's citation style.
CHANAKYA_QUERIES = [
    "what did the Arthashastra say about the Superintendent of Horses",
    "famine versus pestilence which is worse for a kingdom",
    "what makes someone a real friend in times of danger and sickness",
    "who is the greatest tell me O Vipra riddle verse",
    "the story of the businessman and Mr Chheda who saved his life and business",
    "a businessman should plan ten years ahead a politician one generation ahead",
    "why giving a gift is a powerful way to influence someone per Arthashastra",
    "Chandragupta playing king among a group of boys as a child",
]

# Drawn from golden_queries_crisis.jsonl — spread across regions (india x2, europe x3,
# america x3) and crisis types (fraud, data/privacy, safety, governance, PR).
CRISIS_QUERIES = [
    "Nirav Modi Punjab National Bank fraud case summary",
    "Facebook Cambridge Analytica data misuse political manipulation scandal",
    "Wells Fargo unauthorized fake accounts sales culture scandal",
    "Volkswagen Dieselgate emissions regulatory fraud",
    "Boeing product safety mass casualty design defect",
    "Kingfisher Airlines Vijay Mallya loan default fugitive economic offence",
    "United Airlines viral customer mistreatment incident",
    "Siemens systemic bribery corruption scandal",
]


def run_query(query: str, mode: Mode, provider: OpenRouterProvider) -> dict:
    config = MODE_CONFIG[mode]
    result = retrieve_context(query, config, mode)
    check = check_floor(result, config)

    record = {
        "query": query,
        "mode": mode.value,
        "top_score": result.top_score,
        "top_dense_score": result.top_dense_score,
        "passed_floor": check.passed,
        "retrieved_context": [
            {"chunk_id": c.chunk_id, "text": c.text, "payload": c.payload} for c in result.chunks
        ],
    }

    if not check.passed:
        record["answer"] = None
        record["refused"] = True
        return record

    system = config.system_prompt_path.read_text(encoding="utf-8")
    prompt = build_prompt(query, result)

    t0 = time.monotonic()
    answer = provider.generate(prompt, system, stream=False)
    t1 = time.monotonic()

    record["answer"] = answer
    record["refused"] = False
    record["latency_seconds"] = round(t1 - t0, 3)
    return record


def main() -> None:
    provider = OpenRouterProvider()
    records: list[dict] = []

    for q in CHANAKYA_QUERIES:
        print(f"[chanakya] {q}")
        records.append(run_query(q, Mode.CHANAKYA, provider))

    for q in CRISIS_QUERIES:
        print(f"[crisis] {q}")
        records.append(run_query(q, Mode.CRISIS, provider))

    provider.print_cost_summary()

    RAW_OUTPUT_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} raw records to {RAW_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
