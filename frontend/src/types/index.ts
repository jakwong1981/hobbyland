// frontend/src/types/index.ts
// Mirrors backend/src/types/index.ts by hand — there is no shared package.
export const SHOP_CODES = ['hobbyland', 'animes-pro', 'hobbydigi', 'fookle', 'twinnermodel'] as const;
export type ShopCode = (typeof SHOP_CODES)[number];

export const GRADES = ['hg', 'mg', 'rg'] as const;
export type Grade = (typeof GRADES)[number];

export type CheapestShop = ShopCode | 'tie' | null;
export type Faction = 'federation' | 'zeon';
export type DashboardView = 'table' | 'gallery';

export type ShopFilterValue = ShopCode | 'all';
export type SeriesFilterValue = string | 'all';
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
  series: string | null;
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

export type ScrapeJobState = 'idle' | 'running' | 'completed' | 'failed';

export interface ScrapeJobStatus {
  state: ScrapeJobState;
  startedAt: string | null;
  finishedAt: string | null;
  exitCode: number | null;
}

export interface ImportFreshness {
  grade: Grade | null;
  overall: string | null;
  byShop: Record<ShopCode, string | null>;
}

// P-Bandai HK showcase item — mirrors backend PbandaiItem; never joins
// price comparison.
export interface PbandaiItem {
  id: number;
  name: string;
  tcName: string | null;
  price: number | null;
  status: string | null;
  url: string;
  imageUrl: string | null;
  importedAt: string;
}
