// frontend/tests/fixtures.ts
import type { ComparisonRow, Offer } from '../src/types';

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
