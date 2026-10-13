// backend/src/services/import.service.ts
import { parse } from 'csv-parse/sync';
import {
  SHOP_CODES,
  type CsvProductRecord,
  type Grade,
  type ImportFreshness,
  type ImportResult,
  type ShopCode,
  type ShopImportTimestamp,
} from '../types/index.js';
import type { ProductRepository } from '../repositories/product.repository.js';
import { AppError } from '../utils/app-error.js';

interface RawCsvRow {
  title?: string;
  price?: string;
  url?: string;
  regular_price?: string;
  sku?: string;
  stock?: string;
  sell_type?: string;
  image_url?: string;
}

export function parseProductCsv(content: string): { records: CsvProductRecord[]; skipped: number } {
  let rows: RawCsvRow[];
  try {
    rows = parse(content, {
      columns: true,
      bom: true,
      skip_empty_lines: true,
      trim: true,
    }) as RawCsvRow[];
  } catch (err) {
    throw new AppError(400, `Invalid CSV: ${err instanceof Error ? err.message : String(err)}`);
  }

  const records: CsvProductRecord[] = [];
  let skipped = 0;
  for (const row of rows) {
    const record = toRecord(row);
    if (record) {
      records.push(record);
    } else {
      skipped += 1;
    }
  }
  return { records, skipped };
}

export function importProducts(
  repo: ProductRepository,
  shop: ShopCode,
  grade: Grade,
  sourceFile: string,
  records: CsvProductRecord[],
  skipped: number,
): ImportResult {
  const shopId = repo.getShopId(shop);
  let batchId = 0;
  repo.runInTransaction(() => {
    batchId = repo.createBatch(sourceFile, shop, grade, records.length, skipped);
    for (const record of records) {
      if (!isProvisionalSku(record.sku) && record.url) {
        repo.deleteProvisionalByUrl(shopId, grade, record.url);
      }
      repo.upsertProduct(shopId, grade, record, batchId);
    }
  });
  return { batchId, rowCount: records.length, skipped };
}

// Provisional SKUs stand in for a JAN a shop could not supply: hobbydigi uses
// `HD:<slug>`, fookle `FM:<slug>`. Neither is a 13-digit barcode, so when a
// later import resolves the kit to a real JAN the provisional row for the same
// URL is deleted (see deleteProvisionalByUrl) instead of lingering as a
// duplicate that would surface as a false shop-exclusive.
const PROVISIONAL_SKU_PREFIXES = ['HD:', 'FM:'] as const;

export function isProvisionalSku(sku: string): boolean {
  return PROVISIONAL_SKU_PREFIXES.some((prefix) => sku.startsWith(prefix));
}

export function buildFreshness(rows: ShopImportTimestamp[], grade: Grade | null): ImportFreshness {
  const byShop = Object.fromEntries(SHOP_CODES.map((shop) => [shop, null])) as Record<
    ShopCode,
    string | null
  >;
  for (const row of rows) {
    byShop[row.shopCode] = row.importedAt;
  }
  // ISO-8601 timestamps sort lexicographically in chronological order. Reading
  // the populated map rather than iterating a shop list is what keeps `overall`
  // honest: the old form silently dropped any timestamp whose shop was not in
  // that list, so a shop could be imported and still not count towards "latest".
  const stamps = Object.values(byShop)
    .filter((stamp): stamp is string => stamp !== null)
    .sort();
  return { grade, overall: stamps.at(-1) ?? null, byShop };
}

function toRecord(row: RawCsvRow): CsvProductRecord | null {
  const title = row.title?.trim();
  const sku = row.sku?.trim();
  const price = parsePrice(row.price);
  if (!title || !sku || price === null) return null;
  return {
    title,
    sku,
    price,
    url: row.url?.trim() ?? '',
    regularPrice: parsePrice(row.regular_price),
    stock: emptyToNull(row.stock),
    sellType: emptyToNull(row.sell_type),
    imageUrl: emptyToNull(row.image_url),
  };
}

function parsePrice(value: string | undefined): number | null {
  if (value === undefined || value.trim() === '') return null;
  const num = Number(value);
  return Number.isFinite(num) && num >= 0 ? num : null;
}

function emptyToNull(value: string | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}
