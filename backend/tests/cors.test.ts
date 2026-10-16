// backend/tests/cors.test.ts
import { describe, expect, it } from 'vitest';
import request from 'supertest';
import { createApp } from '../src/app.js';
import { createInMemoryDatabase } from '../src/db/client.js';
import { DEFAULT_CORS_ORIGINS } from '../src/config.js';

describe('CORS', () => {
  it('echoes an allowed Capacitor WebView origin on preflight', async () => {
    const app = createApp(createInMemoryDatabase());

    const res = await request(app)
      .options('/api/comparisons')
      .set('Origin', 'capacitor://localhost')
      .set('Access-Control-Request-Method', 'GET');

    expect(res.status).toBe(204);
    expect(res.headers['access-control-allow-origin']).toBe('capacitor://localhost');
  });

  it('allows the Android WebView origin on actual requests', async () => {
    const app = createApp(createInMemoryDatabase());

    const res = await request(app).get('/api/comparisons').set('Origin', 'https://localhost');

    expect(res.status).toBe(200);
    expect(res.headers['access-control-allow-origin']).toBe('https://localhost');
  });

  it('does not echo a disallowed origin', async () => {
    const app = createApp(createInMemoryDatabase());

    const res = await request(app).get('/api/comparisons').set('Origin', 'https://evil.example');

    expect(res.status).toBe(200);
    expect(res.headers['access-control-allow-origin']).toBeUndefined();
  });

  it('honours a custom CORS_ORIGINS list', async () => {
    const app = createApp(createInMemoryDatabase(), undefined, 'https://gunpla.example.com');

    const allowed = await request(app)
      .get('/api/comparisons')
      .set('Origin', 'https://gunpla.example.com');
    expect(allowed.headers['access-control-allow-origin']).toBe('https://gunpla.example.com');

    const rejected = await request(app).get('/api/comparisons').set('Origin', 'capacitor://localhost');
    expect(rejected.headers['access-control-allow-origin']).toBeUndefined();
  });

  it('defaults cover both WebView schemes', () => {
    expect(DEFAULT_CORS_ORIGINS).toContain('capacitor://localhost');
    expect(DEFAULT_CORS_ORIGINS).toContain('https://localhost');
  });
});
