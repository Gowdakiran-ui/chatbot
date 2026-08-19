import { useCallback, useEffect, useRef, useState } from 'react';
import { useConversation } from './useConversation';
import { streamChat } from './streamChat';

let idCounter = 0;
function nextId() {
  idCounter += 1;
  return `m${idCounter}`;
}

// Wraps useConversation with the actual send/stream lifecycle. One turn at a
// time by design (busyRef guards re-entry, isBusy drives the UI) — this app
// never has two generations in flight for the same conversation.
export function useChat() {
  const {
    mode,
    conversationId,
    messages,
    switchMode: switchConversationMode,
    resetConversation,
    setMessages,
  } = useConversation();
  const busyRef = useRef(false);
  const [isBusy, setIsBusy] = useState(false);
  const abortRef = useRef(null);
  // Seconds until the client may send again, or null — 429 happens before
  // any StreamingResponse starts (serving/app.py), so there's never a
  // partial assistant message to attach this to; it's conversation-level
  // state, ticked down locally rather than re-derived from a stored epoch.
  const [retryInSeconds, setRetryInSeconds] = useState(null);
  const rateLimitTimerRef = useRef(null);
  // One-shot text shown after a 403 reset (Piece 5) — cleared on next send.
  const [systemNotice, setSystemNotice] = useState(null);

  useEffect(() => {
    return () => {
      if (rateLimitTimerRef.current) clearInterval(rateLimitTimerRef.current);
    };
  }, []);

  const startRateLimitCountdown = useCallback((seconds) => {
    if (rateLimitTimerRef.current) clearInterval(rateLimitTimerRef.current);
    setRetryInSeconds(seconds);
    rateLimitTimerRef.current = setInterval(() => {
      setRetryInSeconds((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(rateLimitTimerRef.current);
          rateLimitTimerRef.current = null;
          return null;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  const sendMessage = useCallback(
    async (text) => {
      if (busyRef.current) return;
      const trimmed = text.trim();
      if (!trimmed) return;

      setSystemNotice(null);
      busyRef.current = true;
      setIsBusy(true);
      const controller = new AbortController();
      abortRef.current = controller;

      const userMessage = { id: nextId(), role: 'user', text: trimmed };
      const assistantId = nextId();
      const assistantMessage = { id: assistantId, role: 'assistant', text: '', status: 'thinking', meta: null, mode };
      setMessages((prev) => [...prev, userMessage, assistantMessage]);

      const patchAssistant = (patch) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, ...(typeof patch === 'function' ? patch(m) : patch) } : m
          )
        );
      };
      const removeAssistant = () => {
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      };

      await streamChat(
        { message: trimmed, mode, conversationId, signal: controller.signal },
        {
          // First token flips the placeholder from "thinking" to "streaming"
          // — the visible transition the task calls for, rather than an
          // identical spinner regardless of how long generation takes.
          onToken: (delta) => {
            patchAssistant((m) => ({ text: m.text + delta, status: 'streaming' }));
          },
          onFinal: (event) => {
            patchAssistant({ status: 'done', meta: event });
          },
          onError: (error) => {
            if (error.kind === 'rate_limited') {
              // Nothing was ever generated for this turn — the "thinking"
              // placeholder would be misleading left in place. The banner
              // (RateLimitBanner, driven by retryInSeconds) is the actual
              // countdown affordance, not a per-message error.
              removeAssistant();
              startRateLimitCountdown(error.retryAfter);
              return;
            }
            if (error.kind === 'forbidden') {
              // Shouldn't happen from this UI's own flow (it always mints
              // its own conversation_id) — but if it ever does, the id
              // itself is unusable now. Starting over cleanly beats a raw
              // 403 in the middle of the chat.
              removeAssistant();
              resetConversation();
              setSystemNotice('Started a new conversation — please send your message again.');
              return;
            }
            // network / too_large / validation / server / model: keep the
            // partial text (if any) and attach a distinct error panel to it
            // — Message.jsx reads errorKind for kind-specific copy/icon.
            patchAssistant({ status: 'error', errorMessage: error.message, errorKind: error.kind });
          },
        }
      );

      // If a mode switch aborted this stream and started a new one, that new
      // controller now owns busy/isBusy — this stale call must not clear it.
      if (abortRef.current === controller) {
        abortRef.current = null;
        busyRef.current = false;
        setIsBusy(false);
      }
    },
    [mode, conversationId, setMessages, resetConversation, startRateLimitCountdown]
  );

  // Mode switching (Piece 2) clears message history outright, so an in-flight
  // generation for the old mode has nothing left to attach its result to —
  // left running, it would keep isBusy stuck true (blocking new sends) for
  // however long that abandoned request takes, up to the ~30-40s crisis tail.
  // Abort it explicitly instead of letting it dangle.
  const switchMode = useCallback(
    (nextMode) => {
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
      busyRef.current = false;
      setIsBusy(false);
      switchConversationMode(nextMode);
    },
    [switchConversationMode]
  );

  return {
    mode,
    conversationId,
    messages,
    switchMode,
    sendMessage,
    isBusy,
    retryInSeconds,
    systemNotice,
  };
}
