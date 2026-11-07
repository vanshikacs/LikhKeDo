import { useState } from 'react'
import type { Claim, Lang, Verdict } from '../lib/api'
import { t, type Key } from '../lib/i18n'
import { AudioButton } from './AudioButton'
import { VERDICT_STYLE, VerdictBadge } from './ui'

const FALLBACK: Record<Verdict, Key> = { WRITTEN: 'fbWritten', CONTRADICTED: 'fbContradicted', NOT_IN_WRITING: 'fbNotInWriting' }
const REASONS = ['quote_not_in_transcript', 'clause_quote_not_found', 'number_missing', 'invalid_model_output']

export function VerdictCard(props: {
  claim: Claim
  lang: Lang
  audioSrc?: string
  loadAudio?: () => Promise<Blob>
  highlight?: boolean
  delayMs?: number
}) {
  const { claim: c, lang } = props
  const [english, setEnglish] = useState(false)
  // buyer's language first; never fall back to English text in a hi/mr/ta report
  const explain = (lang === 'en' ? c.explain_en : c.explain_local) || t(lang, FALLBACK[c.verdict])
  const ask = c.ask_agent || t(lang, 'fbAsk')
  const reason = c.reason && REASONS.includes(c.reason) ? t(lang, `rsn_${c.reason}` as Key) : null
  return (
    <article
      className={`space-y-3 rounded-2xl border-l-8 bg-white p-4 shadow-sm ${VERDICT_STYLE[c.verdict].box} ${
        props.highlight ? 'lkd-reveal' : ''
      }`}
      style={props.highlight ? { animationDelay: `${props.delayMs ?? 0}ms` } : undefined}
    >
      <VerdictBadge verdict={c.verdict} lang={lang} />
      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">{t(lang, 'whatSaid')}</h3>
        <blockquote className="mt-1 text-lg font-medium">“{c.quote}”</blockquote>
      </section>
      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">{t(lang, 'whatDoc')}</h3>
        {c.clause_quote ? (
          <p className="mt-1 text-lg">
            “{c.clause_quote}”{' '}
            {c.clause_page != null && (
              <span className="whitespace-nowrap text-base text-slate-600">
                ({t(lang, 'page')} {c.clause_page})
              </span>
            )}
          </p>
        ) : (
          <p className="mt-1 text-lg text-slate-700">{t(lang, 'docSilent')}</p>
        )}
      </section>
      <p className="text-lg text-slate-800">{explain}</p>
      {!c.grounded && reason && (
        <p className="text-sm text-slate-600">
          {t(lang, 'notChecked')}: {reason}
        </p>
      )}
      {c.verdict !== 'WRITTEN' && (
        <section className="rounded-xl bg-slate-100 p-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">{t(lang, 'askThis')}</h3>
          <p className="mt-1 text-lg font-semibold">{ask}</p>
        </section>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {(props.audioSrc || props.loadAudio) && (
          <AudioButton lang={lang} label={t(lang, 'playClaim')} src={props.audioSrc} load={props.loadAudio} />
        )}
        {lang !== 'en' && (c.claim_en || c.explain_en) && (
          <button
            type="button"
            onClick={() => setEnglish((v) => !v)}
            aria-expanded={english}
            lang="en"
            className="text-sm font-semibold text-slate-600 underline"
          >
            {english ? t(lang, 'hideEnglish') : t(lang, 'showEnglish')}
          </button>
        )}
      </div>
      {english && (
        <div lang="en" className="rounded-lg border border-slate-300 p-2 text-sm text-slate-700">
          {c.claim_en && <p>{c.claim_en}</p>}
          {c.explain_en && <p className="mt-1">{c.explain_en}</p>}
        </div>
      )}
    </article>
  )
}
