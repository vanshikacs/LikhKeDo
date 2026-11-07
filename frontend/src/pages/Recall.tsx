import { useEffect, useRef, useState } from 'react'
import { Button, ErrorBox, Spinner } from '../components/ui'
import { api, type Lang } from '../lib/api'
import { errText, t, type Key } from '../lib/i18n'
import { MicError, pcmToWav, startMic, type Mic } from '../lib/recorder'

const MAX_S = 30
const MIC_KEY: Record<string, Key> = { denied: 'micDenied', none: 'micNone', unsupported: 'micUnsupported', failed: 'micFailed' }

export function Recall(props: { lang: Lang; caseId: string; onNext: () => void }) {
  const { lang, caseId } = props
  const [recording, setRecording] = useState(false)
  const [secs, setSecs] = useState(0)
  const [clip, setClip] = useState<{ blob: Blob; url: string; secs: number } | null>(null)
  const [heard, setHeard] = useState<{ idx: number; text: string }[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const mic = useRef<Mic | null>(null)
  const chunks = useRef<ArrayBuffer[]>([])
  const wantStop = useRef(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(
    () => () => {
      window.clearInterval(timer.current)
      void mic.current?.stop()
    },
    [],
  )

  async function begin() {
    if (recording || busy) return
    setErr('')
    setClip(null)
    chunks.current = []
    wantStop.current = false
    try {
      mic.current = await startMic((f) => {
        chunks.current.push(f)
        if (chunks.current.length * 0.032 >= MAX_S) void end()
      })
    } catch (e) {
      setErr(t(lang, MIC_KEY[e instanceof MicError ? e.problem : 'failed']))
      return
    }
    setRecording(true)
    const t0 = Date.now()
    timer.current = window.setInterval(() => setSecs(Math.min(MAX_S, Math.floor((Date.now() - t0) / 1000))), 250)
    if (wantStop.current) void end() // released before the mic was ready
  }

  async function end() {
    wantStop.current = true
    if (!mic.current) return
    const m = mic.current
    mic.current = null
    window.clearInterval(timer.current)
    await m.stop()
    setRecording(false)
    setSecs(0)
    const s = chunks.current.length * 0.032
    if (s < 1) {
      setErr(t(lang, 'tooShort'))
      return
    }
    const blob = pcmToWav(chunks.current.slice(0, Math.floor(MAX_S / 0.032)))
    setClip({ blob, url: URL.createObjectURL(blob), secs: s })
  }

  async function submit() {
    if (!clip) return
    setBusy(true)
    setErr('')
    try {
      const r = await api.recall(caseId, clip.blob)
      setHeard((h) => [...h, r.segment])
      URL.revokeObjectURL(clip.url)
      setClip(null)
    } catch (e) {
      setErr(errText(lang, e))
    } finally {
      setBusy(false)
    }
  }

  async function remove(idx: number) {
    try {
      await api.deleteSegment(caseId, idx)
      setHeard((h) => h.filter((x) => x.idx !== idx))
    } catch (e) {
      setErr(errText(lang, e))
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="text-3xl font-bold">{t(lang, 'recallTitle')}</h1>
      <p className="text-lg text-slate-700">{t(lang, 'recallHint')}</p>

      {heard.length > 0 && (
        <section className="space-y-2 rounded-2xl bg-white p-4 shadow-sm">
          <h2 className="text-base font-semibold">{t(lang, 'yourWords')}</h2>
          {heard.map((h) => (
            <div key={h.idx} className="flex items-start justify-between gap-3 border-b border-slate-200 pb-2">
              <p className="text-lg">{h.text}</p>
              <button type="button" onClick={() => remove(h.idx)} className="shrink-0 text-base text-red-800 underline" aria-label="remove">
                ✕
              </button>
            </div>
          ))}
        </section>
      )}

      {!clip && !busy && (
        <div className="flex flex-col items-center gap-3">
          <button
            type="button"
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId)
              void begin()
            }}
            onPointerUp={() => void end()}
            onPointerCancel={() => void end()}
            onContextMenu={(e) => e.preventDefault()}
            onKeyDown={(e) => {
              if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) void begin()
            }}
            onKeyUp={(e) => {
              if (e.key === ' ' || e.key === 'Enter') void end()
            }}
            className={`flex h-40 w-40 touch-none select-none items-center justify-center rounded-full text-center text-xl font-bold text-white shadow-lg ${
              recording ? 'scale-105 bg-red-700' : 'bg-blue-700'
            }`}
          >
            {recording ? `● ${secs}s / ${MAX_S}s` : `🎙 ${heard.length ? t(lang, 'addAnother') : t(lang, 'hold')}`}
          </button>
          {recording && <p className="text-lg text-red-800">{t(lang, 'recording')}</p>}
        </div>
      )}

      {clip && (
        <section className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
          <audio controls src={clip.url} className="w-full" />
          <Button onClick={submit} disabled={busy}>
            {t(lang, 'submit')} ({clip.secs.toFixed(0)}s)
          </Button>
          <Button kind="secondary" onClick={() => setClip(null)} disabled={busy}>
            {t(lang, 'reRecord')}
          </Button>
        </section>
      )}
      {busy && <Spinner label={t(lang, 'transcribing')} />}
      {err && <ErrorBox message={err} />}
      {heard.length > 0 && !clip && !recording && !busy && <Button onClick={props.onNext}>{t(lang, 'next')} →</Button>}
    </div>
  )
}
