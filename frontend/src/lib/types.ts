export type Mode = 'chanakya' | 'crisis'

/** One retrieved chunk cited by an answer (backend: `sources` on the `final` SSE event). */
export interface SourceRef {
  id: string
  label: string
  snippet: string
  /** chanakya: { domain_tags: string[] }; crisis: { crisis_type, industry, resolution_status } */
  metadata: Record<string, unknown>
}

export type ErrorKind = 'network' | 'rate_limited' | 'forbidden' | 'too_large' | 'validation' | 'unauthorized' | 'server' | 'model'

export interface ChatError {
  kind: ErrorKind
  message: string
  /** seconds, only for rate_limited */
  retryAfter?: number
}

export interface Message {
  /** stable React key, never changes */
  uid: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  /** generation was stopped by the user */
  stopped?: boolean
  /** retrieval floor refusal: not enough precedent; calm notice, not an error */
  refused?: boolean
  error?: ChatError
  sources?: SourceRef[]
}

export interface Conversation {
  id: string
  title: string
  mode: Mode
  created_at: number
  updated_at: number
  messages: Message[]
}

export interface FinalEvent {
  mode: Mode
  refused: boolean
  cited_chunk_ids: string[]
  conversation_id: string | null
  sources?: SourceRef[]
}

/** Wire format of serving/app.py: `data: {"type": ...}` frames. */
export type ChatEvent =
  | { type: 'token'; text: string }
  | ({ type: 'final' } & FinalEvent)
  | { type: 'error'; message?: string }
