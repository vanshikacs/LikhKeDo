import { useEffect, useRef, useState } from 'react'
import type { Lang } from '../lib/api'
import { t } from '../lib/i18n'

/** Plays audio from a URL or from a loader that returns a Blob (e.g. POST /speak). */
export function AudioButton(props: {
  lang: Lang
  label: string
  src?: string
  load?: () => Promise<Blob>
  big?: boolean
}) {
  const [state, setState] = useState<'idle' | 'loading' | 'playing' | 'error'>('idle')
  const [err, setErr] = useState('')
  const audio = useRef<HTMLAudioElement | null>(null)
  const url = useRef<string | null>(null)

  useEffect(
    () => () => {
      audio.current?.pause()
      if (url.current?.startsWith('blob:')) URL.revokeObjectURL(url.current)
    },
    [],
  )

  async function play() {
    if (state === 'playing') {
      audio.current?.pause()
      setState('idle')
      return
    }
    setErr('')
    try {
      if (!url.current) {
        if (props.src) url.current = props.src
        else if (props.load) {
          setState('loading')
          url.current = URL.createObjectURL(await props.load())
        } else return
      }
      const a = audio.current ?? new Audio()
      audio.current = a
      a.src = url.current
      a.onended = () => setState('idle')
      await a.play()
      setState('playing')
    } catch (e) {
      setState('error')
      setErr(e instanceof Error ? e.message : t(props.lang, 'noAudio'))
    }
  }

  const base = props.big
    ? 'w-full rounded-xl bg-slate-900 px-5 py-4 text-lg font-semibold text-white hover:bg-slate-700'
    : 'rounded-lg border-2 border-slate-800 bg-white px-3 py-2 text-base font-semibold text-slate-900 hover:bg-slate-100'
  return (
    <div>
      <button type="button" onClick={play} disabled={state === 'loading'} className={base} aria-live="polite">
        {state === 'loading' ? `⏳ ${t(props.lang, 'loadingAudio')}` : state === 'playing' ? `⏸ ${props.label}` : `▶ ${props.label}`}
      </button>
      {state === 'error' && <p className="mt-1 text-sm text-red-800">{err}</p>}
    </div>
  )
}
