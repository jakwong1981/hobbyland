// frontend/src/utils/showcase.ts
import type { ComparisonRow, Offer } from '../types';
import { productImageUrl } from './productImage';

export const SHOWCASE_LIMIT = 16;

export interface ShowcaseKit {
  key: string;
  title: string;
  imageUrl: string;
  bestOffer: Offer;
  saving: number | null;
}

function lowestOffer(row: ComparisonRow): Offer | undefined {
  return row.offers.reduce<Offer | undefined>(
    (best, offer) => (best === undefined || offer.price < best.price ? offer : best),
    undefined,
  );
}

// Kits with the biggest saving lead the strip: they are the most useful to spot at a glance.
export function selectShowcaseKits(rows: ComparisonRow[], limit = SHOWCASE_LIMIT): ShowcaseKit[] {
  const kits: ShowcaseKit[] = [];
  for (const row of rows) {
    const imageUrl = productImageUrl(row);
    const bestOffer = lowestOffer(row);
    if (imageUrl === null || bestOffer === undefined) continue;
    kits.push({ key: `${row.grade}-${row.sku}`, title: row.title, imageUrl, bestOffer, saving: row.saving });
  }
  return kits.sort((a, b) => (b.saving ?? -1) - (a.saving ?? -1)).slice(0, limit);
}
