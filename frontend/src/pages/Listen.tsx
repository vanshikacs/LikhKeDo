import { useEffect, useRef, useState } from 'react'
import { Button, ErrorBox, Spinner } from '../components/ui'
import { api, wsUrl, type Lang } from '../lib/api'
import { t, type Key } from '../lib/i18n'
import { MicError, startMic, type Mic } from '../lib/recorder'

type Phase = 'idle' | 'connecting' | 'queued' | 'listening' | 'stopping' | 'done'

interface ServerMsg {
  type: string
  text?: string
  segment_index?: number
  phrase?: string
  queue?: number
  code?: string
  message?: string
}

const MIC_KEY: Record<string, Key> = { denied: 'micDenied', none: 'micNone', unsupported: 'micUnsupported', failed: 'micFailed' }

export function Listen(props: { lang: Lang; caseId: string; onNext: () => void; onRecall: () => void; dev?: boolean }) {
  const { lang, caseId } = props
  const [phase, setPhase] = useState<Phase>('idle')
  const [captions, setCaptions] = useState<Record<number, string>>({})
  const [flags, setFlags] = useState<string[]>([])
  const [queue, setQueue] = useState(0)
  const [err, setErr] = useState('')
  const [micProblem, setMicProblem] = useState(false)
  const [frames, setFrames] = useState(0)
  const ws = useRef<WebSocket | null>(null)
  const mic = useRef<Mic | null>(null)
  const sent = useRef(0)

  useEffect(
    () => () => {
      void mic.current?.stop()
      ws.current?.close()
    },
    [],
  )

  async function announce() {
    try {
      const blob = await api.speak(caseId, 'announce')
      const a = new Audio(URL.createObjectURL(blob))
      await new Promise<void>((resolve) => {
        a.onended = () => resolve()
        a.onerror = () => resolve()
        a.play().catch(() => resolve())
      })
    } catch {
      /* the announcement is a courtesy; continue without it */
    }
  }

  async function start() {
    setErr('')
    setMicProblem(false)
    setPhase('connecting')
    if (!props.dev) await announce()
    const sock = new WebSocket(wsUrl(`/api/cases/${caseId}/listen`))
    sock.binaryType = 'arraybuffer'
    ws.current = sock
    sock.onmessage = (ev) => {
      let m: ServerMsg
      try {
        m = JSON.parse(ev.data as string)
      } catch {
        return
      }
      if (m.type === 'status') {
        setQueue(m.queue ?? 0)
        setPhase('queued')
      } else if (m.type === 'connected' || m.type === 'speech_start' || m.type === 'processing') {
        setPhase((p) => (p === 'stopping' ? p : 'listening'))
      } else if (m.type === 'transcript' && m.text) {
        const idx = m.segment_index ?? Date.now()
        setCaptions((c) => ({ ...c, [idx]: m.text as string }))
      } else if (m.type === 'redflag' && m.phrase) {
        const phrase = m.phrase
        setFlags((f) => (f.includes(phrase) ? f : [...f, phrase]))
      } else if (m.type === 'error') {
        setErr(m.message ?? 'Error')
      } else if (m.type === 'closed') {
        setPhase('done')
      }
    }
    sock.onclose = () => {
      void mic.current?.stop()
      mic.current = null
      setPhase((p) => (p === 'idle' ? p : 'done'))
    }
    sock.onerror = () => setErr('Connection to the server failed.')
    sock.onopen = async () => {
      sock.send(JSON.stringify({ lang }))
      try {
        mic.current = await startMic((frame) => {
          if (sock.readyState === WebSocket.OPEN) {
            sock.send(frame)
            sent.current += 1
            if (props.dev && sent.current % 16 === 0) setFrames(sent.current)
          }
        })
        setPhase((p) => (p === 'connecting' ? 'listening' : p))
      } catch (e) {
        setMicProblem(true)
        setErr(t(lang, MIC_KEY[e instanceof MicError ? e.problem : 'failed']))
        sock.close()
        setPhase('idle')
      }
    }
  }

  async function stop() {
    setPhase('stopping')
    await mic.current?.stop()
    mic.current = null
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ type: 'stop' }))
    else setPhase('done')
  }

  const lines = Object.entries(captions)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([, v]) => v)
  const active = phase === 'listening' || phase === 'connecting' || phase === 'queued'

  return (
    <div className="space-y-5">
      <h1 className="text-3xl font-bold">{t(lang, 'listenTitle')}</h1>

      <div className="flex flex-col items-center gap-3">
        <button
          type="button"
          onClick={active ? stop : start}
          disabled={phase === 'stopping'}
          aria-pressed={active}
          className={`flex h-40 w-40 items-center justify-center rounded-full text-2xl font-bold text-white shadow-lg transition ${
            active ? 'animate-pulse bg-red-700' : 'bg-blue-700 hover:bg-blue-800'
          } disabled:bg-slate-400`}
        >
          {active ? `■ ${t(lang, 'stop')}` : `🎙 ${t(lang, 'start')}`}
        </button>
        {phase === 'connecting' && <Spinner label={t(lang, 'connecting')} />}
        {phase === 'queued' && <Spinner label={t(lang, 'queued', { n: queue })} />}
        {phase === 'listening' && <p className="text-lg text-slate-700">{t(lang, 'listening')}</p>}
        {phase === 'stopping' && <Spinner label={t(lang, 'transcribing')} />}
        {props.dev && <p className="font-mono text-sm">frames sent: {frames} ({frames * 1024} bytes)</p>}
      </div>

      {flags.length > 0 && (
        <section aria-live="polite">
          <h2 className="mb-2 text-base font-semibold">⚑ {t(lang, 'redflags')}</h2>
          <div className="flex flex-wrap gap-2">
            {flags.map((f) => (
              <span key={f} className="rounded-full border-2 border-red-700 bg-red-50 px-3 py-1 text-base font-semibold text-red-900">
                ⚑ {f}
              </span>
            ))}
          </div>
        </section>
      )}

      <section className="min-h-32 rounded-2xl bg-white p-4 shadow-sm" aria-live="polite">
        {lines.length ? (
          lines.map((l, i) => (
            <p key={i} className="mb-2 text-lg leading-relaxed">
              {l}
            </p>
          ))
        ) : (
          <p className="text-lg text-slate-500">{t(lang, 'captionsEmpty')}</p>
        )}
      </section>

      {err && (
        <ErrorBox message={err}>
          {micProblem && (
            <Button kind="secondary" onClick={props.onRecall}>
              {t(lang, 'useRecallInstead')}
            </Button>
          )}
        </ErrorBox>
      )}

      {phase === 'done' && lines.length > 0 && !props.dev && <Button onClick={props.onNext}>{t(lang, 'next')} →</Button>}
    </div>
  )
}
