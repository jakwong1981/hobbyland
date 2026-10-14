// frontend/tests/without-shop.test.ts
import { describe, expect, it } from 'vitest';
import { productImageUrl } from '../src/utils/productImage';
import { withoutShop } from '../src/utils/withoutShop';
import { buildOffer, buildRow } from './fixtures';

describe('withoutShop', () => {
  it('drops the shop offers and re-derives the verdict from what remains', () => {
    const row = buildRow({
      offers: [
        buildOffer({ shop: 'hobbydigi', price: 70 }),
        buildOffer({ shop: 'hobbyland', price: 78 }),
        buildOffer({ shop: 'animes-pro', price: 100 }),
      ],
      cheapestShop: 'hobbydigi',
      saving: 8,
    });

    const [result] = withoutShop([row], 'hobbydigi');

    expect(result!.offers.map((o) => o.shop)).toEqual(['hobbyland', 'animes-pro']);
    expect(result!.cheapestShop).toBe('hobbyland');
    expect(result!.saving).toBe(22);
    expect(result!.exclusiveShop).toBeNull();
  });

  it('promotes the remaining single offer to an exclusive', () => {
    const row = buildRow({
      offers: [
        buildOffer({ shop: 'hobbyland', price: 80 }),
        buildOffer({ shop: 'hobbydigi', price: 90 }),
      ],
      cheapestShop: 'hobbyland',
      saving: 10,
    });

    const [result] = withoutShop([row], 'hobbydigi');

    expect(result!.cheapestShop).toBe('hobbyland');
    expect(result!.saving).toBeNull();
    expect(result!.exclusiveShop).toBe('hobbyland');
  });

  it('reports a tie when the remaining cheapest offers are level', () => {
    const row = buildRow({
      offers: [
        buildOffer({ shop: 'hobbydigi', price: 50 }),
        buildOffer({ shop: 'hobbyland', price: 78 }),
        buildOffer({ shop: 'animes-pro', price: 78 }),
      ],
      cheapestShop: 'hobbydigi',
      saving: 28,
    });

    const [result] = withoutShop([row], 'hobbydigi');

    expect(result!.cheapestShop).toBe('tie');
    expect(result!.saving).toBe(0);
  });

  it('drops a row only the omitted shop carried', () => {
    const row = buildRow({
      sku: 'HD:some-kit',
      offers: [buildOffer({ shop: 'hobbydigi', price: 90 })],
      cheapestShop: 'hobbydigi',
      saving: null,
      exclusiveShop: 'hobbydigi',
    });

    expect(withoutShop([row], 'hobbydigi')).toEqual([]);
  });

  it('leaves rows untouched when they have no offer from that shop', () => {
    const row = buildRow();

    const [result] = withoutShop([row], 'hobbydigi');

    expect(result).toEqual(row);
  });

  it('sorts remaining offers by price before re-deriving cheapestShop and saving', () => {
    const row = buildRow({
      offers: [
        buildOffer({ shop: 'animes-pro', price: 110 }),
        buildOffer({ shop: 'hobbydigi', price: 70 }),
        buildOffer({ shop: 'fookle', price: 85 }),
      ],
      cheapestShop: 'hobbydigi',
      saving: 15,
    });

    const [result] = withoutShop([row], 'hobbydigi');

    expect(result!.offers.map((o) => o.shop)).toEqual(['fookle', 'animes-pro']);
    expect(result!.cheapestShop).toBe('fookle');
    expect(result!.saving).toBe(25);
  });

  it('skips omitted dashboard shops when picking a product image', () => {
    const row = buildRow({
      offers: [
        buildOffer({ shop: 'hobbydigi', imageUrl: 'https://cdn.example/hd.jpg' }),
        buildOffer({ shop: 'fookle', imageUrl: 'https://cdn.example/fm.jpg' }),
      ],
    });

    expect(productImageUrl(row)).toBe('https://cdn.example/fm.jpg');
  });
});
