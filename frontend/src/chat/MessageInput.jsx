import { useState } from 'react';
import { MAX_MESSAGE_LENGTH } from './constants';
import './MessageInput.css';

// Counter only becomes visible once it's actually useful information —
// showing "12 / 4000" on every keystroke from an empty box is just noise.
const COUNTER_VISIBLE_THRESHOLD = MAX_MESSAGE_LENGTH * 0.85;

export function MessageInput({ onSend, disabled, mode, retryInSeconds }) {
  const [value, setValue] = useState('');

  const rateLimited = retryInSeconds != null;
  const length = value.length;
  const overLimit = length > MAX_MESSAGE_LENGTH;
  const nearLimit = length >= COUNTER_VISIBLE_THRESHOLD;
  const isDisabled = disabled || rateLimited;
  const canSend = !isDisabled && length > 0 && !overLimit && value.trim().length > 0;

  function handleSubmit(event) {
    event.preventDefault();
    if (!canSend) return;
    onSend(value);
    setValue('');
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit(event);
    }
  }

  return (
    <form className="message-input" onSubmit={handleSubmit}>
      {rateLimited && (
        <div className="rate-limit-banner" role="status">
          <span aria-hidden="true">⏳</span>
          Rate limited — try again in {retryInSeconds}s
        </div>
      )}
      <div className={`message-input-field ${overLimit ? 'is-over-limit' : ''}`}>
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={mode === 'crisis' ? 'Describe the situation…' : 'Ask for career or leadership advice…'}
          rows={1}
          disabled={isDisabled}
        />
        <button type="submit" className="message-input-send" disabled={!canSend}>
          Send
        </button>
      </div>
      <div className="message-input-meta">
        <span className="message-input-hint">
          {overLimit ? 'Message is too long to send — trim it below the limit.' : 'Enter to send · Shift+Enter for a new line'}
        </span>
        {nearLimit && (
          <span className={`message-input-counter ${overLimit ? 'is-over' : ''}`}>
            {length} / {MAX_MESSAGE_LENGTH}
          </span>
        )}
      </div>
    </form>
  );
}
