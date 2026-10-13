// frontend/src/types/index.ts
// Mirrors backend/src/types/index.ts by hand — there is no shared package.
export const SHOP_CODES = ['hobbyland', 'animes-pro', 'hobbydigi'] as const;
export type ShopCode = (typeof SHOP_CODES)[number];

export const GRADES = ['hg', 'mg', 'rg'] as const;
export type Grade = (typeof GRADES)[number];

export type CheapestShop = ShopCode | 'tie' | null;
export type Faction = 'federation' | 'zeon';
export type DashboardView = 'table' | 'gallery';

export type ShopFilterValue = ShopCode | 'all';
export type SortKey = 'title' | ShopCode;
export type SortDirection = 'asc' | 'desc';

export interface SortState {
  key: SortKey;
  direction: SortDirection;
}

export interface Offer {
  shop: ShopCode;
  price: number;
  regularPrice: number | null;
  url: string;
  stock: string | null;
  sellType: string | null;
  imageUrl: string | null;
}

export interface ComparisonRow {
  sku: string;
  grade: Grade;
  title: string;
  offers: Offer[];
  cheapestShop: CheapestShop;
  saving: number | null;
  exclusiveShop: ShopCode | null;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
  timestamp: string;
}

export interface ImportResult {
  batchId: number;
  rowCount: number;
  skipped: number;
}

export interface ImportFreshness {
  grade: Grade | null;
  overall: string | null;
  byShop: Record<ShopCode, string | null>;
}
