import { ApiError } from './identity'

export type Period = 'today' | 'yesterday' | '7d' | '30d' | 'custom'
export type Filter = { period: Period; start: string; end: string }
export type Metrics = { revenue_cents: string; sales: string; average_cents: string; units: string }
type Interval = { start_utc: string; end_utc: string; start_local: string; end_local: string }
export type Change = { delta: string; percent_bp: string | null }
export type Ranked = { product_id: number; name: string; code: string | null; units: string; revenue_cents: string }
export type Hour = { hour: number; sales: string; revenue_cents: string }
export type Report = { timezone: string; period: Interval; previous_period: Interval; current: Metrics; previous: Metrics; comparison: Record<keyof Metrics, Change>; top_units: Ranked[]; top_revenue: Ranked[]; hours: Hour[]; peak_hours: number[] }
const keys = ['revenue_cents', 'sales', 'average_cents', 'units'] as const
const record = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null
const integer = (v: unknown): v is string => typeof v === 'string' && /^(0|[1-9]\d*)$/.test(v)
const signed = (v: unknown): v is string => typeof v === 'string' && /^-?(0|[1-9]\d*)$/.test(v)
const metrics = (v: unknown): v is Metrics => record(v) && keys.every(k => integer(v[k]))
const interval = (v: unknown): v is Interval => record(v) && ['start_utc', 'end_utc', 'start_local', 'end_local'].every(k => typeof v[k] === 'string' && Number.isFinite(Date.parse(v[k] as string)))
const rank = (v: unknown): v is Ranked => record(v) && Number.isSafeInteger(v.product_id) && Number(v.product_id) > 0 && typeof v.name === 'string' && (v.code === null || typeof v.code === 'string') && integer(v.units) && integer(v.revenue_cents)
const hour = (v: unknown): v is Hour => record(v) && Number.isInteger(v.hour) && Number(v.hour) >= 0 && Number(v.hour) <= 23 && integer(v.sales) && integer(v.revenue_cents)
export function parseReport(v: unknown): Report {
  if (!record(v) || v.timezone !== 'America/Argentina/Buenos_Aires' || !interval(v.period) || !interval(v.previous_period) || !metrics(v.current) || !metrics(v.previous) || !record(v.comparison) || !keys.every(k => {
    const c = (v.comparison as Record<string, unknown>)[k]
    return record(c) && signed(c.delta) && (c.percent_bp === null || signed(c.percent_bp))
  }) || !Array.isArray(v.top_units) || v.top_units.length > 10 || !v.top_units.every(rank) || !Array.isArray(v.top_revenue) || v.top_revenue.length > 10 || !v.top_revenue.every(rank) || !Array.isArray(v.hours) || v.hours.length !== 24 || !v.hours.every((h, i) => hour(h) && h.hour === i) || !Array.isArray(v.peak_hours) || !v.peak_hours.every(h => Number.isInteger(h) && h >= 0 && h < 24)) throw new Error('Respuesta de reportes inválida. Volvé a intentar.')
  return v as Report
}
export async function getReport(filter: Filter, signal?: AbortSignal, fetcher: typeof fetch = fetch): Promise<Report> {
  const query = new URLSearchParams({ period: filter.period })
  if (filter.period === 'custom') { query.set('start', filter.start); query.set('end', filter.end) }
  const response = await fetcher(`/api/reports/summary?${query}`, { credentials: 'same-origin', signal })
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, record(data) && typeof data.detail === 'string' ? data.detail : 'No pudimos cargar el reporte.')
  }
  return parseReport(await response.json())
}
export function count(value: string): string { return new Intl.NumberFormat('es-AR').format(BigInt(value)) }
export function money(value: string): string {
  const n = BigInt(value), a = n < 0n ? -n : n
  return `${n < 0n ? '−' : ''}$ ${count(String(a / 100n))},${String(a % 100n).padStart(2, '0')}`
}
export function percent(value: string | null): string {
  if (value === null) return 'Sin base de comparación'
  const n = BigInt(value), a = n < 0n ? -n : n
  return `${n < 0n ? '−' : n > 0n ? '+' : ''}${count(String(a / 100n))},${String(a % 100n).padStart(2, '0')} %`
}
export function localInterval(value: Interval): string {
  const fmt = (s: string) => new Intl.DateTimeFormat('es-AR', { timeZone: 'America/Argentina/Buenos_Aires', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(new Date(s))
  return `${fmt(value.start_utc)} → ${fmt(value.end_utc)} (fin excluido)`
}
