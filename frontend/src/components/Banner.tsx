import { useEffect, useState } from 'react'
import { Clock } from 'lucide-react'
import { useUI } from '../store/ui'

export function Banner() {
  const banner = useUI((s) => s.banner)
  const setBanner = useUI((s) => s.setBanner)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (banner?.type !== 'rate_limited') return
    const t = window.setInterval(() => {
      setNow(Date.now())
      if (Date.now() >= banner.until) setBanner(null)
    }, 500)
    setNow(Date.now())
    return () => window.clearInterval(t)
  }, [banner, setBanner])

  if (!banner) return null

  const secs = Math.max(0, Math.ceil((banner.until - now) / 1000))
  return (
    <div role="status" className="anim-fade flex items-center gap-3 border-b border-line bg-fg/[0.04] px-4 py-2 text-sm">
      <Clock size={16} className="shrink-0 text-accent" aria-hidden="true" />
      <p className="min-w-0 flex-1">
        You&rsquo;re sending requests too quickly. You can ask again in {secs} second{secs === 1 ? '' : 's'}.
      </p>
    </div>
  )
}
