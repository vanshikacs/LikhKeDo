export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function getHealth(): Promise<{ ok: boolean }> {
  const r = await fetch(`${API_URL}/api/health`)
  if (!r.ok) throw new Error(`health check failed: ${r.status}`)
  return r.json()
}
