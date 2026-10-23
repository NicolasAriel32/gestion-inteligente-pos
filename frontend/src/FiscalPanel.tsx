import { useEffect, useState } from 'react'
import { ApiError } from './identity'
import * as api from './fiscal'
import type { Access, Connection, FiscalStatus } from './fiscal'
import { Button, Field, Notice, Panel } from './ui'

export default function FiscalPanel({ csrf, disabled, run, onExpired }: {
  csrf: string; disabled: boolean; run: (action: () => Promise<void>) => Promise<void>; onExpired: () => void
}) {
  const [status, setStatus] = useState<FiscalStatus | null>(null)
  const [error, setError] = useState('')
  const [connection, setConnection] = useState<Connection | null>(null)
  const [access, setAccess] = useState<Access | null>(null)
  const [password, setPassword] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let active = true
    api.status(csrf).then(value => { if (active) { setStatus(value); setError('') } }).catch(e => {
      if (!active) return
      if (e instanceof ApiError && e.status === 401) onExpired()
      setError(e instanceof Error ? e.message : 'No pudimos consultar la configuración local de ARCA.')
    })
    return () => { active = false }
  }, [csrf, revision, onExpired])
  return <Panel className="tools-panel fiscal-panel">
    <h2>ARCA · conexión de prueba</h2>
    <Notice>Homologación. Este módulo todavía no emite facturas. Los tickets del POS siguen siendo comprobantes no fiscales.</Notice>
    <p>La gestión local funciona sin internet. Las comprobaciones siguientes usan internet solo al presionar el botón; no verifican actualizaciones.</p>
    {error && <Notice tone="error">{error}</Notice>}
    {!status && !error && <p role="status">Consultando configuración fiscal local…</p>}
    {status?.configuration_error && <Notice tone="error">{status.configuration_error}</Notice>}
    {status?.configured ? <><p>Certificado de prueba configurado para CUIT <strong>{status.cuit}</strong>. Clave local cifrada.</p><p>Vence: {new Date(status.certificate_expires_at!).toLocaleString('es-AR')}. Producción deshabilitada.</p></> : <p>Para verificar acceso, cerrá el POS y usá «Configurar ARCA homologación» en el menú de Windows con tu cuenta ADMIN. Necesitás certificado de homologación asociado a wsfe en WSASS. Consultá la guía incluida; no compartas claves por chat.</p>}
    <div className="backup-actions"><Button disabled={disabled} onClick={() => void run(async () => { setConnection(null); setConnection(await api.connection(csrf)) })}>Comprobar conexión ARCA</Button><Button variant="secondary" disabled={disabled} onClick={() => setRevision(n => n + 1)}>Revisar configuración local</Button></div>
    {connection && <Notice tone={connection.healthy ? 'success' : 'error'}>{connection.healthy ? 'ARCA homologación respondió correctamente.' : 'ARCA homologación informa una incidencia.'} Aplicación: {connection.application}; base: {connection.database}; autenticación: {connection.authentication}. Esto no verifica el certificado ni habilita facturas.</Notice>}
    <form onSubmit={event => { event.preventDefault(); const secret = password; setPassword(''); void run(async () => { setAccess(null); setAccess(await api.access(csrf, secret)) }) }}>
      <Field label="Contraseña local de la clave de homologación" hint="La elegiste al configurar el certificado. No es tu clave fiscal de ARCA. Se usa para esta consulta y no se guarda." type="password" autoComplete="off" required minLength={12} maxLength={128} value={password} disabled={disabled || !status?.configured} onChange={event => setPassword(event.target.value)} />
      <Button type="submit" disabled={disabled || !status?.configured || password.length < 12}>Verificar acceso y puntos de venta</Button>
    </form>
    {access && <><Notice>Acceso a homologación verificado. Ticket válido hasta {new Date(access.ticket_expires_at).toLocaleString('es-AR')}. No se emitió ninguna factura.</Notice>{access.points.length ? <ul>{access.points.map(point => <li key={point.number}>Punto {point.number} · {point.emission_type} · {point.blocked ? 'Bloqueado' : 'Sin bloqueo'}{point.disabled_date ? ` · Baja: ${point.disabled_date}` : ''}</li>)}</ul> : <p>ARCA no devolvió puntos de venta. Revisá su habilitación en homologación.</p>}</>}
  </Panel>
}
