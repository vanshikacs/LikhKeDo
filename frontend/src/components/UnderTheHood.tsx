import type { Lang, Report } from '../lib/api'
import { t } from '../lib/i18n'

/** Real calls made for this case: request ids, latency, cache hits. "Not used" only when there were none. */
export function UnderTheHood({ report, lang }: { report: Report; lang: Lang }) {
  const tr = report.trace
  const prisma = tr.prisma ?? []
  const evon = tr.evon_calls
  const evonSecs = (evon.reduce((n, c) => n + c.latency_ms, 0) / 1000).toFixed(1)
  const thinkOn = evon.filter((c) => c.thinking).length
  const timbreCalls = tr.calls.filter((c) => c.service === 'timbre')
  const timbre = tr.timbre
  const notUsed = <p className="text-sm text-slate-500">{t(lang, 'uthNotUsed')}</p>
  const ms = (v: number | null | undefined) => (v != null ? <span className="text-slate-500"> · {v} ms</span> : null)

  return (
    <details className="rounded-2xl border-2 border-slate-300 bg-white p-4">
      <summary className="cursor-pointer text-lg font-semibold">⚙ {t(lang, 'underHood')}</summary>
      <div className="mt-3 space-y-5 text-base">
        <section>
          <p className="font-semibold">Gnani Prisma v3.0</p>
          <p className="text-slate-600">{t(lang, 'uthPrisma')}</p>
          {prisma.length ? (
            <ul className="mt-1 space-y-0.5 font-mono text-sm break-all text-slate-800">
              {prisma.map((p, i) => (
                <li key={`${p.request_id}-${i}`}>
                  {p.request_id ?? '—'} · {p.mode === 'stream' ? t(lang, 'uthStream') : t(lang, 'uthRest')}
                  {p.lang && ` · ${t(lang, 'uthLang')} ${p.lang}`}
                  {p.cached ? <span className="text-slate-500"> · {t(lang, 'uthCacheHit')}</span> : ms(p.latency_ms)}
                  {p.error_code && <span className="text-red-800"> · {p.error_code}</span>}
                </li>
              ))}
            </ul>
          ) : (
            notUsed
          )}
        </section>

        <section>
          <p className="font-semibold">{report.engine?.mode === 'B' ? t(lang, 'modeB') : report.engine?.label ?? 'Gnani Evon v3.3'}</p>
          <p className="text-slate-600">{t(lang, 'uthEvon')}</p>
          {evon.length ? (
            <>
              <p className="font-mono text-sm break-all text-slate-800">{evon[0].model ?? tr.evon_model}</p>
              <p className="text-sm text-slate-700">
                {t(lang, 'uthCalls', { n: evon.length, s: evonSecs })} ·{' '}
                {t(lang, 'uthThinking', { on: thinkOn, off: evon.length - thinkOn })}
              </p>
              <ul className="mt-1 space-y-0.5 font-mono text-sm break-all text-slate-800">
                {evon.map((c, i) => (
                  <li key={i}>
                    {c.request_id ?? '—'} · {c.thinking ? '🧠' : '⚡'} · {c.tokens} tok{ms(c.latency_ms)}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            notUsed
          )}
        </section>

        <section>
          <p className="font-semibold">Gnani Timbre</p>
          <p className="text-slate-600">{t(lang, 'uthTimbre')}</p>
          {timbre.length ? (
            <ul className="mt-1 space-y-0.5 font-mono text-sm break-all text-slate-800">
              {timbre.map((x, i) => (
                <li key={i}>
                  {x.target} · {x.model}/{x.voice} ·{' '}
                  {x.cached ? <span className="text-slate-500">{t(lang, 'uthCacheHit')}</span> : x.request_ids.join(', ') || '—'}
                  {ms(x.latency_ms)}
                </li>
              ))}
            </ul>
          ) : timbreCalls.length ? (
            <ul className="mt-1 space-y-0.5 font-mono text-sm break-all text-slate-800">
              {timbreCalls.map((c, i) => (
                <li key={i}>
                  {c.request_id ?? '—'}
                  {ms(c.latency_ms)}
                </li>
              ))}
            </ul>
          ) : (
            notUsed
          )}
        </section>

        {tr.summary_source === 'fixed' && <p className="text-slate-600">{t(lang, 'uthSummaryFixed')}</p>}
        {tr.pipeline_ms != null && <p className="text-slate-600">{t(lang, 'uthTotal', { s: (tr.pipeline_ms / 1000).toFixed(1) })}</p>}
      </div>
    </details>
  )
}
