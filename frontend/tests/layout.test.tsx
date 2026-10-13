// frontend/tests/layout.test.tsx
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HeroBanner } from '../src/components/HeroBanner';
import { KitShowcase } from '../src/components/KitShowcase';
import { ComparisonGallery } from '../src/components/ComparisonGallery';
import { FactionWipe } from '../src/components/FactionWipe';
import { DashboardPage } from '../src/pages/DashboardPage';
import { buildOffer, buildRow, stubApi } from './fixtures';

const IMAGED_ROW = buildRow({
  offers: [
    buildOffer({ shop: 'hobbyland', price: 78, imageUrl: 'https://cdn/kit.jpg', url: 'https://hl/kit' }),
    buildOffer({ shop: 'animes-pro', price: 100 }),
  ],
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('HeroBanner', () => {
  it('exposes the target value of every stat tile', () => {
    const rows = [
      buildRow({ sku: '1', cheapestShop: 'hobbyland' }),
      buildRow({ sku: '2', cheapestShop: 'animes-pro', exclusiveShop: 'animes-pro' }),
    ];
    render(<HeroBanner rows={rows} grade="mg" />);

    const values = [...document.querySelectorAll('.stat-value')].map((n) =>
      n.getAttribute('data-value'),
    );
    expect(values).toEqual(['2', '1', '0', '0', '1']);
    expect(document.querySelector('.hero-grade')).toHaveTextContent('MG');
  });

  it('renders both faction heads so CSS can cross-fade between them', () => {
    render(<HeroBanner rows={[]} grade="hg" />);
    expect(document.querySelector('.ms-art-federation')).not.toBeNull();
    expect(document.querySelector('.ms-art-zeon')).not.toBeNull();
  });
});

describe('KitShowcase', () => {
  it('renders nothing when no kit has a photo', () => {
    const { container } = render(<KitShowcase rows={[buildRow()]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('links each photo to the cheapest offer and hides the marquee clone', () => {
    render(<KitShowcase rows={[IMAGED_ROW]} />);

    const link = screen.getByRole('link', { name: /HG Gundam — Hobbyland HK\$78/ });
    expect(link).toHaveAttribute('href', 'https://hl/kit');
    expect(document.querySelectorAll('.showcase-item')).toHaveLength(2);
    expect(document.querySelector('.showcase-clone')).toHaveAttribute('aria-hidden', 'true');
  });

  it('drops a kit whose photo fails to load', () => {
    render(<KitShowcase rows={[IMAGED_ROW]} />);
    const img = document.querySelector('.showcase-item img');
    act(() => {
      fireEvent.error(img!);
    });
    expect(document.querySelector('.showcase')).toBeNull();
  });
});

describe('ComparisonGallery', () => {
  it('shows an empty state without rows', () => {
    render(<ComparisonGallery rows={[]} />);
    expect(screen.getByText(/冇資料/)).toBeInTheDocument();
  });

  it('lists every shop with its price and marks the winner', () => {
    render(<ComparisonGallery rows={[IMAGED_ROW]} />);

    expect(screen.getByText('HG Gundam')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'HK$78' })).toHaveAttribute('href', 'https://hl/kit');
    expect(screen.getByText('HK$100')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(document.querySelector('.gallery-offer.winner')).toHaveTextContent('Hobbyland');
    expect(screen.getByText('Hobbyland 最平')).toBeInTheDocument();
  });
});

describe('FactionWipe', () => {
  it('stays hidden on first render and plays after a switch', () => {
    const { rerender } = render(<FactionWipe faction="federation" />);
    expect(document.querySelector('.faction-wipe')).toBeNull();

    rerender(<FactionWipe faction="zeon" />);
    expect(document.querySelector('.faction-wipe')).toHaveAttribute('data-wipe', 'zeon');
  });
});

describe('DashboardPage view toggle', () => {
  it('switches between the table and the gallery', async () => {
    stubApi([buildRow()]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <DashboardPage />
      </QueryClientProvider>,
    );
    await screen.findByText('HG Gundam');
    expect(document.querySelector('.comparison-table')).not.toBeNull();

    await userEvent.click(screen.getByRole('radio', { name: /圖鑑/ }));

    expect(document.querySelector('.comparison-table')).toBeNull();
    expect(document.querySelector('.gallery-card')).not.toBeNull();
    expect(screen.getByRole('radio', { name: /圖鑑/ })).toHaveAttribute('aria-checked', 'true');
  });
});
