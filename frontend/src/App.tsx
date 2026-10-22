import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { getHealth } from './api'
import * as identity from './identity'
import type { Credentials, Session, User } from './identity'
import './style.css'

function CredentialForm({ title, setup = false, submit }: {
  title: string; setup?: boolean; submit: (value: Credentials, token: string) => Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    setBusy(true); setError('')
    try {
      await submit({ username: String(data.get('username')), password: String(data.get('password')) },
                   String(data.get('setup_token') ?? ''))
      form.reset()
    } catch (error) { setError(error instanceof Error ? error.message : 'Error de conexión local') }
    finally { setBusy(false) }
  }
  return <form onSubmit={onSubmit}>
    <h2>{title}</h2>
    {setup && <label>Secreto de inicialización<input name="setup_token" type="password" required
      autoComplete="off" minLength={32} maxLength={128} /></label>}
    <label>Usuario<input name="username" required minLength={3} maxLength={32}
      pattern="[A-Za-z0-9_.\-]+" autoComplete={title === 'Ingresar' ? 'username' : 'off'} /></label>
    <label>Contraseña<input name="password" type="password" required minLength={12} maxLength={128}
      autoComplete={title === 'Ingresar' ? 'current-password' : 'new-password'} /></label>
    <small>Usuario: 3–32 letras, números, punto, guion o guion bajo. Contraseña: 12–128 caracteres.</small>
    <button disabled={busy} type="submit">{busy ? 'Procesando…' : title}</button>
    {error && <p role="alert">{error}</p>}
  </form>
}

export default function App() {
  const [health, setHealth] = useState('Comprobando conexión local...')
  const [initialized, setInitialized] = useState<boolean | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [staff, setStaff] = useState<User[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const refresh = useCallback(async () => {
    const [ready, current] = await Promise.all([identity.setupStatus(), identity.currentSession()])
    setInitialized(ready); setSession(current)
    setStaff(current?.user.role === 'ADMIN' ? await identity.employees() : [])
  }, [])
  useEffect(() => {
    let active = true
    getHealth().then(() => { if (active) setHealth('Servidor local conectado') })
      .catch(() => { if (active) setHealth('Servidor local no disponible') })
    refresh().catch(error => { if (active) setError(String(error)) })
    return () => { active = false }
  }, [refresh])
  async function authenticated(action: () => Promise<unknown>) {
    try { await action(); await refresh() }
    catch (error) {
      if (error instanceof identity.ApiError && error.status === 401) {
        setSession(null); setStaff([])
      }
      throw error
    }
  }
  async function buttonAction(action: () => Promise<unknown>) {
    setError('')
    try { await authenticated(action) }
    catch (error) { setError(error instanceof Error ? error.message : 'Error de conexión local') }
  }
  return <main>
    <h1>Gestión Inteligente POS</h1>
    <p>F2 — Identidad y usuarios</p><p role="status">{health}</p>
    {error && <p role="alert">{error}</p>}{notice && <p>{notice}</p>}
    {initialized === false && <>
      <p>Configuración inicial: usá el secreto generado localmente para crear al administrador.</p>
      <CredentialForm title="Crear administrador" setup submit={async (value, token) => {
        await identity.initialize(value, token)
        setNotice('Administrador creado. Eliminá el archivo del secreto e ingresá con tu cuenta.')
        await refresh()
      }} />
    </>}
    {initialized && !session && <CredentialForm title="Ingresar" submit={async value => {
      await identity.login(value); setNotice(''); await refresh()
    }} />}
    {session && <section>
      <h2>Sesión de {session.user.username}</h2><p>Rol: {session.user.role}</p>
      <button onClick={() => void buttonAction(() => identity.logout(session.csrf_token))}>
        Cerrar sesión
      </button>
      {session.user.role === 'ADMIN' && <>
        <CredentialForm title="Crear empleado" submit={async value => {
          await authenticated(() => identity.createEmployee(value, session.csrf_token))
        }} />
        <h2>Empleados</h2>
        {staff.length === 0 ? <p>No hay empleados.</p> : <ul>{staff.map(employee => <li key={employee.id}>
          <span>{employee.username} — {employee.is_active ? 'Activo' : 'Inactivo'}</span>
          {employee.is_active && <button aria-label={`Desactivar ${employee.username}`}
            onClick={() => void buttonAction(() => identity.deactivateEmployee(employee.id, session.csrf_token))}>
            Desactivar
          </button>}
        </li>)}</ul>}
      </>}
      {session.user.role === 'EMPLOYEE' && <p>Sesión iniciada. Las funciones comerciales aún no están disponibles.</p>}
    </section>}
    <p>La recuperación de credenciales todavía no está disponible. No borres los datos para recuperar acceso.</p>
  </main>
}
