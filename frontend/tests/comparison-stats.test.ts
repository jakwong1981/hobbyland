// frontend/tests/comparison-stats.test.ts
import { describe, expect, it } from 'vitest';
import { summarizeComparisons } from '../src/utils/comparisonStats';
import { selectShowcaseKits } from '../src/utils/showcase';
import { productImageUrl } from '../src/utils/productImage';
import { buildOffer, buildRow } from './fixtures';

describe('summarizeComparisons', () => {
  it('counts cheapest wins per shop, ties and exclusives separately', () => {
    const rows = [
      buildRow({ sku: '1', cheapestShop: 'hobbyland' }),
      buildRow({ sku: '2', cheapestShop: 'hobbyland' }),
      buildRow({ sku: '3', cheapestShop: 'animes-pro' }),
      buildRow({ sku: '4', cheapestShop: 'tie' }),
      buildRow({ sku: '5', cheapestShop: 'hobbydigi', exclusiveShop: 'hobbydigi' }),
      buildRow({ sku: '6', cheapestShop: null }),
    ];

    const summary = summarizeComparisons(rows);

    expect(summary).toEqual({
      total: 6,
      cheapestByShop: { hobbyland: 2, 'animes-pro': 1, hobbydigi: 0 },
      ties: 1,
      exclusives: 1,
      exclusivesByShop: { hobbyland: 0, 'animes-pro': 0, hobbydigi: 1 },
    });
  });

  it('returns zeroes for no rows', () => {
    expect(summarizeComparisons([])).toEqual({
      total: 0,
      cheapestByShop: { hobbyland: 0, 'animes-pro': 0, hobbydigi: 0 },
      ties: 0,
      exclusives: 0,
      exclusivesByShop: { hobbyland: 0, 'animes-pro': 0, hobbydigi: 0 },
    });
  });
});

describe('productImageUrl', () => {
  it('prefers the first shop in SHOP_CODES order that has a photo', () => {
    const row = buildRow({
      offers: [
        buildOffer({ shop: 'animes-pro', imageUrl: 'https://cdn/a.jpg' }),
        buildOffer({ shop: 'hobbyland', imageUrl: 'https://cdn/h.jpg' }),
      ],
    });
    expect(productImageUrl(row)).toBe('https://cdn/h.jpg');
  });

  it('returns null when no offer has a photo', () => {
    expect(productImageUrl(buildRow())).toBeNull();
  });
});

describe('selectShowcaseKits', () => {
  const withImage = (sku: string, saving: number | null, prices: [number, number]) =>
    buildRow({
      sku,
      saving,
      offers: [
        buildOffer({ shop: 'hobbyland', price: prices[0], imageUrl: `https://cdn/${sku}.jpg` }),
        buildOffer({ shop: 'animes-pro', price: prices[1], url: `https://animes/${sku}` }),
      ],
    });

  it('keeps only kits with a photo, biggest saving first', () => {
    const rows = [withImage('a', 5, [100, 105]), buildRow({ sku: 'no-img' }), withImage('b', 40, [140, 100]), withImage('c', null, [80, 90])];

    const kits = selectShowcaseKits(rows);

    expect(kits.map((k) => k.key)).toEqual(['hg-b', 'hg-a', 'hg-c']);
  });

  it('links each kit to its lowest-priced offer', () => {
    const [kit] = selectShowcaseKits([withImage('b', 40, [140, 100])]);
    expect(kit?.bestOffer.shop).toBe('animes-pro');
    expect(kit?.bestOffer.url).toBe('https://animes/b');
  });

  it('caps the number of kits', () => {
    const rows = Array.from({ length: 30 }, (_, i) => withImage(String(i), i, [100, 110]));
    expect(selectShowcaseKits(rows, 16)).toHaveLength(16);
  });
});
