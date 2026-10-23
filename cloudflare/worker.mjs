// This experiment serves the UI only. It never exposes or replaces the local API.
export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (pathname === '/api' || pathname.startsWith('/api/')) {
      return Response.json({
        detail: 'Vista previa web: el servidor local del POS no está disponible aquí. Usá la aplicación en tu PC para ingresar y registrar operaciones.',
        code: 'LOCAL_BACKEND_REQUIRED',
      }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
    }
    return env.ASSETS.fetch(request);
  },
};
