// frontend/tests/server-settings.test.tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { ServerSettings } from '../src/components/ServerSettings';
import { API_BASE_STORAGE_KEY, clearApiBase, getApiBase } from '../src/api/serverConfig';

const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
  new Response(JSON.stringify({ code: 0, message: 'ok', data: {}, timestamp: 0 }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  }),
);

vi.stubGlobal('fetch', fetchMock);

function renderSettings() {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <ServerSettings />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole('button', { name: '伺服器' }));
}

afterEach(() => {
  // clearApiBase also clears the in-session memory fallback, isolating tests.
  clearApiBase();
  window.localStorage.clear();
  fetchMock.mockClear();
});

describe('ServerSettings', () => {
  it('shows the same-origin default when nothing is configured', () => {
    renderSettings();
    expect(screen.getByText('預設（同源伺服器）')).toBeInTheDocument();
  });

  it('saves a normalized URL and persists it', () => {
    renderSettings();
    fireEvent.change(screen.getByPlaceholderText('https://host:8089'), {
      target: { value: 'https://deploy.example:8089/' },
    });
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(window.localStorage.getItem(API_BASE_STORAGE_KEY)).toBe('https://deploy.example:8089');
    expect(getApiBase()).toBe('https://deploy.example:8089');
    expect(screen.getByText('https://deploy.example:8089')).toBeInTheDocument();
  });

  it('rejects an invalid URL with an error and does not persist it', () => {
    renderSettings();
    fireEvent.change(screen.getByPlaceholderText('https://host:8089'), {
      target: { value: 'not a url' },
    });
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(screen.getByText(/無效的伺服器地址/)).toBeInTheDocument();
    expect(window.localStorage.getItem(API_BASE_STORAGE_KEY)).toBeNull();
  });

  it('tests connectivity against the freshness endpoint', async () => {
    renderSettings();
    fireEvent.change(screen.getByPlaceholderText('https://host:8089'), {
      target: { value: 'https://lan.example:8089' },
    });
    fireEvent.click(screen.getByRole('button', { name: '測試' }));

    expect(await screen.findByText('✓ 連線正常')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('https://lan.example:8089/api/imports/freshness', {
      signal: expect.any(AbortSignal),
    });
  });

  it('reports a failed connection test', async () => {
    fetchMock.mockRejectedValueOnce(new Error('Failed to fetch'));
    renderSettings();
    fireEvent.change(screen.getByPlaceholderText('https://host:8089'), {
      target: { value: 'https://down.example' },
    });
    fireEvent.click(screen.getByRole('button', { name: '測試' }));

    expect(await screen.findByText(/✗ 連線失敗/)).toBeInTheDocument();
  });

  it('resets back to the build-time default', () => {
    window.localStorage.setItem(API_BASE_STORAGE_KEY, 'https://override.example');
    renderSettings();
    expect(screen.getByText('https://override.example')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '重設預設' }));

    expect(window.localStorage.getItem(API_BASE_STORAGE_KEY)).toBeNull();
    expect(screen.getByText('預設（同源伺服器）')).toBeInTheDocument();
  });

  it('refetches mounted queries from the new server after saving', async () => {
    const fetchUrls: string[] = [];
    const probe = vi.fn(async () => {
      const url = `${getApiBase()}/api/comparisons`;
      fetchUrls.push(url);
      await fetch(url);
      return [];
    });
    function Probe() {
      useQuery({ queryKey: ['probe'], queryFn: probe });
      return null;
    }

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <Probe />
        <ServerSettings />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(fetchUrls).toEqual(['/api/comparisons']));

    fireEvent.click(screen.getByRole('button', { name: '伺服器' }));
    fireEvent.change(screen.getByPlaceholderText('https://host:8089'), {
      target: { value: 'https://new-server.example:8089' },
    });
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    await waitFor(() =>
      expect(fetchUrls).toContain('https://new-server.example:8089/api/comparisons'),
    );
  });
});
