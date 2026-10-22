import { describe, expect, it } from 'vitest'
import { findHelp } from '../src/userHelp'

describe('búsqueda local de ayuda por rol', () => {
  it('encuentra palabras sin distinguir mayúsculas ni acentos', () => {
    expect(findHelp('ADMIN', 'MERCADERIA').map(a => a.id)).toContain('adjust-stock')
    expect(findHelp('ADMIN', '  cambiar   PRECIO ').map(a => a.id)).toContain('change-price')
  })
  it('busca en pasos además de títulos y exige todas las palabras', () => {
    expect(findHelp('ADMIN', 'motivo carga inicial').map(a => a.id)).toContain('create-product')
    expect(findHelp('ADMIN', 'precio inexistente-xyz')).toEqual([])
  })
  it('combina tema y texto sin salir del tema elegido', () => {
    expect(findHelp('ADMIN', 'mercaderia', 'Reportes')).toEqual([])
    expect(findHelp('ADMIN', 'precio', 'Productos y precios').map(a => a.id)).toContain('change-price')
  })
  it('empleado no recibe instrucciones administrativas aunque las busque', () => {
    expect(findHelp('EMPLOYEE', 'cambiar precio').map(a => a.id)).toEqual(['permissions'])
    expect(findHelp('EMPLOYEE', '').map(a => a.id)).toContain('pending-sale')
    expect(findHelp('EMPLOYEE', '').map(a => a.id)).not.toContain('void-sale')
  })
  it('sin sesión ofrece ayuda pública y no flujos autenticados', () => {
    expect(findHelp('GUEST', '').map(a => a.id)).toContain('login')
    expect(findHelp('GUEST', '').map(a => a.id)).not.toContain('checkout')
    expect(findHelp('GUEST', 'cargar producto')).toEqual([])
  })
})
