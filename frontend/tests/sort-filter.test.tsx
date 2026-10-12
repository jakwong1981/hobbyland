// frontend/tests/sort-filter.test.tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ComparisonTable } from '../src/components/ComparisonTable';
import { ShopFilter } from '../src/components/ShopFilter';
import { DashboardPage } from '../src/pages/DashboardPage';
import { useComparisonSort } from '../src/hooks/useComparisonSort';
import { SHOP_CODES, type ComparisonRow } from '../src/types';
import { buildOffer, buildRow, stubApi } from './fixtures';

// Alpha is sold by both shops; Beta is hobbyland-only; Gamma is animes-only.
const ALPHA = buildRow({
  sku: '1',
  title: 'Alpha',
  offers: [
    buildOffer({ shop: 'hobbyland', price: 120 }),
    buildOffer({ shop: 'animes-pro', price: 90 }),
  ],
  cheapestShop: 'animes-pro',
  saving: 30,
  exclusiveShop: null,
});
const BETA = buildRow({
  sku: '2',
  title: 'Beta',
  offers: [buildOffer({ shop: 'hobbyland', price: 80 })],
  cheapestShop: 'hobbyland',
  saving: null,
  exclusiveShop: 'hobbyland',
});
const GAMMA = buildRow({
  sku: '3',
  title: 'Gamma',
  offers: [buildOffer({ shop: 'animes-pro', price: 200 })],
  cheapestShop: 'animes-pro',
  saving: null,
  exclusiveShop: 'animes-pro',
});
const ROWS: ComparisonRow[] = [ALPHA, BETA, GAMMA];

function renderedTitles(): Array<string | null> {
  return [...document.querySelectorAll('.product-title')].map((n) => n.textContent);
}

function renderDashboard(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

function shopSelect(): HTMLElement {
  return screen.getByRole('combobox', { name: '有售舖頭' });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useComparisonSort', () => {
  it('keeps the incoming order until a column is sorted', () => {
    const { result } = renderHook(() => useComparisonSort(ROWS));
    expect(result.current.sort).toBeNull();
    expect(result.current.sorted.map((r) => r.title)).toEqual(['Alpha', 'Beta', 'Gamma']);
  });

  it('sorts by title and flips direction on the second toggle', () => {
    const { result } = renderHook(() => useComparisonSort(ROWS));

    act(() => result.current.toggleSort('title'));
    expect(result.current.sort).toEqual({ key: 'title', direction: 'asc' });
    expect(result.current.sorted.map((r) => r.title)).toEqual(['Alpha', 'Beta', 'Gamma']);

    act(() => result.current.toggleSort('title'));
    expect(result.current.sort).toEqual({ key: 'title', direction: 'desc' });
    expect(result.current.sorted.map((r) => r.title)).toEqual(['Gamma', 'Beta', 'Alpha']);
  });

  it('sorts by a shop price and always trails the shop that does not carry the sku', () => {
    const { result } = renderHook(() => useComparisonSort(ROWS));

    act(() => result.current.toggleSort('hobbyland'));
    expect(result.current.sorted.map((r) => r.title)).toEqual(['Beta', 'Alpha', 'Gamma']);

    act(() => result.current.toggleSort('hobbyland'));
    expect(result.current.sorted.map((r) => r.title)).toEqual(['Alpha', 'Beta', 'Gamma']);

    act(() => result.current.toggleSort('animes-pro'));
    expect(result.current.sort).toEqual({ key: 'animes-pro', direction: 'asc' });
    expect(result.current.sorted.map((r) => r.title)).toEqual(['Alpha', 'Gamma', 'Beta']);
  });

  it('does not mutate the incoming array', () => {
    const input = [...ROWS];
    const { result } = renderHook(() => useComparisonSort(input));

    act(() => result.current.toggleSort('title'));
    act(() => result.current.toggleSort('title'));

    expect(input.map((r) => r.title)).toEqual(['Alpha', 'Beta', 'Gamma']);
  });
});

describe('ComparisonTable sorting', () => {
  it('marks the sortable headers unsorted and leaves the verdict header alone', () => {
    render(<ComparisonTable rows={ROWS} />);

    for (const name of ['產品', 'Hobbyland', 'Animes-Pro', 'HobbyDigi']) {
      expect(screen.getByRole('columnheader', { name: new RegExp(name) })).toHaveAttribute(
        'aria-sort',
        'none',
      );
    }

    const verdict = screen.getByRole('columnheader', { name: /判定/ });
    expect(verdict).not.toHaveAttribute('aria-sort');
    expect(verdict.querySelector('button')).toBeNull();
  });

  it('reorders rows and reports aria-sort when the title header is clicked', async () => {
    render(<ComparisonTable rows={ROWS} />);
    const header = screen.getByRole('columnheader', { name: /產品/ });
    const button = screen.getByRole('button', { name: /產品/ });

    await userEvent.click(button);
    expect(header).toHaveAttribute('aria-sort', 'ascending');
    expect(renderedTitles()).toEqual(['Alpha', 'Beta', 'Gamma']);

    await userEvent.click(button);
    expect(header).toHaveAttribute('aria-sort', 'descending');
    expect(renderedTitles()).toEqual(['Gamma', 'Beta', 'Alpha']);
  });

  it('reorders rows by hobbyland price when that header is clicked', async () => {
    render(<ComparisonTable rows={ROWS} />);
    await userEvent.click(screen.getByRole('button', { name: /Hobbyland/ }));
    expect(renderedTitles()).toEqual(['Beta', 'Alpha', 'Gamma']);
  });
});

describe('ShopFilter', () => {
  it('defaults to all and lists every shop', () => {
    render(<ShopFilter value="all" onChange={() => undefined} />);
    expect(shopSelect()).toHaveValue('all');
    // "all" plus one option per entry in SHOP_CODES.
    expect(screen.getAllByRole('option')).toHaveLength(SHOP_CODES.length + 1);
  });

  it('emits the chosen shop', async () => {
    const onChange = vi.fn();
    render(<ShopFilter value="all" onChange={onChange} />);
    await userEvent.selectOptions(shopSelect(), 'animes-pro');
    expect(onChange).toHaveBeenCalledWith('animes-pro');
  });
});

describe('DashboardPage shop filter', () => {
  it('shows every sku by default', async () => {
    stubApi(ROWS);
    renderDashboard();
    expect(await screen.findByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('3 個 SKU')).toBeInTheDocument();
  });

  it('narrows to the skus a shop carries and reports the filtered count', async () => {
    stubApi(ROWS);
    renderDashboard();
    await screen.findByText('Alpha');

    await userEvent.selectOptions(shopSelect(), 'hobbyland');

    expect(screen.getByText('2 / 3 個 SKU')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.queryByText('Gamma')).not.toBeInTheDocument();
  });

  it('shows a filter-specific empty state when no sku matches', async () => {
    stubApi([BETA]);
    renderDashboard();
    await screen.findByText('Beta');

    await userEvent.selectOptions(shopSelect(), 'animes-pro');

    expect(screen.getByText('0 / 1 個 SKU')).toBeInTheDocument();
    expect(screen.getByText('呢個舖頭篩選冇匹配嘅 SKU。')).toBeInTheDocument();
    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
  });
});
