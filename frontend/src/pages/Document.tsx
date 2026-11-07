import { useState } from 'react'
import { LiveBanner } from '../components/LiveBanner'
import { Button, ErrorBox, Spinner } from '../components/ui'
import { api, ApiError, type Lang } from '../lib/api'
import { t } from '../lib/i18n'

export function DocumentPage(props: { lang: Lang; caseId: string; onChecking: () => void; onDemo: () => void }) {
  const { lang, caseId } = props
  const [busy, setBusy] = useState<'' | 'reading' | 'starting'>('')
  const [read, setRead] = useState<{ clauses: number; pages: number } | null>(null)
  const [err, setErr] = useState('')
  const [unavailable, setUnavailable] = useState(false)

  async function load(fn: () => Promise<{ clauses: number; pages: number }>) {
    setErr('')
    setBusy('reading')
    try {
      setRead(await fn())
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy('')
    }
  }

  async function check(engine: 'evon' | 'rules' = 'evon') {
    setErr('')
    setUnavailable(false)
    setBusy('starting')
    try {
      await api.analyze(caseId, engine)
      props.onChecking()
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) setUnavailable(true)
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="text-3xl font-bold">{t(lang, 'docTitle')}</h1>
      <p className="text-lg text-slate-700">{t(lang, 'docHint')}</p>
      <LiveBanner lang={lang} onDemo={props.onDemo} />
      {!read && (
        <div className="space-y-3">
          <Button onClick={() => load(() => api.demoDocument(caseId))} disabled={!!busy}>
            📄 {t(lang, 'useSample')}
          </Button>
          <label className="block w-full cursor-pointer rounded-xl border-2 border-slate-800 bg-white px-5 py-4 text-center text-lg font-semibold hover:bg-slate-100">
            ⬆ {t(lang, 'uploadPdf')}
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              disabled={!!busy}
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void load(() => api.uploadDocument(caseId, f))
                e.target.value = ''
              }}
            />
          </label>
        </div>
      )}
      {busy === 'reading' && <Spinner label={t(lang, 'reading')} />}
      {read && (
        <div className="space-y-4">
          <p className="rounded-xl bg-green-50 p-4 text-lg text-green-900">✓ {t(lang, 'docRead', { n: read.clauses, p: read.pages })}</p>
          <Button onClick={() => void check()} disabled={!!busy}>
            {t(lang, 'check')} →
          </Button>
          {busy === 'starting' && <Spinner label={t(lang, 'starting')} />}
        </div>
      )}
      {err && (
        <ErrorBox message={unavailable ? t(lang, 'liveUnavailable') : err}>
          {unavailable && (
            <>
              <Button kind="secondary" onClick={() => void check('rules')} disabled={!!busy}>
                {t(lang, 'runRules')}
              </Button>
              <Button kind="secondary" onClick={props.onDemo}>
                {t(lang, 'seeDemo')}
              </Button>
            </>
          )}
        </ErrorBox>
      )}
    </div>
  )
}
