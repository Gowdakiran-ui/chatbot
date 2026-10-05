import { create } from 'zustand'
import type { SourceRef } from '../lib/types'

export type Theme = 'system' | 'light' | 'dark'

const store = {
  get: (k: string): string | null => {
    try {
      return localStorage.getItem(k)
    } catch {
      return null
    }
  },
  set: (k: string, v: string) => {
    try {
      localStorage.setItem(k, v)
    } catch {
      /* private mode / quota */
    }
  },
}
export const lstore = store

const mq = window.matchMedia('(prefers-color-scheme: dark)')

export function applyTheme(theme: Theme, animate = true) {
  const dark = theme === 'dark' || (theme === 'system' && mq.matches)
  const root = document.documentElement
  if (animate) {
    root.classList.add('theme-transition')
    window.setTimeout(() => root.classList.remove('theme-transition'), 350)
  }
  root.dataset.theme = dark ? 'dark' : 'light'
  store.set('chanakya:theme', theme)
}

export type Banner = { type: 'rate_limited'; until: number } | { type: 'offline' }

interface UIState {
  theme: Theme
  sidebarOpen: boolean
  settingsOpen: boolean
  sourcesPanel: { sources: SourceRef[] } | null
  banner: Banner | null
  init: () => void
  setTheme: (t: Theme) => void
  setSidebar: (open: boolean) => void
  setSettingsOpen: (open: boolean) => void
  openSources: (sources: SourceRef[]) => void
  closeSources: () => void
  setBanner: (b: Banner | null) => void
}

const isMobile = () => window.matchMedia('(max-width: 767px)').matches
const savedTheme = (): Theme => {
  const t = store.get('chanakya:theme')
  return t === 'light' || t === 'dark' ? t : 'system'
}

export const useUI = create<UIState>((set, get) => ({
  theme: savedTheme(),
  sidebarOpen: !isMobile() && store.get('chanakya:sidebar') !== '0',
  settingsOpen: false,
  sourcesPanel: null,
  banner: null,

  init: () => {
    mq.addEventListener('change', () => {
      if (get().theme === 'system') applyTheme('system', false)
    })
    applyTheme(get().theme, false)
    const override = new URLSearchParams(location.search).get('theme') // deep-link helper: ?theme=dark|light
    if (override === 'dark' || override === 'light') document.documentElement.dataset.theme = override
  },
  setTheme: (t) => {
    set({ theme: t })
    applyTheme(t)
  },
  setSidebar: (open) => {
    set({ sidebarOpen: open })
    if (!isMobile()) store.set('chanakya:sidebar', open ? '1' : '0')
  },
  setSettingsOpen: (open) => set({ settingsOpen: open }),
  openSources: (sources) => set({ sourcesPanel: { sources } }),
  closeSources: () => set({ sourcesPanel: null }),
  setBanner: (b) => set({ banner: b }),
}))
