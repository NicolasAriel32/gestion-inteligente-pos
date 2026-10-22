import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import type { ChildProcess } from 'node:child_process'
import { spawn, spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const frontend = resolve(import.meta.dirname, '..')
const backend = resolve(frontend, '../backend')
const captures = process.env.POS_CAPTURE_DIR
const python = process.env.POS_TEST_PYTHON ?? join(backend, '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')

async function assertFree(port: number) {
  await new Promise<void>((resolve, reject) => {
    const server = createServer()
    server.once('error', reject)
    server.listen(port, '127.0.0.1', () => server.close(error => error ? reject(error) : resolve()))
  })
}
async function ready(url: string, process: ChildProcess) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (process.exitCode !== null) throw new Error('El servicio local terminó antes de iniciar')
    if (await fetch(url).then(response => response.ok).catch(() => false)) return
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('El servicio local no inició a tiempo')
}
async function stop(child?: ChildProcess) {
  if (!child || child.exitCode !== null) return
  const exited = new Promise<void>(resolve => child.once('exit', () => resolve()))
  child.kill('SIGTERM')
  await exited
}

async function screenshot(page: Page, name: string) {
  if (!captures) return
  mkdirSync(captures, { recursive: true })
  // Las capturas solo se toman con campos secretos vacíos.
  expect(await page.locator('input[type="password"]').evaluateAll(inputs => inputs.every(input => !(input as HTMLInputElement).value))).toBe(true)
  await page.screenshot({ path: join(captures, `${name}.png`), fullPage: true })
}
async function accessible(page: Page) {
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}
async function screens(page: Page, name: string) {
  await page.setViewportSize({ width: 1366, height: 768 })
  await accessible(page)
  await screenshot(page, `${name}-desktop`)
  await page.setViewportSize({ width: 390, height: 844 })
  await accessible(page)
  await screenshot(page, `${name}-mobile`)
  await page.setViewportSize({ width: 320, height: 740 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.setViewportSize({ width: 1366, height: 768 })
}

test('identidad local completa, permisos, reinicio y revocación sin red externa', async ({ browser }) => {
  await assertFree(8765)
  await assertFree(5173)
  const root = mkdtempSync(join(tmpdir(), 'pos-f2-e2e-'))
  const env = { ...process.env, LOCALAPPDATA: root }
  let api: ChildProcess | undefined
  let vite: ChildProcess | undefined
  const external: string[] = []
  const errors: string[] = []
  const context = await browser.newContext()
  const workerContext = await browser.newContext()
  for (const current of [context, workerContext]) {
    await current.route('**/*', route => {
      const hostname = new URL(route.request().url()).hostname
      if (!['127.0.0.1', 'localhost'].includes(hostname)) {
        external.push(hostname)
        return route.abort()
      }
      return route.continue()
    })
  }
  try {
    for (const args of [['-m', 'alembic', '-c', 'alembic.ini', 'upgrade', 'head'], ['-m', 'app.bootstrap']]) {
      const result = spawnSync(python, args, { cwd: backend, env, encoding: 'utf8' })
      if (result.status !== 0) throw new Error('Falló la preparación aislada de SQLite')
    }
    const setup = readFileSync(join(root, 'GestionInteligentePOS/config/setup-token.txt'), 'utf8')
    const startApi = () => spawn(python, ['-m', 'app'], { cwd: backend, env, stdio: 'ignore' })
    api = startApi()
    vite = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--strictPort'], {
      cwd: frontend, env, stdio: 'ignore',
    })
    await Promise.all([ready('http://127.0.0.1:8765/api/health', api), ready('http://127.0.0.1:5173', vite)])
    const page = await context.newPage()
    page.on('pageerror', error => errors.push(error.message))
    await page.setViewportSize({ width: 1366, height: 768 })
    const fonts: string[] = []
    page.on('response', response => { if (response.url().endsWith('.woff2') && response.status() === 200) fonts.push(response.url()) })
    await page.goto('http://127.0.0.1:5173')
    await expect(page.getByRole('status')).toHaveText('Servidor local conectado')
    await page.getByLabel('Secreto de inicialización').waitFor()
    await page.evaluate(() => document.fonts.ready)
    expect(fonts).toHaveLength(1)
    expect(new URL(fonts[0]).origin).toBe('http://127.0.0.1:5173')
    const cdp = await context.newCDPSession(page)
    await cdp.send('DOM.enable'); await cdp.send('CSS.enable')
    const { root: documentNode } = await cdp.send('DOM.getDocument')
    const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: documentNode.nodeId, selector: 'h1' })
    const renderedFonts = await cdp.send('CSS.getPlatformFontsForNode', { nodeId })
    // La fuente variable conserva el nombre interno de su instancia base 200.
    // CSS selecciona el peso 800 del título; no es una fuente de sistema.
    expect(await page.locator('h1').evaluate(element => getComputedStyle(element).fontWeight)).toBe('800')
    expect(renderedFonts.fonts.some(font => font.familyName === 'Manrope ExtraLight' && font.isCustomFont && font.glyphCount > 0)).toBe(true)
    await cdp.detach()
    await screens(page, 'setup')
    await page.getByRole('link', { name: 'Ir al contenido' }).focus()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('main')).toBeFocused()
    await page.getByLabel('Secreto de inicialización').fill(setup)
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-owner-42')
    await page.getByRole('button', { name: 'Crear administrador', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Ingresar', exact: true })).toBeVisible()
    await screens(page, 'login')
    // Comprobar error real de credenciales y foco en el mensaje.
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('Wrong-test-password-42')
    await page.getByRole('button', { name: 'Ingresar', exact: true }).click()
    await expect(page.getByRole('alert')).toHaveText('Usuario o contraseña incorrectos')
    await expect(page.getByRole('alert')).toBeFocused()
    await page.getByLabel('Usuario', { exact: true }).clear()
    await page.getByLabel('Contraseña', { exact: true }).clear()
    await accessible(page)
    await screenshot(page, 'login-error-desktop')
    // Orden de teclado y foco visible en controles.
    await page.getByRole('heading', { level: 1 }).focus()
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Usuario', { exact: true })).toBeFocused()
    expect(await page.getByLabel('Usuario', { exact: true }).evaluate(element => getComputedStyle(element).outlineWidth)).toBe('3px')
    await page.keyboard.press('Tab')
    await expect(page.getByLabel('Contraseña', { exact: true })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'Ingresar', exact: true })).toBeFocused()
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-owner-42')
    let releaseLogin!: () => void
    const loginGate = new Promise<void>(resolve => { releaseLogin = resolve })
    let submissions = 0
    await page.route('**/api/auth/login', async route => { submissions++; await loginGate; await route.continue() })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.getByRole('button', { name: 'Ingresar', exact: true }).press('Enter')
    try {
      await expect(page.getByRole('button', { name: 'Procesando…' })).toBeDisabled()
      await expect(page.getByLabel('Usuario', { exact: true })).toBeDisabled()
      expect(await page.locator('.spinner').evaluate(element => getComputedStyle(element).animationName)).toBe('none')
      expect(await page.locator('button[type="submit"]').evaluate(element => getComputedStyle(element).transitionDuration)).toBe('0s')
      await page.locator('form').evaluate(form => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
      expect(submissions).toBe(1)
    } finally { releaseLogin() }
    await page.emulateMedia({ reducedMotion: 'no-preference' })

    await expect(page.getByRole('heading', { name: 'Sesión de owner' })).toBeVisible()
    await page.getByLabel('Usuario', { exact: true }).fill('worker')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-worker-42')
    await page.getByRole('button', { name: 'Crear empleado', exact: true }).click()
    await expect(page.getByRole('listitem').filter({ has: page.getByText('worker', { exact: true }) }).getByText('Activo', { exact: true })).toBeVisible()
    await expect(page.getByLabel('Usuario', { exact: true })).toBeFocused()
    await screens(page, 'employees')
    const worker = await workerContext.newPage()
    worker.on('pageerror', error => errors.push(error.message))
    await worker.goto('http://127.0.0.1:5173')
    await worker.getByLabel('Usuario', { exact: true }).fill('worker')
    await worker.getByLabel('Contraseña', { exact: true }).fill('E2e-password-worker-42')
    await worker.getByRole('button', { name: 'Ingresar', exact: true }).click()
    await expect(worker.getByRole('heading', { name: 'Sesión de worker' })).toBeVisible()
    await expect(worker.getByRole('button', { name: 'Crear empleado', exact: true })).toHaveCount(0)
    expect(await worker.evaluate(async () => (await fetch('/api/employees')).status)).toBe(403)
    // Reinicio real del proceso Python manteniendo DB y cookies del navegador.
    await stop(api)
    api = startApi()
    await ready('http://127.0.0.1:8765/api/health', api)
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Sesión de owner' })).toBeVisible()
    await expect(page.getByRole('listitem').filter({ has: page.getByText('worker', { exact: true }) }).getByText('Activo', { exact: true })).toBeVisible()
    await worker.reload()
    await expect(worker.getByRole('heading', { name: 'Sesión de worker' })).toBeVisible()
    await page.getByRole('button', { name: 'Desactivar worker', exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Cancelar', exact: true })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Desactivar worker', exact: true })).toBeFocused()
    await page.getByRole('button', { name: 'Desactivar worker', exact: true }).press('Enter')
    await accessible(page)
    await screenshot(page, 'deactivate-desktop')
    await page.getByRole('button', { name: 'Cancelar', exact: true }).press('Tab')
    await expect(page.getByRole('button', { name: 'Confirmar desactivación', exact: true })).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'Cancelar', exact: true })).toBeFocused()
    await page.keyboard.press('Shift+Tab')
    await page.keyboard.press('Enter')
    await expect(page.getByRole('listitem').filter({ has: page.getByText('worker', { exact: true }) }).getByText('Inactivo', { exact: true })).toBeVisible()
    await worker.reload()
    await expect(worker.getByRole('heading', { name: 'Ingresar', exact: true })).toBeVisible()
    await worker.getByLabel('Usuario', { exact: true }).fill('worker')
    await worker.getByLabel('Contraseña', { exact: true }).fill('E2e-password-worker-42')
    await worker.getByRole('button', { name: 'Ingresar', exact: true }).click()
    await expect(worker.getByRole('alert')).toHaveText('Usuario o contraseña incorrectos')
    await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Ingresar', exact: true })).toBeVisible()
    expect(external).toEqual([])
    expect(errors).toEqual([])
  } finally {
    await context.close()
    await workerContext.close()
    await stop(vite)
    await stop(api)
    // Solo se elimina el directorio temporal creado por esta prueba.
    rmSync(root, { recursive: true, force: true })
  }
})
