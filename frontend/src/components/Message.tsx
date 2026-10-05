import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, Check, Copy, Info, Pencil, RotateCw, Scale, Scissors } from 'lucide-react'
import { MAX_MESSAGE_LENGTH, NOT_LEGAL_ADVICE_LINE } from '../lib/constants'
import type { Message as Msg } from '../lib/types'
import { copyText, splitAnswer } from '../lib/util'
import { useChat } from '../store/chat'
import { useUI } from '../store/ui'
import { Mark } from './Logo'
import { Markdown } from './Markdown'
import { SourceChips } from './Sources'
import { IconButton, useCopied } from './ui'

/** Kinds where sending the same message again can plausibly succeed. */
const RETRYABLE = new Set<string>(['network', 'server', 'model', 'rate_limited'])

function CopyButton({ text }: { text: string }) {
  const [copied, mark] = useCopied()
  return (
    <IconButton label={copied ? 'Copied' : 'Copy'} onClick={() => void copyText(text).then(mark)}>
      {copied ? <Check size={16} /> : <Copy size={16} />}
    </IconButton>
  )
}

/* ------------------------------------------------------------------ user */

function UserMessage({ m }: { m: Msg }) {
  const edit = useChat((s) => s.edit)
  const busy = useChat((s) => s.streaming)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(m.content)
  const ta = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!editing || !ta.current) return
    const el = ta.current
    el.focus()
    el.setSelectionRange(el.value.length, el.value.length)
  }, [editing])
  useEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`
  }, [draft, editing])

  const save = () => {
    if (!draft.trim()) return
    setEditing(false)
    if (draft.trim() !== m.content) void edit(m.uid, draft)
  }

  if (editing)
    return (
      <div className="anim-fade ml-auto w-full rounded-2xl border border-line bg-elevated p-3 shadow-soft">
        <textarea
          ref={ta}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="Edit message"
          maxLength={MAX_MESSAGE_LENGTH}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              save()
            }
            if (e.key === 'Escape') {
              e.stopPropagation()
              setEditing(false)
              setDraft(m.content)
            }
          }}
          className="block w-full resize-none bg-transparent leading-relaxed outline-none"
        />
        <div className="mt-2 flex justify-end gap-2">
          <button type="button" onClick={() => { setEditing(false); setDraft(m.content) }} className="rounded-lg px-3 py-1.5 text-sm text-muted transition-colors hover:bg-fg/[0.07] hover:text-fg">
            Cancel
          </button>
          <button type="button" onClick={save} disabled={!draft.trim()} className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-40">
            Save &amp; resend
          </button>
        </div>
      </div>
    )

  return (
    <div className="group anim-rise flex flex-col items-end gap-1.5">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-bubble px-4 py-2.5 [overflow-wrap:anywhere]">{m.content}</div>
      <div className="flex gap-0.5 opacity-0 transition-opacity duration-150 focus-within:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100">
        <CopyButton text={m.content} />
        <IconButton label="Edit message" onClick={() => { setDraft(m.content); setEditing(true) }} disabled={busy}>
          <Pencil size={16} />
        </IconButton>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------- assistant */

function AssistantMessage({ m, isLast }: { m: Msg; isLast: boolean }) {
  const regenerate = useChat((s) => s.regenerate)
  const busy = useChat((s) => s.streaming)
  const banner = useUI((s) => s.banner)
  const streaming = !!m.streaming
  const { body, truncated, disclaimer } = useMemo(() => splitAnswer(m.content), [m.content])
  const waiting = banner?.type === 'rate_limited'
  const retry = () => void regenerate(m.uid)

  return (
    <div className="anim-rise group flex gap-3 sm:gap-4">
      <div className="mt-0.5 hidden sm:block">
        <Mark size={28} />
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        {body &&
          (m.refused ? (
            <div role="note" className="flex items-start gap-3 rounded-card border border-line bg-surface px-4 py-3 text-[15px]">
              <Info size={18} className="mt-0.5 shrink-0 text-muted" aria-hidden="true" />
              <div className="md min-w-0 flex-1">
                <Markdown text={body} />
              </div>
            </div>
          ) : (
            <div className={`md ${streaming ? 'streaming' : ''}`}>
              <Markdown text={body} />
            </div>
          ))}
        {streaming && !body && <div className="streaming md empty" aria-label="Chanakya is writing" />}
        {!streaming && truncated && (
          <p role="note" className="flex items-start gap-2 rounded-lg bg-amber-500/10 px-3 py-2 text-[13px] leading-snug">
            <Scissors size={15} className="mt-px shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <span>This answer was cut short. Ask a follow-up for more detail.</span>
          </p>
        )}
        {!streaming && disclaimer && (
          <aside className="flex items-start gap-2.5 rounded-lg border border-line bg-fg/[0.04] px-3 py-2.5 text-[13px] leading-snug text-muted">
            <Scale size={15} className="mt-px shrink-0" aria-hidden="true" />
            <div>
              <span className="mb-0.5 block text-xs font-medium text-fg">Legal notice</span>
              {NOT_LEGAL_ADVICE_LINE}
            </div>
          </aside>
        )}
        {m.error && (
          <div role="alert" className="flex items-start gap-3 rounded-card border border-danger/30 bg-danger/[0.06] px-3.5 py-3 text-sm">
            <AlertCircle size={18} className="mt-0.5 shrink-0 text-danger" />
            <div className="min-w-0 flex-1 text-fg">{m.error.message}</div>
            {!busy && isLast && RETRYABLE.has(m.error.kind) && (
              <button
                type="button"
                onClick={retry}
                disabled={waiting}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-danger/30 px-2.5 py-1 text-xs text-danger transition-colors hover:bg-danger/10 disabled:opacity-40"
              >
                <RotateCw size={12} /> Retry
              </button>
            )}
          </div>
        )}
        {!streaming && !m.content && !m.error && (
          <p className="text-sm text-muted">{m.stopped ? 'Stopped before any response was generated.' : 'No response was generated.'}</p>
        )}
        {!streaming && m.stopped && m.content && <p className="text-xs text-muted">Generation stopped.</p>}
        {!streaming && m.sources && m.sources.length > 0 && <SourceChips sources={m.sources} />}
        {!streaming && (
          <div className={`-ml-1.5 flex gap-0.5 transition-opacity duration-150 focus-within:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100 ${isLast ? 'opacity-100' : 'opacity-0'}`}>
            {body && <CopyButton text={m.content} />}
            <IconButton label="Regenerate" onClick={retry} disabled={busy || waiting}>
              <RotateCw size={16} />
            </IconButton>
          </div>
        )}
      </div>
    </div>
  )
}

export const MessageView = memo(function MessageView({ m, isLast }: { m: Msg; isLast: boolean }) {
  return m.role === 'user' ? <UserMessage m={m} /> : <AssistantMessage m={m} isLast={isLast} />
})
