// frontend/tests/pbandai-page.test.tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from '../src/App';
import { PbandaiPage } from '../src/pages/PbandaiPage';
import { fetchPbandaiItems } from '../src/api/pbandai.api';
import { buildFreshness } from './fixtures';
import type { PbandaiItem, ScrapeJobStatus } from '../src/types';

const IDLE_SCRAPE: ScrapeJobStatus = { state: 'idle', startedAt: null, finishedAt: null, exitCode: null };

function buildItem(overrides: Partial<PbandaiItem> = {}): PbandaiItem {
  return {
    id: 1,
    name: 'HG 1/144 Kit A',
    tcName: 'HG 1/144 甲',
    price: 450,
    status: 'PRE-ORDER',
    url: 'https://p-bandai.com/hk/item/A1',
    imageUrl: 'https://p-bandai.com/img/a.jpg',
    importedAt: '2026-10-17T01:00:00.000Z',
    ...overrides,
  };
}

function envelope(data: unknown): Response {
  return new Response(
    JSON.stringify({ code: 0, message: 'ok', data, timestamp: '2026-01-01T00:00:00Z' }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  );
}

function stubPbandai(items: PbandaiItem[]) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(envelope(items)));
}

function renderPage(ui: React.ReactElement): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fetchPbandaiItems', () => {
  it('requests the plain list without a query string', async () => {
    const fetchMock = vi.fn().mockResolvedValue(envelope([]));
    vi.stubGlobal('fetch', fetchMock);

    await fetchPbandaiItems();

    expect(fetchMock).toHaveBeenCalledWith('/api/pbandai');
  });
});

describe('PbandaiPage', () => {
  it('renders cards with image, translated title, price and status', async () => {
    stubPbandai([buildItem()]);
    renderPage(<PbandaiPage />);

    expect(await screen.findByText('HG 1/144 甲')).toBeInTheDocument();
    expect(screen.getByText('HG 1/144 Kit A')).toBeInTheDocument();
    expect(screen.getByText('HK$450')).toBeInTheDocument();
    // The status shows up twice: filter chip + card badge.
    expect(screen.getAllByText('PRE-ORDER')).toHaveLength(2);
    expect(screen.getByText('1 件')).toBeInTheDocument();

    const img = document.querySelector('img.pbandai-image');
    expect(img).toHaveAttribute('src', 'https://p-bandai.com/img/a.jpg');
    expect(img).toHaveAttribute('loading', 'lazy');
    expect(img).toHaveAttribute('referrerPolicy', 'no-referrer');

    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', 'https://p-bandai.com/hk/item/A1');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('renders the PB fallback block when an item has no image', async () => {
    stubPbandai([buildItem({ imageUrl: null })]);
    renderPage(<PbandaiPage />);

    expect(await screen.findByText('HG 1/144 甲')).toBeInTheDocument();
    expect(document.querySelector('img.pbandai-image')).not.toBeInTheDocument();
    expect(document.querySelector('.pbandai-thumb-fallback')).toHaveTextContent('PB');
  });

  it('narrows the grid via the search box, matching the translated name', async () => {
    stubPbandai([
      buildItem(),
      buildItem({ id: 2, name: 'MG 1/100 Kit B', tcName: 'MG 1/100 乙', url: 'https://p-bandai.com/hk/item/B2' }),
    ]);
    renderPage(<PbandaiPage />);
    await screen.findByText('HG 1/144 甲');

    await userEvent.type(screen.getByLabelText('搜尋產品'), '乙');

    expect(screen.queryByText('HG 1/144 甲')).not.toBeInTheDocument();
    expect(screen.getByText('MG 1/100 乙')).toBeInTheDocument();
    expect(screen.getByText('1 / 2 件')).toBeInTheDocument();
  });

  it('filters by a status chip and toggles back to all', async () => {
    stubPbandai([
      buildItem(),
      buildItem({ id: 2, name: 'MG Kit B', tcName: null, status: 'WAITING', url: 'https://p-bandai.com/hk/item/B2' }),
    ]);
    renderPage(<PbandaiPage />);
    await screen.findByText('HG 1/144 甲');

    await userEvent.click(screen.getByRole('button', { name: 'WAITING' }));
    expect(screen.queryByText('HG 1/144 甲')).not.toBeInTheDocument();
    expect(screen.getByText('MG Kit B')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '全部' }));
    expect(screen.getByText('HG 1/144 甲')).toBeInTheDocument();
    expect(screen.getByText('MG Kit B')).toBeInTheDocument();
  });

  it('shows the empty state before any import', async () => {
    stubPbandai([]);
    renderPage(<PbandaiPage />);

    expect(await screen.findByText(/冇資料 — 請先撳更新/)).toBeInTheDocument();
  });
});

describe('App nav', () => {
  function stubAll(pbandaiItems: PbandaiItem[]) {
    // The App shell mounts the dashboard first, so the stub must answer the
    // freshness/scrape queries with their real shapes too.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/api/pbandai')) return Promise.resolve(envelope(pbandaiItems));
        if (url.includes('/api/imports/freshness')) return Promise.resolve(envelope(buildFreshness()));
        if (url.includes('/api/scrape')) return Promise.resolve(envelope(IDLE_SCRAPE));
        return Promise.resolve(envelope([]));
      }),
    );
  }

  it('switches 格價表 → P-Bandai and back', async () => {
    stubAll([buildItem()]);
    renderPage(<App />);

    await userEvent.click(screen.getByRole('button', { name: 'P-Bandai' }));
    expect(await screen.findByText('P-Bandai HK 最新預訂')).toBeInTheDocument();
    expect(await screen.findByText('HG 1/144 甲')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '格價表' }));
    expect(screen.queryByText('P-Bandai HK 最新預訂')).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'HG' })).toBeInTheDocument();
  });
});
