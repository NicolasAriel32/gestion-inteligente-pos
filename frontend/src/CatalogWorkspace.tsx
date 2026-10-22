import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { Session } from './identity'
import { ApiError } from './identity'
import * as api from './catalog'
import type { Category, Product, Movement, ProductInput } from './catalog'
import { Button, ConfirmDialog, Field, Notice, Panel } from './ui'

export default function CatalogWorkspace({ session, mode, onBusyChange, onExpired }: {
  session: Session; mode: 'catalog' | 'inventory'; onBusyChange: (busy: boolean) => void; onExpired: () => void
}) {
  const admin = session.user.role === 'ADMIN'
  const [categories, setCategories] = useState<Category[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [activeOnly, setActiveOnly] = useState(true)
  const [low, setLow] = useState(false)
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState<Product | null>(null)
  const [editingCategory, setEditingCategory] = useState<Category | null>(null)
  const [selected, setSelected] = useState<Product | null>(null)
  const [movements, setMovements] = useState<Movement[]>([])
  const [movementTotal, setMovementTotal] = useState(0)
  const [confirm, setConfirm] = useState<{ type: 'product' | 'category'; id: number; name: string } | null>(null)
  const pending = useRef(false)
  const request = useRef<{ fingerprint: string; key: string } | null>(null)
  const selectedId = selected?.id
  const expired = useRef(onExpired)
  expired.current = onExpired
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    const query = new URLSearchParams({ search, active_only: String(activeOnly), low_stock: String(low), limit: '20', offset: String(offset) })
    if (category) query.set('category_id', category)
    Promise.all([api.categories(), api.products(query)]).then(([cats, page]) => {
      if (active) { setCategories(cats); setProducts(page.items); setTotal(page.total) }
    }).catch(error => {
      if (!active) return
      if (error instanceof ApiError && error.status === 401) expired.current()
      setError(error instanceof ApiError ? error.message : 'No pudimos cargar el catálogo. Volvé a intentar.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [search, category, activeOnly, low, offset, revision])
  useEffect(() => {
    let active = true
    if (!selectedId || mode !== 'inventory') return
    Promise.all([api.product(selectedId), api.movements(selectedId)]).then(([product, page]) => {
      if (active) { setSelected(product); setMovements(page.items); setMovementTotal(page.total) }
    }).catch(error => {
      if (!active) return
      if (error instanceof ApiError && error.status === 401) expired.current()
      setError(error instanceof ApiError ? error.message : 'No pudimos consultar los movimientos.')
    })
    return () => { active = false }
  }, [selectedId, mode, revision])

  async function run(action: () => Promise<string>) {
    if (pending.current) return
    pending.current = true; setBusy(true); onBusyChange(true); setError(''); setNotice('')
    try { setNotice(await action()); setConfirm(null); setRevision(value => value + 1) }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) onExpired()
      setConfirm(null)
      setError(error instanceof Error ? error.message : 'No se pudo completar. Intentá nuevamente.')
    } finally { pending.current = false; setBusy(false); onBusyChange(false) }
  }
  function submitProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget, data = new FormData(form)
    void run(async () => {
      const cost = String(data.get('cost') ?? '').trim()
      const payload: ProductInput = {
        name: String(data.get('name')).trim(), code: String(data.get('code') ?? '').trim() || null,
        category_id: data.get('category_id') ? Number(data.get('category_id')) : null,
        price_cents: api.parseMoney(String(data.get('price'))), cost_cents: cost ? api.parseMoney(cost) : null,
        minimum_stock: api.parseQuantity(String(data.get('minimum_stock'))),
      }
      if (!editing) {
        payload.initial_stock = api.parseQuantity(String(data.get('initial_stock')))
        payload.initial_reason = String(data.get('initial_reason') ?? '').trim() || null
        if (payload.initial_stock && (!payload.initial_reason || payload.initial_reason.length < 3)) throw new Error('Indicá el motivo de la carga inicial (al menos 3 caracteres).')
      }
      await api.saveProduct(payload, session.csrf_token, editing?.id)
      const message = editing ? 'Los cambios del producto quedaron guardados.' : 'Producto creado. Ya forma parte de tu catálogo.'
      setEditing(null); form.reset()
      return message
    })
  }
  function submitAdjustment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected) return
    const form = event.currentTarget, data = new FormData(form), target = selected
    void run(async () => {
      const delta = api.parseQuantity(String(data.get('delta')), true)
      const reason = String(data.get('reason')).trim()
      if (delta === 0) throw new Error('El ajuste debe sumar o restar unidades.')
      const fingerprint = JSON.stringify([target.id, delta, reason])
      if (request.current?.fingerprint !== fingerprint) request.current = { fingerprint, key: crypto.randomUUID() }
      const movement = await api.adjust(target.id, delta, reason, request.current.key, session.csrf_token)
      request.current = null; form.reset()
      return `Ajuste registrado: ${movement.stock_before} → ${movement.stock_after} unidades. Movimiento #${movement.id}.`
    })
  }
  const resetFilters = () => setOffset(0)
  return <div className="catalog-workspace">
    {error && <Notice tone="error" focus>{error}</Notice>}
    {notice && <Notice focus>{notice}</Notice>}
    <Panel className="catalog-filters">
      <form onSubmit={event => { event.preventDefault(); setSearch(String(new FormData(event.currentTarget).get('search')).trim()); resetFilters() }}>
        <label>Buscar producto<input name="search" type="search" placeholder="Nombre o código" maxLength={160} disabled={busy} /></label>
        <Button type="submit" disabled={busy}>Buscar</Button>
      </form>
      <label>Filtrar categoría<select value={category} disabled={busy} onChange={event => { setCategory(event.target.value); resetFilters() }}><option value="">Todas las categorías</option>{categories.map(cat => <option key={cat.id} value={cat.id}>{cat.name}{!cat.is_active ? ' (inactiva)' : ''}</option>)}</select></label>
      <label className="check-label"><input type="checkbox" checked={low} disabled={busy} onChange={event => { setLow(event.target.checked); resetFilters() }} />Solo stock bajo</label>
      {admin && <label className="check-label"><input type="checkbox" checked={!activeOnly} disabled={busy} onChange={event => { setActiveOnly(!event.target.checked); resetFilters() }} />Incluir inactivos</label>}
    </Panel>
    <div className={admin ? 'catalog-layout' : ''}>
      <Panel className="product-panel" aria-labelledby="products-title">
        <div className="panel-heading"><div><h2 id="products-title">{mode === 'inventory' ? 'Existencias' : 'Productos'}</h2><p>{total} productos encontrados</p></div></div>
        {loading ? <p className="catalog-empty" role="status">Cargando productos…</p> : products.length === 0 ? <p className="catalog-empty">No hay productos para estos filtros.{admin && mode === 'catalog' ? ' Creá el primero desde el formulario.' : ''}</p> : <ul className="product-list">{products.map(product => <li key={product.id}>
          <div className="product-info"><h3>{product.name}</h3><p>Código: {product.code ?? 'Sin código'} · {categories.find(cat => cat.id === product.category_id)?.name ?? (product.category_id === null ? 'Sin categoría' : 'Categoría no disponible')}</p><span className={`badge ${!product.is_active ? 'badge--inactive' : ''}`}>{!product.is_active ? 'Inactivo' : product.stock_quantity <= product.minimum_stock ? 'Stock bajo' : 'Activo'}</span></div>
          <div className="product-numbers"><strong>{api.formatMoney(product.price_cents)}</strong><span>{product.stock_quantity} unidades · mínimo {product.minimum_stock}</span>{admin && product.cost_cents !== null && <small>Costo: {api.formatMoney(product.cost_cents)}</small>}</div>
          {admin && <div className="product-actions">{mode === 'inventory' ? <Button variant="secondary" disabled={busy || !product.is_active} aria-label={`Ajustar stock de ${product.name}`} onClick={() => { setSelected(product); setMovements([]); setMovementTotal(0); setRevision(value => value + 1); setNotice(''); setError('') }}>Ajustar</Button> : <>
            <Button variant="secondary" disabled={busy} aria-label={`Editar producto ${product.name}`} onClick={() => { setEditing(product); setNotice(''); setError('') }}>Editar</Button>
            <Button variant="quiet" disabled={busy} aria-label={`${product.is_active ? 'Desactivar' : 'Reactivar'} producto ${product.name}`} onClick={() => product.is_active ? setConfirm({ type: 'product', id: product.id, name: product.name }) : void run(async () => { await api.productActive(product.id, true, session.csrf_token); return 'Producto reactivado.' })}>{product.is_active ? 'Desactivar' : 'Reactivar'}</Button>
          </>}</div>}
        </li>)}</ul>}
        <div className="pagination"><Button variant="secondary" disabled={busy || loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Anterior</Button><span>Página {Math.floor(offset / 20) + 1}</span><Button variant="secondary" disabled={busy || loading || offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Siguiente</Button></div>
      </Panel>
      {admin && (mode === 'catalog' ? <Panel className="catalog-editor">
        <form key={editing?.id ?? 'new'} onSubmit={submitProduct} aria-label={editing ? 'Editar producto' : 'Crear producto'}>
          <h2>{editing ? 'Editar producto' : 'Crear producto'}</h2><p className="form-description">Precio de venta en pesos. El stock se registra con su movimiento.</p>
          <fieldset disabled={busy}>
            <Field label="Nombre del producto" hint="Entre 1 y 160 caracteres." name="name" defaultValue={editing?.name} maxLength={160} required />
            <Field label="Código" hint="Opcional. Conserva ceros iniciales; no se repite." name="code" defaultValue={editing?.code ?? ''} maxLength={64} />
            <label>Categoría<select name="category_id" defaultValue={editing?.category_id ?? ''}><option value="">Sin categoría</option>{categories.map(cat => <option key={cat.id} value={cat.id} disabled={!cat.is_active && cat.id !== editing?.category_id}>{cat.name}{!cat.is_active ? ' (inactiva)' : ''}</option>)}</select></label>
            <div className="field-pair"><Field label="Precio de venta (ARS)" hint="Sin miles; hasta 2 decimales." name="price" inputMode="decimal" placeholder="0,00" defaultValue={editing ? api.moneyInput(editing.price_cents) : ''} required /><Field label="Costo (ARS)" hint="Opcional; solo visible para ADMIN." name="cost" inputMode="decimal" placeholder="0,00" defaultValue={editing?.cost_cents != null ? api.moneyInput(editing.cost_cents) : ''} /></div>
            <Field label="Stock mínimo" hint="Alerta cuando las unidades llegan a este valor." name="minimum_stock" type="number" min="0" step="1" defaultValue={editing?.minimum_stock ?? 0} required />
            {!editing && <><Field label="Stock inicial" hint="Unidades enteras. Puede empezar en cero." name="initial_stock" type="number" min="0" step="1" defaultValue="0" required /><Field label="Motivo de carga inicial" hint="Obligatorio al cargar unidades; entre 3 y 240 caracteres." name="initial_reason" maxLength={240} /></>}
            <Button type="submit" busy={busy}>{busy ? 'Guardando…' : editing ? 'Guardar producto' : 'Crear producto'}</Button>
            {editing && <Button variant="secondary" onClick={() => setEditing(null)} type="button">Cancelar edición</Button>}
          </fieldset>
        </form>
      </Panel> : <Panel className="catalog-editor">
        <h2>Ajustar existencias</h2>
        {selected ? <><p className="selected-product"><strong>{selected.name}</strong><br />Stock consultado: {selected.stock_quantity} unidades.</p><form onSubmit={submitAdjustment} key={selected.id} aria-label="Ajustar existencias"><fieldset disabled={busy || !selected.is_active}>
          <Field label="Cambio de unidades" hint="Positivo para sumar; negativo para restar. Sin decimales." name="delta" type="number" step="1" placeholder="Ej.: 5 o -2" required />
          <Field label="Motivo del ajuste" hint="Explicá por qué cambia el stock (3–240 caracteres)." name="reason" minLength={3} maxLength={240} required />
          <p className="form-description">Se registrará tu usuario y el stock antes/después. El servidor confirma el resultado.</p>
          <Button type="submit" busy={busy}>{busy ? 'Registrando…' : 'Confirmar ajuste'}</Button>
        </fieldset></form><h3 className="movement-heading">Movimientos de {selected.name}</h3><p className="form-description">{movementTotal > 100 ? `Últimos 100 de ${movementTotal} movimientos.` : `${movementTotal} movimientos registrados.`}</p><ol className="movement-list">{movements.map(movement => <li key={movement.id}><strong>{movement.stock_before} → {movement.stock_after} unidades</strong><span>{movement.reason}</span><small>{new Date(movement.created_at_utc).toLocaleString('es-AR')} · Usuario #{movement.performed_by}</small></li>)}</ol></> : <p className="catalog-empty">Elegí Ajustar en un producto para consultar sus movimientos y registrar un cambio.</p>}
      </Panel>)}
    </div>
    {admin && mode === 'catalog' && <Panel className="category-panel" aria-labelledby="categories-title">
      <div><h2 id="categories-title">Categorías</h2><p>Organizá productos sin perder su historial.</p></div>
      <form key={editingCategory?.id ?? 'new-category'} onSubmit={event => {
        event.preventDefault(); const form = event.currentTarget; const name = String(new FormData(form).get('category_name')).trim()
        void run(async () => { await api.saveCategory(name, session.csrf_token, editingCategory?.id); setEditingCategory(null); form.reset(); return 'Categoría guardada.' })
      }}><fieldset disabled={busy}><Field label="Nombre de categoría" hint="Hasta 100 caracteres; no se repite." name="category_name" maxLength={100} defaultValue={editingCategory?.name ?? ''} required /><div className="category-actions"><Button type="submit" busy={busy}>{editingCategory ? 'Guardar categoría' : 'Crear categoría'}</Button>{editingCategory && <Button type="button" variant="secondary" onClick={() => setEditingCategory(null)}>Cancelar</Button>}</div></fieldset></form>
      <ul className="category-list">{categories.map(cat => <li key={cat.id}><span>{cat.name} · {cat.is_active ? 'Activa' : 'Inactiva'}</span><Button variant="secondary" disabled={busy} aria-label={`Editar categoría ${cat.name}`} onClick={() => setEditingCategory(cat)}>Editar</Button><Button variant="quiet" disabled={busy} aria-label={`${cat.is_active ? 'Desactivar' : 'Reactivar'} categoría ${cat.name}`} onClick={() => cat.is_active ? setConfirm({ type: 'category', id: cat.id, name: cat.name }) : void run(async () => { await api.categoryActive(cat.id, true, session.csrf_token); return 'Categoría reactivada.' })}>{cat.is_active ? 'Desactivar' : 'Reactivar'}</Button></li>)}</ul>
    </Panel>}
    {confirm && <ConfirmDialog title={`¿Desactivar ${confirm.name}?`} description={confirm.type === 'category' ? 'Sus productos conservan su estado. La categoría no estará disponible para asignar nuevos productos.' : 'Se conservará el historial. El producto no admitirá ajustes mientras esté inactivo.'} confirmLabel={confirm.type === 'category' ? 'Desactivar categoría' : 'Desactivar producto'} busy={busy} onCancel={() => setConfirm(null)} onConfirm={() => void run(async () => { if (confirm.type === 'category') await api.categoryActive(confirm.id, false, session.csrf_token); else await api.productActive(confirm.id, false, session.csrf_token); if (editing?.id === confirm.id && confirm.type === 'product') setEditing(null); return 'Desactivación guardada. El historial se conserva.' })} />}
  </div>
}
