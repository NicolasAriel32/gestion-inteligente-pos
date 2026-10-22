import { describe, expect, it, vi } from 'vitest'
import { count, getReport, money, parseReport, percent } from '../src/reporting'
const interval = { start_utc: '2026-01-01T03:00:00+00:00', end_utc: '2026-01-02T03:00:00+00:00', start_local: '2026-01-01T00:00:00-03:00', end_local: '2026-01-02T00:00:00-03:00' }
const metrics = { revenue_cents: '0', sales: '0', units: '0', average_cents: '0' }
const change = { delta: '0', percent_bp: '0' }
const report = { timezone: 'America/Argentina/Buenos_Aires', period: interval, previous_period: interval, current: metrics, previous: metrics, comparison: { revenue_cents: change, sales: change, units: change, average_cents: change }, top_units: [], top_revenue: [], hours: Array.from({ length: 24 }, (_, hour) => ({ hour, sales: '0', revenue_cents: '0' })), peak_hours: [] }
describe('reportes exactos', () => {
  it('formatea importes mayores que int64 sin redondeo JS', () => {
    expect(money('9232379236109515775')).toBe('$ 92.323.792.361.095.157,75')
    expect(money('-101')).toBe('−$ 1,01')
    expect(count('9007199254740993')).toBe('9.007.199.254.740.993')
  })
  it('distingue base cero, decremento y porcentaje exacto', () => {
    expect(percent(null)).toBe('Sin base de comparación')
    expect(percent('-10000')).toBe('−100,00 %')
    expect(percent('12345')).toBe('+123,45 %')
  })
  it('valida reporte vacío y strings arbitrarios', () => {
    expect(parseReport(report)).toEqual(report)
    expect(parseReport({ ...report, current: { ...metrics, units: '9232379236109515775' } }).current.units).toBe('9232379236109515775')
  })
  it.each([123, '1.5', '01', '-1', 'NaN'])('rechaza cantidades no canónicas: %s', units => {
    expect(() => parseReport({ ...report, current: { ...metrics, units } })).toThrow('inválida')
  })
  it('rechaza horas incompletas y zona ajena', () => {
    expect(() => parseReport({ ...report, hours: [] })).toThrow()
    expect(() => parseReport({ ...report, timezone: 'UTC' })).toThrow()
  })
  it('envía rango solo cuando corresponde y propaga cancelación', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => report })
    const signal = new AbortController().signal
    await getReport({ period: 'custom', start: '2026-01-01', end: '2026-01-02' }, signal, fetcher)
    expect(fetcher).toHaveBeenCalledWith('/api/reports/summary?period=custom&start=2026-01-01&end=2026-01-02', { credentials: 'same-origin', signal })
    await getReport({ period: 'today', start: 'unused', end: 'unused' }, signal, fetcher)
    expect(fetcher).toHaveBeenLastCalledWith('/api/reports/summary?period=today', { credentials: 'same-origin', signal })
  })
  it('conserva error 403 y mensaje del backend', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({ detail: 'Se requiere rol ADMIN' }) })
    await expect(getReport({ period: 'today', start: '', end: '' }, undefined, fetcher)).rejects.toMatchObject({ status: 403, message: 'Se requiere rol ADMIN' })
  })
})
