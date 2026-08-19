import './SystemNotice.css';

// One-shot, conversation-level notice — currently used for the Piece 5 403
// recovery message ("started a new conversation"). Not a chat bubble: this
// isn't something either party "said," it's the app telling the user what it
// just did on their behalf.
export function SystemNotice({ text }) {
  return (
    <div className="system-notice" role="status">
      {text}
    </div>
  );
}
