import { useAuth } from '../store/auth'
import type { ChatError, ChatEvent, FinalEvent, Mode } from './types'

/** Relative `/api` by default (same-origin behind the reverse proxy); override with VITE_API_BASE_URL. */
const BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api').replace(/\/$/, '')

export interface ChatRequest {
  message: string
  mode: Mode
  conversationId: string
}

export interface StreamHandlers {
  onToken: (text: string) => void
  onFinal: (e: FinalEvent) => void
  onError: (e: ChatError) => void
}

async function classify(res: Response): Promise<ChatError> {
  switch (res.status) {
    case 401:
      return { kind: 'unauthorized', message: 'Your session expired or the token was invalid. Please sign in again.' }
    case 403:
      return { kind: 'forbidden', message: 'This conversation is no longer available. Start a new chat to continue.' }
    case 413:
      return { kind: 'too_large', message: 'That message is too large to send. Please shorten it and try again.' }
    case 422:
      return { kind: 'validation', message: 'That message was rejected as invalid. Please edit it and try again.' }
    case 429: {
      const retryAfter = parseInt(res.headers.get('Retry-After') ?? '', 10)
      return {
        kind: 'rate_limited',
        message: 'Too many requests right now.',
        retryAfter: Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : 5,
      }
    }
  }
  let message = `The server returned an error (${res.status}).`
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') message = body.detail
  } catch {
    /* not JSON */
  }
  return { kind: 'server', message }
}

export function parseFrame(frame: string): ChatEvent | null {
  const line = frame.split('\n').find((l) => l.startsWith('data:'))
  if (!line) return null
  try {
    const e = JSON.parse(line.slice(5).trim()) as ChatEvent
    return e && typeof e === 'object' && 'type' in e ? e : null
  } catch {
    return null
  }
}

/**
 * POST /chat and read the SSE stream (`data: {...}` frames separated by a blank line). Not EventSource: it
 * cannot send a POST body or an Authorization header. Always resolves; outcomes are reported through the
 * handlers. A deliberate abort reports nothing.
 */
export async function streamChat(req: ChatRequest, h: StreamHandlers, signal: AbortSignal): Promise<void> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = useAuth.getState().token
  if (token) headers.Authorization = `Bearer ${token}`

  let res: Response
  try {
    res = await fetch(`${BASE}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message: req.message, mode: req.mode, conversation_id: req.conversationId }),
      signal,
    })
  } catch {
    if (signal.aborted) return
    h.onError({ kind: 'network', message: 'Could not reach the server. Check your connection and try again.' })
    return
  }

  if (!res.ok || !res.body) {
    const err = await classify(res)
    if (err.kind === 'unauthorized') useAuth.getState().expire()
    h.onError(err)
    return
  }

  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  let finished = false
  let failed = false
  const dispatch = (frame: string) => {
    const e = parseFrame(frame)
    if (!e) return
    if (e.type === 'token') h.onToken(e.text)
    else if (e.type === 'final') {
      finished = true
      h.onFinal(e)
    } else if (e.type === 'error') {
      failed = true
      h.onError({ kind: 'model', message: e.message || 'The model returned an error.' })
    }
  }
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      let i: number
      while ((i = buf.indexOf('\n\n')) >= 0) {
        dispatch(buf.slice(0, i))
        buf = buf.slice(i + 2)
      }
    }
    if (buf.trim()) dispatch(buf)
  } catch {
    if (signal.aborted) return
    if (!failed) h.onError({ kind: 'network', message: 'The connection was lost while the answer was streaming.' })
    return
  }
  if (!finished && !failed && !signal.aborted) {
    h.onError({ kind: 'network', message: 'The connection was interrupted before the answer finished.' })
  }
}
