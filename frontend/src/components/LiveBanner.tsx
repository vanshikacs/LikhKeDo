import { useEffect, useState } from 'react'
import { api, type Health, type Lang } from '../lib/api'
import { t, type Key } from '../lib/i18n'

/** Says clearly when live checking is unavailable and why (from /api/health). Renders nothing when Evon is up. */
export function LiveBanner({ lang, onDemo }: { lang: Lang; onDemo?: () => void }) {
  const [h, setH] = useState<Health | null>(null)
  useEffect(() => {
    let alive = true
    api
      .health()
      .then((x) => alive && setH(x))
      .catch(() => undefined) // the API client already reports unreachable servers where it matters
    return () => {
      alive = false
    }
  }, [])
  if (!h || (h.evon === 'ok' && !h.demo_only)) return null
  const reason = (h.demo_only ? 'evon_demo_only' : `evon_${h.evon_reason}`) as Key
  return (
    <div role="status" className="space-y-2 rounded-xl border-2 border-amber-600 bg-amber-50 p-3 text-base text-amber-950">
      <p className="font-semibold">⚠ {t(lang, 'evonDown')}</p>
      <p className="text-sm">{t(lang, reason)}</p>
      {onDemo && (
        <button type="button" onClick={onDemo} className="text-base font-semibold text-blue-800 underline">
          {t(lang, 'seeDemo')} →
        </button>
      )}
    </div>
  )
}
