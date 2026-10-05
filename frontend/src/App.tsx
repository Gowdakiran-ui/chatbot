import { lazy, Suspense, useEffect } from 'react'
import { PanelLeft, SquarePen } from 'lucide-react'
import { Banner } from './components/Banner'
import { EmptyState } from './components/EmptyState'
import { SettingsModal } from './components/SettingsModal'
import { Sidebar } from './components/Sidebar'
import { SourcesPanel } from './components/Sources'
import { TokenGate } from './components/TokenGate'
import { IconButton } from './components/ui'
import { useShortcuts } from './hooks/useShortcuts'
import { AUTH_DISABLED, useAuth } from './store/auth'
import { useChat } from './store/chat'
import { useUI } from './store/ui'

// Thread pulls in markdown + syntax highlighting; the empty state doesn't need them for first paint.
const Thread = lazy(() => import('./components/Thread').then((m) => ({ default: m.Thread })))

function TopBar() {
  const open = useUI((s) => s.sidebarOpen)
  const setSidebar = useUI((s) => s.setSidebar)
  const title = useChat((s) => s.conversations.find((c) => c.id === s.activeId)?.title)
  const newChat = useChat((s) => s.newChat)
  return (
    <header className="flex h-12 shrink-0 items-center gap-1 px-2">
      <div className={`flex items-center gap-1 ${open ? 'md:hidden' : ''}`}>
        <IconButton label="Open sidebar" onClick={() => setSidebar(true)}>
          <PanelLeft size={18} />
        </IconButton>
        <IconButton label="New chat" onClick={newChat}>
          <SquarePen size={17} />
        </IconButton>
      </div>
      <h1 className="min-w-0 flex-1 truncate px-2 text-center text-sm text-muted md:text-left">{title ?? ''}</h1>
      <div className="w-8 md:hidden" />
    </header>
  )
}

function Shell() {
  const init = useUI((s) => s.init)
  const hasMessages = useChat((s) => s.messages.length > 0)
  useShortcuts()

  useEffect(() => {
    init()
  }, [init])

  return (
    <div className="flex h-dvh overflow-hidden bg-bg text-fg">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <Banner />
        {hasMessages ? (
          <Suspense fallback={<div className="flex-1" />}>
            <Thread />
          </Suspense>
        ) : (
          <EmptyState />
        )}
      </main>
      <SourcesPanel />
      <SettingsModal />
    </div>
  )
}

export default function App() {
  const token = useAuth((s) => s.token)
  const init = useUI((s) => s.init)
  // The gate renders outside Shell, so apply the saved theme here too.
  useEffect(() => {
    if (!AUTH_DISABLED && !token) init()
  }, [token, init])
  return !AUTH_DISABLED && !token ? <TokenGate /> : <Shell />
}
