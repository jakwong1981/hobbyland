// frontend/tests/fixtures.ts
import { vi, type Mock } from 'vitest';
import type { ComparisonRow, ImportFreshness, Offer } from '../src/types';

export function buildOffer(overrides: Partial<Offer> = {}): Offer {
  return {
    shop: 'hobbyland',
    price: 100,
    regularPrice: null,
    url: 'https://example.com/p',
    stock: null,
    sellType: null,
    imageUrl: null,
    ...overrides,
  };
}

export function buildRow(overrides: Partial<ComparisonRow> = {}): ComparisonRow {
  return {
    sku: '4573102000001',
    grade: 'hg',
    title: 'HG Gundam',
    offers: [
      buildOffer({ shop: 'hobbyland', price: 78 }),
      buildOffer({ shop: 'animes-pro', price: 100 }),
    ],
    cheapestShop: 'hobbyland',
    saving: 22,
    exclusiveShop: null,
    ...overrides,
  };
}

export function buildFreshness(overrides: Partial<ImportFreshness> = {}): ImportFreshness {
  return {
    grade: 'hg',
    overall: '2026-10-11T11:47:00.000Z',
    byShop: {
      hobbyland: '2026-10-11T11:46:00.000Z',
      'animes-pro': '2026-10-11T11:47:00.000Z',
      // A shop that has never been imported must be explicitly null: an absent
      // key reads as undefined, which the FreshnessBar's `=== null` check would
      // render as a <time> with no dateTime.
      hobbydigi: null,
    },
    ...overrides,
  };
}

function envelope(data: unknown): Response {
  return new Response(
    JSON.stringify({ code: 0, message: 'ok', data, timestamp: '2026-01-01T00:00:00Z' }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  );
}

// The dashboard issues two queries, so the stub must route on the requested URL
// instead of answering every path with the comparison payload.
export function stubApi(
  comparisons: ComparisonRow[],
  freshness: ImportFreshness = buildFreshness(),
): Mock {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const data = String(input).includes('/api/imports/freshness') ? freshness : comparisons;
    return Promise.resolve(envelope(data));
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
