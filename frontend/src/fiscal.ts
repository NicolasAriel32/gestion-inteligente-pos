import { ApiError } from './identity'

export type FiscalStatus = {
  environment: 'homologation'; emission_enabled: false; production_enabled: false
  configured: boolean; configuration_error: string | null; cuit: string | null
  certificate_fingerprint: string | null; certificate_expires_at: string | null; key_encrypted: boolean
}
export type Connection = { environment: 'homologation'; healthy: boolean; application: 'OK' | 'NO'; database: 'OK' | 'NO'; authentication: 'OK' | 'NO' }
export type Access = { environment: 'homologation'; authenticated: boolean; ticket_expires_at: string; points: { number: number; emission_type: string; blocked: boolean; disabled_date: string | null }[] }
async function request<T>(path: string, csrf: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/fiscal/${path}`, {
    method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null)
    throw new ApiError(response.status, typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string' ? data.detail : 'No pudimos verificar ARCA homologación.')
  }
  return response.json() as Promise<T>
}
export const status = (csrf: string) => request<FiscalStatus>('status', csrf)
export const connection = (csrf: string) => request<Connection>('connection', csrf, {})
export const access = (csrf: string, password: string) => request<Access>('access', csrf, { private_key_password: password })
