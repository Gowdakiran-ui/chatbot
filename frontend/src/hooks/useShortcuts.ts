import { useEffect } from 'react'
import { useChat } from '../store/chat'
import { useUI } from '../store/ui'

export const focusComposer = () => requestAnimationFrame(() => document.getElementById('composer-input')?.focus())

/** Ctrl/Cmd+K new chat, Ctrl/Cmd+/ focus composer, Esc stop generation. */
export function useShortcuts() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey
      if (mod && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        useChat.getState().newChat()
        focusComposer()
      } else if (mod && e.key === '/') {
        e.preventDefault()
        focusComposer()
      } else if (e.key === 'Escape' && !e.defaultPrevented) {
        const ui = useUI.getState()
        if (ui.settingsOpen || ui.sourcesPanel) return
        if (useChat.getState().streaming) {
          e.preventDefault()
          useChat.getState().stop()
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}
