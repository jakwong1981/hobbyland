// frontend/src/shops.ts
// One home for how a shop is presented. Previously CheaperBadge, FreshnessBar
// and ComparisonTable each carried their own label map and had drifted apart
// ('Animes' vs 'Animes-Pro'); the tone classes and filter options were
// duplicated alongside them. Adding a shop is now one entry per map.
import { SHOP_CODES, type ShopCode } from './types';

// The dashboard compares these shops only. HobbyDigi is deliberately hidden
// from every dashboard surface; imports and the API still carry its data.
export const DASHBOARD_SHOPS: readonly ShopCode[] = SHOP_CODES.filter(
  (shop) => shop !== 'hobbydigi',
);

export const SHOP_LABEL: Record<ShopCode, string> = {
  'hobbyland': 'Hobbyland',
  'animes-pro': 'Animes-Pro',
  'hobbydigi': 'HobbyDigi',
  'fookle': 'Fookle Model',
  'twinnermodel': 'Twinner Model 千里達',
};

// Compact form for the verdict badge, whose column is the narrowest on the page.
export const SHOP_SHORT_LABEL: Record<ShopCode, string> = {
  'hobbyland': 'Hobbyland',
  'animes-pro': 'Animes',
  'hobbydigi': 'HobbyDigi',
  'fookle': 'Fookle',
  'twinnermodel': 'Twinnermodel',
};

// Tone classes drive each shop's logo colour (see --shop-* tokens in styles/tokens.css).
// Price text stays neutral so the faction accent keeps meaning "the winner".
export const SHOP_TONE: Record<ShopCode, string> = {
  'hobbyland': 'shop-a',
  'animes-pro': 'shop-b',
  'hobbydigi': 'shop-c',
  'fookle': 'shop-d',
  'twinnermodel': 'shop-e',
};

export const SHOP_MONOGRAM: Record<ShopCode, string> = {
  'hobbyland': 'HL',
  'animes-pro': 'AP',
  'hobbydigi': 'HD',
  'fookle': 'FM',
  'twinnermodel': 'TM',
};
