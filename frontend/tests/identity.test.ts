import { describe, expect, it, vi } from 'vitest'
import { login, logout } from '../src/identity'

const user = { id: 1, username: 'admin', role: 'ADMIN', is_active: true }
describe('Identidad HTTP', () => {
  it('login usa JSON y cookies del mismo origen, sin aceptar roles del cliente', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ user, csrf_token: 'csrf' })))
    await expect(login({ username: 'admin', password: 'example-password' }, fetcher)).resolves.toEqual({ user, csrf_token: 'csrf' })
    expect(fetcher).toHaveBeenCalledWith('/api/auth/login', expect.objectContaining({
      method: 'POST', credentials: 'same-origin',
      body: JSON.stringify({ username: 'admin', password: 'example-password' }),
      headers: { 'Content-Type': 'application/json' },
    }))
  })
  it('logout adjunta CSRF y acepta 204', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    await logout('csrf', fetcher)
    expect(fetcher).toHaveBeenCalledWith('/api/auth/logout', expect.objectContaining({
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': 'csrf' },
    }))
  })
  it('propaga 401 para limpiar la sesión en la interfaz', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Sesión vencida' }), { status: 401 }))
    await expect(logout('csrf', fetcher)).rejects.toMatchObject({ status: 401 })
  })
  it('rechaza un contrato de sesión inválido', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ user: { ...user, role: 'OWNER' }, csrf_token: 'csrf' })))
    await expect(login({ username: 'admin', password: 'example-password' }, fetcher)).rejects.toThrow('Respuesta de usuario inválida')
  })
})
