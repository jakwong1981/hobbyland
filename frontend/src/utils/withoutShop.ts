// frontend/src/utils/withoutShop.ts
import type { CheapestShop, ComparisonRow, Offer, ShopCode } from '../types';

// Mirrors the backend's computeCheapest so a row re-computed on the client is
// indistinguishable from one the API would have returned without that shop.
function computeCheapest(offers: Offer[]): { cheapestShop: CheapestShop; saving: number | null } {
  if (offers.length === 0) return { cheapestShop: null, saving: null };
  if (offers.length === 1) return { cheapestShop: offers[0]!.shop, saving: null };

  const [lowest, runnerUp] = offers as [Offer, Offer, ...Offer[]];
  const levelWithLowest = offers.filter((offer) => offer.price === lowest.price).length;
  if (levelWithLowest > 1) return { cheapestShop: 'tie', saving: 0 };

  return {
    cheapestShop: lowest.shop,
    saving: Math.round((runnerUp.price - lowest.price) * 100) / 100,
  };
}

/**
 * Drops one shop from every row: its offers disappear and cheapestShop, saving
 * and exclusiveShop are re-derived from what remains, so no verdict can still
 * name the omitted shop. A row only that shop carried is dropped entirely.
 */
export function withoutShop(rows: ComparisonRow[], shop: ShopCode): ComparisonRow[] {
  const result: ComparisonRow[] = [];
  for (const row of rows) {
    const offers = row.offers.filter((offer) => offer.shop !== shop);
    if (offers.length === 0) continue;
    const { cheapestShop, saving } = computeCheapest(offers);
    result.push({
      ...row,
      offers,
      cheapestShop,
      saving,
      exclusiveShop: offers.length === 1 ? offers[0]!.shop : null,
    });
  }
  return result;
}
