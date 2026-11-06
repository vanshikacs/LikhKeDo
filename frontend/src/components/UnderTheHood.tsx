import type { Lang, Report } from '../lib/api'
import { t } from '../lib/i18n'

export function UnderTheHood({ report, lang }: { report: Report; lang: Lang }) {
  const tr = report.trace
  const by = (s: string) => tr.calls.filter((c) => c.service === s)
  const prisma = [...by('prisma-rest'), ...by('prisma-stream')]
  const timbre = by('timbre')
  const evon = by('evon')
  const evonMs = tr.evon_calls.reduce((n, c) => n + c.latency_ms, 0)
  const rows: { name: string; detail: string; ids: string[]; ms: number[] }[] = [
    {
      name: 'Prisma v3.0',
      detail: 'speech-to-text · codemix · finance keyterms',
      ids: prisma.map((c) => c.request_id ?? '—'),
      ms: prisma.map((c) => c.latency_ms),
    },
    {
      name: 'Evon v3.3 (self-hosted)',
      detail: `${tr.evon_model ?? 'gnani/gnani-evon-v3.3-30B-A3B'} · ${tr.evon_calls.length} calls · ${(evonMs / 1000).toFixed(1)} s`,
      ids: evon.map((c) => c.request_id ?? '—').slice(0, 8),
      ms: evon.map((c) => c.latency_ms),
    },
    {
      name: 'Timbre v3.0',
      detail: tr.timbre.length ? `${tr.timbre[0].voice} · ${tr.timbre[0].model}` : 'text-to-speech · Tarika voice',
      ids: [...timbre.map((c) => c.request_id ?? '—'), ...tr.timbre.flatMap((x) => x.request_ids)].filter(
        (v, i, a) => a.indexOf(v) === i,
      ),
      ms: timbre.map((c) => c.latency_ms),
    },
  ]
  return (
    <details className="rounded-2xl border-2 border-slate-300 bg-white p-4">
      <summary className="cursor-pointer text-lg font-semibold">⚙ {t(lang, 'underHood')}</summary>
      <div className="mt-3 space-y-4 text-base">
        {rows.map((r) => (
          <div key={r.name}>
            <p className="font-semibold">{r.name}</p>
            <p className="text-slate-600">{r.detail}</p>
            {r.ids.length > 0 ? (
              <ul className="mt-1 space-y-0.5 font-mono text-sm break-all text-slate-800">
                {r.ids.map((id, i) => (
                  <li key={`${id}-${i}`}>
                    {id}
                    {r.ms[i] != null && <span className="text-slate-500"> · {r.ms[i]} ms</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">—</p>
            )}
          </div>
        ))}
        {tr.pipeline_ms != null && <p className="text-slate-600">Pipeline: {(tr.pipeline_ms / 1000).toFixed(1)} s</p>}
      </div>
    </details>
  )
}
