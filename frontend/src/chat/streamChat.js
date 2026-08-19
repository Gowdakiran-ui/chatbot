import { apiFetch, ApiError } from '../api/client';

// Not EventSource — EventSource can't send a POST body or an Authorization
// header, and /chat needs both. Reads the raw SSE stream (data: {...}\n\n)
// straight off fetch's ReadableStream instead, matching serving/app.py's
// `_sse()` framing exactly.
//
// onError receives a structured { kind, message, retryAfter? } rather than a
// bare string — Piece 5 gives 429/403/413/422/network each their own
// handling in useChat.js, not one generic "something went wrong" bucket.
export async function streamChat({ message, mode, conversationId, signal }, { onToken, onFinal, onError }) {
  let response;
  try {
    response = await apiFetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, mode, conversation_id: conversationId }),
      signal,
    });
  } catch (err) {
    // A deliberate abort (e.g. the user switched modes mid-stream) is not a
    // failure worth surfacing — the message it belonged to is already gone.
    if (err.name === 'AbortError') return;
    // apiFetch already cleared the token + flagged sessionExpired on a 401;
    // any other network-level failure (server unreachable, DNS, etc.) lands
    // here too.
    onError({
      kind: 'network',
      message: err instanceof ApiError ? err.message : 'Connection lost — could not reach the server.',
    });
    return;
  }

  if (!response.ok || !response.body) {
    onError(await classifyErrorResponse(response));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sepIndex;
      while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        dispatchEvent(rawEvent, { onToken, onFinal, onError });
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') return;
    onError({ kind: 'network', message: 'Connection lost while streaming the response.' });
  }
}

async function classifyErrorResponse(response) {
  const { status } = response;

  if (status === 429) {
    // Both 429 sources (serving/app.py's per-client rate limiter and the
    // generation-concurrency cap) set this header with the same semantics —
    // one code path covers both.
    const retryAfter = parseInt(response.headers.get('Retry-After'), 10);
    return {
      kind: 'rate_limited',
      message: 'Rate limit exceeded.',
      retryAfter: Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : 5,
    };
  }

  if (status === 403) {
    return { kind: 'forbidden', message: 'This conversation is no longer available.' };
  }

  if (status === 413) {
    return { kind: 'too_large', message: 'That message is too large to send.' };
  }

  if (status === 422) {
    // FastAPI's validation `detail` is a list of error objects, not a
    // string — not worth surfacing raw Pydantic internals to the user.
    return { kind: 'validation', message: 'That message was rejected as invalid.' };
  }

  let detail = `Request failed (status ${status})`;
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') detail = body.detail;
  } catch {
    // body wasn't JSON (or already consumed) — keep the generic detail.
  }
  return { kind: 'server', message: detail };
}

function dispatchEvent(rawEvent, { onToken, onFinal, onError }) {
  const dataLine = rawEvent.split('\n').find((line) => line.startsWith('data:'));
  if (!dataLine) return;

  const jsonText = dataLine.slice(5).trim();
  if (!jsonText) return;

  let event;
  try {
    event = JSON.parse(jsonText);
  } catch {
    return;
  }

  if (event.type === 'token') {
    onToken(event.text);
  } else if (event.type === 'final') {
    onFinal(event);
  } else if (event.type === 'error') {
    onError({ kind: 'model', message: event.message || 'The model returned an error.' });
  }
}
