import { create } from 'zustand'

const KEY = 'chanakya_auth_token'

/** Mirrors the backend's AUTH_DISABLED flag: when true the token gate is skipped entirely. */
export const AUTH_DISABLED = import.meta.env.VITE_AUTH_DISABLED === 'true'

// sessionStorage, not localStorage: the token clears when the tab closes.
const read = (): string | null => {
  try {
    return sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}
const write = (v: string | null) => {
  try {
    if (v) sessionStorage.setItem(KEY, v)
    else sessionStorage.removeItem(KEY)
  } catch {
    /* storage unavailable: token lives in memory only */
  }
}

interface AuthState {
  token: string | null
  /** a request came back 401: show the gate with an explanation */
  sessionExpired: boolean
  setToken: (t: string) => void
  expire: () => void
  logout: () => void
  dismissExpired: () => void
}

export const useAuth = create<AuthState>((set) => ({
  token: read(),
  sessionExpired: false,
  setToken: (t) => {
    write(t)
    set({ token: t, sessionExpired: false })
  },
  expire: () => {
    write(null)
    set({ token: null, sessionExpired: true })
  },
  logout: () => {
    write(null)
    set({ token: null, sessionExpired: false })
  },
  dismissExpired: () => set({ sessionExpired: false }),
}))
