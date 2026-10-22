import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError } from './identity'
import { Button, Field, Notice, Panel } from './ui'
import { count, getReport, localInterval, money, percent } from './reporting'
import type { Filter, Metrics, Period, Report } from './reporting'

const labels: Record<keyof Metrics, string> = { revenue_cents: 'Facturación', sales: 'Ventas', average_cents: 'Ticket promedio', units: 'Unidades vendidas' }
const initial: Filter = { period: 'today', start: '', end: '' }
export default function ReportsWorkspace({ onExpired }: { onExpired: () => void }) {
  const [draft, setDraft] = useState(initial)
  const [filter, setFilter] = useState(initial)
  const [attempt, setAttempt] = useState(0)
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [order, setOrder] = useState<'units' | 'revenue'>('units')
  const [hourMetric, setHourMetric] = useState<'sales' | 'revenue_cents'>('sales')
  const result = useRef<HTMLHeadingElement>(null)
  const expired = useRef(onExpired)
  useEffect(() => { expired.current = onExpired }, [onExpired])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError(''); setReport(null)
    getReport(filter, controller.signal).then(value => {
      if (controller.signal.aborted) return
      setReport(value); setLoading(false)
    }).catch(e => {
      if (controller.signal.aborted) return
      if (e instanceof ApiError && e.status === 401) expired.current()
      setError(e instanceof Error ? e.message : 'No pudimos cargar el reporte.'); setLoading(false)
    })
    return () => controller.abort()
  }, [filter, attempt])
  useEffect(() => { if (report) result.current?.focus() }, [report])
  function apply(e: FormEvent) { e.preventDefault(); setFilter({ ...draft }); setAttempt(n => n + 1) }
  const ranking = report ? order === 'units' ? report.top_units : report.top_revenue : []
  const maximum = report?.hours.reduce((max, h) => BigInt(h[hourMetric]) > max ? BigInt(h[hourMetric]) : max, 0n) ?? 0n
  return <div className="reports">
    <Panel>
      <form className="report-filters" onSubmit={apply} aria-label="Período del reporte">
        <label className="field">Período<select value={draft.period} onChange={e => setDraft({ ...draft, period: e.target.value as Period })}>
          <option value="today">Hoy</option><option value="yesterday">Ayer</option><option value="7d">Últimos 7 días</option><option value="30d">Últimos 30 días</option><option value="custom">Rango personalizado</option>
        </select></label>
        {draft.period === 'custom' && <><Field label="Desde" hint="Primer día incluido." type="date" min="2000-01-01" max="2099-12-31" required value={draft.start} onChange={e => setDraft({ ...draft, start: e.target.value })} /><Field label="Hasta" hint="Último día incluido. Máximo 366 días." type="date" min="2000-01-01" max="2099-12-31" required value={draft.end} onChange={e => setDraft({ ...draft, end: e.target.value })} /></>}
        <Button type="submit" busy={loading}>Consultar</Button>
      </form>
      <p className="panel-note">Hora de Buenos Aires · ARS · Solo ventas completadas. Las anuladas quedan excluidas.</p>
    </Panel>
    {loading && <Panel><p role="status" className="catalog-empty">Cargando reporte…</p></Panel>}
    {error && <Panel><Notice tone="error" focus>{error}</Notice><Button onClick={() => setAttempt(n => n + 1)}>Reintentar reporte</Button></Panel>}
    {report && <>
      <div className="report-periods"><h2 ref={result} tabIndex={-1}>Resumen del período</h2><p><strong>Actual:</strong> {localInterval(report.period)}</p><p><strong>Anterior:</strong> {localInterval(report.previous_period)}</p><p>Misma extensión y corte horario local. Hoy se consulta hasta este momento. Consultá otra vez para actualizar.</p></div>
      {report.current.sales === '0' && <Notice>No hay ventas completadas en este período. Probá otras fechas.</Notice>}
      <div className="report-kpis">{(Object.keys(labels) as (keyof Metrics)[]).map(key => {
        const monetary = key === 'revenue_cents' || key === 'average_cents'
        const format = monetary ? money : count
        const change = report.comparison[key]
        return <Panel key={key} className="report-kpi"><h3>{labels[key]}</h3><p className="report-value">{format(report.current[key])}</p><p>Anterior: {format(report.previous[key])}</p><p>{percent(change.percent_bp)}</p><p className="report-delta">Diferencia: {format(change.delta)}</p></Panel>
      })}</div>
      <div className="report-details">
        <Panel><div className="report-panel-heading"><h2>Productos más vendidos</h2><label className="field">Ordenar por<select value={order} onChange={e => setOrder(e.target.value as typeof order)}><option value="units">Unidades</option><option value="revenue">Ingresos</option></select></label></div><p>Hasta 10 productos. Nombre y código de su última venta válida en el período.</p>
          {ranking.length ? <ol className="report-ranking">{ranking.map(product => <li key={product.product_id}><div><strong>{product.name}</strong><span>{product.code ? `Código ${product.code}` : `Producto #${product.product_id}`}</span></div><div><strong>{order === 'units' ? `${count(product.units)} unidades` : money(product.revenue_cents)}</strong><span>{order === 'units' ? money(product.revenue_cents) : `${count(product.units)} unidades`}</span></div></li>)}</ol> : <p className="catalog-empty">Sin productos vendidos.</p>}
        </Panel>
        <Panel><div className="report-panel-heading"><h2>Ventas por hora</h2><label className="field">Mostrar por hora<select value={hourMetric} onChange={e => setHourMetric(e.target.value as typeof hourMetric)}><option value="sales">Transacciones</option><option value="revenue_cents">Facturación</option></select></label></div>
          <p><strong>Hora pico por transacciones:</strong> {report.peak_hours.length ? report.peak_hours.map(h => `${String(h).padStart(2, '0')}:00`).join(', ') : 'Sin ventas'}.</p><p>Franjas de una hora en Buenos Aires; se suman los días del período.</p>
          <div className="report-hours"><table><caption>{hourMetric === 'sales' ? 'Cantidad de transacciones' : 'Facturación en ARS'} por hora local</caption><thead><tr><th scope="col">Hora</th><th scope="col">{hourMetric === 'sales' ? 'Ventas' : 'Monto'}</th></tr></thead><tbody>{report.hours.map(h => <tr key={h.hour}><th scope="row">{String(h.hour).padStart(2, '0')}:00</th><td><span className="hour-bar" aria-hidden="true" style={{ width: `${maximum ? Number(BigInt(h[hourMetric]) * 100n / maximum) : 0}%` }} /><span>{hourMetric === 'sales' ? count(h.sales) : money(h.revenue_cents)}</span></td></tr>)}</tbody></table></div>
        </Panel>
      </div>
    </>}
  </div>
}
