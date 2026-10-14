// frontend/tests/series-filter.test.tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardPage } from '../src/pages/DashboardPage';
import { SeriesFilter } from '../src/components/SeriesFilter';
import type { ComparisonRow } from '../src/types';
import { buildOffer, buildRow, stubApi } from './fixtures';

const ZETA_A = buildRow({
  sku: '1',
  title: 'Zeta Kit A',
  series: 'zeta',
  offers: [buildOffer({ shop: 'hobbyland', price: 120 })],
  exclusiveShop: 'hobbyland',
});
const ZETA_B = buildRow({
  sku: '2',
  title: 'Zeta Kit B',
  series: 'zeta',
  offers: [buildOffer({ shop: 'hobbyland', price: 90 })],
  exclusiveShop: 'hobbyland',
});
const SEED = buildRow({
  sku: '3',
  title: 'Seed Kit',
  series: 'seed',
  offers: [buildOffer({ shop: 'animes-pro', price: 200 })],
  exclusiveShop: 'animes-pro',
});
const UNCLASSIFIED = buildRow({
  sku: '4',
  title: 'Mystery Kit',
  series: null,
  offers: [buildOffer({ shop: 'hobbyland', price: 50 })],
  exclusiveShop: 'hobbyland',
});
const ROWS: ComparisonRow[] = [ZETA_A, ZETA_B, SEED, UNCLASSIFIED];

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

function seriesSelect(): HTMLElement {
  return screen.getByRole('combobox', { name: '系列' });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('SeriesFilter', () => {
  it('lists only series present in the rows, with counts', () => {
    render(<SeriesFilter value="all" onChange={() => {}} rows={ROWS} />);

    const options = [...screen.getByRole('combobox').querySelectorAll('option')].map(
      (o) => o.textContent,
    );
    expect(options).toEqual(['全部系列', 'Z (2)', 'SEED (1)', '未分類 (1)']);
  });
});

describe('DashboardPage series filtering', () => {
  it('narrows the table to the chosen series and shows per-series stats', async () => {
    stubApi(ROWS);
    renderDashboard();
    await screen.findByText('Zeta Kit A');

    expect(renderedTitles()).toEqual(
      expect.arrayContaining(['Zeta Kit A', 'Zeta Kit B', 'Seed Kit', 'Mystery Kit']),
    );

    await userEvent.selectOptions(seriesSelect(), 'seed');

    expect(renderedTitles()).toEqual(['Seed Kit']);
    expect(screen.getByText('1 / 4 個 SKU')).toBeTruthy();
  });

  it('filters to unclassified rows via the __none__ option', async () => {
    stubApi(ROWS);
    renderDashboard();
    await screen.findByText('Zeta Kit A');

    await userEvent.selectOptions(seriesSelect(), '__none__');

    expect(renderedTitles()).toEqual(['Mystery Kit']);
  });

  it('toggles the series when a stat chip is clicked', async () => {
    stubApi(ROWS);
    renderDashboard();
    await screen.findByText('Zeta Kit A');

    const findZetaChip = () =>
      [...document.querySelectorAll('.series-stat-btn')].find((c) =>
        c.textContent?.includes('Z'),
      );
    await userEvent.click(findZetaChip()!);

    expect(renderedTitles()).toEqual(['Zeta Kit A', 'Zeta Kit B']);

    await userEvent.click(findZetaChip()!);
    expect(renderedTitles()).toHaveLength(4);
  });

  it('renders the series name under the product title and a dash when unclassified', async () => {
    stubApi([ZETA_A, UNCLASSIFIED]);
    renderDashboard();
    await screen.findByText('Zeta Kit A');

    const tags = [...document.querySelectorAll('.title-cell .series-tag')].map(
      (n) => n.textContent,
    );
    expect(tags).toContain('Z');
    expect(tags).toContain('—');
  });
});
