import { useSyncExternalStore } from 'react';
import {
  getToken,
  getSessionExpired,
  subscribe,
  setToken,
  logout,
  dismissSessionExpired,
} from './authStore';

// Thin React binding over authStore — keeps the store itself framework-free
// so src/api/client.js can use it without pulling in React.
export function useAuth() {
  const token = useSyncExternalStore(subscribe, getToken);
  const sessionExpired = useSyncExternalStore(subscribe, getSessionExpired);

  return { token, sessionExpired, setToken, logout, dismissSessionExpired };
}
