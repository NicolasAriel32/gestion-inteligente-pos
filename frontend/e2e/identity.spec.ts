import { test, expect } from '@playwright/test'
import type { ChildProcess } from 'node:child_process'
import { spawn, spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const frontend = resolve(import.meta.dirname, '..')
const backend = resolve(frontend, '../backend')
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
    await page.goto('http://127.0.0.1:5173')
    await expect(page.getByRole('status')).toHaveText('Servidor local conectado')
    await page.getByLabel('Secreto de inicialización').fill(setup)
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-owner-42')
    await page.getByRole('button', { name: 'Crear administrador', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Ingresar', exact: true })).toBeVisible()
    await page.getByLabel('Usuario', { exact: true }).fill('owner')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-owner-42')
    await page.getByRole('button', { name: 'Ingresar', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Sesión de owner' })).toBeVisible()
    await page.getByLabel('Usuario', { exact: true }).fill('worker')
    await page.getByLabel('Contraseña', { exact: true }).fill('E2e-password-worker-42')
    await page.getByRole('button', { name: 'Crear empleado', exact: true }).click()
    await expect(page.getByText('worker — Activo', { exact: true })).toBeVisible()
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
    await expect(page.getByText('worker — Activo', { exact: true })).toBeVisible()
    await worker.reload()
    await expect(worker.getByRole('heading', { name: 'Sesión de worker' })).toBeVisible()
    await page.getByRole('button', { name: 'Desactivar worker', exact: true }).click()
    await expect(page.getByText('worker — Inactivo', { exact: true })).toBeVisible()
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
