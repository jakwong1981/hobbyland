// backend/src/services/import.service.ts
import { parse } from 'csv-parse/sync';
import type { CsvProductRecord, Grade, ImportResult, ShopCode } from '../types/index.js';
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
      repo.upsertProduct(shopId, grade, record, batchId);
    }
  });
  return { batchId, rowCount: records.length, skipped };
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
