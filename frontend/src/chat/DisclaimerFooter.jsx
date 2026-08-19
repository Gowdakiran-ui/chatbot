import './DisclaimerFooter.css';

// Crisis-mode answers always carry this line (backend-enforced — see
// serving/app.py). Pulled out of the flowing paragraph and given its own
// persistent footer treatment: task.md is explicit that it's "supposed to be
// seen, not blend into the paragraph" — labeled and bordered like a real
// design-system component, not bolted onto a generic bubble.
export function DisclaimerFooter({ text }) {
  return (
    <div className="disclaimer-footer">
      <span className="disclaimer-icon" aria-hidden="true">§</span>
      <div className="disclaimer-body">
        <span className="disclaimer-label">Legal notice</span>
        <span className="disclaimer-text">{text}</span>
      </div>
    </div>
  );
}
