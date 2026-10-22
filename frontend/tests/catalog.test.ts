import { describe, expect, it } from 'vitest'
import { parseMoney, moneyInput, formatMoney, parseQuantity } from '../src/catalog'

describe('Importes exactos en la UI', () => {
  it.each(['0', '0,01', '1,5', '1234.56', '90071992547409,91'])('convierte sin redondear %s', value => {
    const result = parseMoney(value)
    expect(parseMoney(moneyInput(result))).toBe(result)
  })
  it('conserva centavos en el límite entero seguro', () => {
    expect(parseMoney('90071992547409,91')).toBe(Number.MAX_SAFE_INTEGER)
    expect(formatMoney(Number.MAX_SAFE_INTEGER)).toBe('$ 90.071.992.547.409,91')
    expect(parseMoney('1,01')).toBe(101)
  })
  it.each(['1.000', '-1', '1,234', '', 'NaN', '1e3', '90071992547409,92'])('rechaza importe ambiguo o inválido %s', value => {
    expect(() => parseMoney(value)).toThrow()
  })
  it('valida cantidades enteras con signo únicamente en ajustes', () => {
    expect(parseQuantity('-2', true)).toBe(-2)
    expect(() => parseQuantity('-2')).toThrow()
    expect(() => parseQuantity('1.5', true)).toThrow()
    expect(() => parseQuantity('9007199254740992')).toThrow()
  })
})
