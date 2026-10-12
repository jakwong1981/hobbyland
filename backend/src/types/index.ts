// backend/src/types/index.ts
export const SHOP_CODES = ['hobbyland', 'animes-pro', 'hobbydigi'] as const;
export type ShopCode = (typeof SHOP_CODES)[number];

export const GRADES = ['hg', 'mg', 'rg'] as const;
export type Grade = (typeof GRADES)[number];

export type CheapestShop = ShopCode | 'tie' | null;

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

export interface ApiErrorResponse {
  code: number;
  message: string;
  data: null;
  timestamp: string;
  traceId: string;
}

export interface ProductRow {
  id: number;
  shopCode: ShopCode;
  sku: string;
  grade: Grade;
  title: string;
  price: number;
  regularPrice: number | null;
  url: string;
  stock: string | null;
  sellType: string | null;
  imageUrl: string | null;
  importedAt: string;
}

export interface CsvProductRecord {
  title: string;
  price: number;
  url: string;
  regularPrice: number | null;
  sku: string;
  stock: string | null;
  sellType: string | null;
  imageUrl: string | null;
}

export interface ImportResult {
  batchId: number;
  rowCount: number;
  skipped: number;
}

export interface ImportBatchDto {
  id: number;
  sourceFile: string;
  shopCode: string;
  grade: string;
  rowCount: number;
  skippedCount: number;
  importedAt: string;
}

export interface ShopImportTimestamp {
  shopCode: ShopCode;
  importedAt: string;
}

export interface ImportFreshness {
  grade: Grade | null;
  overall: string | null;
  byShop: Record<ShopCode, string | null>;
}
