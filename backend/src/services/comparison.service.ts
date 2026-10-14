// backend/src/services/comparison.service.ts
import {
  SHOP_CODES,
  type CheapestShop,
  type ComparisonRow,
  type Grade,
  type Offer,
  type ProductRow,
  type ShopCode,
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

  const first = representative(group);
  const { cheapestShop, saving } = computeCheapest(offers);
  return {
    sku: first.sku,
    grade: first.grade as Grade,
    title: first.title,
    series: groupSeries(group),
    offers,
    cheapestShop,
    saving,
    exclusiveShop: offers.length === 1 ? (offers[0] as Offer).shop : null,
  };
}

/**
 * The row whose title is shown for the whole group.
 *
 * `findProducts` orders by sku alone, so the order *within* a group is
 * unspecified and each shop words the same kit differently — which title was
 * displayed used to depend on row insertion order. Ranking by SHOP_CODES makes
 * it stable and predictable.
 */
function representative(group: ProductRow[]): ProductRow {
  let best = group[0] as ProductRow;
  for (const row of group) {
    if (shopRank(row.shopCode) < shopRank(best.shopCode)) {
      best = row;
    }
  }
  return best;
}

function shopRank(code: ShopCode): number {
  const index = SHOP_CODES.indexOf(code);
  return index === -1 ? SHOP_CODES.length : index;
}

// Shops are enriched at different times, so a group can mix classified and
// unclassified rows; any classification beats none.
function groupSeries(group: ProductRow[]): string | null {
  for (const row of group) {
    if (row.series !== null) return row.series;
  }
  return null;
}

function computeCheapest(offers: Offer[]): { cheapestShop: CheapestShop; saving: number | null } {
  if (offers.length === 0) return { cheapestShop: null, saving: null };
  // A single offer cannot win a comparison; it is reported through `exclusiveShop` instead.
  if (offers.length === 1) {
    return { cheapestShop: (offers[0] as Offer).shop, saving: null };
  }

  // `offers` is sorted ascending, so index 0 is the cheapest and index 1 the
  // runner-up. Asserting a *minimum* length stays true for any number of shops,
  // where `as [Offer, Offer]` quietly stopped describing the array at three.
  const [lowest, runnerUp] = offers as [Offer, Offer, ...Offer[]];
  // Sorting puts every offer level with the cheapest at the front, so counting
  // them is equivalent to comparing the top two — but it says what it means and
  // keeps holding if the sort is ever removed.
  const levelWithLowest = offers.filter((offer) => offer.price === lowest.price).length;
  if (levelWithLowest > 1) {
    return { cheapestShop: 'tie', saving: 0 };
  }

  // At three or more shops this is the gap to the runner-up, i.e. what you save
  // versus the next-best alternative, rather than versus one specific rival.
  const saving = Math.round((runnerUp.price - lowest.price) * 100) / 100;
  return { cheapestShop: lowest.shop, saving };
}
