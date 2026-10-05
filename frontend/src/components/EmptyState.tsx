import { MODES } from '../lib/modes'
import { useChat } from '../store/chat'
import { Composer } from './Composer'
import { Mark } from './Logo'

export function EmptyState() {
  const mode = useChat((s) => s.mode)
  const send = useChat((s) => s.send)
  const cfg = MODES[mode]

  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 pb-16 pt-6">
      {/* keyed by mode so the entrance animation replays when the mode changes */}
      <div key={mode} className="anim-rise w-full max-w-[720px]">
        <h1 className="mb-3 flex items-center justify-center gap-3.5 text-center font-serif text-[clamp(30px,6vw,42px)] font-medium leading-tight tracking-tight">
          <Mark size={40} />
          <span>{cfg.title}</span>
        </h1>
        <p className="mx-auto mb-8 max-w-[560px] text-center text-[15px] leading-relaxed text-muted">{cfg.description}</p>
        <Composer />
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {cfg.starters.map(({ icon: Icon, text }) => (
            <button
              key={text}
              type="button"
              onClick={() => void send(text)}
              className="inline-flex items-center gap-2 rounded-full border border-line bg-transparent px-3.5 py-2 text-left text-[13.5px] text-muted transition-colors duration-150 hover:border-fg/25 hover:bg-elevated hover:text-fg"
            >
              <Icon size={15} className="shrink-0" aria-hidden="true" />
              {text}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
