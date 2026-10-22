import { beforeEach, describe, expect, it } from 'vitest'
import { clearPending, decodeSale, loadPending, savePending } from '../src/sales'
import type { Intent, Sale } from '../src/sales'

const sale: Sale = { id: 1, user_id: 2, username_snapshot: 'worker', status: 'COMPLETED', total_cents: 87, created_at_utc: '2026-10-22T10:00:00+00:00', voided_at_utc: null, voided_by: null, void_reason: null, items: [{ product_id: 1, product_name_snapshot: 'Agua', product_code_snapshot: '0001', quantity: 3, unit_price_cents: 29, subtotal_cents: 87 }], payment: { method: 'CASH', amount_cents: 87 } }
const intent: Intent = { items: [{ product_id: 1, quantity: 3 }], payment_method: 'CASH', quote_fingerprint: 'a'.repeat(64), idempotency_key: '00000000-0000-4000-8000-000000000001' }

beforeEach(() => sessionStorage.clear())
describe('Confirmaciones verificadas e intento recuperable', () => {
  it('acepta un comprobante coherente con importes exactos', () => {
    expect(decodeSale(sale)).toEqual(sale)
  })
  it.each([undefined, {}, { ...sale, total_cents: 86 }, { ...sale, status: 'PENDING' }, { ...sale, payment: { method: 'CASH', amount_cents: 1 } }, { ...sale, payment: { method: 'ONLINE', amount_cents: 87 } }, { ...sale, items: [] }, { ...sale, items: [...sale.items, ...sale.items], total_cents: 174, payment: { method: 'CASH', amount_cents: 174 } }, { ...sale, items: [{ ...sale.items[0], quantity: 1.5 }] }, { ...sale, total_cents: Number.MAX_SAFE_INTEGER + 1 }])('rechaza una respuesta incoherente sin tratarla como venta confirmada', value => {
    expect(() => decodeSale(value)).toThrow()
  })
  it('recupera el mismo UUID y pedido, separado por usuario', () => {
    savePending(2, intent)
    expect(loadPending(2)).toEqual(intent)
    expect(loadPending(1)).toBeNull()
    clearPending(1)
    expect(loadPending(2)).toEqual(intent)
    clearPending(2)
    expect(loadPending(2)).toBeNull()
  })
  it('un intento corrupto se conserva y bloquea su descarte silencioso', () => {
    sessionStorage.setItem('pos.checkout.pending.v1.2', '{bad')
    expect(() => loadPending(2)).toThrow()
    expect(sessionStorage.getItem('pos.checkout.pending.v1.2')).toBe('{bad')
  })
  it('rechaza un UUID corrupto sin borrar la evidencia del intento', () => {
    savePending(2, { ...intent, idempotency_key: '-'.repeat(36) })
    expect(() => loadPending(2)).toThrow()
    expect(sessionStorage.getItem('pos.checkout.pending.v1.2')).not.toBeNull()
  })
})
