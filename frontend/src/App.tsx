import { useEffect, useState } from 'react'
import { getHealth } from './api'
export default function App() {
  const [status, setStatus] = useState('Comprobando conexión local...')
  useEffect(() => {
    let active = true
    getHealth().then(() => { if (active) setStatus('Servidor local conectado') })
      .catch(() => { if (active) setStatus('Servidor local no disponible') })
    return () => { active = false }
  }, [])
  return <main><h1>Gestión Inteligente POS</h1><p>F1 — esqueleto técnico (sin ventas)</p><p role="status">{status}</p></main>
}
