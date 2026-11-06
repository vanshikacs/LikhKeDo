import type { ReactNode } from 'react'
import type { Lang, Verdict } from '../lib/api'
import { t } from '../lib/i18n'

type BtnKind = 'primary' | 'secondary' | 'danger' | 'ghost'

const BTN: Record<BtnKind, string> = {
  primary: 'bg-blue-700 text-white hover:bg-blue-800 disabled:bg-slate-400',
  secondary: 'bg-white text-slate-900 border-2 border-slate-800 hover:bg-slate-100 disabled:opacity-50',
  danger: 'bg-white text-red-800 border-2 border-red-800 hover:bg-red-50',
  ghost: 'text-blue-800 underline underline-offset-4 hover:text-blue-950',
}

export function Button(props: {
  children: ReactNode
  onClick?: () => void
  kind?: BtnKind
  disabled?: boolean
  className?: string
  type?: 'button' | 'submit'
}) {
  const { kind = 'primary', className = '' } = props
  return (
    <button
      type={props.type ?? 'button'}
      onClick={props.onClick}
      disabled={props.disabled}
      className={`w-full rounded-xl px-5 py-4 text-lg font-semibold transition ${BTN[kind]} ${className}`}
    >
      {props.children}
    </button>
  )
}

export function ErrorBox({ message, children }: { message: string; children?: ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border-2 border-red-700 bg-red-50 p-4 text-red-900">
      <p className="font-semibold">⚠ {message}</p>
      {children && <div className="mt-3 space-y-2">{children}</div>}
    </div>
  )
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-2 text-slate-700" role="status" aria-live="polite">
      <span className="h-6 w-6 animate-spin rounded-full border-4 border-slate-300 border-t-blue-700" />
      <span>{label}</span>
    </div>
  )
}

export function Shell(props: { lang: Lang; onHome?: () => void; title?: string; children: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col px-4">
      <header className="flex items-center justify-between py-4">
        <button onClick={props.onHome} className="text-xl font-bold tracking-tight text-slate-900" aria-label={t(props.lang, 'home')}>
          Likh<span className="text-blue-700">Ke</span>Do
        </button>
        {props.title && <span className="text-base text-slate-600">{props.title}</span>}
      </header>
      <main className="flex-1 space-y-5 pb-8">{props.children}</main>
      <footer className="border-t border-slate-300 py-4 text-sm text-slate-700">{t(props.lang, 'footer')}</footer>
    </div>
  )
}

export const VERDICT_STYLE: Record<Verdict, { box: string; badge: string; icon: string; key: 'written' | 'contradicted' | 'notInWriting' }> = {
  WRITTEN: { box: 'border-green-700', badge: 'bg-green-700 text-white', icon: '✓', key: 'written' },
  CONTRADICTED: { box: 'border-red-700', badge: 'bg-red-700 text-white', icon: '✕', key: 'contradicted' },
  NOT_IN_WRITING: { box: 'border-amber-600', badge: 'bg-amber-400 text-slate-950', icon: '?', key: 'notInWriting' },
}

export function VerdictBadge({ verdict, lang }: { verdict: Verdict; lang: Lang }) {
  const s = VERDICT_STYLE[verdict]
  return (
    <span className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-[22px] font-bold leading-tight ${s.badge}`}>
      <span aria-hidden="true">{s.icon}</span>
      {t(lang, s.key)}
    </span>
  )
}
