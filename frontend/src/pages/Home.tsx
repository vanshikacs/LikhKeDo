import { useState } from 'react'
import { LiveBanner } from '../components/LiveBanner'
import { Button, ErrorBox } from '../components/ui'
import type { Lang } from '../lib/api'
import { LANG_LABELS, t } from '../lib/i18n'

export function Home(props: {
  lang: Lang
  setLang: (l: Lang) => void
  onListen: () => Promise<void>
  onRecall: () => Promise<void>
  onDemo: () => void
}) {
  const { lang } = props
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function go(fn: () => Promise<void>, needConsent: boolean) {
    setErr('')
    if (needConsent && !consent) {
      setErr(t(lang, 'consentNeeded'))
      return
    }
    setBusy(true)
    try {
      await fn()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="pt-4">
        <h1 className="text-[34px] font-bold leading-tight">{t(lang, 'tagline')}</h1>
        <p className="mt-2 text-lg text-slate-700">{t(lang, 'taglineSub')}</p>
      </section>

      <LiveBanner lang={lang} onDemo={props.onDemo} />

      <fieldset>
        <legend className="mb-2 text-base font-semibold">{t(lang, 'chooseLang')}</legend>
        <div className="grid grid-cols-2 gap-2">
          {(Object.keys(LANG_LABELS) as Lang[]).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => props.setLang(l)}
              aria-pressed={lang === l}
              className={`rounded-xl border-2 px-3 py-3 text-lg font-semibold ${
                lang === l ? 'border-blue-700 bg-blue-700 text-white' : 'border-slate-400 bg-white'
              }`}
            >
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
      </fieldset>

      <section className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
        <label className="flex items-start gap-3 text-base">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-1 h-6 w-6 shrink-0 accent-blue-700"
          />
          <span>{t(lang, 'consent')}</span>
        </label>
        <Button onClick={() => go(props.onListen, true)} disabled={busy}>
          🎙 {t(lang, 'listenBtn')}
        </Button>
        <p className="text-base text-slate-600">{t(lang, 'listenSub')}</p>
      </section>

      <section className="space-y-2">
        <Button kind="secondary" onClick={() => go(props.onRecall, false)} disabled={busy}>
          🗣 {t(lang, 'recallBtn')}
        </Button>
        <p className="text-base text-slate-600">{t(lang, 'recallSub')}</p>
      </section>

      <Button kind="ghost" onClick={props.onDemo}>
        {t(lang, 'demoBtn')} →
      </Button>
      {err && <ErrorBox message={err} />}
    </div>
  )
}
