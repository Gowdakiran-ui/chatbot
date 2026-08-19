import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ThinkingIndicator } from './ThinkingIndicator';
import { Sources } from './Sources';
import { TruncatedChip } from './TruncatedChip';
import { DisclaimerFooter } from './DisclaimerFooter';
import { MessageBadge } from './MessageBadge';
import { NOT_LEGAL_ADVICE_LINE, TRUNCATION_NOTICE } from './backendConstants';
import './Message.css';

function splitDisclaimer(text) {
  const idx = text.indexOf(NOT_LEGAL_ADVICE_LINE);
  if (idx === -1) return { body: text, disclaimer: null };
  const before = text.slice(0, idx);
  const after = text.slice(idx + NOT_LEGAL_ADVICE_LINE.length);
  return { body: `${before}${after}`.trim(), disclaimer: NOT_LEGAL_ADVICE_LINE };
}

export function Message({ message, isLatest }) {
  if (message.role === 'user') {
    return (
      <div className="message message-user">
        <div className="message-bubble message-bubble-user">{message.text}</div>
      </div>
    );
  }

  if (message.status === 'thinking') {
    return (
      <div className="message message-assistant">
        <div className="message-bubble message-bubble-assistant status-thinking">
          <ThinkingIndicator mode={message.mode} />
        </div>
      </div>
    );
  }

  // `refused` is only knowable once the final SSE event lands, at which point
  // `status` is already 'done' too (same patch call) — so this never renders
  // refusal text in the normal-answer bubble style first and "snaps" later.
  if (message.meta?.refused) {
    return (
      <div className="message message-assistant">
        <div className={`message-bubble message-bubble-refusal ${isLatest ? 'is-latest' : ''}`}>
          <MessageBadge kind="refusal" />
          <span className="message-text">{message.text}</span>
        </div>
      </div>
    );
  }

  const isStreaming = message.status === 'streaming';
  const isDone = message.status === 'done';
  const isError = message.status === 'error';

  const { body, disclaimer } = splitDisclaimer(message.text || '');
  const truncated = (message.text || '').includes(TRUNCATION_NOTICE);
  const sources = message.meta?.cited_chunk_ids;

  return (
    <div className="message message-assistant">
      <div
        className={`message-bubble message-bubble-assistant status-${message.status} ${
          isLatest ? 'is-latest' : ''
        }`}
      >
        {isDone && <MessageBadge kind="grounded" />}

        {body && (
          <div className="message-text markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
            {isStreaming && <span className="stream-cursor" aria-hidden="true" />}
          </div>
        )}

        {isDone && truncated && <TruncatedChip />}
        {isDone && disclaimer && <DisclaimerFooter text={disclaimer} />}
        {isDone && sources?.length > 0 && <Sources chunkIds={sources} />}

        {isError && (
          <>
            <MessageBadge kind={message.errorKind === 'network' ? 'network' : 'error'} />
            <div className="message-error-note" role="alert">
              {message.errorMessage}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
