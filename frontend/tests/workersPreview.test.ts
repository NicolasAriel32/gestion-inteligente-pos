// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { expect, test, vi } from 'vitest'

test('the Workers build explains its limits without requesting credentials or calling the local API', async () => {
  vi.stubEnv('MODE', 'workers')
  const fetcher = vi.fn()
  vi.stubGlobal('fetch', fetcher)
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  const element = document.createElement('div')
  document.body.append(element)
  const root = createRoot(element)
  try {
    const { default: App } = await import('../src/App')
    await act(async () => { root.render(createElement(App)) })
    expect(element.textContent).toContain('Vista previa publicada')
    expect(element.textContent).toContain('no guarda operaciones ni permite iniciar sesión')
    expect(element.querySelectorAll('input')).toHaveLength(0)
    expect(element.querySelector('.spinner')).toBeNull()
    expect(fetcher).not.toHaveBeenCalled()
  } finally {
    await act(async () => { root.unmount() })
    element.remove()
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  }
})
