// frontend/src/types/index.ts
export type ShopCode = 'hobbyland' | 'animes-pro';
export type Grade = 'hg' | 'mg' | 'rg';
export type CheapestShop = ShopCode | 'tie' | null;
export type Faction = 'federation' | 'zeon';

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
