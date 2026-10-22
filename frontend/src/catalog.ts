import { ApiError } from './identity'
export type Category = { id: number; name: string; is_active: boolean }
export type Product = { id: number; name: string; code: string | null; category_id: number | null; price_cents: number; cost_cents: number | null; stock_quantity: number; minimum_stock: number; is_active: boolean; created_at: string; updated_at: string }
export type Movement = { id: number; product_id: number; movement_type: string; quantity_delta: number; stock_before: number; stock_after: number; performed_by: number; reason: string; created_at_utc: string }
export type Page<T> = { items: T[]; total: number }
export type ProductInput = { name: string; code: string | null; category_id: number | null; price_cents: number; cost_cents: number | null; minimum_stock: number; initial_stock?: number; initial_reason?: string | null }

async function request<T>(path: string, method = 'GET', body?: unknown, csrf?: string): Promise<T> {
  const response = await fetch(`/api${path}`, { method, credentials: 'same-origin',
    headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(csrf ? { 'X-CSRF-Token': csrf } : {}) },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  })
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string' ? data.detail : 'No pudimos completar la operación')
  }
  return response.json() as Promise<T>
}
export const categories = () => request<Category[]>('/categories')
export const saveCategory = (name: string, csrf: string, id?: number) => request<Category>(id ? `/categories/${id}` : '/categories', id ? 'PATCH' : 'POST', { name }, csrf)
export const categoryActive = (id: number, is_active: boolean, csrf: string) => request<Category>(`/categories/${id}`, 'PATCH', { is_active }, csrf)
export const products = (query: URLSearchParams) => request<Page<Product>>(`/products?${query}`)
export const product = (id: number) => request<Product>(`/products/${id}`)
export const saveProduct = (data: ProductInput, csrf: string, id?: number) => request<Product>(id ? `/products/${id}` : '/products', id ? 'PATCH' : 'POST', data, csrf)
export const productActive = (id: number, is_active: boolean, csrf: string) => request<Product>(`/products/${id}`, 'PATCH', { is_active }, csrf)
export const movements = (id: number) => request<Page<Movement>>(`/stock/movements?product_id=${id}&limit=100`)
export const adjust = (id: number, quantity_delta: number, reason: string, idempotency_key: string, csrf: string) => request<Movement>('/stock/adjustments', 'POST', { product_id: id, quantity_delta, reason, idempotency_key }, csrf)

export function parseMoney(value: string): number {
  const normalized = value.trim()
  if (!/^\d+(?:[.,]\d{1,2})?$/.test(normalized)) throw new Error('Ingresá el importe sin miles y con hasta dos decimales.')
  const [whole, decimal = ''] = normalized.split(/[.,]/)
  const cents = BigInt(whole) * 100n + BigInt(decimal.padEnd(2, '0'))
  if (cents > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('El importe excede el rango admitido.')
  return Number(cents)
}
export function moneyInput(cents: number): string {
  const value = BigInt(cents)
  return `${value / 100n},${(value % 100n).toString().padStart(2, '0')}`
}
export function formatMoney(cents: number): string {
  const value = BigInt(cents)
  return `$ ${new Intl.NumberFormat('es-AR').format(value / 100n)},${(value % 100n).toString().padStart(2, '0')}`
}
export function parseQuantity(value: string, signed = false): number {
  if (!(signed ? /^-?\d+$/ : /^\d+$/).test(value.trim())) throw new Error('Usá una cantidad entera.')
  const quantity = Number(value)
  if (!Number.isSafeInteger(quantity)) throw new Error('La cantidad excede el rango admitido.')
  return quantity
}
