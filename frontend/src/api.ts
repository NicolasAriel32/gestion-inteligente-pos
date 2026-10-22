export type Health = { status: 'ok' }
export async function getHealth(fetcher: typeof fetch = fetch): Promise<Health> {
  const response = await fetcher('/api/health')
  if (!response.ok) throw new Error('No se pudo conectar con el servidor local')
  const json: unknown = await response.json()
  if (typeof json !== 'object' || json === null || !('status' in json) || json.status !== 'ok') {
    throw new Error('Respuesta de diagnóstico inválida')
  }
  return { status: 'ok' }
}
