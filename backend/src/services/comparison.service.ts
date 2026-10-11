// backend/src/services/comparison.service.ts
import type {
  CheapestShop,
  ComparisonRow,
  Grade,
  Offer,
  ProductRow,
  ShopCode,
} from '../types/index.js';

export function buildComparisons(products: ProductRow[]): ComparisonRow[] {
  const groups = new Map<string, ProductRow[]>();
  for (const product of products) {
    const key = `${product.grade}:${product.sku}`;
    const group = groups.get(key);
    if (group) {
      group.push(product);
    } else {
      groups.set(key, [product]);
    }
  }

  const rows: ComparisonRow[] = [];
  for (const group of groups.values()) {
    rows.push(toComparisonRow(group));
  }
  return rows.sort((a, b) => a.sku.localeCompare(b.sku));
}

function toComparisonRow(group: ProductRow[]): ComparisonRow {
  const offers: Offer[] = group
    .map((p) => ({
      shop: p.shopCode,
      price: p.price,
      regularPrice: p.regularPrice,
      url: p.url,
      stock: p.stock,
      sellType: p.sellType,
      imageUrl: p.imageUrl,
    }))
    .sort((a, b) => a.price - b.price);

  const first = group[0] as ProductRow;
  const { cheapestShop, saving } = computeCheapest(offers);
  return {
    sku: first.sku,
    grade: first.grade as Grade,
    title: first.title,
    offers,
    cheapestShop,
    saving,
    exclusiveShop: offers.length === 1 ? (offers[0] as Offer).shop : null,
  };
}

function computeCheapest(offers: Offer[]): { cheapestShop: CheapestShop; saving: number | null } {
  if (offers.length === 0) return { cheapestShop: null, saving: null };
  // A single offer cannot win a comparison; it is reported through `exclusiveShop` instead.
  if (offers.length === 1) {
    return { cheapestShop: (offers[0] as Offer).shop, saving: null };
  }
  const [lowest, second] = offers as [Offer, Offer];
  if (lowest.price === second.price) {
    return { cheapestShop: 'tie', saving: 0 };
  }
  const saving = Math.round((second.price - lowest.price) * 100) / 100;
  return { cheapestShop: lowest.shop as ShopCode, saving };
}
