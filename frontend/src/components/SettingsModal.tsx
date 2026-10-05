import { useEffect, useRef, useState, type ReactNode } from 'react'
import { LogOut, Monitor, Moon, Sun, X } from 'lucide-react'
import { AUTH_DISABLED, useAuth } from '../store/auth'
import { useUI, type Theme } from '../store/ui'
import { IconButton } from './ui'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-4">
      <h3 className="font-serif text-base font-semibold">{title}</h3>
      {children}
    </section>
  )
}

const inputCls =
  'w-full rounded-xl border border-line bg-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-accent'

const maskToken = (t: string | null) => (t ? `${'•'.repeat(8)}${t.slice(-4)}` : 'none')

export function SettingsModal() {
  const open = useUI((s) => s.settingsOpen)
  const close = useUI((s) => s.setSettingsOpen)
  const theme = useUI((s) => s.theme)
  const setTheme = useUI((s) => s.setTheme)
  const token = useAuth((s) => s.token)
  const setToken = useAuth((s) => s.setToken)
  const logout = useAuth((s) => s.logout)
  const [next, setNext] = useState('')
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    setNext('')
    requestAnimationFrame(() => panel.current?.querySelector<HTMLElement>('button[role="radio"][aria-checked="true"]')?.focus())
  }, [open])

  useEffect(() => {
    if (!open) return
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        close(false)
      }
      if (e.key === 'Tab' && panel.current) {
        const f = [...panel.current.querySelectorAll<HTMLElement>('button,input,[tabindex]:not([tabindex="-1"])')].filter((x) => !x.hasAttribute('disabled'))
        if (!f.length) return
        const first = f[0]!
        const last = f[f.length - 1]!
        if (e.shiftKey && document.activeElement === first) (e.preventDefault(), last.focus())
        else if (!e.shiftKey && document.activeElement === last) (e.preventDefault(), first.focus())
      }
    }
    window.addEventListener('keydown', key, true)
    return () => window.removeEventListener('keydown', key, true)
  }, [open, close])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6" role="presentation">
      <div className="anim-fade absolute inset-0 bg-black/40" onClick={() => close(false)} aria-hidden="true" />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="anim-pop relative flex max-h-[92dvh] w-full max-w-[620px] flex-col rounded-t-3xl border border-line bg-elevated shadow-pop sm:rounded-3xl"
      >
        <header className="flex items-center justify-between px-6 pb-2 pt-5">
          <h2 id="settings-title" className="font-serif text-xl font-semibold">
            Settings
          </h2>
          <IconButton label="Close settings" onClick={() => close(false)}>
            <X size={18} />
          </IconButton>
        </header>

        <div className="min-h-0 flex-1 space-y-8 overflow-y-auto px-6 py-4">
          <Section title="Appearance">
            <div>
              <span className="mb-1.5 block text-sm font-medium">Theme</span>
              <div className="inline-flex rounded-xl border border-line bg-bg p-1" role="radiogroup" aria-label="Theme">
                {([['light', Sun, 'Light'], ['dark', Moon, 'Dark'], ['system', Monitor, 'System']] as const).map(([v, Icon, label]) => (
                  <button
                    key={v}
                    type="button"
                    role="radio"
                    aria-checked={theme === v}
                    onClick={() => setTheme(v as Theme)}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors duration-150 ${theme === v ? 'bg-fg/10 text-fg' : 'text-muted hover:text-fg'}`}
                  >
                    <Icon size={15} /> {label}
                  </button>
                ))}
              </div>
            </div>
          </Section>

          {!AUTH_DISABLED && (
            <Section title="Account">
              <div>
                <span className="mb-1.5 block text-sm font-medium">Access token</span>
                <p className="text-sm text-muted" aria-label="Current token, masked">
                  {maskToken(token)}
                </p>
              </div>
              <form
                className="space-y-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (!next.trim()) return
                  setToken(next.trim())
                  setNext('')
                  close(false)
                }}
              >
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium">Replace token</span>
                  <input
                    type="password"
                    autoComplete="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    className={inputCls}
                    value={next}
                    onChange={(e) => setNext(e.target.value)}
                    placeholder="Paste a new token"
                  />
                </label>
                <button
                  type="submit"
                  disabled={!next.trim()}
                  className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-40"
                >
                  Update token
                </button>
              </form>
              <button
                type="button"
                onClick={() => {
                  close(false)
                  logout()
                }}
                className="inline-flex items-center gap-2 rounded-xl border border-line px-3 py-2 text-sm transition-colors duration-150 hover:border-accent/60"
              >
                <LogOut size={15} /> Sign out
              </button>
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}
