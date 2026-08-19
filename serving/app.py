"""Piece 6 (serving) + Piece 2 (security/auth hardening) — POST /chat FastAPI endpoint.

Wires Pieces 1-5 of the serving task together: resolve mode -> retrieve+expand ->
floor check -> build prompt -> generate -> stream to the client as SSE, ending
with a final structured payload (mode, retrieval scores, cited chunk ids).

requires_disclaimer (ModeConfig) is enforced here in code, not left to prompt
compliance: if a crisis-mode response's full generated text doesn't already
contain the not-legal-advice line, it is appended before the turn ends.

Auth + rate limiting (security/auth hardening task):
  - Piece 1: every request resolves to a ClientIdentity via get_current_client, or
    401s — no anonymous fallback.
  - Piece 2: a per-client request-rate limit is enforced before retrieval runs at
    all, and a separate global cap on in-flight *generation* calls is enforced
    right before a generation call is made. Both need to raise a real HTTP 429
    (with Retry-After), which is only possible *before* a StreamingResponse is
    constructed — once streaming has started, the status code is already
    committed. That's why retrieval + the floor check happen synchronously in
    chat() itself rather than inside the streamed generator: it's the only point
    where a floor pass/refusal decision AND a clean pre-generation 429 are both
    still possible. This changes *where* retrieve_context()/check_floor() are
    called from, not what they do — same functions, same outcomes.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from providers.base import GenerationProvider
from providers.openrouter import OpenRouterProvider
from serving.auth import ClientIdentity, get_current_client
from serving.config import (
    ALLOWED_ORIGINS,
    AUTH_DISABLED,
    GENERATION_CONCURRENCY_LIMIT,
    GENERATION_RETRY_AFTER_SECONDS,
    MAX_BODY_BYTES,
    MAX_MESSAGE_LENGTH,
    RATE_LIMIT_REQUESTS_PER_MINUTE,
    RATE_LIMIT_WINDOW_SECONDS,
)
from serving.conversations import ConversationOwnershipStore
from serving.disclaimer import NOT_LEGAL_ADVICE_LINE
from serving.floor import FloorCheckResult, check_floor, refusal_text_for
from serving.groundedness_check import check_groundedness
from serving.injection_check import check_for_injection
from serving.middleware import BodySizeLimitMiddleware
from serving.mode_config import MODE_CONFIG, Mode
from serving.prompt import build_prompt
from serving.rate_limit import GenerationConcurrencyLimiter, InMemoryTokenBucketLimiter
from serving.retrieval import RetrievalResult, retrieve_context
from serving.secrets import redact_secrets

logger = logging.getLogger("serving.app")

# Discovered during the empty-response/latency investigation (2026-08-18):
# nothing here or in uvicorn's own startup ever raised the root logger above
# its WARNING default, so every INFO-level chat_turn line — mode, retrieval
# scores, finish-reason-derived truncated flag, cited chunks, latency — was
# silently never emitted to any sink in real usage. Only WARNING+ records
# (groundedness_flagged, generation_truncated) ever reached uvicorn's console,
# and only via Python's logging.lastResort fallback, not real configuration.
# Configured explicitly so real/manual-testing runs actually produce the
# evidence this project's debugging standard has assumed was there all along.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

if AUTH_DISABLED:
    # Deliberately a raw print(), not a log line — a log line can be filtered,
    # redirected, or scrolled past silently. This flag being left on by
    # accident in a real deployment is the one real risk in the whole
    # team-review-prep task; the warning is built to be impossible to miss on
    # the console at startup, not just discoverable if you go looking.
    #
    # ASCII-only deliberately: a warning-sign emoji here would crash startup
    # outright on a plain Windows console (cp1252 can't encode it) -- the one
    # time this warning must never fail to print is exactly when
    # AUTH_DISABLED is true.
    _WARNING_TEXT = "AUTH DISABLED -- INTERNAL REVIEW MODE, DO NOT DEPLOY LIKE THIS"
    _BOX_WIDTH = len(_WARNING_TEXT) + 8
    print(
        "\n"
        + ("!" * _BOX_WIDTH) + "\n"
        + "!!" + " " * (_BOX_WIDTH - 4) + "!!\n"
        + "!!  " + _WARNING_TEXT + "  !!\n"
        + "!!" + " " * (_BOX_WIDTH - 4) + "!!\n"
        + ("!" * _BOX_WIDTH) + "\n"
    )

app = FastAPI()

# Explicit allowlist, config-driven, never "*" — see serving/config.py.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)

_provider: GenerationProvider | None = None


def get_provider() -> GenerationProvider:
    """Lazily constructed so importing this module (e.g. for tests) doesn't
    require an OpenRouter API key to be set — only actually calling /chat does."""
    global _provider
    if _provider is None:
        _provider = OpenRouterProvider()
    return _provider


_client_rate_limiter = InMemoryTokenBucketLimiter(RATE_LIMIT_REQUESTS_PER_MINUTE, RATE_LIMIT_WINDOW_SECONDS)
_generation_concurrency = GenerationConcurrencyLimiter(GENERATION_CONCURRENCY_LIMIT)


def get_client_rate_limiter() -> InMemoryTokenBucketLimiter:
    return _client_rate_limiter


def get_generation_concurrency_limiter() -> GenerationConcurrencyLimiter:
    return _generation_concurrency


def enforce_rate_limit(
    client: ClientIdentity = Depends(get_current_client),
    limiter: InMemoryTokenBucketLimiter = Depends(get_client_rate_limiter),
) -> ClientIdentity:
    """Runs as a FastAPI dependency, before the route body (and therefore before
    retrieval) executes — a rate-limited request never reaches Qdrant."""
    allowed, retry_after = limiter.allow(client.client_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, int(retry_after) + 1))},
        )
    return client


_conversation_store = ConversationOwnershipStore()


def get_conversation_store() -> ConversationOwnershipStore:
    return _conversation_store


# Allows normal whitespace (space, tab, newline, CR) but rejects other C0 control
# characters and DEL — these have no legitimate place in a chat message and are a
# common smuggling/obfuscation vector.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    mode: Mode
    conversation_id: str | None = None

    @field_validator("message")
    @classmethod
    def _validate_message_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        if _CONTROL_CHAR_RE.search(value):
            raise ValueError("message contains disallowed control characters")
        return value


def enforce_conversation_ownership(
    request: ChatRequest,
    client: ClientIdentity = Depends(enforce_rate_limit),
    store: ConversationOwnershipStore = Depends(get_conversation_store),
) -> ClientIdentity:
    """A conversation_id is claimed by whichever client first uses it; every
    later request carrying that id must come from the same client. Runs as a
    dependency (before retrieval) for the same reason enforce_rate_limit does —
    an ownership violation shouldn't cost a Qdrant query either."""
    if request.conversation_id is not None:
        allowed = store.check_and_claim(request.conversation_id, client.client_id)
        if not allowed:
            raise HTTPException(status_code=403, detail="conversation_id does not belong to this client")
    return client


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


# Generation-quality fixes task, Fix 1: appended instead of ending on a cut-off
# sentence when OpenRouter's finish_reason reports the response was cut off by
# max_tokens. Deliberately short and honest, not a generic error.
TRUNCATION_NOTICE = "\n\n[Response truncated — ask a follow-up for more detail.]"


def _stream_refusal(
    request: ChatRequest, client: ClientIdentity, check: FloorCheckResult, start: float, flagged: bool
) -> Generator[str, None, None]:
    yield _sse({"type": "token", "text": refusal_text_for(request.mode)})
    latency = time.monotonic() - start
    logger.info(
        "chat_turn client_id=%s mode=%s query=%r path=refusal top_score=%.4f top_dense_score=%.4f "
        "latency=%.3f flagged=%s cited=[]",
        client.client_id,
        request.mode.value,
        request.message,
        check.top_score,
        check.top_dense_score,
        latency,
        flagged,
    )
    yield _sse(
        {
            "type": "final",
            "mode": request.mode.value,
            "refused": True,
            "top_score": check.top_score,
            "top_dense_score": check.top_dense_score,
            "cited_chunk_ids": [],
            "conversation_id": request.conversation_id,
        }
    )


class _GenerationFailed(Exception):
    """Signals that _attempt_generation already logged and yielded an SSE
    error event for this attempt — the caller just needs to stop, not handle
    the exception itself."""


def _attempt_generation(
    client: ClientIdentity,
    request: ChatRequest,
    provider: GenerationProvider,
    prompt: str,
    system: str,
    max_tokens: int,
) -> Generator[str, None, str]:
    """Runs one provider.generate() call, yielding SSE token events live as
    they arrive, and returns the concatenated text via `yield from`'s return
    value. Shared by the initial attempt and the single empty-response retry
    below so their error handling can't drift apart."""
    parts: list[str] = []
    try:
        for token in provider.generate(prompt, system, stream=True, max_tokens=max_tokens):
            parts.append(token)
            yield _sse({"type": "token", "text": token})
    except Exception as exc:
        # Belt and suspenders: no code path should embed a credential in an
        # exception message in the first place (see serving/secrets.py's
        # docstring), but redact defensively before this reaches a log line
        # or the client anyway.
        safe_message = redact_secrets(str(exc))
        logger.error(
            "chat_turn client_id=%s mode=%s query=%r path=generation_error error=%s",
            client.client_id,
            request.mode.value,
            request.message,
            safe_message,
        )
        yield _sse({"type": "error", "message": safe_message})
        raise _GenerationFailed from exc
    return "".join(parts)


def _stream_generation(
    request: ChatRequest,
    client: ClientIdentity,
    provider: GenerationProvider,
    result: RetrievalResult,
    start: float,
    flagged: bool,
) -> Generator[str, None, None]:
    config = MODE_CONFIG[request.mode]
    try:
        system = config.system_prompt_path.read_text(encoding="utf-8")
        prompt = build_prompt(request.message, result)

        try:
            full_text = yield from _attempt_generation(client, request, provider, prompt, system, config.max_tokens)
        except _GenerationFailed:
            return

        # Empty-response investigation (2026-08-18): real usage surfaced an
        # occasional fully-empty completion — finish_reason == "stop" (never
        # "length", which is truncation's own signal, handled separately
        # below), no exception raised (that path is handled above), reasoning
        # confirmed disabled on every real call site. Most consistent with an
        # occasional degenerate completion from one of the backend providers
        # OpenRouter routes this model across, not an application bug — see
        # this task's report for the live-log evidence. Nothing has been
        # yielded to the client yet if full_text is empty (the loop above
        # only yields once a token actually arrives), so one silent retry
        # here is safe: it cannot produce duplicate or out-of-order content.
        if not full_text.strip() and getattr(provider, "last_finish_reason", None) != "length":
            logger.warning(
                "empty_generation_retry client_id=%s mode=%s query=%r finish_reason=%s",
                client.client_id,
                request.mode.value,
                request.message,
                getattr(provider, "last_finish_reason", None),
            )
            try:
                full_text = yield from _attempt_generation(
                    client, request, provider, prompt, system, config.max_tokens
                )
            except _GenerationFailed:
                return
            logger.warning(
                "empty_generation_retry_result client_id=%s mode=%s query=%r retry_output_chars=%d "
                "retry_finish_reason=%s",
                client.client_id,
                request.mode.value,
                request.message,
                len(full_text),
                getattr(provider, "last_finish_reason", None),
            )

        # Detection only — never blocks or alters what was already streamed to
        # the client, same philosophy as the injection check above. Checked
        # against the model's raw output only (before any of our own
        # truncation-notice/disclaimer text is appended below), so those
        # insertions can't themselves trip the check. Includes each chunk's
        # chunk_id (with underscores as spaces) alongside its body text, since
        # build_prompt() shows the model a "[chunk_id]" header per chunk and a
        # citation can be legitimately derived from that alone.
        groundedness_context = [chunk.text for chunk in result.chunks] + [
            chunk.chunk_id.replace("_", " ") for chunk in result.chunks
        ]
        groundedness = check_groundedness(full_text, groundedness_context, query=request.message)
        if groundedness.flagged:
            logger.warning(
                "groundedness_flagged client_id=%s mode=%s query=%r flagged_terms=%s answer=%r",
                client.client_id,
                request.mode.value,
                request.message,
                groundedness.flagged_terms,
                full_text,
            )

        # Fix 1: detect truncation directly from OpenRouter's finish_reason
        # rather than guessing from content. "length" means max_tokens cut the
        # response off mid-generation — even at crisis mode's higher 1400 cap,
        # an unusually citation-dense answer can still hit it.
        truncated = getattr(provider, "last_finish_reason", None) == "length"
        # Computed unconditionally, not just on the truncated path — the
        # empty-response/latency investigation (2026-08-18) needs output_tokens
        # on every call (to correlate against latency, Piece 2) and on
        # near-empty non-truncated completions (Piece 1), not only truncated ones.
        output_tokens = provider.usage_log[-1]["output_tokens"] if getattr(provider, "usage_log", None) else None
        if truncated:
            yield _sse({"type": "token", "text": TRUNCATION_NOTICE})
            full_text += TRUNCATION_NOTICE
            logger.warning(
                "generation_truncated client_id=%s mode=%s query=%r max_tokens=%d output_tokens=%s",
                client.client_id,
                request.mode.value,
                request.message,
                config.max_tokens,
                output_tokens,
            )

        if config.requires_disclaimer and NOT_LEGAL_ADVICE_LINE not in full_text:
            # Fires on truncation just as much as on plain omission — this check
            # only cares whether the disclaimer text is present in the final
            # full_text, not why it's missing.
            addendum = f"\n\n{NOT_LEGAL_ADVICE_LINE}"
            yield _sse({"type": "token", "text": addendum})
            full_text += addendum

        latency = time.monotonic() - start
        cited_chunk_ids = [chunk.chunk_id for chunk in result.chunks]
        logger.info(
            "chat_turn client_id=%s mode=%s query=%r path=generation top_score=%.4f top_dense_score=%.4f "
            "latency=%.3f flagged=%s groundedness_flagged=%s truncated=%s finish_reason=%s output_tokens=%s "
            "output_chars=%d cited=%s",
            client.client_id,
            request.mode.value,
            request.message,
            result.top_score,
            result.top_dense_score,
            latency,
            flagged,
            groundedness.flagged,
            truncated,
            getattr(provider, "last_finish_reason", None),
            output_tokens,
            len(full_text),
            cited_chunk_ids,
        )
        yield _sse(
            {
                "type": "final",
                "mode": request.mode.value,
                "refused": False,
                "top_score": result.top_score,
                "top_dense_score": result.top_dense_score,
                "cited_chunk_ids": cited_chunk_ids,
                "conversation_id": request.conversation_id,
            }
        )
    finally:
        # Released here, once streaming actually ends, rather than right after
        # provider.generate() returns an iterator — the slot must stay held for
        # the full duration a generation call is in flight, which for a streamed
        # response is until the last token (or error) has been produced.
        _generation_concurrency.release()


@app.post("/chat")
def chat(
    request: ChatRequest,
    provider: GenerationProvider = Depends(get_provider),
    client: ClientIdentity = Depends(enforce_conversation_ownership),
    generation_limiter: GenerationConcurrencyLimiter = Depends(get_generation_concurrency_limiter),
) -> StreamingResponse:
    start = time.monotonic()
    config = MODE_CONFIG[request.mode]

    # Detection only — never blocks or alters the message, see injection_check.py.
    # Logged immediately (with the full message) as its own review-able event,
    # and also carried into the per-turn chat_turn log line below.
    flagged = check_for_injection(request.message)
    if flagged:
        logger.warning(
            "prompt_injection_flagged client_id=%s mode=%s message=%r",
            client.client_id,
            request.mode.value,
            request.message,
        )

    result = retrieve_context(request.message, config, request.mode)
    check = check_floor(result, config)

    if not check.passed:
        return StreamingResponse(
            _stream_refusal(request, client, check, start, flagged), media_type="text/event-stream"
        )

    if not generation_limiter.try_acquire():
        raise HTTPException(
            status_code=429,
            detail="Server is at capacity for generation requests, try again shortly",
            headers={"Retry-After": str(GENERATION_RETRY_AFTER_SECONDS)},
        )

    return StreamingResponse(
        _stream_generation(request, client, provider, result, start, flagged), media_type="text/event-stream"
    )
