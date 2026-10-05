import { create } from 'zustand'
import { streamChat } from '../lib/api'
import type { ChatError, Conversation, FinalEvent, Message, Mode } from '../lib/types'
import { deriveTitle, newId, uid } from '../lib/util'
import { lstore, useUI } from './ui'

const CHATS_KEY = 'chanakya:chats'
const ACTIVE_KEY = 'chanakya:active'
const MAX_CONVERSATIONS = 100

/** Conversations live in this browser only (localStorage); the backend keeps no history. */
function loadConversations(): Conversation[] {
  try {
    const raw = JSON.parse(lstore.get(CHATS_KEY) ?? '[]') as unknown
    if (!Array.isArray(raw)) return []
    return (raw as Conversation[])
      .filter((c) => c && typeof c.id === 'string' && Array.isArray(c.messages) && (c.mode === 'chanakya' || c.mode === 'crisis'))
      .map((c) => ({ ...c, messages: c.messages.map((m) => ({ ...m, streaming: false })) }))
  } catch {
    return []
  }
}
const saveConversations = (list: Conversation[]) => lstore.set(CHATS_KEY, JSON.stringify(list.slice(0, MAX_CONVERSATIONS)))

interface ChatState {
  conversations: Conversation[]
  activeId: string | null
  messages: Message[]
  /** mode of the active chat, or the mode the next new chat will use */
  mode: Mode
  streaming: boolean
  setMode: (mode: Mode) => void
  select: (id: string) => void
  newChat: () => void
  send: (text: string) => Promise<void>
  regenerate: (messageUid: string) => Promise<void>
  /** re-run when the thread ends with an unanswered user message */
  retry: () => Promise<void>
  edit: (messageUid: string, text: string) => Promise<void>
  stop: () => void
  rename: (id: string, title: string) => void
  remove: (id: string) => void
}

// Module-level, not store state: both must flip synchronously, before React re-renders, to make double-send impossible.
let controller: AbortController | null = null
let busy = false
let flushNow: (() => void) | null = null

const rateLimited = () => {
  const b = useUI.getState().banner
  return b?.type === 'rate_limited' && b.until > Date.now()
}

export const useChat = create<ChatState>((set, get) => {
  const initial = loadConversations()
  const savedActive = lstore.get(ACTIVE_KEY)
  const active = initial.find((c) => c.id === savedActive)

  const patchMessage = (u: string, fn: (m: Message) => Message) =>
    set((s) => ({ messages: s.messages.map((m) => (m.uid === u ? fn(m) : m)) }))

  /** Copy the active thread into its stored conversation and persist. Empty in-flight placeholders are not stored. */
  const commit = () => {
    const { activeId, messages, mode, conversations } = get()
    if (!activeId) return
    const stored = messages.filter((m) => !(m.streaming && !m.content)).map((m) => ({ ...m, streaming: false }))
    const now = Date.now() / 1000
    const exists = conversations.some((c) => c.id === activeId)
    const next = exists
      ? conversations.map((c) => (c.id === activeId ? { ...c, messages: stored, updated_at: now } : c))
      : [{ id: activeId, title: deriveTitle(stored), mode, created_at: now, updated_at: now, messages: stored }, ...conversations]
    next.sort((a, b) => b.updated_at - a.updated_at)
    set({ conversations: next })
    saveConversations(next)
  }

  /** Run one generation for `history` (which must end with a user message). */
  async function run(history: Message[]) {
    const { activeId: convId, mode } = get()
    const question = history[history.length - 1]
    if (!convId || question?.role !== 'user') {
      busy = false
      return
    }
    busy = true
    const assistant: Message = { uid: uid(), role: 'assistant', content: '', streaming: true }
    set({ messages: [...history, assistant], streaming: true })
    commit()
    const ctrl = (controller = new AbortController())

    let text = ''
    let raf = 0
    let final: FinalEvent | null = null
    let error: ChatError | null = null
    const flush = () => {
      raf = 0
      patchMessage(assistant.uid, (m) => ({ ...m, content: text }))
    }
    flushNow = () => {
      if (raf) cancelAnimationFrame(raf)
      flush()
    }

    await streamChat(
      { message: question.content, mode, conversationId: convId },
      {
        onToken: (t) => {
          text += t
          if (useUI.getState().banner?.type === 'offline') useUI.getState().setBanner(null)
          if (!raf) raf = requestAnimationFrame(flush)
        },
        onFinal: (e) => {
          final = e
        },
        onError: (e) => {
          error = e
        },
      },
      ctrl.signal,
    )

    // stop() already finalised the message and released the lock
    if (ctrl.signal.aborted) return

    if (raf) cancelAnimationFrame(raf)
    flushNow = null
    const err = error as ChatError | null
    const fin = final as FinalEvent | null
    if (err?.kind === 'rate_limited') useUI.getState().setBanner({ type: 'rate_limited', until: Date.now() + (err.retryAfter ?? 5) * 1000 })
    else if (err?.kind === 'network') useUI.getState().setBanner({ type: 'offline' })
    patchMessage(assistant.uid, (m) => ({
      ...m,
      content: text,
      streaming: false,
      refused: fin?.refused || undefined,
      sources: fin?.sources?.length ? fin.sources : undefined,
      error: err ?? undefined,
    }))
    controller = null
    busy = false
    set({ streaming: false })
    commit()
  }

  return {
    conversations: initial,
    activeId: active?.id ?? null,
    messages: active?.messages ?? [],
    mode: active?.mode ?? 'chanakya',
    streaming: false,

    setMode: (mode) => {
      if (mode === get().mode) return
      get().stop()
      set({ mode, activeId: null, messages: [] })
      lstore.set(ACTIVE_KEY, '')
    },

    select: (id) => {
      if (id === get().activeId) return
      const c = get().conversations.find((x) => x.id === id)
      if (!c) return
      get().stop()
      set({ activeId: id, messages: c.messages.map((m) => ({ ...m, streaming: false })), mode: c.mode })
      lstore.set(ACTIVE_KEY, id)
    },

    newChat: () => {
      get().stop()
      set({ activeId: null, messages: [] })
      lstore.set(ACTIVE_KEY, '')
    },

    send: async (text) => {
      const t = text.trim()
      if (!t || busy || get().streaming || rateLimited()) return
      busy = true
      let id = get().activeId
      if (!id) {
        id = newId()
        set({ activeId: id })
        lstore.set(ACTIVE_KEY, id)
      }
      await run([...get().messages, { uid: uid(), role: 'user', content: t }])
    },

    regenerate: async (messageUid) => {
      const { messages, streaming } = get()
      const idx = messages.findIndex((m) => m.uid === messageUid)
      if (busy || streaming || rateLimited() || idx < 1 || messages[idx - 1]?.role !== 'user') return
      busy = true
      await run(messages.slice(0, idx))
    },

    retry: async () => {
      const { messages, streaming } = get()
      if (busy || streaming || rateLimited() || messages[messages.length - 1]?.role !== 'user') return
      busy = true
      await run(messages)
    },

    edit: async (messageUid, text) => {
      const { messages, streaming } = get()
      const idx = messages.findIndex((m) => m.uid === messageUid)
      if (busy || streaming || rateLimited() || idx < 0 || !text.trim()) return
      busy = true
      await run([...messages.slice(0, idx), { ...messages[idx]!, content: text.trim() }])
    },

    stop: () => {
      if (!controller) return
      flushNow?.()
      flushNow = null
      controller.abort()
      controller = null
      busy = false
      set((s) => ({ streaming: false, messages: s.messages.map((m) => (m.streaming ? { ...m, streaming: false, stopped: true } : m)) }))
      commit()
    },

    rename: (id, title) => {
      const t = title.trim()
      if (!t) return
      const next = get().conversations.map((c) => (c.id === id ? { ...c, title: t } : c))
      set({ conversations: next })
      saveConversations(next)
    },

    remove: (id) => {
      if (get().activeId === id) get().newChat()
      const next = get().conversations.filter((c) => c.id !== id)
      set({ conversations: next })
      saveConversations(next)
    },
  }
})
