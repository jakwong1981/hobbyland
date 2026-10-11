// backend/tests/comparison.service.test.ts
import { describe, expect, it } from 'vitest';
import { buildComparisons } from '../src/services/comparison.service.js';
import type { ProductRow } from '../src/types/index.js';

function product(overrides: Partial<ProductRow>): ProductRow {
  return {
    id: 1,
    shopCode: 'hobbyland',
    sku: '4573102663849',
    grade: 'hg',
    title: 'Strike Freedom',
    price: 100,
    regularPrice: null,
    url: 'https://example.com/p/1',
    stock: null,
    sellType: '現貨',
    importedAt: '2026-10-11T00:00:00.000Z',
    ...overrides,
  };
}

describe('buildComparisons', () => {
  it('marks the cheaper shop and computes the saving', () => {
    const rows = buildComparisons([
      product({ shopCode: 'hobbyland', price: 140 }),
      product({ id: 2, shopCode: 'animes-pro', price: 118 }),
    ]);

    expect(rows).toHaveLength(1);
    const row = rows[0]!;
    expect(row.cheapestShop).toBe('animes-pro');
    expect(row.saving).toBe(22);
    expect(row.exclusiveShop).toBeNull();
    expect(row.offers.map((o) => o.shop)).toEqual(['animes-pro', 'hobbyland']);
  });

  it('marks a tie when both shops charge the same price', () => {
    const rows = buildComparisons([
      product({ price: 200 }),
      product({ id: 2, shopCode: 'animes-pro', price: 200 }),
    ]);

    expect(rows[0]!.cheapestShop).toBe('tie');
    expect(rows[0]!.saving).toBe(0);
    expect(rows[0]!.exclusiveShop).toBeNull();
  });

  it('reports the only shop with null saving for a single-shop sku', () => {
    const rows = buildComparisons([product({ price: 99 })]);

    expect(rows[0]!.cheapestShop).toBe('hobbyland');
    expect(rows[0]!.saving).toBeNull();
    expect(rows[0]!.offers).toHaveLength(1);
  });

  it('flags a single-shop sku as exclusive so the ui cannot call it cheaper', () => {
    const rows = buildComparisons([product({ shopCode: 'animes-pro', price: 99 })]);

    expect(rows[0]!.exclusiveShop).toBe('animes-pro');
  });

  it('keeps different grades of the same sku in separate groups', () => {
    const rows = buildComparisons([
      product({ grade: 'hg' }),
      product({ id: 2, grade: 'mg', shopCode: 'animes-pro' }),
    ]);

    expect(rows).toHaveLength(2);
  });

  it('sorts rows by sku', () => {
    const rows = buildComparisons([
      product({ sku: '9999999999999' }),
      product({ id: 2, sku: '1111111111111' }),
    ]);

    expect(rows.map((r) => r.sku)).toEqual(['1111111111111', '9999999999999']);
  });
});
