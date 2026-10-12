// frontend/tests/components.test.tsx
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CheaperBadge } from '../src/components/CheaperBadge';
import { ComparisonTable } from '../src/components/ComparisonTable';
import { FreshnessBar } from '../src/components/FreshnessBar';
import { GradeTabs } from '../src/components/GradeTabs';
import { SearchBar } from '../src/components/SearchBar';
import { buildFreshness, buildOffer, buildRow } from './fixtures';

describe('CheaperBadge', () => {
  it('shows the cheaper shop with the saving', () => {
    render(<CheaperBadge cheapestShop="hobbyland" saving={22} exclusiveShop={null} />);
    expect(screen.getByText('Hobbyland 平 HK$22')).toBeInTheDocument();
  });

  it('shows a tie label for equal prices', () => {
    render(<CheaperBadge cheapestShop="tie" saving={0} exclusiveShop={null} />);
    expect(screen.getByText('同價')).toBeInTheDocument();
  });

  it('labels a single-shop SKU as the only shop in stock instead of the cheaper one', () => {
    render(<CheaperBadge cheapestShop="animes-pro" saving={null} exclusiveShop="animes-pro" />);
    expect(screen.getByText('只有 Animes 有貨')).toBeInTheDocument();
    expect(screen.queryByText(/平/)).not.toBeInTheDocument();
  });

  it('labels a hobbyland-exclusive SKU with the hobbyland name', () => {
    render(<CheaperBadge cheapestShop="hobbyland" saving={null} exclusiveShop="hobbyland" />);
    expect(screen.getByText('只有 Hobbyland 有貨')).toBeInTheDocument();
  });

  it('prefers the exclusive label over a tie or cheapest verdict', () => {
    render(<CheaperBadge cheapestShop="tie" saving={0} exclusiveShop="hobbyland" />);
    expect(screen.getByText('只有 Hobbyland 有貨')).toBeInTheDocument();
  });

  it('shows a dash when there is no cheapest shop', () => {
    render(<CheaperBadge cheapestShop={null} saving={null} exclusiveShop={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});

describe('ComparisonTable', () => {
  it('shows an empty state without rows', () => {
    render(<ComparisonTable rows={[]} />);
    expect(screen.getByText(/冇資料/)).toBeInTheDocument();
  });

  it('renders both shop prices and the cheaper badge', () => {
    render(<ComparisonTable rows={[buildRow()]} />);
    expect(screen.getByText('HG Gundam')).toBeInTheDocument();
    expect(screen.getByText(/HK\$78/)).toBeInTheDocument();
    expect(screen.getByText(/HK\$100/)).toBeInTheDocument();
    expect(screen.getByText('Hobbyland 平 HK$22')).toBeInTheDocument();
  });

  it('renders a placeholder and the exclusive label for a single-shop SKU', () => {
    const row = buildRow({
      offers: [buildOffer({ shop: 'animes-pro', price: 50 })],
      cheapestShop: 'animes-pro',
      saving: null,
      exclusiveShop: 'animes-pro',
    });
    render(<ComparisonTable rows={[row]} />);
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('只有 Animes 有貨')).toBeInTheDocument();
  });

  it('shows the regular price only when it exceeds the sale price', () => {
    const row = buildRow({
      offers: [
        buildOffer({ shop: 'hobbyland', price: 78, regularPrice: 90 }),
        buildOffer({ shop: 'animes-pro', price: 100, regularPrice: 100 }),
      ],
    });
    render(<ComparisonTable rows={[row]} />);
    expect(screen.getByText('HK$90')).toBeInTheDocument();
    expect(document.querySelectorAll('.regular-price')).toHaveLength(1);
  });

  it('flags a pre-order offer', () => {
    const row = buildRow({
      offers: [buildOffer({ shop: 'animes-pro', sellType: '預訂' })],
      exclusiveShop: 'animes-pro',
    });
    render(<ComparisonTable rows={[row]} />);
    expect(document.querySelector('.stock-note.preorder')).not.toBeNull();
  });

  it('renders a preview image for a row that has one', () => {
    const row = buildRow({
      offers: [buildOffer({ shop: 'hobbyland', imageUrl: 'https://cdn.example/kit.webp' })],
    });
    render(<ComparisonTable rows={[row]} />);
    expect(document.querySelector('img.product-thumb')).toHaveAttribute(
      'src',
      'https://cdn.example/kit.webp',
    );
    expect(document.querySelector('.product-thumb-fallback')).toBeNull();
  });

  it('renders a grade placeholder for every row without an image', () => {
    render(<ComparisonTable rows={[buildRow(), buildRow({ sku: '999', grade: 'mg' })]} />);
    expect(document.querySelector('img.product-thumb')).toBeNull();
    expect(document.querySelectorAll('.product-thumb-fallback')).toHaveLength(2);
    expect(screen.getAllByText('HG')).toHaveLength(1);
    expect(screen.getAllByText('MG')).toHaveLength(1);
  });

  it('falls back to the placeholder when the preview image fails to load', () => {
    const row = buildRow({
      offers: [buildOffer({ shop: 'animes-pro', imageUrl: 'https://cdn.example/gone.jpg' })],
    });
    render(<ComparisonTable rows={[row]} />);
    const thumb = document.querySelector('img.product-thumb');
    expect(thumb).not.toBeNull();
    fireEvent.error(thumb!);
    expect(document.querySelector('img.product-thumb')).toBeNull();
    expect(document.querySelector('.product-thumb-fallback')).not.toBeNull();
  });
});

describe('FreshnessBar', () => {
  it('renders one timestamp per shop with a machine-readable dateTime', () => {
    render(<FreshnessBar freshness={buildFreshness()} isLoading={false} />);

    expect(screen.getByText(/最後更新 · HG/)).toBeInTheDocument();
    const times = document.querySelectorAll('time.freshness-time');
    expect(times).toHaveLength(2);
    expect(times[0]).toHaveAttribute('dateTime', '2026-10-11T11:46:00.000Z');
    expect(times[1]).toHaveAttribute('dateTime', '2026-10-11T11:47:00.000Z');
    expect(screen.getByText('Hobbyland')).toBeInTheDocument();
    expect(screen.getByText('Animes-Pro')).toBeInTheDocument();
    // The third shop is listed even though it has never been imported.
    expect(screen.getByText('HobbyDigi')).toBeInTheDocument();
    expect(screen.getByText('冇紀錄')).toBeInTheDocument();
  });

  it('marks a shop that has never been imported for this grade', () => {
    render(
      <FreshnessBar
        freshness={buildFreshness({
          overall: '2026-10-11T11:46:00.000Z',
          byShop: { hobbyland: '2026-10-11T11:46:00.000Z', 'animes-pro': null, hobbydigi: null },
        })}
        isLoading={false}
      />,
    );

    expect(screen.getAllByText('冇紀錄')).toHaveLength(2);
    expect(document.querySelectorAll('time.freshness-time')).toHaveLength(1);
  });

  it('reports when the grade has no import history at all', () => {
    render(
      <FreshnessBar
        freshness={buildFreshness({
          overall: null,
          byShop: { hobbyland: null, 'animes-pro': null, hobbydigi: null },
        })}
        isLoading={false}
      />,
    );

    expect(screen.getByText('最後更新 · 呢個級別未有匯入紀錄')).toBeInTheDocument();
  });

  it('shows a pending state while loading and a failure state when the query errored', () => {
    const { rerender } = render(<FreshnessBar freshness={undefined} isLoading />);
    expect(screen.getByText('最後更新 · 載入中…')).toBeInTheDocument();

    rerender(<FreshnessBar freshness={undefined} isLoading={false} />);
    expect(screen.getByText('最後更新 · 未能載入')).toBeInTheDocument();
  });
});

describe('GradeTabs', () => {
  it('marks the current grade as selected', () => {
    render(<GradeTabs value="mg" onChange={() => undefined} />);
    expect(screen.getByRole('tab', { name: 'MG' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'HG' })).toHaveAttribute('aria-selected', 'false');
  });

  it('emits the clicked grade', async () => {
    const onChange = vi.fn();
    render(<GradeTabs value="hg" onChange={onChange} />);
    await userEvent.click(screen.getByRole('tab', { name: 'RG' }));
    expect(onChange).toHaveBeenCalledWith('rg');
  });
});

describe('SearchBar', () => {
  it('emits typed text', async () => {
    const onChange = vi.fn();
    render(<SearchBar value="" onChange={onChange} />);
    await userEvent.type(screen.getByLabelText('搜尋產品'), 'a');
    expect(onChange).toHaveBeenCalledWith('a');
  });
});
