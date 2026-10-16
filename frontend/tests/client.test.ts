// frontend/tests/client.test.ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet, apiPost } from '../src/api/client';
import { clearApiBase, setApiBase } from '../src/api/serverConfig';

const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
  new Response(JSON.stringify({ code: 0, message: 'ok', data: [], timestamp: 0 }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  }),
);

vi.stubGlobal('fetch', fetchMock);

afterEach(() => {
  vi.stubEnv('VITE_API_BASE_URL', '');
  clearApiBase();
  fetchMock.mockClear();
});

describe('api client base URL resolution', () => {
  it('uses same-origin relative paths by default', async () => {
    await apiGet('/api/comparisons');

    expect(fetchMock).toHaveBeenCalledWith('/api/comparisons');
  });

  it('resolves the effective base per request, so a settings change applies without reload', async () => {
    await apiGet('/api/comparisons');
    setApiBase('https://phone-lan.example:8089');
    await apiGet('/api/comparisons');
    setApiBase('https://deploy.example');
    await apiPost('/api/scrape');

    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual([
      '/api/comparisons',
      'https://phone-lan.example:8089/api/comparisons',
      'https://deploy.example/api/scrape',
    ]);
    expect(fetchMock.mock.calls[2][1]).toEqual({ method: 'POST' });
  });

  it('throws ApiError with the server message on non-2xx', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ code: 1, message: 'boom', data: null, timestamp: 0 }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(apiGet('/api/comparisons')).rejects.toThrow(ApiError);
  });
});
