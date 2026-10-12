// frontend/src/shops.ts
// One home for how a shop is presented. Previously CheaperBadge, FreshnessBar
// and ComparisonTable each carried their own label map and had drifted apart
// ('Animes' vs 'Animes-Pro'); the tone classes and filter options were
// duplicated alongside them. Adding a shop is now one entry per map.
import type { ShopCode } from './types';

export const SHOP_LABEL: Record<ShopCode, string> = {
  'hobbyland': 'Hobbyland',
  'animes-pro': 'Animes-Pro',
  'hobbydigi': 'HobbyDigi',
};

// Compact form for the verdict badge, whose column is the narrowest on the page.
export const SHOP_SHORT_LABEL: Record<ShopCode, string> = {
  'hobbyland': 'Hobbyland',
  'animes-pro': 'Animes',
  'hobbydigi': 'HobbyDigi',
};

// Shops are told apart by neutral value only, never by faction colour — see the
// --shop-* tokens in styles.css.
export const SHOP_TONE: Record<ShopCode, string> = {
  'hobbyland': 'shop-a',
  'animes-pro': 'shop-b',
  'hobbydigi': 'shop-c',
};
