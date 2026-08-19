import { useEffect, useRef } from 'react';
import { Message } from './Message';
import { MessageInput } from './MessageInput';
import { SystemNotice } from './SystemNotice';
import { Mode, MODE_LABEL } from './modes';
import './ChatWindow.css';

const EMPTY_STATE_COPY = {
  [Mode.CHANAKYA]: 'Ask about career decisions, leadership, or ethics — grounded in the Arthashastra.',
  [Mode.CRISIS]: 'Describe the situation. Guidance is drawn from documented precedent, not general opinion.',
};

export function ChatWindow({
  mode,
  conversationId,
  messages,
  isBusy,
  onSend,
  retryInSeconds,
  systemNotice,
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' });
  }, [messages]);

  return (
    // data-conversation-id: not user-facing, just a debugging/support hook to
    // correlate what's on screen with backend logs (which key everything off
    // conversation_id) without adding a visible UI element for it.
    <div className="chat-window" data-conversation-id={conversationId}>
      <div className="chat-history">
        {messages.length === 0 ? (
          <div className="chat-empty-state">
            <span className="chat-empty-mode">{MODE_LABEL[mode]}</span>
            <p>{EMPTY_STATE_COPY[mode]}</p>
          </div>
        ) : (
          messages.map((message, i) => (
            <Message key={message.id} message={message} isLatest={i === messages.length - 1} />
          ))
        )}
        <div ref={bottomRef} />
      </div>
      {systemNotice && <SystemNotice text={systemNotice} />}
      <MessageInput onSend={onSend} disabled={isBusy} mode={mode} retryInSeconds={retryInSeconds} />
    </div>
  );
}
