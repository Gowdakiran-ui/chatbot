import { useCallback, useState } from 'react';
import { Mode } from './modes';

function newConversationId() {
  return crypto.randomUUID();
}

// Chanakya and Crisis Advisor query different collections with different
// framing (see serving/mode_config.py) — continuing one conversation_id across
// both would confuse the backend's context, even though ownership itself
// (serving/conversations.py) is keyed per-client, not per-mode, so it wouldn't
// actually 403. Switching modes therefore always starts a fresh conversation:
// a new client-generated conversation_id and cleared message history.
export function useConversation(initialMode = Mode.CHANAKYA) {
  const [state, setState] = useState(() => ({
    mode: initialMode,
    conversationId: newConversationId(),
    messages: [],
  }));

  const switchMode = useCallback((nextMode) => {
    setState((prev) => {
      if (prev.mode === nextMode) return prev;
      return { mode: nextMode, conversationId: newConversationId(), messages: [] };
    });
  }, []);

  // Piece 5: a 403 means this client no longer owns its own conversation_id
  // (should never happen from the UI's own flow, since it always generates a
  // fresh random one — but a defensive backstop, not a real recurring path).
  // Same reset shape as switchMode, minus the mode change.
  const resetConversation = useCallback(() => {
    setState((prev) => ({ ...prev, conversationId: newConversationId(), messages: [] }));
  }, []);

  const setMessages = useCallback((updater) => {
    setState((prev) => ({
      ...prev,
      messages: typeof updater === 'function' ? updater(prev.messages) : updater,
    }));
  }, []);

  return {
    mode: state.mode,
    conversationId: state.conversationId,
    messages: state.messages,
    switchMode,
    resetConversation,
    setMessages,
  };
}
