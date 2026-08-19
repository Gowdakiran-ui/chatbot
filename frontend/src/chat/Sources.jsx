import './Sources.css';

// Raw chunk ids only — human-readable source labels are a real gap (task.md
// flags this explicitly as a follow-up, not something to solve here).
export function Sources({ chunkIds }) {
  return (
    <div className="sources">
      <span className="sources-label">
        <span className="sources-label-icon" aria-hidden="true">▤</span>
        Sources
      </span>
      <div className="sources-list">
        {chunkIds.map((id) => (
          <span className="source-chip" key={id} title={id}>
            {id}
          </span>
        ))}
      </div>
    </div>
  );
}
