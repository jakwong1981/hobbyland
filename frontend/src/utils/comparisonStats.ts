// frontend/src/utils/comparisonStats.ts
import { SHOP_CODES, type ComparisonRow, type ShopCode } from '../types';

export interface ComparisonSummary {
  total: number;
  cheapestByShop: Record<ShopCode, number>;
  ties: number;
  exclusives: number;
  exclusivesByShop: Record<ShopCode, number>;
}

function emptyShopCounts(): Record<ShopCode, number> {
  return Object.fromEntries(SHOP_CODES.map((shop) => [shop, 0])) as Record<ShopCode, number>;
}

// Exclusive SKUs are counted apart from "cheapest": being the only seller is not a price win.
export function summarizeComparisons(rows: ComparisonRow[]): ComparisonSummary {
  const cheapestByShop = emptyShopCounts();
  const exclusivesByShop = emptyShopCounts();
  let ties = 0;
  let exclusives = 0;

  for (const row of rows) {
    if (row.exclusiveShop !== null) {
      exclusives += 1;
      exclusivesByShop[row.exclusiveShop] += 1;
    } else if (row.cheapestShop === 'tie') {
      ties += 1;
    } else if (row.cheapestShop !== null) {
      cheapestByShop[row.cheapestShop] += 1;
    }
  }

  return { total: rows.length, cheapestByShop, ties, exclusives, exclusivesByShop };
}
