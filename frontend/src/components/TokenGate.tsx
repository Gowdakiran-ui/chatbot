import { useState } from 'react'
import { X } from 'lucide-react'
import { useAuth } from '../store/auth'
import { Mark } from './Logo'

/** Shown instead of the app when no access token is stored (and the backend has auth enabled). */
export function TokenGate() {
  const setToken = useAuth((s) => s.setToken)
  const expired = useAuth((s) => s.sessionExpired)
  const dismiss = useAuth((s) => s.dismissExpired)
  const [value, setValue] = useState('')

  return (
    <div className="flex h-dvh items-center justify-center bg-bg px-4 text-fg">
      <form
        className="anim-rise w-full max-w-[420px] rounded-3xl border border-line bg-elevated p-7 shadow-soft"
        onSubmit={(e) => {
          e.preventDefault()
          if (value.trim()) setToken(value.trim())
        }}
      >
        <div className="mb-5 flex items-center gap-3">
          <Mark size={32} />
          <h1 className="font-serif text-[26px] font-semibold tracking-tight">Chanakya</h1>
        </div>
        <p className="mb-5 text-[15px] leading-relaxed text-muted">Enter the access token issued for your account to continue.</p>

        {expired && (
          <div role="alert" className="mb-4 flex items-start gap-3 rounded-card border border-danger/30 bg-danger/[0.06] px-3.5 py-3 text-sm">
            <p className="min-w-0 flex-1">Your session expired or the token was invalid. Please sign in again.</p>
            <button type="button" aria-label="Dismiss" onClick={dismiss} className="shrink-0 rounded p-0.5 text-muted hover:bg-fg/10">
              <X size={14} />
            </button>
          </div>
        )}

        <label className="block">
          <span className="mb-1.5 block text-sm font-medium">Access token</span>
          <input
            type="password"
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Paste your token here"
            className="w-full rounded-xl border border-line bg-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-accent"
          />
        </label>
        <button
          type="submit"
          disabled={!value.trim()}
          className="mt-4 w-full rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          Continue
        </button>
        <p className="mt-4 text-xs text-muted">Your token is stored only for this browser tab and is cleared when you close it.</p>
      </form>
    </div>
  )
}
