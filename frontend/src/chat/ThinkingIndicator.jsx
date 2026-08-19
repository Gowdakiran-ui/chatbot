import { Mode } from './modes';
import './ThinkingIndicator.css';

const LABEL = {
  [Mode.CHANAKYA]: 'consulting the source texts…',
  [Mode.CRISIS]: 'cross-referencing precedent cases…',
};

// Shown immediately on send, before the first token arrives. Floor refusals
// return in ~4s and real answers can take 30+ — this must read as "working",
// not "identical regardless of path", so it stays visibly alive rather than
// a static spinner.
export function ThinkingIndicator({ mode }) {
  return (
    <div className="thinking-indicator" role="status" aria-label="Generating response">
      <span className="thinking-dot" />
      <span className="thinking-dot" />
      <span className="thinking-dot" />
      <span className="thinking-label">{LABEL[mode] ?? 'thinking…'}</span>
    </div>
  );
}
