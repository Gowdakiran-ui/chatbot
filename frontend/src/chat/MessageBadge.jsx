import './MessageBadge.css';

// Piece 2: one consistent icon/color/label system across all four response
// states, so each reads at a glance — not just by reading the paragraph
// underneath it. Truncated isn't listed here: it's an attribute of a
// grounded answer, not a mutually-exclusive state, so it stays its own
// secondary chip (TruncatedChip) rather than replacing this badge.
const BADGE_BY_KIND = {
  grounded: { icon: '◆', label: 'Grounded answer', className: 'badge-grounded' },
  refusal: { icon: '◈', label: 'No match — honest boundary', className: 'badge-refusal' },
  error: { icon: '⚠', label: 'Error', className: 'badge-error' },
  network: { icon: '🔌', label: 'Connection lost', className: 'badge-error' },
};

export function MessageBadge({ kind }) {
  const config = BADGE_BY_KIND[kind];
  if (!config) return null;
  return (
    <span className={`message-badge ${config.className}`}>
      <span className="message-badge-icon" aria-hidden="true">
        {config.icon}
      </span>
      {config.label}
    </span>
  );
}
