import { describe, expect, it, vi } from 'vitest'
import { getHealth } from '../src/api'
describe('API local', () => {
  it('acepta estado sano', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) })
    await expect(getHealth(fn as unknown as typeof fetch)).resolves.toEqual({ status: 'ok' })
    expect(fn).toHaveBeenCalledWith('/api/health')
  })
  it('rechaza error del backend', async () => {
    const fn = vi.fn().mockResolvedValue({ ok: false })
    await expect(getHealth(fn as unknown as typeof fetch)).rejects.toThrow('No se pudo conectar')
  })
})
