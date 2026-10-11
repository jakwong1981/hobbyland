// frontend/tests/dashboard.test.tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardPage } from '../src/pages/DashboardPage';
import { ApiError, apiGet } from '../src/api/client';
import { fetchComparisons } from '../src/api/comparison.api';
import { buildRow } from './fixtures';

function jsonResponse(status: number, message: string, data: unknown): Response {
  return new Response(
    JSON.stringify({ code: status, message, data, timestamp: '2026-01-01T00:00:00Z' }),
    { status, headers: { 'Content-Type': 'application/json' } },
  );
}

function renderDashboard(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api client', () => {
  it('unwraps the data of a successful response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, 'ok', [1, 2])));
    await expect(apiGet<number[]>('/api/x')).resolves.toEqual([1, 2]);
  });

  it('throws ApiError carrying the server message on failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(400, 'bad grade', null)));
    await expect(apiGet('/api/x')).rejects.toEqual(new ApiError(400, 'bad grade'));
  });

  it('builds the comparisons query string from filters', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, 'ok', []));
    vi.stubGlobal('fetch', fetchMock);
    await fetchComparisons({ grade: 'hg', q: 'zaku', cheaper: 'animes-pro' });
    expect(fetchMock).toHaveBeenCalledWith('/api/comparisons?grade=hg&q=zaku&cheaper=animes-pro');
  });
});

describe('DashboardPage', () => {
  it('loads and shows HG comparisons by default', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, 'ok', [buildRow()]));
    vi.stubGlobal('fetch', fetchMock);
    renderDashboard();

    expect(await screen.findByText('HG Gundam')).toBeInTheDocument();
    expect(screen.getByText('1 個 SKU')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/comparisons?grade=hg');
  });

  it('refetches when the grade tab changes', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, 'ok', []));
    vi.stubGlobal('fetch', fetchMock);
    renderDashboard();

    await userEvent.click(screen.getByRole('tab', { name: 'MG' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/comparisons?grade=mg'));
  });

  it('shows an error message when loading fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(500, 'boom', null)));
    renderDashboard();

    expect(await screen.findByText('載入失敗：boom')).toBeInTheDocument();
  });
});
