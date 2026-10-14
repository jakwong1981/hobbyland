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
    imageUrl: null,
    series: null,
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

  it('takes any classified series across the group when shops were enriched at different times', () => {
    const rows = buildComparisons([
      product({ shopCode: 'hobbyland', price: 140, series: null }),
      product({ id: 2, shopCode: 'animes-pro', price: 118, series: 'seed_destiny' }),
    ]);

    expect(rows[0]!.series).toBe('seed_destiny');
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

  it('takes the group title from the highest-ranked shop, not row order', () => {
    // findProducts orders by sku alone, so within a group the order is
    // unspecified. Animes-Pro arriving first must not win the displayed title.
    const rows = buildComparisons([
      product({ id: 2, shopCode: 'animes-pro', price: 118, title: 'Animes wording' }),
      product({ id: 1, shopCode: 'hobbyland', price: 140, title: 'Hobbyland wording' }),
    ]);

    expect(rows[0]!.title).toBe('Hobbyland wording');
  });
});

describe('buildComparisons with more than two offers', () => {
  // ShopCode has two members today. Casting a third pins the N-way arithmetic
  // without adding a shop that has no data source behind it.
  const thirdShop = () => 'third-shop' as ProductRow['shopCode'];

  it('picks the cheapest and measures the saving against the runner-up', () => {
    const rows = buildComparisons([
      product({ id: 1, shopCode: 'hobbyland', price: 100 }),
      product({ id: 2, shopCode: 'animes-pro', price: 150 }),
      product({ id: 3, shopCode: thirdShop(), price: 120 }),
    ]);
    const row = rows[0]!;

    expect(row.offers.map((o) => o.price)).toEqual([100, 120, 150]);
    expect(row.cheapestShop).toBe('hobbyland');
    expect(row.saving).toBe(20);
    expect(row.exclusiveShop).toBeNull();
  });

  it('calls a two-way tie for the lowest price a tie even with a dearer third offer', () => {
    const rows = buildComparisons([
      product({ id: 1, shopCode: 'hobbyland', price: 100 }),
      product({ id: 2, shopCode: 'animes-pro', price: 150 }),
      product({ id: 3, shopCode: thirdShop(), price: 100 }),
    ]);

    expect(rows[0]!.cheapestShop).toBe('tie');
    expect(rows[0]!.saving).toBe(0);
  });

  it('calls three level offers a tie', () => {
    const rows = buildComparisons([
      product({ id: 1, shopCode: 'hobbyland', price: 100 }),
      product({ id: 2, shopCode: 'animes-pro', price: 100 }),
      product({ id: 3, shopCode: thirdShop(), price: 100 }),
    ]);

    expect(rows[0]!.cheapestShop).toBe('tie');
    expect(rows[0]!.exclusiveShop).toBeNull();
  });
});

describe('buildComparisons across all five real shops', () => {
  it('picks twinnermodel when it undercuts the other four', () => {
    const rows = buildComparisons([
      product({ id: 1, shopCode: 'hobbyland', price: 140 }),
      product({ id: 2, shopCode: 'animes-pro', price: 130 }),
      product({ id: 3, shopCode: 'hobbydigi', price: 125 }),
      product({ id: 4, shopCode: 'fookle', price: 120 }),
      product({ id: 5, shopCode: 'twinnermodel', price: 102 }),
    ]);
    const row = rows[0]!;

    expect(row.cheapestShop).toBe('twinnermodel');
    expect(row.saving).toBe(18);
    expect(row.exclusiveShop).toBeNull();
    expect(row.offers.map((o) => o.shop)[0]).toBe('twinnermodel');
  });

  it('flags a twinnermodel-only sku as exclusive', () => {
    const rows = buildComparisons([
      product({ id: 1, shopCode: 'twinnermodel', price: 102 }),
    ]);
    const row = rows[0]!;

    expect(row.exclusiveShop).toBe('twinnermodel');
    expect(row.saving).toBeNull();
  });
});
