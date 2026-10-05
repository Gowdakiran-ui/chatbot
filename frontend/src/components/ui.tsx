import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'

export function IconButton({
  label,
  className = '',
  children,
  ...rest
}: { label: string; children: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted transition-colors duration-150 hover:bg-fg/[0.07] hover:text-fg disabled:opacity-40 ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}

/** Close on outside click / Escape. */
export function useDismiss<T extends HTMLElement>(open: boolean, onClose: () => void) {
  const ref = useRef<T>(null)
  useEffect(() => {
    if (!open) return
    const down = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('mousedown', down)
    document.addEventListener('keydown', key, true)
    return () => {
      document.removeEventListener('mousedown', down)
      document.removeEventListener('keydown', key, true)
    }
  }, [open, onClose])
  return ref
}

export function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <div className="reveal" data-open={open} inert={!open}>
      <div>{children}</div>
    </div>
  )
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-10 shrink-0 rounded-full transition-colors duration-200 ${checked ? 'bg-accent' : 'bg-fg/20'}`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${checked ? 'translate-x-[18px]' : 'translate-x-0.5'}`}
      />
    </button>
  )
}

export function useCopied(ms = 1600): [boolean, () => void] {
  const [copied, setCopied] = useState(false)
  const t = useRef<number>(0)
  useEffect(() => () => window.clearTimeout(t.current), [])
  return [
    copied,
    () => {
      setCopied(true)
      window.clearTimeout(t.current)
      t.current = window.setTimeout(() => setCopied(false), ms)
    },
  ]
}
