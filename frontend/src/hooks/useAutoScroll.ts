import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Follows the bottom of a scroll container while content grows (streaming), stops following as soon as the
 * user scrolls up, and exposes `atBottom` for a "scroll to bottom" pill.
 */
export function useAutoScroll(resetKey: unknown) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const [atBottom, setAtBottom] = useState(true)

  const scrollToBottom = useCallback((smooth = false) => {
    const el = scrollRef.current
    if (!el) return
    stick.current = true
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
    setAtBottom(true)
  }, [])

  const onScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight
    stick.current = dist < 64
    setAtBottom(dist < 120)
  }, [])

  useEffect(() => {
    const content = contentRef.current
    if (!content) return
    const ro = new ResizeObserver(() => {
      const el = scrollRef.current
      if (el && stick.current) el.scrollTop = el.scrollHeight
      else onScroll()
    })
    ro.observe(content)
    return () => ro.disconnect()
  }, [onScroll])

  // a different conversation starts pinned to the bottom
  useEffect(() => {
    stick.current = true
    requestAnimationFrame(() => scrollToBottom())
  }, [resetKey, scrollToBottom])

  return { scrollRef, contentRef, atBottom, onScroll, scrollToBottom }
}
