import type { Report } from '../lib/api'
import { t } from '../lib/i18n'

const LOCALE: Record<string, string> = { hi: 'hi-IN', mr: 'mr-IN', ta: 'ta-IN', en: 'en-IN' }

/** Which mode produced this report: A live Evon, B rules check (no AI model), C saved from a live run. */
export function EngineBadge({ report: r }: { report: Report }) {
  const lang = r.lang
  if (r.demo) {
    const when = new Date(r.demo.live_run_at).toLocaleString(LOCALE[lang])
    const label = r.demo.label ?? r.engine?.label
    return (
      <p className="rounded-xl bg-blue-50 p-3 text-base text-blue-950">
        <span className="mr-2 rounded bg-blue-800 px-1.5 py-0.5 font-mono text-sm font-bold text-white">C</span>
        {t(lang, 'demoLive', { date: when })}
        {label && <span className="block text-sm text-blue-900">{label}</span>}
      </p>
    )
  }
  if (r.engine?.mode === 'B')
    return (
      <div className="rounded-xl border-2 border-amber-600 bg-amber-50 p-3 text-base text-amber-950">
        <p className="font-semibold">
          <span className="mr-2 rounded bg-amber-700 px-1.5 py-0.5 font-mono text-sm font-bold text-white">B</span>
          {t(lang, 'modeB')}
        </p>
        <p className="mt-1 text-sm">{t(lang, 'modeBNote')}</p>
      </div>
    )
  if (r.engine?.mode === 'A')
    return (
      <p className="rounded-xl bg-green-50 p-3 text-base text-green-950">
        <span className="mr-2 rounded bg-green-800 px-1.5 py-0.5 font-mono text-sm font-bold text-white">A</span>
        {t(lang, 'modeA', { label: r.engine.label })}
      </p>
    )
  return null
}
