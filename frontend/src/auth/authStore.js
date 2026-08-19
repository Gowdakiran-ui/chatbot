// Plain-JS store (no React) so both React components and the non-component
// API client (src/api/client.js) can read/mutate auth state from one place.
//
// sessionStorage, not localStorage — deliberate: token clears on tab close,
// smaller exposure window for a pre-launch product with no revocation UI yet.
// This is a conscious simplification, not an oversight; proper session/cookie
// -based auth is a real follow-up once this goes past pilot.
const STORAGE_KEY = 'chanakya_auth_token';

let token = sessionStorage.getItem(STORAGE_KEY);
let sessionExpired = false;
const listeners = new Set();

function emit() {
  for (const listener of listeners) listener();
}

export function getToken() {
  return token;
}

export function getSessionExpired() {
  return sessionExpired;
}

export function setToken(newToken) {
  token = newToken;
  sessionExpired = false;
  sessionStorage.setItem(STORAGE_KEY, newToken);
  emit();
}

// Called by the API client when a request comes back 401 — clears the token
// and flags it so the UI can show "session expired or invalid" instead of
// silently failing on the next request.
export function clearTokenAsExpired() {
  token = null;
  sessionExpired = true;
  sessionStorage.removeItem(STORAGE_KEY);
  emit();
}

export function logout() {
  token = null;
  sessionExpired = false;
  sessionStorage.removeItem(STORAGE_KEY);
  emit();
}

export function dismissSessionExpired() {
  sessionExpired = false;
  emit();
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
