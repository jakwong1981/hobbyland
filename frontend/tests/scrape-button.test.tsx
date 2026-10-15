// frontend/tests/scrape-button.test.tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardPage } from '../src/pages/DashboardPage';
import type { ScrapeJobStatus } from '../src/types';
import { buildFreshness, buildRow } from './fixtures';

function envelope(data: unknown, status = 200): Response {
  return new Response(
    JSON.stringify({ code: 0, message: 'ok', data, timestamp: '2026-01-01T00:00:00Z' }),
    { status, headers: { 'Content-Type': 'application/json' } },
  );
}

function stubScrapeApi(scrapeState: { current: ScrapeJobStatus['state'] }) {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const status = (): ScrapeJobStatus => ({
      state: scrapeState.current,
      startedAt: null,
      finishedAt: null,
      exitCode: scrapeState.current === 'completed' ? 0 : null,
    });
    if (url.includes('/api/scrape/status')) return Promise.resolve(envelope(status()));
    if (url.includes('/api/scrape')) {
      scrapeState.current = 'running';
      return Promise.resolve(envelope(status(), 202));
    }
    if (url.includes('/api/imports/freshness')) {
      return Promise.resolve(envelope(buildFreshness()));
    }
    return Promise.resolve(envelope([buildRow()]));
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function renderDashboard(): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('DashboardPage scrape button', () => {
  it('triggers the scrape, greys out while processing, and re-enables on completion', async () => {
    const scrapeState = { current: 'idle' as ScrapeJobStatus['state'] };
    const fetchMock = stubScrapeApi(scrapeState);
    const user = userEvent.setup();
    renderDashboard();

    await screen.findByText('HG Gundam');
    const button = screen.getByRole('button', { name: '更新' });
    expect(button).toBeEnabled();

    await user.click(button);

    expect(fetchMock).toHaveBeenCalledWith('/api/scrape', { method: 'POST' });
    await waitFor(() => {
      const processing = screen.getByRole('button', { name: 'Processing…' });
      expect(processing).toBeDisabled();
    });

    scrapeState.current = 'completed';
    await waitFor(
      () => {
        expect(screen.getByRole('button', { name: '更新' })).toBeEnabled();
      },
      { timeout: 5000 },
    );
  });

  it('shows an error when the scrape fails', async () => {
    const scrapeState = { current: 'idle' as ScrapeJobStatus['state'] };
    stubScrapeApi(scrapeState);
    const user = userEvent.setup();
    renderDashboard();

    await screen.findByText('HG Gundam');
    await user.click(screen.getByRole('button', { name: '更新' }));

    scrapeState.current = 'failed';
    await waitFor(
      () => {
        expect(screen.getByText(/scrape script 執行出錯/)).toBeInTheDocument();
      },
      { timeout: 5000 },
    );
    expect(screen.getByRole('button', { name: '更新' })).toBeEnabled();
  });
});
