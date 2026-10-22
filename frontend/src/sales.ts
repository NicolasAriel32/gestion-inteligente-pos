import { ApiError } from './identity'
import type { Page } from './catalog'

export const paymentLabels = { CASH: 'Efectivo', TRANSFER: 'Transferencia', DEBIT: 'Débito', CREDIT: 'Crédito' } as const
export type PaymentMethod = keyof typeof paymentLabels
export type Item = { product_id: number; quantity: number }
export type Line = Item & { product_name_snapshot: string; product_code_snapshot: string | null; unit_price_cents: number; subtotal_cents: number }
export type Quote = { items: Line[]; total_cents: number; quote_fingerprint: string }
export type Intent = { items: Item[]; payment_method: PaymentMethod; idempotency_key: string; quote_fingerprint: string }
export type SaleSummary = { id: number; user_id: number; username_snapshot: string; status: 'COMPLETED' | 'VOIDED'; total_cents: number; created_at_utc: string; payment_method: PaymentMethod }
export type Sale = Omit<SaleSummary, 'payment_method'> & { items: Line[]; payment: { method: PaymentMethod; amount_cents: number }; voided_by: number | null; voided_at_utc: string | null; void_reason: string | null }
export type Draft = Item & { name: string; code: string | null }

const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null
const integer = (value: unknown, positive = false): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= (positive ? 1 : 0)
const method = (value: unknown): value is PaymentMethod => typeof value === 'string' && Object.hasOwn(paymentLabels, value)
const items = (value: unknown): value is Item[] => Array.isArray(value) && value.length > 0 && value.length <= 100 && value.every(line => object(line) && integer(line.product_id, true) && integer(line.quantity, true)) && new Set(value.map(line => line.product_id)).size === value.length
const hash = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)
function line(value: unknown): value is Line {
  return object(value) && integer(value.product_id, true) && integer(value.quantity, true) && typeof value.product_name_snapshot === 'string' && (typeof value.product_code_snapshot === 'string' || value.product_code_snapshot === null) && integer(value.unit_price_cents) && integer(value.subtotal_cents) && BigInt(value.unit_price_cents) * BigInt(value.quantity) === BigInt(value.subtotal_cents)
}
function lines(value: unknown, total: unknown): value is Line[] {
  if (!integer(total) || !Array.isArray(value) || !value.every(line)) return false
  return items(value) && value.reduce((sum, line) => sum + BigInt(line.subtotal_cents), 0n) === BigInt(total)
}
export function decodeSale(value: unknown): Sale {
  if (!object(value) || !integer(value.id, true) || !integer(value.user_id, true) || typeof value.username_snapshot !== 'string' || !['COMPLETED', 'VOIDED'].includes(String(value.status)) || typeof value.created_at_utc !== 'string' || Number.isNaN(Date.parse(value.created_at_utc)) || !lines(value.items, value.total_cents) || !object(value.payment) || !method(value.payment.method) || value.payment.amount_cents !== value.total_cents || (value.status === 'COMPLETED' ? value.voided_by !== null || value.voided_at_utc !== null || value.void_reason !== null : !integer(value.voided_by, true) || typeof value.voided_at_utc !== 'string' || typeof value.void_reason !== 'string')) {
    throw new Error('No pudimos verificar la respuesta. Conservamos el intento para comprobar la misma venta.')
  }
  return value as Sale
}
async function request(path: string, method = 'GET', body?: unknown, csrf?: string): Promise<unknown> {
  const response = await fetch(`/api/sales${path}`, { method, credentials: 'same-origin', signal: AbortSignal.timeout(15000), headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(csrf ? { 'X-CSRF-Token': csrf } : {}) }, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) })
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, object(data) && typeof data.detail === 'string' ? data.detail : 'No pudimos completar la operación')
  }
  return response.json()
}
export async function quote(items: Item[], csrf: string): Promise<Quote> {
  const data = await request('/quote', 'POST', { items }, csrf)
  if (!object(data) || !lines(data.items, data.total_cents) || !hash(data.quote_fingerprint)) throw new Error('No pudimos verificar la cotización. Volvé a consultar.')
  return data as Quote
}
export const checkout = async (intent: Intent, csrf: string) => decodeSale(await request('', 'POST', intent, csrf))
export const sale = async (id: number) => decodeSale(await request(`/${id}`))
export const voidSale = async (id: number, reason: string, csrf: string) => decodeSale(await request(`/${id}/void`, 'POST', { reason }, csrf))
export const history = async (query: URLSearchParams) => await request(`?${query}`) as Page<SaleSummary>
export const dateTime = (value: string) => new Date(value).toLocaleString('es-AR', { timeZone: 'America/Argentina/Buenos_Aires' })
const pendingKey = (user: number) => `pos.checkout.pending.v1.${user}`
const draftKey = (user: number) => `pos.checkout.draft.v1.${user}`
export function loadPending(user: number): Intent | null {
  const raw = sessionStorage.getItem(pendingKey(user))
  if (raw === null) return null
  const data: unknown = JSON.parse(raw)
  if (!object(data) || !items(data.items) || !method(data.payment_method) || !hash(data.quote_fingerprint) || typeof data.idempotency_key !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(data.idempotency_key)) throw new Error('El intento guardado no pudo verificarse. Consultá el historial antes de generar otra venta.')
  return { items: data.items, payment_method: data.payment_method, quote_fingerprint: data.quote_fingerprint, idempotency_key: data.idempotency_key }
}
export function savePending(user: number, intent: Intent) { sessionStorage.setItem(pendingKey(user), JSON.stringify(intent)) }
export function clearPending(user: number) { sessionStorage.removeItem(pendingKey(user)) }
export function loadDraft(user: number): Draft[] {
  try {
    const data: unknown = JSON.parse(sessionStorage.getItem(draftKey(user)) ?? '[]')
    const validDraft = (value: unknown): value is Draft => object(value) && integer(value.product_id, true) && integer(value.quantity, true) && typeof value.name === 'string' && (typeof value.code === 'string' || value.code === null)
    return Array.isArray(data) && data.every(validDraft) && (data.length === 0 || items(data)) ? data : []
  } catch { return [] }
}
export function saveDraft(user: number, draft: Draft[]) { sessionStorage.setItem(draftKey(user), JSON.stringify(draft)) }
