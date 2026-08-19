import './TruncatedChip.css';

// The bracketed truncation note is already inline in the streamed text
// (serving/app.py's TRUNCATION_NOTICE) — this chip is the more visible
// affordance task.md asks for on top of it, not a replacement for it.
export function TruncatedChip() {
  return (
    <div className="truncated-chip">
      <span className="truncated-chip-icon" aria-hidden="true">✂</span>
      This answer was cut short — ask a follow-up for more detail.
    </div>
  );
}
