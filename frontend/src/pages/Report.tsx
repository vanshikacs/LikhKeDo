import { useState } from 'react'
import { AudioButton } from '../components/AudioButton'
import { Button, ErrorBox } from '../components/ui'
import { UnderTheHood } from '../components/UnderTheHood'
import { VerdictCard } from '../components/VerdictCard'
import { api, demoAudioUrl, demoSlipUrl, slipUrl, type Report } from '../lib/api'
import { t } from '../lib/i18n'
import { RECORD } from '../lib/record'

const LOCALE: Record<string, string> = { hi: 'hi-IN', mr: 'mr-IN', ta: 'ta-IN', en: 'en-IN' }
const stripTags = (s: string) => s.replace(/<\/?(slow|pauses)>/g, ' ').replace(/\s+/g, ' ').trim()

export function ReportPage(props: { report: Report; onHome: () => void }) {
  const r = props.report
  const lang = r.lang
  const demo = r.demo
  const [freeLook, setFreeLook] = useState(false)
  const [copied, setCopied] = useState(false)
  const [deleted, setDeleted] = useState(false)
  const [err, setErr] = useState('')
  const [trace, setTrace] = useState(r.trace)
  // live cases: after Timbre speaks, refresh the trace so "Under the hood" shows the new call
  const speak = async (target: string) => {
    const blob = await api.speak(r.id, target)
    api
      .report(r.id)
      .then((x) => setTrace(x.trace))
      .catch(() => undefined)
    return blob
  }

  const summaryAudio = demo
    ? r.audio?.summary
      ? { src: demoAudioUrl(demo.slug, r.audio.summary) }
      : null
    : { load: () => speak('summary') }

  async function del() {
    setErr('')
    try {
      await api.deleteCase(r.id)
      setDeleted(true)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  if (deleted)
    return (
      <div className="space-y-4">
        <p className="rounded-xl bg-green-50 p-4 text-lg text-green-900">✓ {t(lang, 'deleted')}</p>
        <Button onClick={props.onHome}>{t(lang, 'home')}</Button>
      </div>
    )

  return (
    <div className="space-y-5">
      {demo && (
        <p className="rounded-xl bg-blue-50 p-3 text-base text-blue-950">
          {t(lang, 'demoLive', { date: new Date(demo.live_run_at).toLocaleString(LOCALE[lang]) })}
        </p>
      )}
      <h1 className="text-[28px] font-bold leading-tight">{t(lang, 'reportTitle')}</h1>
      {r.product_label && <p className="text-base text-slate-600">{r.product_label}</p>}

      <section className="space-y-3 rounded-2xl bg-slate-900 p-5 text-white">
        <h2 className="text-base font-semibold uppercase tracking-wide text-slate-300">{t(lang, 'summaryTitle')}</h2>
        {r.summary && <p className="text-xl leading-relaxed">{stripTags(r.summary)}</p>}
        <p className="text-base text-slate-300">
          {t(lang, 'counts', { w: r.counts.WRITTEN, c: r.counts.CONTRADICTED, n: r.counts.NOT_IN_WRITING })}
        </p>
        {summaryAudio ? (
          <div className="[&_button]:bg-white [&_button]:text-slate-900">
            <AudioButton lang={lang} label={t(lang, 'play')} big {...summaryAudio} />
          </div>
        ) : (
          <p className="text-sm text-slate-400">{t(lang, 'noAudio')}</p>
        )}
      </section>

      {r.claims.length === 0 && <p className="text-lg">{t(lang, 'noPromises')}</p>}
      {r.claims.map((c, i) => (
        <VerdictCard
          key={c.id}
          highlight={RECORD}
          delayMs={i * 500}
          claim={c}
          lang={lang}
          audioSrc={demo && r.audio?.[c.id] ? demoAudioUrl(demo.slug, r.audio[c.id]) : undefined}
          loadAudio={demo ? undefined : () => speak(c.id)}
        />
      ))}

      <p className="rounded-xl bg-amber-50 p-3 text-base text-amber-950">{t(lang, 'verifyNote')}</p>

      <div className="space-y-3">
        <a
          href={demo ? demoSlipUrl(demo.slug) : slipUrl(r.id)}
          target="_blank"
          rel="noreferrer"
          className="block w-full rounded-xl bg-blue-700 px-5 py-4 text-center text-lg font-semibold text-white hover:bg-blue-800"
        >
          ✍ {t(lang, 'slip')}
        </a>
        <Button kind="secondary" onClick={() => setFreeLook((v) => !v)}>
          ↩ {t(lang, 'freeLook')}
        </Button>
        {freeLook && (
          <section className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
            <p className="text-lg">{t(lang, 'freeLookText')}</p>
            <h3 className="font-semibold">{t(lang, 'draftTitle')}</h3>
            <pre className="whitespace-pre-wrap rounded-xl bg-slate-100 p-3 font-sans text-base">{t(lang, 'draftText')}</pre>
            <Button
              kind="secondary"
              onClick={async () => {
                await navigator.clipboard?.writeText(t(lang, 'draftText'))
                setCopied(true)
              }}
            >
              {copied ? `✓ ${t(lang, 'copied')}` : t(lang, 'copy')}
            </Button>
          </section>
        )}
        {!demo && (
          <Button kind="danger" onClick={del}>
            🗑 {t(lang, 'deleteData')}
          </Button>
        )}
      </div>
      {err && <ErrorBox message={err} />}

      <UnderTheHood report={{ ...r, trace }} lang={lang} />
      <p className="text-sm text-slate-600">{t(lang, 'footer')}</p>
    </div>
  )
}
