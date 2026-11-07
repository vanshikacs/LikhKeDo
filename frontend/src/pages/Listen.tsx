import { useEffect, useRef, useState } from 'react'
import { Button, ErrorBox, Spinner } from '../components/ui'
import { API_URL, api, wsUrl, type Lang } from '../lib/api'
import { errText, t, type Key } from '../lib/i18n'
import { MicError, startMic, type Mic } from '../lib/recorder'

type Phase = 'idle' | 'connecting' | 'announcing' | 'listening' | 'stopping' | 'done'

interface ServerMsg {
  type: string
  text?: string
  segment_index?: number
  phrase?: string
  queue?: number
  code?: string
  message?: string
  reconnecting?: boolean
}

const MIC_KEY: Record<string, Key> = { denied: 'micDenied', none: 'micNone', unsupported: 'micUnsupported', failed: 'micFailed' }
const LOW_LEVEL = 0.01 // RMS below this for 3 s while listening -> "speak closer"

export function Listen(props: { lang: Lang; caseId: string; onNext: () => void; onRecall: () => void; dev?: boolean }) {
  const { lang, caseId, dev } = props
  const [phase, setPhase] = useState<Phase>('idle')
  const [captions, setCaptions] = useState<Record<number, string>>({})
  const [flags, setFlags] = useState<string[]>([])
  const [queue, setQueue] = useState(0)
  const [err, setErr] = useState('')
  const [micProblem, setMicProblem] = useState(false)
  const [level, setLevel] = useState(0)
  const [quiet, setQuiet] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  // dev-only diagnostics and switches
  const [stats, setStats] = useState({ rate: 0, fps: 0, sent: 0 })
  const [ec, setEc] = useState(true)
  const [ns, setNs] = useState(true)
  const [agc, setAgc] = useState(true)
  const [saveDebug, setSaveDebug] = useState(false)
  const [pitchSlug, setPitchSlug] = useState('hi_hinglish')
  const pitchAudio = useRef<HTMLAudioElement | null>(null)

  const ws = useRef<WebSocket | null>(null)
  const mic = useRef<Mic | null>(null)
  const sending = useRef(false) // false while the announcement plays (so it isn't transcribed)
  const connected = useRef(false)
  const sent = useRef(0)
  const announceUrl = useRef<string | null>(null)
  const quietSince = useRef<number | null>(null)

  // Prefetch the spoken consent announcement when the screen opens (cached on the server after the first time).
  useEffect(() => {
    if (dev) return
    let cancelled = false
    api
      .speak(caseId, 'announce')
      .then((b) => {
        if (!cancelled) announceUrl.current = URL.createObjectURL(b)
      })
      .catch(() => undefined) // a courtesy only; listening works without it
    return () => {
      cancelled = true
    }
  }, [caseId, dev])

  useEffect(
    () => () => {
      void mic.current?.stop()
      ws.current?.close()
      pitchAudio.current?.pause()
      if (announceUrl.current) URL.revokeObjectURL(announceUrl.current)
    },
    [],
  )

  // dev: frames per second
  useEffect(() => {
    if (!dev) return
    let last = 0
    const id = window.setInterval(() => {
      setStats((s) => ({ ...s, fps: sent.current - last, sent: sent.current }))
      last = sent.current
    }, 1000)
    return () => window.clearInterval(id)
  }, [dev])

  function markReady() {
    if (connected.current && sending.current) setPhase((p) => (p === 'stopping' || p === 'done' ? p : 'listening'))
  }

  function onLevel(rms: number) {
    setLevel(rms)
    if (!sending.current) return
    const now = Date.now()
    if (rms < LOW_LEVEL) {
      quietSince.current ??= now
      setQuiet(now - quietSince.current > 3000)
    } else {
      quietSince.current = null
      setQuiet(false)
    }
  }

  async function playAnnouncement() {
    const url = announceUrl.current
    if (!url) return
    setPhase('announcing')
    const a = new Audio(url)
    await new Promise<void>((resolve) => {
      a.onended = () => resolve()
      a.onerror = () => resolve()
      a.play().catch(() => resolve())
    })
  }

  async function start(over?: { echoCancellation?: boolean; onSending?: () => void }) {
    setErr('')
    setMicProblem(false)
    setPhase('connecting')
    sending.current = false
    connected.current = false
    sent.current = 0

    // 1) open our socket (and therefore Prisma) right away
    const sock = new WebSocket(wsUrl(`/api/cases/${caseId}/listen`))
    sock.binaryType = 'arraybuffer'
    ws.current = sock
    sock.onopen = () => {
      sock.send(JSON.stringify({ lang, sample_rate: mic.current?.sampleRate ?? null, debug_save: dev && saveDebug }))
    }
    sock.onmessage = (ev) => {
      let m: ServerMsg
      try {
        m = JSON.parse(ev.data as string)
      } catch {
        return
      }
      if (m.type === 'status') {
        setQueue(m.queue ?? 0)
        if (m.reconnecting) setReconnecting(true)
      } else if (m.type === 'connected') {
        connected.current = true
        markReady()
      } else if (m.type === 'transcript' && m.text) {
        setReconnecting(false)
        const idx = m.segment_index ?? Date.now()
        setCaptions((c) => ({ ...c, [idx]: m.text as string }))
      } else if (m.type === 'redflag' && m.phrase) {
        const phrase = m.phrase
        setFlags((f) => (f.includes(phrase) ? f : [...f, phrase]))
      } else if (m.type === 'error') {
        setErr(errText(lang, m))
      } else if (m.type === 'closed') {
        setPhase('done')
      }
    }
    sock.onclose = () => {
      void mic.current?.stop()
      mic.current = null
      sending.current = false
      setPhase((p) => (p === 'idle' ? p : 'done'))
    }
    sock.onerror = () => setErr(t(lang, 'err_NETWORK'))

    // 2) start the mic in parallel (frames are dropped until the announcement has finished)
    const micReady = startMic(
      (frame) => {
        if (sending.current && sock.readyState === WebSocket.OPEN) {
          sock.send(frame)
          sent.current += 1
        }
      },
      { echoCancellation: over?.echoCancellation ?? ec, noiseSuppression: ns, autoGainControl: agc, onLevel },
    )
      .then((m) => {
        mic.current = m
        if (dev) setStats((s) => ({ ...s, rate: m.sampleRate }))
        if (sock.readyState === WebSocket.OPEN) sock.send(JSON.stringify({ type: 'info', sample_rate: m.sampleRate }))
        return true
      })
      .catch((e) => {
        setMicProblem(true)
        setErr(t(lang, MIC_KEY[e instanceof MicError ? e.problem : 'failed']))
        sock.close()
        setPhase('idle')
        return false
      })

    // 3) play the announcement meanwhile, then start sending
    await playAnnouncement()
    if (!(await micReady)) return
    sending.current = true
    setPhase((p) => (p === 'announcing' ? 'connecting' : p))
    markReady()
    over?.onSending?.()
  }

  // dev: play the synthetic pitch from the speakers while listening. Echo cancellation must be off,
  // otherwise the browser removes exactly the speaker audio we are trying to capture.
  async function startWithPitch() {
    setEc(false)
    const a = new Audio(`${API_URL}/api/dev/pitch/${pitchSlug}`)
    a.onerror = () =>
      setErr('No pitch audio. Run scripts/make_pitch_audio.py and start the backend with DEBUG_SAVE_AUDIO=true.')
    pitchAudio.current = a
    await start({ echoCancellation: false, onSending: () => void a.play().catch(() => undefined) })
  }

  async function stop() {
    pitchAudio.current?.pause()
    setPhase('stopping')
    sending.current = false
    await mic.current?.stop()
    mic.current = null
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ type: 'stop' }))
    else setPhase('done')
  }

  const lines = Object.entries(captions)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .map(([, v]) => v)
  const active = phase === 'listening' || phase === 'connecting' || phase === 'announcing'
  const levelPct = Math.min(100, Math.round(Math.sqrt(level) * 220))

  return (
    <div className="space-y-5">
      <h1 className="text-3xl font-bold">{t(lang, 'listenTitle')}</h1>

      <div className="flex flex-col items-center gap-3">
        <button
          type="button"
          onClick={active ? stop : () => start()}
          disabled={phase === 'stopping'}
          aria-pressed={active}
          className={`flex h-40 w-40 items-center justify-center rounded-full text-2xl font-bold text-white shadow-lg transition ${
            active ? 'bg-red-700' : 'bg-blue-700 hover:bg-blue-800'
          } disabled:bg-slate-400`}
        >
          {active ? `■ ${t(lang, 'stop')}` : `🎙 ${t(lang, 'start')}`}
        </button>
        {phase === 'connecting' && <Spinner label={queue ? t(lang, 'queued', { n: queue }) : t(lang, 'connecting')} />}
        {phase === 'announcing' && <Spinner label={t(lang, 'announcing')} />}
        {phase === 'listening' && !reconnecting && <p className="text-2xl font-bold text-green-800">🟢 {t(lang, 'speakNow')}</p>}
        {phase === 'listening' && reconnecting && <Spinner label={t(lang, 'reconnecting')} />}
        {phase === 'stopping' && <Spinner label={t(lang, 'transcribing')} />}

        {(phase === 'listening' || phase === 'announcing' || phase === 'connecting') && (
          <div className="w-full max-w-xs" aria-label={t(lang, 'micLevel')}>
            <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200">
              <div className={`h-full transition-all ${quiet ? 'bg-amber-500' : 'bg-green-600'}`} style={{ width: `${levelPct}%` }} />
            </div>
            {quiet && <p className="mt-1 text-base text-amber-900">{t(lang, 'micQuiet')}</p>}
          </div>
        )}
      </div>

      {dev && (
        <section className="space-y-2 rounded-xl border-2 border-dashed border-slate-400 bg-white p-3 font-mono text-sm">
          <p>
            AudioContext.sampleRate: {stats.rate || '—'} Hz · frames/s: {stats.fps} (target 31.25) · bytes/frame: 1024 · sent: {stats.sent}
          </p>
          <p>level (RMS): {level.toFixed(4)}</p>
          <div className="flex flex-wrap gap-4 font-sans text-base">
            {(
              [
                ['echoCancellation', ec, setEc],
                ['noiseSuppression', ns, setNs],
                ['autoGainControl', agc, setAgc],
              ] as const
            ).map(([label, val, set]) => (
              <label key={label} className="flex items-center gap-2">
                <input type="checkbox" checked={val} disabled={active} onChange={(e) => set(e.target.checked)} /> {label}
              </label>
            ))}
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={saveDebug} disabled={active} onChange={(e) => setSaveDebug(e.target.checked)} /> Save what
              Prisma hears (backend needs DEBUG_SAVE_AUDIO=true → data/debug/last_stream.wav)
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-2 font-sans text-base">
            <select
              value={pitchSlug}
              disabled={active}
              onChange={(e) => setPitchSlug(e.target.value)}
              className="rounded border-2 border-slate-400 px-2 py-1"
            >
              <option value="hi_hinglish">hi_hinglish</option>
              <option value="mr_marathi">mr_marathi</option>
              <option value="ta_tamil_english">ta_tamil_english</option>
            </select>
            <button
              type="button"
              disabled={active}
              onClick={() => void startWithPitch()}
              className="rounded-lg border-2 border-slate-800 px-3 py-1 font-semibold disabled:opacity-50"
            >
              ▶ Start + play pitch audio (echoCancellation off)
            </button>
          </div>
        </section>
      )}

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

      {phase === 'done' && lines.length > 0 && !dev && <Button onClick={props.onNext}>{t(lang, 'next')} →</Button>}
    </div>
  )
}
