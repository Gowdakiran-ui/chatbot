# TASK: React Chat Interface

## Context
Backend is fully done and live-verified: auth, rate limiting, ownership checks,
retrieval, floor refusal, groundedness flagging, truncation handling, disclaimer
enforcement — all tested against real DeepSeek V4 Pro output. This task is the first
thing a real client will actually see. It should surface what the backend already
does well (grounded, cited, honestly-refusing-when-appropriate) rather than hide it
behind a generic chat box.

Stack: React SPA, Vite, no heavy component library — plain CSS is fine, this doesn't
need to look like a design showcase, it needs to be clear and trustworthy.

Known backend characteristics this UI must be built around, not surprised by:
- **Latency is real**: median ~12.5s, average ~15.9s, tail to 30-40s on citation-dense
  crisis answers. A spinner alone will feel broken at that duration — needs a proper
  streaming-in-progress state (see Piece 3).
- **Refusals are fast** (~4s) and are a *feature*, not an error — the UI must not
  present a floor-refusal the same way it presents a network failure.
- Every response carries real structured metadata (mode, scores, `cited_chunk_ids`,
  `refused`, `truncated`) — use it, don't just render raw streamed text and discard
  the rest.

---

## Piece 1 — Auth
- Simple token-entry screen: paste the bearer token issued via
  `scripts/issue_token.py`, stored in `sessionStorage` (not `localStorage` —
  deliberate: clears on tab close, smaller exposure window for a pre-launch product
  with no revocation UI yet; document this as a conscious simplification, not an
  oversight, and flag proper session/cookie-based auth as a real follow-up once this
  goes past pilot).
- Every API call attaches `Authorization: Bearer <token>`.
- A 401 response at any point clears the stored token and returns to the entry
  screen with a clear "session expired or invalid" message — don't just fail silently
  on the next request.

## Piece 2 — Mode toggle
- Two-state toggle: Chanakya / Crisis Advisor, visually distinct (this is a real
  product differentiator, not a settings checkbox — crisis mode should look and feel
  more serious/urgent than the philosophy-advice mode).
- Switching modes starts a **new** conversation (new client-generated
  `conversation_id`, cleared message history) — modes query different collections
  with different framing; continuing one conversation across both would confuse the
  ownership/context model on the backend. Confirm this against `serving/conversations.py`'s
  actual ownership semantics before assuming, but this is the expected behavior.

## Piece 3 — Chat UI + streaming
- Standard chat layout: message history, input box with the same 4000-char limit as
  the backend (`MAX_MESSAGE_LENGTH`) enforced client-side too, with a live character
  counter as it approaches the limit — don't let a user type a long message and only
  discover the rejection after sending.
- Consume the `/chat` SSE stream: render `{"type":"token"}` events as they arrive
  (real streaming text, not a fake typing animation), handle the final
  `{"type":"final", ...}` event, handle `{"type":"error"}` distinctly from either.
- **Streaming-in-progress state**: since a floor-refusal returns in ~4s but a real
  answer can take 30+, show an immediate "thinking" indicator, then transition
  smoothly into streamed text the moment the first token arrives — the UI shouldn't
  look identical for the first 4 seconds regardless of which path it's on, since a
  user who's used to fast refusals shouldn't have to wonder if a slow real answer has
  hung.

## Piece 4 — Response states (this is the part that makes the backend's work visible)
- **Normal grounded answer**: render text, and below it a distinct "Sources" section
  listing `cited_chunk_ids` from the final event (raw chunk ids are fine for now —
  human-readable source labels are a real gap, worth flagging as follow-up, not
  solving in this task).
- **Refusal** (`refused: true`): visually distinct from both a normal answer and an
  error — not red/alarming, more like "here's an honest boundary." This is a trust
  feature; don't bury it in the same bubble style as everything else.
- **Truncated** (`truncated: true`): the truncation notice text is already part of the
  streamed content per the backend fix — but add a small UI affordance (e.g. a
  "this answer was cut short — ask a follow-up" chip) rather than relying on the user
  to notice the inline bracketed note.
- **Disclaimer** (crisis mode, always present in output per backend enforcement):
  style it as a persistent, slightly separated footer note on crisis-mode answers —
  it's supposed to be seen, not blend into the paragraph.
- Render answer text as sanitized markdown (headings/bold/lists are plausible model
  output) — use a safe renderer, never `dangerouslySetInnerHTML` on raw model output.

## Piece 5 — Errors and rate limiting
- 429 (rate limit): show actual retry-after countdown from the response header, not a
  generic "try again" — the backend already computes this correctly.
- 403 (conversation ownership): shouldn't normally happen from the UI's own flow since
  it always uses its own generated `conversation_id`s, but handle it gracefully
  (start a fresh conversation) rather than a raw error if it ever does.
- 413 (body too large) / 422 (validation): these should be prevented client-side by
  Piece 3's character limit, but handle the response gracefully as a backstop.
- Network failure / stream drop mid-response: show a clear "connection lost" state,
  don't leave a half-rendered answer looking like a complete one.

## Constraints
- Don't modify backend code — this is a pure frontend task consuming the existing
  `/chat` contract as-is.
- `ALLOWED_ORIGINS` on the backend needs this app's dev origin (e.g.
  `http://localhost:5173`) added before local testing will work at all — flag this
  explicitly in your report, since it's a one-line backend config change this task
  depends on but shouldn't itself make silently.
- Keep it simple: no state-management library needed for this scope, React's own
  state is enough. No component library needed — plain, clear CSS.
- Report back: screenshots or a clear description of each of the 4 response states
  from Piece 4 actually rendering against a real backend call (reuse the cheap
  known-good queries from prior tasks — e.g. the PNB/Nirav Modi query — no need for
  new live spend beyond a handful of confirmation calls).