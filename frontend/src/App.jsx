import { useEffect, useRef, useState } from 'react';
import { useAuth } from './auth/useAuth';
import { TokenEntry } from './auth/TokenEntry';
import { ModeToggle } from './chat/ModeToggle';
import { ChatWindow } from './chat/ChatWindow';
import { useChat } from './chat/useChat';
import { Mode } from './chat/modes';
import './App.css';

// team-review-prep task, Piece 1: mirrors the backend's AUTH_DISABLED flag.
// Reversible dev-mode bypass, not a removal — TokenEntry.jsx is untouched,
// this just skips rendering it. Default (unset) leaves the real gate below
// fully in place.
const AUTH_DISABLED = import.meta.env.VITE_AUTH_DISABLED === 'true';

function App() {
  const { token, logout } = useAuth();
  const { mode, conversationId, messages, isBusy, switchMode, sendMessage, retryInSeconds, systemNotice } = useChat();

  // Piece 2: a brief glitch overlay on every real mode change — ties into
  // the existing crisis-mode color shift rather than replacing it. Purely a
  // decorative overlay (not a remount), so an in-progress typed message in
  // MessageInput is never lost when this fires.
  const [isGlitching, setIsGlitching] = useState(false);
  const prevModeRef = useRef(mode);
  useEffect(() => {
    if (prevModeRef.current === mode) return;
    prevModeRef.current = mode;
    setIsGlitching(true);
    const timer = setTimeout(() => setIsGlitching(false), 400);
    return () => clearTimeout(timer);
  }, [mode]);

  if (!AUTH_DISABLED && !token) {
    return <TokenEntry />;
  }

  return (
    <div className={`authenticated-shell ${mode === Mode.CRISIS ? 'is-crisis' : ''}`}>
      {isGlitching && <div className="mode-glitch-overlay" aria-hidden="true" />}
      {AUTH_DISABLED && (
        <div className="auth-disabled-banner" role="status">
          INTERNAL REVIEW MODE — auth disabled
        </div>
      )}
      <header className="authenticated-header">
        <div className="brand">
          <h1>Chanakya</h1>
          <span className="brand-tag">Advisory Interface</span>
        </div>
        {!AUTH_DISABLED && (
          <button type="button" onClick={logout}>
            Sign out
          </button>
        )}
      </header>
      <div className="mode-toggle-row">
        <ModeToggle mode={mode} onChange={switchMode} />
      </div>
      <ChatWindow
        mode={mode}
        conversationId={conversationId}
        messages={messages}
        isBusy={isBusy}
        onSend={sendMessage}
        retryInSeconds={retryInSeconds}
        systemNotice={systemNotice}
      />
    </div>
  );
}

export default App;
