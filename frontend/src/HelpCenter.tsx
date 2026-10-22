import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Button } from './ui'
import { findHelp, helpTopics } from './userHelp'
import type { HelpRole } from './userHelp'

function HelpDialog({ role, onClose, returnTo }: { role: HelpRole; onClose: () => void; returnTo: HTMLElement | null }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const search = useRef<HTMLInputElement>(null)
  const title = useId()
  const description = useId()
  const searchId = useId()
  const topicId = useId()
  const [query, setQuery] = useState('')
  const [topic, setTopic] = useState('')
  const results = findHelp(role, query, topic)
  const availableTopics = helpTopics.filter(value => findHelp(role, '', value).length > 0)
  useEffect(() => {
    const element = dialog.current
    const previousOverflow = document.body.style.overflow
    element?.showModal()
    search.current?.focus()
    document.body.style.overflow = 'hidden'
    return () => {
      element?.close()
      document.body.style.overflow = previousOverflow
      if (returnTo?.isConnected) returnTo.focus()
    }
  }, [returnTo])
  function containFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== 'Tab') return
    const controls = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input, select, summary') ?? []).filter(element => element.getClientRects().length > 0)
    const first = controls[0], last = controls.at(-1)
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }
  return <dialog ref={dialog} className="help-dialog" aria-labelledby={title} aria-describedby={description} onCancel={event => { event.preventDefault(); onClose() }} onKeyDown={containFocus}>
    <div className="help-dialog__header"><div><span className="eyebrow">GUÍA DE USO</span><h2 id={title}>Una mano para seguir.</h2><p id={description}>Pasos cortos y respuestas rápidas. Disponible sin internet.</p></div><Button variant="secondary" onClick={onClose}>Cerrar ayuda</Button></div>
    <div className="help-dialog__body">
      <div className="help-search"><div className="field"><label htmlFor={searchId}>Buscar en la ayuda</label><input ref={search} id={searchId} type="search" placeholder="Ej.: cambiar precio, stock, ticket…" value={query} onChange={event => setQuery(event.target.value)} /></div><div className="field"><label htmlFor={topicId}>Tema de ayuda</label><select id={topicId} value={topic} onChange={event => setTopic(event.target.value)}><option value="">Todos los temas</option>{availableTopics.map(value => <option key={value}>{value}</option>)}</select></div></div>
      <p className="help-scope">{role === 'ADMIN' ? 'Guías para administrador: productos, stock, ventas, equipo y reportes.' : role === 'EMPLOYEE' ? 'Guías para tu cuenta de empleado. Los precios, ajustes de stock y reportes los gestiona el administrador.' : 'Ayuda de acceso, conexión e impresión. Ingresá para ver las guías de tu cuenta.'}</p>
      <p className="help-result-count" role="status">{results.length === 1 ? '1 respuesta' : `${results.length} respuestas`}</p>
      {results.length ? <div className="help-articles">{results.map(article => <details key={article.id}>
        <summary><span>{article.topic}</span>{article.title}</summary>
        <div className="help-answer"><p>{article.summary}</p><ol>{article.steps.map((step, index) => <li key={index}>{step}</li>)}</ol>{article.note && <p className="help-note">{article.note}</p>}</div>
      </details>)}</div> : <div className="help-empty"><h3>No encontramos una respuesta.</h3><p>Probá con otra palabra o elegí Todos los temas.</p><Button variant="secondary" onClick={() => { setQuery(''); setTopic(''); search.current?.focus() }}>Ver todas las guías</Button></div>}
      <p className="help-footer">Esta ayuda explica cómo usar las pantallas. Las operaciones las confirmás vos desde cada sección.</p>
    </div>
  </dialog>
}

export default function HelpCenter({ role, disabled }: { role: HelpRole; disabled: boolean }) {
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  return <>
    <Button className="help-trigger" variant="secondary" disabled={disabled} aria-label="Abrir ayuda" aria-haspopup="dialog" aria-expanded={open} title="Ayuda y guías rápidas" onClick={event => { trigger.current = event.currentTarget; setOpen(true) }}><span aria-hidden="true">?</span></Button>
    {open && <HelpDialog role={role} onClose={() => setOpen(false)} returnTo={trigger.current} />}
  </>
}
