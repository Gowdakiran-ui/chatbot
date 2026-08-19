import { Mode, MODE_LABEL } from './modes';
import './ModeToggle.css';

export function ModeToggle({ mode, onChange }) {
  return (
    <div className="mode-toggle" role="radiogroup" aria-label="Advisory mode">
      <button
        type="button"
        role="radio"
        aria-checked={mode === Mode.CHANAKYA}
        className={`mode-toggle-option mode-toggle-chanakya ${mode === Mode.CHANAKYA ? 'is-active' : ''}`}
        onClick={() => onChange(Mode.CHANAKYA)}
      >
        <span className="mode-toggle-icon" aria-hidden="true">✦</span>
        <span className="mode-toggle-text">
          <span className="mode-toggle-name">{MODE_LABEL[Mode.CHANAKYA]}</span>
          <span className="mode-toggle-sub">Career &amp; leadership guidance</span>
        </span>
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={mode === Mode.CRISIS}
        className={`mode-toggle-option mode-toggle-crisis ${mode === Mode.CRISIS ? 'is-active' : ''}`}
        onClick={() => onChange(Mode.CRISIS)}
      >
        <span className="mode-toggle-icon" aria-hidden="true">⚠</span>
        <span className="mode-toggle-text">
          <span className="mode-toggle-name">{MODE_LABEL[Mode.CRISIS]}</span>
          <span className="mode-toggle-sub">Precedent-based crisis response</span>
        </span>
      </button>
    </div>
  );
}
