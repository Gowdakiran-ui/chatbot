import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Square } from 'lucide-react'
import { MAX_MESSAGE_LENGTH } from '../lib/constants'
import { MODES, SINGLE_TURN_DETAIL, SINGLE_TURN_HINT } from '../lib/modes'
import { useChat } from '../store/chat'
import { ModePicker } from './ModePicker'
import { useUI } from '../store/ui'

export function Composer({ autoFocus = true }: { autoFocus?: boolean }) {
  const send = useChat((s) => s.send)
  const stop = useChat((s) => s.stop)
  const streaming = useChat((s) => s.streaming)
  const mode = useChat((s) => s.mode)
  const waiting = useUI((s) => s.banner?.type === 'rate_limited')
  const [text, setText] = useState('')
  const ta = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (autoFocus) ta.current?.focus()
  }, [autoFocus])

  // auto-grow up to ~8 lines
  useEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 8 * 26 + 4)}px`
  }, [text])

  const canSend = text.trim().length > 0 && !waiting
  const nearLimit = text.length > MAX_MESSAGE_LENGTH * 0.9

  const submit = () => {
    if (!canSend || streaming) return
    const t = text
    setText('')
    void send(t)
    ta.current?.focus()
  }

  return (
    <div className="rounded-composer border border-line bg-elevated shadow-soft transition-[border-color,box-shadow] duration-200 focus-within:border-fg/25">
      <textarea
        id="composer-input"
        ref={ta}
        value={text}
        rows={1}
        maxLength={MAX_MESSAGE_LENGTH}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            submit()
          }
        }}
        aria-label={`Message ${MODES[mode].label}`}
        placeholder={MODES[mode].placeholder}
        className="block max-h-[212px] w-full resize-none bg-transparent px-5 pb-1 pt-4 text-[16px] leading-[26px] outline-none placeholder:text-muted"
      />
      <div className="flex items-center gap-1 px-2.5 pb-2.5 pt-1">
        <p className="min-w-0 flex-1 truncate px-2.5 text-xs text-muted" title={SINGLE_TURN_DETAIL}>
          {nearLimit ? `${text.length} / ${MAX_MESSAGE_LENGTH}` : SINGLE_TURN_HINT}
        </p>
        <ModePicker />
        {streaming ? (
          <button
            type="button"
            onClick={stop}
            aria-label="Stop generating"
            title="Stop (Esc)"
            className="ml-1 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-fg text-bg transition-opacity duration-150 hover:opacity-85"
          >
            <Square size={13} fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            aria-label="Send message"
            title={waiting ? 'Please wait for the rate limit to clear' : 'Send (Enter)'}
            className="ml-1 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-accent-fg transition-[opacity,transform] duration-150 hover:opacity-90 active:scale-95 disabled:bg-fg/15 disabled:text-muted"
          >
            <ArrowUp size={18} strokeWidth={2.4} />
          </button>
        )}
      </div>
    </div>
  )
}
