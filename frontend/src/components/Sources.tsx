import { useEffect } from 'react'
import { X } from 'lucide-react'
import type { SourceRef } from '../lib/types'
import { CHIP_MAX, chipsFor } from '../lib/util'
import { useUI } from '../store/ui'
import { IconButton } from './ui'

/** Numbered pills under an answer; each opens the drawer with the full source detail. */
export function SourceChips({ sources }: { sources: SourceRef[] }) {
  const openSources = useUI((s) => s.openSources)
  return (
    <div className="anim-fade mt-4 flex flex-wrap items-center gap-2" role="group" aria-label="Sources">
      {sources.map((s, i) => (
        <button
          key={s.id}
          type="button"
          onClick={() => openSources(sources)}
          title={s.label}
          className="group inline-flex max-w-[16rem] items-center gap-1.5 rounded-full border border-line bg-elevated py-1 pl-1.5 pr-3 text-[13px] leading-none text-fg transition-colors duration-150 hover:border-accent/60"
        >
          <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-surface px-1 text-[11px] font-medium text-muted group-hover:bg-accent group-hover:text-accent-fg">
            {i + 1}
          </span>
          <span className="truncate">{s.label}</span>
        </button>
      ))}
      <button
        type="button"
        onClick={() => openSources(sources)}
        className="rounded-full px-2.5 py-1 text-[13px] leading-none text-muted transition-colors duration-150 hover:bg-fg/[0.07] hover:text-fg"
      >
        {sources.length} source{sources.length === 1 ? '' : 's'}
      </button>
    </div>
  )
}

/** Right-hand drawer listing every source with label, tags and snippet. */
export function SourcesPanel() {
  const panel = useUI((s) => s.sourcesPanel)
  const close = useUI((s) => s.closeSources)
  useEffect(() => {
    if (!panel) return
    const key = (e: KeyboardEvent) => e.key === 'Escape' && close()
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [panel, close])
  if (!panel) return null
  return (
    <>
      <div className="anim-fade fixed inset-0 z-40 bg-black/25 md:bg-transparent" onClick={close} aria-hidden="true" />
      <aside
        role="dialog"
        aria-label="Sources"
        className="anim-slide-right fixed inset-y-0 right-0 z-50 flex w-full max-w-[400px] flex-col border-l border-line bg-elevated shadow-pop"
      >
        <header className="flex items-center justify-between px-5 py-4">
          <h2 className="font-serif text-lg font-semibold">Sources</h2>
          <IconButton label="Close sources" onClick={close}>
            <X size={18} />
          </IconButton>
        </header>
        <ol className="flex-1 space-y-1 overflow-y-auto px-3 pb-6">
          {panel.sources.map((s, i) => {
            const chips = chipsFor(s)
            return (
              <li key={s.id} className="rounded-xl p-3">
                <div className="mb-1 flex items-center gap-2 text-xs text-muted">
                  <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-surface px-1 font-medium">
                    {i + 1}
                  </span>
                </div>
                <div className="text-[15px] font-medium leading-snug text-fg">{s.label}</div>
                {chips.length > 0 && (
                  <ul className="mt-1.5 flex flex-wrap gap-1.5" aria-label="Tags">
                    {chips.map((c) => (
                      <li key={c} title={c} className="rounded-full border border-line px-2 py-0.5 text-[11.5px] leading-snug text-muted">
                        {c.length > CHIP_MAX ? `${c.slice(0, CHIP_MAX - 1).trimEnd()}…` : c}
                      </li>
                    ))}
                  </ul>
                )}
                {s.snippet && <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">{s.snippet}</p>}
              </li>
            )
          })}
        </ol>
      </aside>
    </>
  )
}
