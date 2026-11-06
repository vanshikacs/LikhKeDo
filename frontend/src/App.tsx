import { useCallback, useEffect, useState } from 'react'
import { Button, ErrorBox, Shell, Spinner } from './components/ui'
import { api, type Lang, type Report } from './lib/api'
import { LANG_LABELS, t } from './lib/i18n'
import { Checking } from './pages/Checking'
import { DocumentPage } from './pages/Document'
import { Home } from './pages/Home'
import { Listen } from './pages/Listen'
import { Recall } from './pages/Recall'
import { ReportPage } from './pages/Report'

type Screen =
  | { name: 'home' }
  | { name: 'listen'; caseId: string }
  | { name: 'recall'; caseId: string }
  | { name: 'document'; caseId: string }
  | { name: 'checking'; caseId: string }
  | { name: 'report'; report: Report }
  | { name: 'demos' }

const initialLang = (): Lang => {
  const s = localStorage.getItem('lkd-lang')
  return s === 'hi' || s === 'en' || s === 'ta' || s === 'mr' ? s : 'hi'
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(initialLang)
  const [screen, setScreen] = useState<Screen>({ name: 'home' })
  const setLang = (l: Lang) => {
    setLangState(l)
    localStorage.setItem('lkd-lang', l)
    document.documentElement.lang = l
  }
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])
  useEffect(() => window.scrollTo(0, 0), [screen.name])

  const home = () => setScreen({ name: 'home' })
  const onDone = useCallback((r: Report) => setScreen({ name: 'report', report: r }), [])

  if (window.location.pathname === '/dev/listen') return <DevListen lang={lang} />

  const reportLang = screen.name === 'report' ? screen.report.lang : lang
  return (
    <Shell lang={reportLang} onHome={home}>
      {screen.name === 'home' && (
        <Home
          lang={lang}
          setLang={setLang}
          onListen={async () => setScreen({ name: 'listen', caseId: (await api.createCase(lang, 'listen')).id })}
          onRecall={async () => setScreen({ name: 'recall', caseId: (await api.createCase(lang, 'recall')).id })}
          onDemo={() => setScreen({ name: 'demos' })}
        />
      )}
      {screen.name === 'listen' && (
        <Listen
          lang={lang}
          caseId={screen.caseId}
          onNext={() => setScreen({ name: 'document', caseId: screen.caseId })}
          onRecall={async () => setScreen({ name: 'recall', caseId: (await api.createCase(lang, 'recall')).id })}
        />
      )}
      {screen.name === 'recall' && (
        <Recall lang={lang} caseId={screen.caseId} onNext={() => setScreen({ name: 'document', caseId: screen.caseId })} />
      )}
      {screen.name === 'document' && (
        <DocumentPage
          lang={lang}
          caseId={screen.caseId}
          onChecking={() => setScreen({ name: 'checking', caseId: screen.caseId })}
          onDemo={() => setScreen({ name: 'demos' })}
        />
      )}
      {screen.name === 'checking' && (
        <Checking lang={lang} caseId={screen.caseId} onDone={onDone} onDemo={() => setScreen({ name: 'demos' })} />
      )}
      {screen.name === 'report' && <ReportPage report={screen.report} onHome={home} />}
      {screen.name === 'demos' && <Demos lang={lang} onOpen={onDone} />}
    </Shell>
  )
}

function Demos({ lang, onOpen }: { lang: Lang; onOpen: (r: Report) => void }) {
  const [list, setList] = useState<{ slug: string; lang: Lang; title: string }[] | null>(null)
  const [err, setErr] = useState('')
  const [opening, setOpening] = useState('')

  const load = useCallback(() => {
    setErr('')
    setList(null)
    api
      .demos()
      .then((l) => setList([...l].sort((a, b) => Number(b.lang === lang) - Number(a.lang === lang))))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }, [lang])
  useEffect(load, [load])

  async function open(slug: string) {
    setOpening(slug)
    setErr('')
    try {
      onOpen(await api.demo(slug))
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setOpening('')
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">{t(lang, 'demoBtn')}</h1>
      {!list && !err && <Spinner label={t(lang, 'loading')} />}
      {list?.map((d) => (
        <Button key={d.slug} kind={d.lang === lang ? 'primary' : 'secondary'} onClick={() => open(d.slug)} disabled={!!opening}>
          {LANG_LABELS[d.lang] ?? d.lang} · {d.title}
        </Button>
      ))}
      {opening && <Spinner label={t(lang, 'loading')} />}
      {err && (
        <ErrorBox message={err}>
          <Button kind="secondary" onClick={load}>
            {t(lang, 'retry')}
          </Button>
        </ErrorBox>
      )}
    </div>
  )
}

function DevListen({ lang }: { lang: Lang }) {
  const [caseId, setCaseId] = useState('')
  const [err, setErr] = useState('')
  useEffect(() => {
    api
      .createCase(lang, 'listen')
      .then((c) => setCaseId(c.id))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }, [lang])
  return (
    <Shell lang={lang} title="/dev/listen" onHome={() => (window.location.href = '/')}>
      {err && <ErrorBox message={err} />}
      {caseId ? (
        <Listen lang={lang} caseId={caseId} dev onNext={() => undefined} onRecall={() => undefined} />
      ) : (
        !err && <Spinner label={t(lang, 'loading')} />
      )}
    </Shell>
  )
}
