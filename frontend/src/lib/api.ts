export const API_URL: string = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

/** ws:// for http, wss:// for https (Render serves https). */
export function wsUrl(path: string): string {
  return API_URL.replace(/^http/, 'ws') + path
}

export type Lang = 'hi' | 'en' | 'ta' | 'mr'
export type Verdict = 'WRITTEN' | 'CONTRADICTED' | 'NOT_IN_WRITING'

export interface Claim {
  id: string
  quote: string
  claim_en: string
  category: string
  numbers: string[]
  verdict: Verdict
  clause_id: string | null
  clause_quote: string | null
  clause_page: number | null
  explain_en: string
  explain_local: string
  ask_agent: string
  grounded: boolean
  reason: string | null
}

export interface TraceCall {
  service: string
  request_id: string | null
  status: number | null
  error_code: string | null
  latency_ms: number
}

export interface Report {
  id: string
  lang: Lang
  mode: string
  status: string
  error: string | null
  product_label: string | null
  summary: string | null
  engine?: { mode: 'A' | 'B'; provider: string; label: string; quant: string | null; model: string | null } | null
  counts: Record<Verdict, number>
  clauses: number
  transcript: { idx: number; text: string; source: string; lang: string | null }[]
  claims: Claim[]
  trace: {
    prisma_model: string | null
    prisma?: {
      request_id: string | null
      mode: string
      status: number | null
      error_code: string | null
      latency_ms: number | null
      cached: boolean
      lang: string | null
    }[]
    evon_model: string | null
    evon_calls: { model?: string; thinking: boolean; latency_ms: number; tokens: number; request_id?: string | null }[]
    pipeline_ms: number | null
    timbre: { target: string; model: string; voice: string; request_ids: string[]; cached: boolean; latency_ms?: number }[]
    calls: TraceCall[]
  }
  disclaimer: string
  audio?: Record<string, string>
  demo?: {
    slug: string
    lang: Lang
    title: string
    source: 'live'
    live_run_at: string
    created: string
    evon_model?: string
    prisma_request_ids?: string[]
    provider?: string
    label?: string
    quant?: string | null
  }
}

export interface Health {
  ok: boolean
  gnani: 'ok' | 'error'
  evon: 'ok' | 'down'
  evon_reason: 'ok' | 'provider_none' | 'not_configured' | 'unreachable' | 'bad_key' | 'bad_url' | 'model_missing' | 'http_error'
  evon_model: string
  evon_provider: 'vllm' | 'llamacpp' | 'none'
  evon_label: string
  queue: number
  demo_only: boolean
}

export class ApiError extends Error {
  status: number
  code?: string
  constructor(status: number, message: string, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response
  try {
    r = await fetch(API_URL + path, init)
  } catch {
    throw new ApiError(0, 'Cannot reach the LikhKeDo server. Check your internet connection and try again.')
  }
  if (!r.ok) {
    let msg = `Request failed (${r.status}).`
    let code: string | undefined
    try {
      const body = await r.json()
      const d = body.detail
      if (typeof d === 'string') msg = d
      else if (d && typeof d.message === 'string') {
        msg = d.message
        code = d.code
      } else if (Array.isArray(d) && d[0]?.msg) msg = d[0].msg
    } catch {
      /* not JSON */
    }
    throw new ApiError(r.status, msg, code)
  }
  const type = r.headers.get('content-type') ?? ''
  if (type.includes('application/json')) return (await r.json()) as T
  return (await r.blob()) as unknown as T
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => call<Health>('/api/health'),
  createCase: (lang: Lang, mode: 'listen' | 'recall') =>
    call<{ id: string }>('/api/cases', json({ lang, mode, consent: true })),
  recall: (id: string, wav: Blob) =>
    call<{ segment: { idx: number; text: string }; request_ids: string[]; latency_ms: number }>(
      `/api/cases/${id}/recall`,
      { method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: wav },
    ),
  deleteSegment: (id: string, idx: number) => call<{ deleted: number }>(`/api/cases/${id}/segments/${idx}`, { method: 'DELETE' }),
  demoDocument: (id: string) =>
    call<{ clauses: number; pages: number }>(`/api/cases/${id}/document`, json({ demo_doc: 'suraksha_plus' })),
  uploadDocument: (id: string, pdf: File) =>
    call<{ clauses: number; pages: number }>(`/api/cases/${id}/document`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/pdf' },
      body: pdf,
    }),
  analyze: (id: string, engine: 'evon' | 'rules' = 'evon') =>
    call<{ status: string; engine: string }>(`/api/cases/${id}/analyze?engine=${engine}`, { method: 'POST' }),
  report: (id: string) => call<Report>(`/api/cases/${id}/report`),
  speak: (id: string, target: string) => call<Blob>(`/api/cases/${id}/speak`, json({ target })),
  deleteCase: (id: string) => call<{ deleted: boolean }>(`/api/cases/${id}`, { method: 'DELETE' }),
  demos: () => call<{ slug: string; lang: Lang; title: string; live_run_at: string }[]>('/api/demo'),
  demo: (slug: string) => call<Report>(`/api/demo/${slug}`),
}

export const progressUrl = (id: string) => `${API_URL}/api/cases/${id}/progress`
export const slipUrl = (id: string) => `${API_URL}/api/cases/${id}/slip`
export const demoSlipUrl = (slug: string) => `${API_URL}/api/demo/${slug}/slip`
export const demoAudioUrl = (slug: string, file: string) => `${API_URL}/api/demo/${slug}/audio/${file}`

export async function getHealth(): Promise<Health> {
  return api.health()
}
