import { useEffect, useState } from 'react'
import { Button, ErrorBox, Spinner } from '../components/ui'
import { api, progressUrl, type Lang, type Report } from '../lib/api'
import { t } from '../lib/i18n'

interface Ev {
  stage: string
  i?: number
  n?: number
  message?: string | null
}

export function Checking(props: { lang: Lang; caseId: string; onDone: (r: Report) => void; onDemo: () => void }) {
  const { lang, caseId, onDone } = props
  const [ev, setEv] = useState<Ev>({ stage: 'starting' })
  const [err, setErr] = useState('')

  useEffect(() => {
    const es = new EventSource(progressUrl(caseId))
    let finished = false
    es.onmessage = async (m) => {
      const e = JSON.parse(m.data) as Ev
      setEv(e)
      if (e.stage === 'done') {
        finished = true
        es.close()
        try {
          onDone(await api.report(caseId))
        } catch (x) {
          setErr(x instanceof Error ? x.message : String(x))
        }
      } else if (e.stage === 'error') {
        finished = true
        es.close()
        setErr(e.message ?? 'Error')
      }
    }
    es.onerror = () => {
      if (!finished) {
        // the stream may have dropped; fall back to the report status
        es.close()
        api
          .report(caseId)
          .then((r) => (r.status === 'done' ? onDone(r) : r.status === 'error' ? setErr(r.error ?? 'Error') : setErr('Connection lost.')))
          .catch((x) => setErr(x instanceof Error ? x.message : String(x)))
      }
    }
    return () => es.close()
  }, [caseId, onDone])

  const label =
    ev.stage === 'extracting'
      ? t(lang, 'extracting')
      : ev.stage === 'checking'
        ? t(lang, 'checking', { i: ev.i ?? 0, n: ev.n ?? 0 })
        : ev.stage === 'summarizing'
          ? t(lang, 'summarizing')
          : t(lang, 'starting')
  const pct = ev.stage === 'checking' && ev.n ? Math.round((100 * (ev.i ?? 0)) / ev.n) : ev.stage === 'summarizing' ? 100 : 5

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">{t(lang, 'checkingTitle')}</h1>
      {!err && (
        <>
          <Spinner label={label} />
          <div className="h-4 w-full overflow-hidden rounded-full bg-slate-200" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full bg-blue-700 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </>
      )}
      {err && (
        <ErrorBox message={err}>
          <Button kind="secondary" onClick={props.onDemo}>
            {t(lang, 'seeDemo')}
          </Button>
        </ErrorBox>
      )}
    </div>
  )
}
