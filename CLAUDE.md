# CLAUDE.md — Chanakya RAG Project

## Project Overview
Building for **Onlyne Reputation** (ORM agency):
1. **Chanakya persona chatbot** — RAG-based advisor on *career, leadership, ethics, general* topics, grounded in Arthashastra/Chanakya Niti sourced content, paraphrased into modern business advice.
2. **Crisis toggle** — routes to a separate knowledge base of past PR/reputation crisis case studies, returning precedent-based guidance.

Two features, one app. Shared plumbing, separate knowledge bases and system prompts.

## Architecture Principles

- **Separation of concerns**: retrieval, generation, and routing are distinct layers. No business logic inside prompt strings.
- **Two collections, not two apps**: `chanakya_kb` and `crisis_kb` live in the same vector store as separate namespaces/collections. Don't fork the codebase per mode — one pipeline, mode-parameterized.
- **Mode is a request parameter, not a global**: `mode: "chanakya" | "crisis"` passed per-request, resolves to `{collection, system_prompt, output_schema}` via a small config map — not scattered if/else.
- **Config over hardcoding**: model names, chunk sizes, top-k, system prompts live in a config file (`config.py` / `config.yaml`), not inline in code.
- **Stateless retrieval layer**: retrieval functions take `(query, mode) -> chunks`. No side effects, no hidden state — easy to unit test.



## Coding Standards

- **Type hints everywhere** (Python). Use `pydantic` models for request/response schemas — don't pass raw dicts across layer boundaries.
- **No magic strings for mode/collection names** — use an `Enum` (`Mode.CHANAKYA`, `Mode.CRISIS`).
- **Every ingestion chunk carries metadata**: `{source, domain_tag, date_added, mode}` at minimum. Never store raw text without metadata — you'll need it for filtering and debugging retrieval quality later.
- **Prompts live in files, not code**: keep `chanakya_system.md` / `crisis_system.md` as separate markdown files, loaded at runtime. Makes prompt iteration a content change, not a deploy.
- **Log retrieval, not just generation**: for every query, log which chunks were retrieved (ids + scores) alongside the final response. Essential for debugging "why did it say that" later, especially for crisis advice where accuracy matters.
- **Fail loudly on empty retrieval**: if top-k returns nothing above a similarity threshold, don't silently let the LLM hallucinate — return a fallback ("I don't have enough precedent on this yet") or flag for human review.
- **Keep the two KBs genuinely separate at query time**: never let a Chanakya-mode query retrieve from `crisis_kb` or vice versa. Enforce this at the retriever level, not by trusting the prompt.

## Testing Expectations

- Unit tests for chunking, retrieval filtering, and mode-routing logic (pure functions, no API calls needed).
- A small "golden set" of ~15–20 query→expected-chunk pairs per KB to catch retrieval regressions when you change embeddings or chunk size.
- Don't test LLM output text verbatim (it's non-deterministic) — test that the *right chunks* were retrieved and the *right prompt/mode* was selected.

## What NOT to do

- Don't merge Chanakya and crisis content into one collection "for simplicity" — retrieval quality drops when unrelated content shares embedding space.
- Don't hardcode the LLM/embedding provider — wrap both behind a thin interface so swapping models later (once the company decides) is a config change, not a rewrite.
- Don't skip metadata tagging during ingestion to save time now — retrofitting tags onto thousands of chunks later is far more expensive.

## Current Status
- Tech stack: **not finalized** (org decision pending) — write provider-agnostic code.
- Content: sourcing Arthashastra/Chanakya Niti (public domain) for Chanakya KB; internal case history + researched public cases for crisis KB. Both still in progress.
