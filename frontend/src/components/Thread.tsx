import { useEffect, useRef } from 'react'
import { ArrowDown, RotateCw } from 'lucide-react'
import { useAutoScroll } from '../hooks/useAutoScroll'
import { useChat } from '../store/chat'
import { Composer } from './Composer'
import { MessageView } from './Message'

export function Thread() {
  const messages = useChat((s) => s.messages)
  const activeId = useChat((s) => s.activeId)
  const streaming = useChat((s) => s.streaming)
  const retry = useChat((s) => s.retry)
  const unanswered = !streaming && messages.length > 0 && messages[messages.length - 1]!.role === 'user'
  const { scrollRef, contentRef, atBottom, onScroll, scrollToBottom } = useAutoScroll(activeId)

  // when the user sends a message, jump to it even if they had scrolled up
  const lastUserUid = useRef<string | undefined>(undefined)
  useEffect(() => {
    const last = [...messages].reverse().find((m) => m.role === 'user')
    if (last && last.uid !== lastUserUid.current) {
      if (lastUserUid.current !== undefined) scrollToBottom(true)
      lastUserUid.current = last.uid
    }
  }, [messages, scrollToBottom])

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} onScroll={onScroll} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div
          ref={contentRef}
          role="log"
          aria-live="polite"
          aria-busy={streaming}
          aria-label="Conversation"
          className="mx-auto w-full max-w-[768px] space-y-7 px-4 pb-10 pt-6"
        >
          {messages.map((m, i) => (
            <MessageView key={m.uid} m={m} isLast={i === messages.length - 1} />
          ))}
          {unanswered && (
            <div className="anim-fade flex items-center gap-3 text-sm text-muted">
              <span>No reply was saved for this message.</span>
              <button
                type="button"
                onClick={() => void retry()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-xs text-fg transition-colors hover:border-accent/60"
              >
                <RotateCw size={12} /> Retry
              </button>
            </div>
          )}
        </div>
      </div>
      <div className="relative shrink-0 px-4 pb-3 pt-1">
        <div className="pointer-events-none absolute inset-x-0 -top-8 h-8 bg-gradient-to-t from-bg to-transparent" />
        {!atBottom && (
          <button
            type="button"
            onClick={() => scrollToBottom(true)}
            aria-label="Scroll to bottom"
            className="anim-pop absolute -top-12 left-1/2 z-10 inline-flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-line bg-elevated px-3 py-1.5 text-xs text-muted shadow-soft transition-colors hover:text-fg"
          >
            <ArrowDown size={14} /> {streaming ? 'Following answer' : 'Scroll to bottom'}
          </button>
        )}
        <div className="mx-auto w-full max-w-[768px]">
          <Composer />
          <p className="mt-2 text-center text-xs text-muted">Chanakya can make mistakes. Check important points against the sources.</p>
        </div>
      </div>
    </div>
  )
}
