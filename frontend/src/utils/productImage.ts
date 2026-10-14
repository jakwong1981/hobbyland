// frontend/src/utils/productImage.ts
import type { ComparisonRow } from '../types';
import { DASHBOARD_SHOPS } from '../shops';

// DASHBOARD_SHOPS order doubles as the preference order: the first shop that
// has a photo for this kit supplies the image.
export function productImageUrl(row: ComparisonRow): string | null {
  for (const shop of DASHBOARD_SHOPS) {
    const imageUrl = row.offers.find((o) => o.shop === shop)?.imageUrl;
    if (imageUrl) return imageUrl;
  }
  return null;
}
