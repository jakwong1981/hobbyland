// backend/src/repositories/product.repository.ts
import type { DatabaseSync } from 'node:sqlite';
import type {
  CsvProductRecord,
  Grade,
  ImportBatchDto,
  ProductRow,
  ShopCode,
  ShopImportTimestamp,
} from '../types/index.js';

interface ProductQueryRow {
  id: number;
  shop_code: string;
  sku: string;
  grade: string;
  title: string;
  price: number;
  regular_price: number | null;
  url: string;
  stock: string | null;
  sell_type: string | null;
  image_url: string | null;
  series: string | null;
  imported_at: string;
}

interface BatchQueryRow {
  id: number;
  source_file: string;
  shop_code: string;
  grade: string;
  row_count: number;
  skipped_count: number;
  imported_at: string;
}

export class ProductRepository {
  constructor(private readonly db: DatabaseSync) {}

  getShopId(code: ShopCode): number {
    const row = this.db
      .prepare('SELECT id FROM shops WHERE code = ?')
      .get(code) as { id: number } | undefined;
    if (!row) throw new Error(`Unknown shop code: ${code}`);
    return row.id;
  }

  createBatch(sourceFile: string, shopCode: ShopCode, grade: Grade, rowCount: number, skipped: number): number {
    const result = this.db
      .prepare(
        `INSERT INTO import_batches (source_file, shop_code, grade, row_count, skipped_count, imported_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .run(sourceFile, shopCode, grade, rowCount, skipped, new Date().toISOString());
    return Number(result.lastInsertRowid);
  }

  upsertProduct(shopId: number, grade: Grade, record: CsvProductRecord, batchId: number): void {
    // A CSV predating the image_url/series columns parses to null; COALESCE keeps
    // the stored value instead of letting a stale re-import wipe it.
    this.db
      .prepare(
        `INSERT INTO products (shop_id, sku, grade, title, price, regular_price, url, stock, sell_type, image_url, series, batch_id, imported_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT (shop_id, sku, grade) DO UPDATE SET
           title = excluded.title,
           price = excluded.price,
           regular_price = excluded.regular_price,
           url = excluded.url,
           stock = excluded.stock,
           sell_type = excluded.sell_type,
           image_url = COALESCE(excluded.image_url, products.image_url),
           series = COALESCE(excluded.series, products.series),
           batch_id = excluded.batch_id,
           imported_at = excluded.imported_at`,
      )
      .run(
        shopId,
        record.sku,
        grade,
        record.title,
        record.price,
        record.regularPrice,
        record.url,
        record.stock,
        record.sellType,
        record.imageUrl,
        record.series,
        batchId,
        new Date().toISOString(),
      );
  }

  deleteProvisionalByUrl(shopId: number, grade: Grade, url: string): void {
    // A provisional key is `<PREFIX>:<slug>` (HD: hobbydigi, FM: fookle,
    // TM: twinnermodel) — the only sku shape that carries a colon, since a real
    // JAN is 13 digits. Deleting by
    // that marker replaces a stale provisional row for this URL whatever prefix
    // it used, so a kit that later resolves a JAN leaves no duplicate behind.
    this.db
      .prepare("DELETE FROM products WHERE shop_id = ? AND grade = ? AND url = ? AND sku LIKE '%:%'")
      .run(shopId, grade, url);
  }

  findProducts(filters: { shop?: ShopCode; grade?: Grade; q?: string; series?: string }): ProductRow[] {
    const conditions: string[] = [];
    const params: string[] = [];
    if (filters.shop) {
      conditions.push('s.code = ?');
      params.push(filters.shop);
    }
    if (filters.grade) {
      conditions.push('p.grade = ?');
      params.push(filters.grade);
    }
    if (filters.series) {
      conditions.push('p.series = ?');
      params.push(filters.series);
    }
    if (filters.q) {
      conditions.push('(p.title LIKE ? OR p.sku LIKE ?)');
      params.push(`%${filters.q}%`, `%${filters.q}%`);
    }
    const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
    const rows = this.db
      .prepare(
        `SELECT p.id, s.code AS shop_code, p.sku, p.grade, p.title, p.price, p.regular_price,
                p.url, p.stock, p.sell_type, p.image_url, p.series, p.imported_at
         FROM products p JOIN shops s ON s.id = p.shop_id
         ${where}
         ORDER BY p.sku`,
      )
      .all(...params) as unknown as ProductQueryRow[];
    return rows.map(mapProductRow);
  }

  listBatches(limit: number): ImportBatchDto[] {
    const rows = this.db
      .prepare(
        `SELECT id, source_file, shop_code, grade, row_count, skipped_count, imported_at
         FROM import_batches ORDER BY id DESC LIMIT ?`,
      )
      .all(limit) as unknown as BatchQueryRow[];
    return rows.map((r) => ({
      id: r.id,
      sourceFile: r.source_file,
      shopCode: r.shop_code,
      grade: r.grade,
      rowCount: r.row_count,
      skippedCount: r.skipped_count,
      importedAt: r.imported_at,
    }));
  }

  findLatestImportPerShop(grade?: Grade): ShopImportTimestamp[] {
    const where = grade ? 'WHERE p.grade = ?' : '';
    const params = grade ? [grade] : [];
    const rows = this.db
      .prepare(
        `SELECT s.code AS shop_code, MAX(p.imported_at) AS imported_at
         FROM products p JOIN shops s ON s.id = p.shop_id
         ${where}
         GROUP BY s.code`,
      )
      .all(...params) as unknown as Array<{ shop_code: string; imported_at: string }>;
    return rows.map((r) => ({ shopCode: r.shop_code as ShopCode, importedAt: r.imported_at }));
  }

  runInTransaction(work: () => void): void {
    this.db.exec('BEGIN');
    try {
      work();
      this.db.exec('COMMIT');
    } catch (err) {
      this.db.exec('ROLLBACK');
      throw err;
    }
  }
}

function mapProductRow(r: ProductQueryRow): ProductRow {
  return {
    id: r.id,
    shopCode: r.shop_code as ShopCode,
    sku: r.sku,
    grade: r.grade as Grade,
    title: r.title,
    price: r.price,
    regularPrice: r.regular_price,
    url: r.url,
    stock: r.stock,
    sellType: r.sell_type,
    imageUrl: r.image_url,
    series: r.series,
    importedAt: r.imported_at,
  };
}
