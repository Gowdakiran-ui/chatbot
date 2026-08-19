import { useState } from 'react';
import { useAuth } from './useAuth';
import './TokenEntry.css';

export function TokenEntry() {
  const { setToken, sessionExpired, dismissSessionExpired } = useAuth();
  const [value, setValue] = useState('');

  function handleSubmit(event) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    setToken(trimmed);
  }

  return (
    <div className="token-entry">
      <form className="token-entry-card" onSubmit={handleSubmit}>
        <h1>Chanakya</h1>
        <p className="token-entry-subtitle">
          Enter the access token issued for your account to continue.
        </p>

        {sessionExpired && (
          <div className="token-entry-notice" role="alert">
            <span>Your session expired or the token was invalid. Please sign in again.</span>
            <button
              type="button"
              className="token-entry-notice-dismiss"
              aria-label="Dismiss"
              onClick={dismissSessionExpired}
            >
              &times;
            </button>
          </div>
        )}

        <label htmlFor="token">Access token</label>
        <input
          id="token"
          name="token"
          type="password"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Paste your token here"
        />

        <button type="submit" className="token-entry-submit" disabled={!value.trim()}>
          Continue
        </button>

        <p className="token-entry-footnote">
          Your token is stored only for this browser tab and is cleared when you close it.
        </p>
      </form>
    </div>
  );
}
