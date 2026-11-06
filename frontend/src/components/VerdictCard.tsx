import type { Claim, Lang } from '../lib/api'
import { t } from '../lib/i18n'
import { AudioButton } from './AudioButton'
import { VERDICT_STYLE, VerdictBadge } from './ui'

export function VerdictCard(props: {
  claim: Claim
  lang: Lang
  audioSrc?: string
  loadAudio?: () => Promise<Blob>
}) {
  const { claim: c, lang } = props
  const explain = lang !== 'en' && c.explain_local ? c.explain_local : c.explain_en
  return (
    <article className={`space-y-3 rounded-2xl border-l-8 bg-white p-4 shadow-sm ${VERDICT_STYLE[c.verdict].box}`}>
      <VerdictBadge verdict={c.verdict} lang={lang} />
      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">{t(lang, 'whatSaid')}</h3>
        <blockquote className="mt-1 text-lg font-medium">“{c.quote}”</blockquote>
        {lang !== 'en' && <p className="mt-1 text-base text-slate-600">{c.claim_en}</p>}
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
      {explain && <p className="text-lg text-slate-800">{explain}</p>}
      {!c.grounded && c.reason && (
        <p className="text-sm text-slate-600">
          {t(lang, 'notChecked')}: {c.reason}
        </p>
      )}
      {c.verdict !== 'WRITTEN' && c.ask_agent && (
        <section className="rounded-xl bg-slate-100 p-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-600">{t(lang, 'askThis')}</h3>
          <p className="mt-1 text-lg font-semibold">{c.ask_agent}</p>
        </section>
      )}
      {(props.audioSrc || props.loadAudio) && (
        <AudioButton lang={lang} label={t(lang, 'playClaim')} src={props.audioSrc} load={props.loadAudio} />
      )}
    </article>
  )
}
