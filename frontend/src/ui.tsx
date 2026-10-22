import { useEffect, useId, useRef } from 'react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'

export function Icon({ name, className = '' }: { name: 'arrow' | 'users' | 'lock' | 'check' | 'exit' | 'plus' | 'alert'; className?: string }) {
  const paths = {
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    users: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 4v2" /></>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    exit: <><path d="M9 4H5v16h4M10 12h11m-5-5 5 5-5 5" /></>,
    plus: <path d="M12 5v14M5 12h14" />,
    alert: <><path d="m12 3 10 18H2L12 3ZM12 9v5" /><path d="M12 17v.1" /></>,
  }
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

export function Button({ children, variant = 'primary', busy = false, className = '', disabled, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'quiet'; busy?: boolean }) {
  return <button {...props} className={`button button--${variant} ${className}`} disabled={disabled || busy} aria-busy={busy || undefined}>
    {busy && <span className="spinner" aria-hidden="true" />}{children}
  </button>
}

export function Field({ label, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; hint: string }) {
  const id = useId()
  return <div className="field">
    <label htmlFor={id}>{label}</label>
    <input {...props} id={id} aria-describedby={`${id}-hint`} />
    <p className="field__hint" id={`${id}-hint`}>{hint}</p>
  </div>
}

export function Notice({ children, tone = 'success', focus = false }: { children: ReactNode; tone?: 'success' | 'error'; focus?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { if (focus) ref.current?.focus() }, [focus, children])
  return <div ref={ref} tabIndex={-1} className={`notice notice--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
    <Icon name={tone === 'error' ? 'alert' : 'check'} /><div>{children}</div>
  </div>
}

export function Panel({ children, className = '', ...props }: { children: ReactNode; className?: string; 'aria-labelledby'?: string }) {
  return <section className={`panel ${className}`} {...props}>{children}</section>
}

export function ConfirmDialog({ title: label, description: content, confirmLabel, busy, onCancel, onConfirm }: { title: string; description: string; confirmLabel: string; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const returnFocus = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null)
  const title = useId()
  const description = useId()
  useEffect(() => {
    const dialog = ref.current
    const target = returnFocus.current
    dialog?.showModal()
    return () => {
      dialog?.close()
      if (target?.isConnected) target.focus()
    }
  }, [])
  return <dialog ref={ref} className="confirm" aria-labelledby={title} aria-describedby={description} onCancel={event => { event.preventDefault(); if (!busy) onCancel() }} onKeyDown={event => {
    if (event.key !== 'Tab') return
    const buttons = Array.from(ref.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [])
    const first = buttons[0], last = buttons.at(-1)
    if (!first || !last) { event.preventDefault(); return }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus()
    }
  }}>
    <div className="section-icon"><Icon name="lock" /></div>
    <h2 id={title}>{label}</h2>
    <p id={description}>{content}</p>
    <div className="confirm__actions">
      <Button variant="secondary" autoFocus disabled={busy} onClick={onCancel}>Cancelar</Button>
      <Button busy={busy} onClick={onConfirm}>{busy ? 'Procesando…' : confirmLabel}</Button>
    </div>
  </dialog>
}

export function ConfirmDeactivation(props: { username: string; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <ConfirmDialog {...props} title={`¿Desactivar a ${props.username}?`} description="Esta persona ya no podrá ingresar. Sus registros se conservarán." confirmLabel="Confirmar desactivación" />
}
