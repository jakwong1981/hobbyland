// frontend/tests/dashboard.test.tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardPage } from '../src/pages/DashboardPage';
import { ApiError, apiGet } from '../src/api/client';
import { fetchComparisons } from '../src/api/comparison.api';
import { buildFreshness, buildOffer, buildRow, stubApi } from './fixtures';

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
    const fetchMock = stubApi([buildRow()]);
    renderDashboard();

    expect(await screen.findByText('HG Gundam')).toBeInTheDocument();
    expect(screen.getByText('1 個 SKU')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/comparisons?grade=hg');
  });

  it('omits HobbyDigi offers and HobbyDigi-only skus', async () => {
    stubApi([
      buildRow({
        sku: '1',
        offers: [
          buildOffer({ shop: 'hobbydigi', price: 70 }),
          buildOffer({ shop: 'hobbyland', price: 78 }),
          buildOffer({ shop: 'animes-pro', price: 100 }),
        ],
        cheapestShop: 'hobbydigi',
        saving: 8,
      }),
      buildRow({
        sku: 'HD:some-kit',
        title: 'HD Only Kit',
        offers: [buildOffer({ shop: 'hobbydigi', price: 90 })],
        cheapestShop: 'hobbydigi',
        saving: null,
        exclusiveShop: 'hobbydigi',
      }),
    ]);
    renderDashboard();

    expect(await screen.findByText('HG Gundam')).toBeInTheDocument();
    expect(screen.queryByText('HD Only Kit')).not.toBeInTheDocument();
    expect(screen.queryByText('HobbyDigi')).not.toBeInTheDocument();
    // The HobbyDigi column is gone and the verdict is re-derived: Hobbyland now wins.
    expect(screen.getByText('Hobbyland 最平')).toBeInTheDocument();
    expect(screen.getByText('1 個 SKU')).toBeInTheDocument();
  });

  it('refetches when the grade tab changes', async () => {
    const fetchMock = stubApi([]);
    renderDashboard();

    await userEvent.click(screen.getByRole('tab', { name: 'MG' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/comparisons?grade=mg'));
  });

  it('asks for freshness scoped to the current grade', async () => {
    const fetchMock = stubApi([]);
    renderDashboard();

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/api/imports/freshness?grade=hg'),
    );
  });

  it('shows the last import time of each shop on the page', async () => {
    stubApi(
      [buildRow()],
      buildFreshness({
        grade: 'hg',
        overall: '2026-10-11T11:47:00.000Z',
        byShop: {
          hobbyland: '2026-10-11T11:46:00.000Z',
          'animes-pro': '2026-10-11T11:47:00.000Z',
          hobbydigi: null,
          fookle: null,
          twinnermodel: null,
        },
      }),
    );
    renderDashboard();

    await screen.findByText('HG Gundam');

    const times = document.querySelectorAll('time.freshness-time');
    expect(times).toHaveLength(2);
    expect(times[0]).toHaveAttribute('dateTime', '2026-10-11T11:46:00.000Z');
    expect(times[1]).toHaveAttribute('dateTime', '2026-10-11T11:47:00.000Z');
    expect(screen.getByText(/最後更新 · HG/)).toBeInTheDocument();
  });

  it('shows an error message when loading fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(500, 'boom', null)));
    renderDashboard();

    expect(await screen.findByText('載入失敗：boom')).toBeInTheDocument();
    expect(await screen.findByText('最後更新 · 未能載入')).toBeInTheDocument();
  });
});
