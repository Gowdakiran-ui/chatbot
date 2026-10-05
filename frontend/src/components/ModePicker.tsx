import { useState, type KeyboardEvent } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { MODES, MODE_ORDER } from '../lib/modes'
import { useChat } from '../store/chat'
import { useDismiss } from './ui'

/** Mode switch that lives next to the send button, like a model picker. Switching starts a new chat. */
export function ModePicker() {
  const mode = useChat((s) => s.mode)
  const setMode = useChat((s) => s.setMode)
  const [open, setOpen] = useState(false)
  const ref = useDismiss<HTMLDivElement>(open, () => setOpen(false))

  const choose = (m: (typeof MODE_ORDER)[number]) => {
    setOpen(false)
    setMode(m)
    requestAnimationFrame(() => document.getElementById('composer-input')?.focus())
  }

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const items = [...(ref.current?.querySelectorAll<HTMLElement>('[role=option]') ?? [])]
      const i = items.indexOf(document.activeElement as HTMLElement)
      items[(i + (e.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length]?.focus()
    }
  }

  return (
    <div ref={ref} className="relative min-w-0" onKeyDown={onKey}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Mode: ${MODES[mode].label}`}
        title="Switch mode (starts a new chat)"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex h-9 max-w-[12rem] items-center gap-1.5 rounded-xl px-2.5 text-[13px] text-muted transition-colors duration-150 hover:bg-fg/[0.07] hover:text-fg sm:max-w-[16rem]"
      >
        <span className="truncate">{MODES[mode].label}</span>
        <ChevronDown size={14} className={`shrink-0 transition-transform duration-150 ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      {open && (
        <div
          role="listbox"
          aria-label="Mode"
          className="anim-pop absolute bottom-full right-0 z-30 mb-2 w-[min(18rem,calc(100vw-2rem))] rounded-card border border-line bg-elevated p-1 shadow-pop"
        >
          {MODE_ORDER.map((m) => (
            <button
              key={m}
              type="button"
              role="option"
              aria-selected={mode === m}
              onClick={() => choose(m)}
              className="flex w-full items-start gap-2.5 rounded-lg px-3 py-2 text-left transition-colors duration-150 hover:bg-fg/[0.07]"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{MODES[m].label}</span>
                <span className="mt-0.5 block text-xs leading-snug text-muted">{MODES[m].blurb}</span>
              </span>
              {mode === m && <Check size={16} className="mt-0.5 shrink-0 text-accent" aria-hidden="true" />}
            </button>
          ))}
          <p className="px-3 pb-1.5 pt-1 text-[11.5px] text-muted">Switching mode starts a new chat.</p>
        </div>
      )}
    </div>
  )
}
