import { getToken, clearTokenAsExpired } from '../auth/authStore';

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

// Every backend call goes through here so the Bearer token attachment and
// 401 handling live in exactly one place (Piece 3's streaming /chat calls
// will reuse this too). A 401 at any point clears the stored token and flips
// authStore's sessionExpired flag, which routes the whole app back to the
// token-entry screen with an explicit message — never a silent failure.
export async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (response.status === 401) {
    clearTokenAsExpired();
    throw new ApiError(401, 'Session expired or invalid — please sign in again');
  }

  return response;
}
