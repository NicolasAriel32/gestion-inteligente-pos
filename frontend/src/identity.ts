export type User = { id: number; username: string; role: 'ADMIN' | 'EMPLOYEE'; is_active: boolean }
export type Session = { user: User; csrf_token: string }
export type Credentials = { username: string; password: string }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

function user(value: unknown): User {
  if (typeof value !== 'object' || value === null ||
      !('id' in value) || typeof value.id !== 'number' ||
      !('username' in value) || typeof value.username !== 'string' ||
      !('role' in value) || (value.role !== 'ADMIN' && value.role !== 'EMPLOYEE') ||
      !('is_active' in value) || typeof value.is_active !== 'boolean') {
    throw new Error('Respuesta de usuario inválida')
  }
  return { id: value.id, username: value.username, role: value.role, is_active: value.is_active }
}

function session(value: unknown): Session {
  if (typeof value !== 'object' || value === null || !('user' in value) ||
      !('csrf_token' in value) || typeof value.csrf_token !== 'string') {
    throw new Error('Respuesta de sesión inválida')
  }
  return { user: user(value.user), csrf_token: value.csrf_token }
}

async function request(path: string, method = 'GET', body?: unknown, csrf?: string,
                       fetcher: typeof fetch = fetch): Promise<unknown> {
  const response = await fetcher(`/api${path}`, {
    method, credentials: 'same-origin',
    headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
               ...(csrf ? { 'X-CSRF-Token': csrf } : {}) },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const message = typeof payload === 'object' && payload !== null && 'detail' in payload &&
      typeof payload.detail === 'string' ? payload.detail : 'No se pudo completar la operación'
    throw new ApiError(response.status, message)
  }
  return response.status === 204 ? undefined : response.json()
}

export async function setupStatus(): Promise<boolean> {
  const data = await request('/auth/setup')
  if (typeof data !== 'object' || data === null || !('initialized' in data) ||
      typeof data.initialized !== 'boolean') throw new Error('Respuesta de inicialización inválida')
  return data.initialized
}
export async function currentSession(): Promise<Session | null> {
  try { return session(await request('/auth/me')) }
  catch (error) { if (error instanceof ApiError && error.status === 401) return null; throw error }
}
export async function initialize(credentials: Credentials, setup_token: string): Promise<void> {
  user(await request('/auth/setup', 'POST', { ...credentials, setup_token }))
}
export async function login(credentials: Credentials, fetcher: typeof fetch = fetch): Promise<Session> {
  return session(await request('/auth/login', 'POST', credentials, undefined, fetcher))
}
export async function logout(csrf: string, fetcher: typeof fetch = fetch): Promise<void> {
  await request('/auth/logout', 'POST', {}, csrf, fetcher)
}
export async function employees(): Promise<User[]> {
  const data = await request('/employees')
  if (!Array.isArray(data)) throw new Error('Lista de empleados inválida')
  return data.map(user)
}
export async function createEmployee(credentials: Credentials, csrf: string): Promise<User> {
  return user(await request('/employees', 'POST', credentials, csrf))
}
export async function deactivateEmployee(id: number, csrf: string): Promise<User> {
  return user(await request(`/employees/${id}`, 'PATCH', { is_active: false }, csrf))
}
