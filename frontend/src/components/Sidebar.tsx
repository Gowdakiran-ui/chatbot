import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, PanelLeftClose, Pencil, Plus, Search, Settings, Trash2, X } from 'lucide-react'
import { MODES } from '../lib/modes'
import type { Conversation } from '../lib/types'
import { groupConversations } from '../lib/util'
import { useChat } from '../store/chat'
import { useUI } from '../store/ui'
import { Wordmark } from './Logo'
import { IconButton } from './ui'

const isMobile = () => window.matchMedia('(max-width: 767px)').matches

function ConvItem({ c, active }: { c: Conversation; active: boolean }) {
  const select = useChat((s) => s.select)
  const rename = useChat((s) => s.rename)
  const remove = useChat((s) => s.remove)
  const setSidebar = useUI((s) => s.setSidebar)
  const [editing, setEditing] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [draft, setDraft] = useState(c.title)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) input.current?.select()
  }, [editing])

  const commit = () => {
    setEditing(false)
    if (draft.trim() && draft.trim() !== c.title) rename(c.id, draft)
    else setDraft(c.title)
  }

  if (editing)
    return (
      <li className="px-1">
        <input
          ref={input}
          value={draft}
          aria-label="Chat title"
          maxLength={120}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit()
            if (e.key === 'Escape') {
              e.stopPropagation()
              setDraft(c.title)
              setEditing(false)
            }
          }}
          className="w-full rounded-lg border border-accent/60 bg-elevated px-2.5 py-1.5 text-sm outline-none"
        />
      </li>
    )

  return (
    <li className="group relative px-1">
      <button
        type="button"
        onClick={() => {
          select(c.id)
          if (isMobile()) setSidebar(false)
        }}
        data-active={active}
        aria-current={active ? 'page' : undefined}
        title={c.title}
        className="row flex w-full items-center rounded-lg py-2 pl-2.5 pr-2 text-left text-sm"
      >
        <span className="mr-2 shrink-0 rounded border border-line px-1.5 text-[10.5px] leading-[16px] text-muted">{MODES[c.mode].tag}</span>
        <span className="truncate pr-14">{c.title}</span>
      </button>
      <div
        className={`absolute inset-y-0 right-2 flex items-center gap-0.5 transition-opacity duration-150 focus-within:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100 ${confirm ? 'opacity-100' : 'opacity-0'}`}
      >
        {confirm ? (
          <>
            <span className="mr-1 text-xs text-muted">Delete?</span>
            <IconButton label="Confirm delete" className="!h-7 !w-7 !text-danger" onClick={() => remove(c.id)}>
              <Check size={15} />
            </IconButton>
            <IconButton label="Cancel delete" className="!h-7 !w-7" onClick={() => setConfirm(false)}>
              <X size={15} />
            </IconButton>
          </>
        ) : (
          <>
            <IconButton label="Rename chat" className="!h-7 !w-7" onClick={() => { setDraft(c.title); setEditing(true) }}>
              <Pencil size={14} />
            </IconButton>
            <IconButton label="Delete chat" className="!h-7 !w-7" onClick={() => setConfirm(true)}>
              <Trash2 size={14} />
            </IconButton>
          </>
        )}
      </div>
    </li>
  )
}

export function Sidebar() {
  const open = useUI((s) => s.sidebarOpen)
  const setSidebar = useUI((s) => s.setSidebar)
  const setSettingsOpen = useUI((s) => s.setSettingsOpen)
  const conversations = useChat((s) => s.conversations)
  const activeId = useChat((s) => s.activeId)
  const newChat = useChat((s) => s.newChat)
  const [q, setQ] = useState('')
  const term = q.trim().toLowerCase()
  const results = useMemo(
    () =>
      term
        ? conversations.filter((c) => c.title.toLowerCase().includes(term) || c.messages.some((m) => m.content.toLowerCase().includes(term)))
        : null,
    [term, conversations],
  )

  const groups = useMemo(() => groupConversations(results ?? conversations), [results, conversations])

  return (
    <>
      {open && <div className="anim-fade fixed inset-0 z-30 bg-black/35 md:hidden" onClick={() => setSidebar(false)} aria-hidden="true" />}
      <aside
        aria-label="Chat history"
        inert={!open}
        className={`fixed inset-y-0 left-0 z-40 flex w-[280px] shrink-0 flex-col border-r border-line bg-surface transition-[transform,margin] duration-200 ease-out md:static ${open ? 'translate-x-0 md:ml-0' : '-translate-x-full md:-ml-[280px]'}`}
      >
        <div className="flex items-center justify-between px-4 pb-2 pt-4">
          <Wordmark />
          <IconButton label="Close sidebar" onClick={() => setSidebar(false)}>
            <PanelLeftClose size={18} />
          </IconButton>
        </div>

        <div className="space-y-2 px-3 pb-2 pt-2">
          <button
            type="button"
            onClick={() => {
              newChat()
              if (isMobile()) setSidebar(false)
              requestAnimationFrame(() => document.getElementById('composer-input')?.focus())
            }}
            className="flex w-full items-center gap-2 rounded-xl border border-line bg-elevated px-3 py-2 text-sm font-medium shadow-soft transition-colors duration-150 hover:border-accent/50"
          >
            <Plus size={17} className="text-accent" />
            New chat
            <kbd className="ml-auto hidden rounded border border-line px-1.5 font-sans text-[11px] text-muted lg:inline">Ctrl K</kbd>
          </button>
          <label className="relative block">
            <span className="sr-only">Search chats</span>
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search chats"
              className="w-full rounded-xl bg-fg/[0.05] py-2 pl-9 pr-3 text-sm outline-none transition-colors duration-150 placeholder:text-muted focus:bg-fg/[0.08]"
            />
          </label>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-3 pt-1" aria-label="Conversations">
          {groups.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-muted">{q.trim() ? 'No chats match your search.' : 'Your conversations will appear here.'}</p>
          )}
          {groups.map((g) => (
            <section key={g.label} className="mb-3">
              <h2 className="px-3 pb-1 pt-2 text-xs font-medium text-muted">{g.label}</h2>
              <ul className="space-y-px">
                {g.items.map((c) => (
                  <ConvItem key={c.id} c={c} active={c.id === activeId} />
                ))}
              </ul>
            </section>
          ))}
        </nav>

        <div className="border-t border-line p-2">
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="row flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm"
          >
            <Settings size={17} className="text-muted" />
            Settings
          </button>
        </div>
      </aside>
    </>
  )
}
