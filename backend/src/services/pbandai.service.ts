// backend/src/services/pbandai.service.ts
import { parse } from 'csv-parse/sync';
import type { PbandaiCsvRecord } from '../types/index.js';
import type { PbandaiRepository } from '../repositories/pbandai.repository.js';
import { AppError } from '../utils/app-error.js';

// Matches pbandai_scraper_v2.py's save_csv fieldnames.
interface RawPbandaiCsvRow {
  name?: string;
  tc_name?: string;
  price?: string;
  status?: string;
  url?: string;
  image?: string;
}

export function parsePbandaiCsv(content: string): { records: PbandaiCsvRecord[]; skipped: number } {
  let rows: RawPbandaiCsvRow[];
  try {
    rows = parse(content, {
      columns: true,
      bom: true,
      skip_empty_lines: true,
      trim: true,
    }) as RawPbandaiCsvRow[];
  } catch (err) {
    throw new AppError(400, `Invalid CSV: ${err instanceof Error ? err.message : String(err)}`);
  }

  const records: PbandaiCsvRecord[] = [];
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

export function importPbandaiItems(
  repo: PbandaiRepository,
  records: PbandaiCsvRecord[],
): { rowCount: number } {
  repo.replaceAll(records, new Date().toISOString());
  return { rowCount: records.length };
}

function toRecord(row: RawPbandaiCsvRow): PbandaiCsvRecord | null {
  const name = row.name?.trim();
  const url = row.url?.trim();
  if (!name || !url) return null;
  return {
    name,
    url,
    tcName: emptyToNull(row.tc_name),
    price: parsePrice(row.price),
    status: emptyToNull(row.status),
    imageUrl: emptyToNull(row.image),
  };
}

// The scraper writes the raw card text ("HK$450.00", "N/A"); only the numeric
// part is worth storing.
function parsePrice(value: string | undefined): number | null {
  if (value === undefined) return null;
  const digits = value.replace(/[^\d.]/g, '');
  if (digits === '') return null;
  const num = Number(digits);
  return Number.isFinite(num) && num >= 0 ? num : null;
}

function emptyToNull(value: string | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}
