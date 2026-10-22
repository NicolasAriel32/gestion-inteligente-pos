import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { Session, User } from './identity'
import { ApiError, employees } from './identity'
import * as catalog from './catalog'
import type { Product } from './catalog'
import * as api from './sales'
import type { Draft, Intent, PaymentMethod, Quote, Sale, SaleSummary } from './sales'
import { Button, ConfirmDialog, Field, Notice, Panel } from './ui'

function restore(user: number) {
  try { return { pending: api.loadPending(user), error: '' } }
  catch { return { pending: null, error: 'No pudimos recuperar un intento de venta de esta pestaña. Consultá el historial y revisá el navegador antes de generar otra venta.' } }
}

export function Receipt({ sale }: { sale: Sale }) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [sale])
  return <Panel className="receipt-panel">
    <div className="receipt-toolbar"><h2 ref={heading} tabIndex={-1}>Venta #{sale.id} · {sale.status === 'VOIDED' ? 'Anulada' : 'Registrada'}</h2><Button variant="secondary" onClick={() => window.print()}>Imprimir ticket de 58 mm</Button></div>
    <p className="form-description receipt-help">Seleccioná tu impresora y papel de 58 mm. Podés reimprimir sin registrar otra venta. La aplicación no confirma la salida física del papel.</p>
    <article className="receipt-paper" aria-label={`Comprobante no fiscal de venta ${sale.id}`}>
      <h3>Gestión Inteligente</h3><p className="receipt-caption">COMPROBANTE NO FISCAL</p>
      <p>Venta #{sale.id}<br />{api.dateTime(sale.created_at_utc)}<br />Atendió: {sale.username_snapshot}</p>
      {sale.status === 'VOIDED' && <div className="receipt-void"><strong>VENTA ANULADA</strong><p>{sale.void_reason}</p><p>{sale.voided_at_utc && api.dateTime(sale.voided_at_utc)}</p></div>}
      <ul>{sale.items.map(line => <li key={line.product_id}><strong>{line.product_name_snapshot}</strong>{line.product_code_snapshot && <small>Código: {line.product_code_snapshot}</small>}<div><span>{line.quantity} × {catalog.formatMoney(line.unit_price_cents)}</span><span>{catalog.formatMoney(line.subtotal_cents)}</span></div></li>)}</ul>
      <p className="receipt-total"><span>TOTAL ARS</span><strong>{catalog.formatMoney(sale.total_cents)}</strong></p>
      <p>Medio declarado: {api.paymentLabels[sale.payment.method]}</p>
      <p className="receipt-caption">Registro interno. Sin validez fiscal.<br />El pago se informa manualmente; no implica confirmación bancaria.</p>
    </article>
  </Panel>
}

export default function SalesWorkspace({ session, mode, onBusyChange, onExpired }: { session: Session; mode: 'checkout' | 'history'; onBusyChange: (value: boolean) => void; onExpired: () => void }) {
  const user = session.user
  const [restored] = useState(() => restore(user.id))
  const [pending, setPending] = useState<Intent | null>(restored.pending)
  const [cart, setCart] = useState<Draft[]>(() => api.loadDraft(user.id))
  const [quote, setQuote] = useState<Quote | null>(null)
  const [method, setMethod] = useState<PaymentMethod>('CASH')
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [history, setHistory] = useState<SaleSummary[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyOffset, setHistoryOffset] = useState(0)
  const [seller, setSeller] = useState('')
  const [status, setStatus] = useState('')
  const [staff, setStaff] = useState<User[]>([])
  const [detail, setDetail] = useState<Sale | null>(null)
  const [result, setResult] = useState<Sale | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [revision, setRevision] = useState(0)
  const [reason, setReason] = useState('')
  const [confirm, setConfirm] = useState(false)
  const locked = useRef(false)
  const quoteHeading = useRef<HTMLHeadingElement>(null)
  const expired = useRef(onExpired)
  expired.current = onExpired
  useEffect(() => { setError(''); setNotice('') }, [mode])
  useEffect(() => { quoteHeading.current?.focus() }, [quote])
  useEffect(() => {
    try { api.saveDraft(user.id, cart) } catch { setError('El navegador no pudo conservar el borrador. Mantené esta pantalla abierta hasta terminar.') }
  }, [cart, user.id])
  useEffect(() => {
    let active = true
    setLoading(true)
    const query = new URLSearchParams(mode === 'checkout' ? { search, active_only: 'true', limit: '20', offset: String(offset) } : { limit: '20', offset: String(historyOffset) })
    if (mode === 'history') { if (seller) query.set('user_id', seller); if (status) query.set('status', status) }
    const task = mode === 'checkout' ? catalog.products(query).then(page => { if (active) { setProducts(page.items); setTotal(page.total) } }) : Promise.all([api.history(query), user.role === 'ADMIN' ? employees() : Promise.resolve([])]).then(([page, people]) => { if (active) { setHistory(page.items); setHistoryTotal(page.total); setStaff(people) } })
    task.catch(error => { if (active) { if (error instanceof ApiError && error.status === 401) expired.current(); setError(error instanceof ApiError ? error.message : 'No pudimos consultar los datos locales. Volvé a intentar.') } }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [mode, search, offset, historyOffset, seller, status, revision, user.role])
  async function run(action: () => Promise<void>) {
    if (locked.current) return
    locked.current = true; setBusy(true); onBusyChange(true); setError(''); setNotice('')
    try { await action() }
    catch (error) { if (error instanceof ApiError && error.status === 401) onExpired(); setError(error instanceof Error && error.name !== 'TypeError' && error.name !== 'TimeoutError' ? error.message : 'No pudimos comprobar la respuesta. Si confirmaste una venta, reintentá el mismo intento para evitar duplicados.') }
    finally { locked.current = false; setBusy(false); onBusyChange(false) }
  }
  function changeCart(next: Draft[]) { if (busy || pending) return; setCart(next); setQuote(null); setError(''); setNotice('') }
  function add(product: Product) {
    const existing = cart.find(item => item.product_id === product.id)
    if ((!existing && cart.length >= 100) || (existing && existing.quantity === Number.MAX_SAFE_INTEGER)) { setError('El carrito alcanzó el límite admitido.'); return }
    changeCart(existing ? cart.map(item => item.product_id === product.id ? { ...item, quantity: item.quantity + 1 } : item) : [...cart, { product_id: product.id, name: product.name, code: product.code, quantity: 1 }])
  }
  async function confirmSale() {
    if (!pending && !quote) return
    const attempt = pending ?? { items: quote!.items.map(({ product_id, quantity }) => ({ product_id, quantity })), payment_method: method, quote_fingerprint: quote!.quote_fingerprint, idempotency_key: crypto.randomUUID() }
    // Persistir ANTES de enviar; si el navegador falla, no se envía una venta irrecuperable.
    api.savePending(user.id, attempt); setPending(attempt)
    let sale: Sale
    try { sale = await api.checkout(attempt, session.csrf_token) }
    catch (error) {
      // El servidor busca primero la clave. Estos rechazos prueban que no existe la venta
      // con ese pedido; auth/5xx/red/JSON inválido conservan el intento y bloquean otra venta.
      if (error instanceof ApiError && error.status === 409 && !error.message.includes('clave de venta')) { api.clearPending(user.id); setPending(null); setQuote(null) }
      throw error
    }
    api.clearPending(user.id); setPending(null); setCart([]); setQuote(null); setResult(sale); setRevision(value => value + 1)
  }
  function preview(event: FormEvent) {
    event.preventDefault()
    void run(async () => { setQuote(await api.quote(cart.map(({ product_id, quantity }) => ({ product_id, quantity })), session.csrf_token)) })
  }
  return <div className="sales-workspace">
    {error && <><Notice tone="error" focus>{error}</Notice><Button className="retry-query" variant="secondary" disabled={busy} onClick={() => { setError(''); setRevision(value => value + 1) }}>Volver a consultar</Button></>}{notice && <Notice focus>{notice}</Notice>}
    {mode === 'checkout' ? restored.error ? <Notice tone="error">{restored.error}</Notice> : result ? <><Receipt sale={result} /><Button className="new-sale" onClick={() => { setResult(null); setNotice(''); setError('') }}>Nueva venta</Button></> : <>
      {pending && <Panel className="pending-sale"><h2>Comprobar una venta pendiente</h2><p>Conservamos tu confirmación en esta pestaña. Reintentaremos la misma venta; si ya se registró, recuperaremos su comprobante sin duplicarla.</p><ul>{pending.items.map(item => <li key={item.product_id}>{cart.find(line => line.product_id === item.product_id)?.name ?? `Producto #${item.product_id}`} · {item.quantity} unidades</li>)}</ul><p>{api.paymentLabels[pending.payment_method]} · {pending.items.length} {pending.items.length === 1 ? 'producto' : 'productos'}</p><Button busy={busy} onClick={() => void run(confirmSale)}>{busy ? 'Comprobando…' : 'Reintentar la misma venta'}</Button></Panel>}
      {!pending && <div className="catalog-layout">
        <Panel className="checkout-products"><form onSubmit={event => { event.preventDefault(); setSearch(String(new FormData(event.currentTarget).get('search')).trim()); setOffset(0) }} className="checkout-search"><label>Buscar para vender<input type="search" name="search" placeholder="Nombre o código" maxLength={160} disabled={busy || !!pending} /></label><Button type="submit" disabled={busy || !!pending}>Buscar</Button></form>
          <div className="panel-heading"><h2>Productos disponibles</h2><span>{total} {total === 1 ? 'producto' : 'productos'}</span></div>
          {loading ? <p className="catalog-empty" role="status">Cargando productos…</p> : products.length ? <ul className="product-list">{products.map(product => <li key={product.id}><div className="product-info"><h3>{product.name}</h3><p>Código: {product.code ?? 'Sin código'} · {product.stock_quantity} unidades</p></div><div className="product-numbers"><strong>{catalog.formatMoney(product.price_cents)}</strong><Button variant="secondary" disabled={busy || !!pending || product.stock_quantity === 0} aria-label={`Agregar ${product.name} al carrito`} onClick={() => add(product)}>Agregar</Button></div></li>)}</ul> : <p className="catalog-empty">No hay productos disponibles para esta búsqueda.</p>}
          <div className="pagination"><Button variant="secondary" disabled={busy || !!pending || loading || offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Anterior</Button><span>Página {Math.floor(offset / 20) + 1}</span><Button variant="secondary" disabled={busy || !!pending || loading || offset + 20 >= total} onClick={() => setOffset(value => value + 20)}>Siguiente</Button></div>
        </Panel>
        <Panel className="cart-panel"><h2>Tu carrito</h2><p className="form-description">Revisá los precios y las cantidades antes de registrar el cobro.</p>
          <form onSubmit={preview} aria-label="Carrito"><fieldset disabled={busy || !!pending}>
            {cart.length ? <ul className="cart-list">{cart.map(item => <li key={item.product_id}><strong>{item.name}</strong><small>{item.code ?? 'Sin código'}</small><label>Cantidad de {item.name}<input type="number" min="1" step="1" value={item.quantity} onChange={event => { try { const quantity = catalog.parseQuantity(event.target.value); if (quantity < 1) throw new Error('La cantidad debe ser mayor que cero.'); changeCart(cart.map(line => line.product_id === item.product_id ? { ...line, quantity } : line)) } catch (error) { setError((error as Error).message) } }} /></label><Button type="button" variant="quiet" aria-label={`Quitar ${item.name} del carrito`} onClick={() => changeCart(cart.filter(line => line.product_id !== item.product_id))}>Quitar</Button></li>)}</ul> : <p className="catalog-empty">Agregá productos para empezar una venta.</p>}
            <label>Medio de pago declarado<select value={method} onChange={event => setMethod(event.target.value as PaymentMethod)}>{Object.entries(api.paymentLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
            <p className="form-description">Confirmá el cobro por tu cuenta. Registrar una transferencia o tarjeta no verifica el pago con un banco.</p>
            <Button type="submit" disabled={!cart.length} busy={busy}>{busy ? 'Consultando…' : 'Revisar importe'}</Button>
          </fieldset></form>
          {quote && !pending && <section className="quote-summary" aria-label="Revisión de venta"><h3 ref={quoteHeading} tabIndex={-1}>Revisá antes de confirmar</h3><ul>{quote.items.map(line => <li key={line.product_id}><span>{line.product_name_snapshot} · {line.quantity} × {catalog.formatMoney(line.unit_price_cents)}</span><strong>{catalog.formatMoney(line.subtotal_cents)}</strong></li>)}</ul><p className="quote-total">Total: <strong>{catalog.formatMoney(quote.total_cents)}</strong></p><p>{api.paymentLabels[method]} · Pago informado manualmente</p><Button busy={busy} onClick={() => void run(confirmSale)}>Confirmar venta y registrar cobro</Button></section>}
        </Panel>
      </div>}
    </> : <>
      <Panel className="history-filters"><h2>Buscar en el historial</h2><div>{user.role === 'ADMIN' && <label>Filtrar por persona<select value={seller} disabled={busy} onChange={event => { setSeller(event.target.value); setHistoryOffset(0); setDetail(null) }}><option value="">Todas las personas</option><option value={user.id}>{user.username} (administrador)</option>{staff.map(person => <option key={person.id} value={person.id}>{person.username}{!person.is_active ? ' (inactivo)' : ''}</option>)}</select></label>}<label>Estado de venta<select value={status} disabled={busy} onChange={event => { setStatus(event.target.value); setHistoryOffset(0); setDetail(null) }}><option value="">Todos los estados</option><option value="COMPLETED">Registradas</option><option value="VOIDED">Anuladas</option></select></label></div></Panel>
      <Panel className="history-list-panel"><div className="panel-heading"><h2>{user.role === 'ADMIN' ? 'Ventas del negocio' : 'Mis ventas'}</h2><span>{historyTotal} {historyTotal === 1 ? 'venta' : 'ventas'}</span></div>{loading ? <p className="catalog-empty" role="status">Cargando ventas…</p> : history.length ? <ul className="history-list">{history.map(sale => <li key={sale.id}><div><h3>Venta #{sale.id}</h3><p>{api.dateTime(sale.created_at_utc)} · {sale.username_snapshot}</p><span className="badge">{sale.status === 'VOIDED' ? 'Anulada' : 'Registrada'} · {api.paymentLabels[sale.payment_method]}</span></div><strong>{catalog.formatMoney(sale.total_cents)}</strong><Button variant="secondary" disabled={busy} aria-label={`Ver venta ${sale.id}`} onClick={() => void run(async () => { setDetail(await api.sale(sale.id)); setReason('') })}>Ver detalle</Button></li>)}</ul> : <p className="catalog-empty">No hay ventas para estos filtros.</p>}<div className="pagination"><Button variant="secondary" disabled={busy || loading || historyOffset === 0} onClick={() => setHistoryOffset(value => Math.max(0, value - 20))}>Anterior</Button><span>Página {Math.floor(historyOffset / 20) + 1}</span><Button variant="secondary" disabled={busy || loading || historyOffset + 20 >= historyTotal} onClick={() => setHistoryOffset(value => value + 20)}>Siguiente</Button></div></Panel>
      {detail && <><Receipt sale={detail} />{user.role === 'ADMIN' && detail.status === 'COMPLETED' && <Panel className="void-panel"><form aria-label="Anular venta" onSubmit={event => { event.preventDefault(); setConfirm(true) }}><h2>Anular venta #{detail.id}</h2><p>Se devolverán todas las unidades al inventario y se conservará la venta en el historial.</p><fieldset disabled={busy}><Field label="Motivo de anulación" hint="Entre 3 y 240 caracteres. Se registrará tu usuario." required minLength={3} maxLength={240} value={reason} onChange={event => setReason(event.target.value)} /><Button type="submit" variant="secondary">Revisar anulación</Button></fieldset></form></Panel>}</>}
    </>}
    {confirm && detail && <ConfirmDialog title={`¿Anular venta #${detail.id}?`} description={`Se repondrán las unidades una sola vez. Motivo: ${reason.trim()}`} confirmLabel="Confirmar anulación de venta" busy={busy} onCancel={() => setConfirm(false)} onConfirm={() => void run(async () => { try { setDetail(await api.voidSale(detail.id, reason.trim(), session.csrf_token)); setRevision(value => value + 1); setNotice('Venta anulada. Las unidades volvieron al inventario.') } finally { setConfirm(false) } })} />}
  </div>
}
