// frontend/src/utils/productImage.ts
import { SHOP_CODES, type ComparisonRow } from '../types';

// SHOP_CODES order doubles as the preference order: the first shop that has a
// photo for this kit supplies the image.
export function productImageUrl(row: ComparisonRow): string | null {
  for (const shop of SHOP_CODES) {
    const imageUrl = row.offers.find((o) => o.shop === shop)?.imageUrl;
    if (imageUrl) return imageUrl;
  }
  return null;
}
