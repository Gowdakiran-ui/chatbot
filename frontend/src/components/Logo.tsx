export function Mark({ size = 28 }: { size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="inline-flex shrink-0 select-none items-center justify-center rounded-full bg-accent font-serif font-semibold italic text-accent-fg"
      style={{ width: size, height: size, fontSize: size * 0.68, lineHeight: 1 }}
    >
      <span style={{ transform: 'translateY(-6%)' }}>c</span>
    </span>
  )
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2">
      <Mark size={26} />
      <span className="font-serif text-[22px] font-semibold tracking-tight text-fg">Chanakya</span>
    </span>
  )
}
