// backend/src/repositories/pbandai.repository.ts
import type { DatabaseSync } from 'node:sqlite';
import type { PbandaiCsvRecord, PbandaiItem } from '../types/index.js';

interface PbandaiQueryRow {
  id: number;
  name: string;
  tc_name: string | null;
  price: number | null;
  status: string | null;
  url: string;
  image_url: string | null;
  imported_at: string;
}

export class PbandaiRepository {
  constructor(private readonly db: DatabaseSync) {}

  // Snapshot semantics: the scrape reflects the current P-Bandai catalog, so
  // an import replaces the whole table — closed pre-orders must disappear.
  // Insert order preserves the site's NewArrival sort.
  replaceAll(records: PbandaiCsvRecord[], importedAt: string): void {
    this.db.exec('BEGIN');
    try {
      this.db.prepare('DELETE FROM pbandai_items').run();
      const insert = this.db.prepare(
        `INSERT INTO pbandai_items (name, tc_name, price, status, url, image_url, imported_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
      );
      for (const record of records) {
        insert.run(
          record.name,
          record.tcName,
          record.price,
          record.status,
          record.url,
          record.imageUrl,
          importedAt,
        );
      }
      this.db.exec('COMMIT');
    } catch (err) {
      this.db.exec('ROLLBACK');
      throw err;
    }
  }

  findAll(q?: string): PbandaiItem[] {
    const where = q ? 'WHERE name LIKE ? OR tc_name LIKE ?' : '';
    const params = q ? [`%${q}%`, `%${q}%`] : [];
    const rows = this.db
      .prepare(
        `SELECT id, name, tc_name, price, status, url, image_url, imported_at
         FROM pbandai_items ${where} ORDER BY id`,
      )
      .all(...params) as unknown as PbandaiQueryRow[];
    return rows.map((r) => ({
      id: r.id,
      name: r.name,
      tcName: r.tc_name,
      price: r.price,
      status: r.status,
      url: r.url,
      imageUrl: r.image_url,
      importedAt: r.imported_at,
    }));
  }
}
