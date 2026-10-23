import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './worker.mjs';

for (const [path, method] of [['/api', 'GET'], ['/api/health', 'GET'], ['/api/auth/login', 'POST'], ['/api/sales', 'POST']]) {
  test(`${method} ${path} reports a missing backend instead of returning the SPA or a fake success`, async () => {
    const response = await worker.fetch(new Request(`https://preview.example${path}`, { method }), {
      ASSETS: { fetch() { throw new Error('API must not fall through to index.html'); } },
    });
    assert.equal(response.status, 503);
    assert.equal(response.headers.get('Cache-Control'), 'no-store');
    assert.match(response.headers.get('Content-Type'), /application\/json/);
    assert.equal((await response.json()).code, 'LOCAL_BACKEND_REQUIRED');
    assert.equal(response.headers.get('Set-Cookie'), null);
  });
}

test('page and asset requests are passed through unchanged', async () => {
  for (const path of ['/', '/assets/index-123.js', '/catalogo', '/api-example']) {
    const request = new Request(`https://preview.example${path}`);
    const assetResponse = new Response('compiled asset');
    const response = await worker.fetch(request, { ASSETS: { fetch(received) {
      assert.equal(received, request);
      return assetResponse;
    } } });
    assert.equal(response, assetResponse);
  }
});
