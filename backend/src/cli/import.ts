// backend/src/cli/import.ts
import { readFileSync, readdirSync } from 'node:fs';
import { basename, join } from 'node:path';
import { loadConfig } from '../config.js';
import { createDatabase } from '../db/client.js';
import { ProductRepository } from '../repositories/product.repository.js';
import { PbandaiRepository } from '../repositories/pbandai.repository.js';
import { importProducts, parseProductCsv } from '../services/import.service.js';
import { importPbandaiItems, parsePbandaiCsv } from '../services/pbandai.service.js';
import { GRADES, SHOP_CODES, type Grade, type ShopCode } from '../types/index.js';
import { logger } from '../utils/logger.js';

// Derived from the same constants that type `ShopCode` and `Grade`, so a shop
// added to SHOP_CODES is recognised here without a second edit. Shop codes are
// plain lowercase words and hyphens, which need no escaping in an alternation.
const FILE_PATTERN = new RegExp(`^(${SHOP_CODES.join('|')})_(${GRADES.join('|')})\\.csv$`);

// The P-Bandai showcase snapshot is not a <shop>_<grade> price CSV; the
// scraper always writes this fixed name and it imports into pbandai_items.
const PBANDAI_FILE = 'pbandai_products.csv';

interface CliArgs {
  dir?: string;
  file?: string;
}

function parseArgs(argv: string[]): CliArgs {
  const config = loadConfig();
  const args: CliArgs = { ...(config.CSV_DIR ? { dir: config.CSV_DIR } : {}) };
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    const value = argv[i + 1];
    if (flag === '--dir' && value) {
      args.dir = value;
      i++;
    } else if (flag === '--file' && value) {
      args.file = value;
      i++;
    }
  }
  return args;
}

function resolveFiles(args: CliArgs): string[] {
  if (args.file) return [args.file];
  const { dir } = args;
  if (dir === undefined) return [];
  return readdirSync(dir)
    .filter((name) => FILE_PATTERN.test(name) || name === PBANDAI_FILE)
    .map((name) => join(dir, name));
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const config = loadConfig();
  const files = resolveFiles(args);
  if (files.length === 0) {
    logger.error(
      { dir: args.dir ?? null },
      `no CSV files matched — set CSV_DIR or pass --dir <folder> / --file <path> (expected <shop>_<grade>.csv; shops: ${SHOP_CODES.join(', ')}, grades: ${GRADES.join(', ')})`,
    );
    process.exit(1);
  }

  const db = createDatabase(config.DATA_DIR);
  const repo = new ProductRepository(db);
  const pbandaiRepo = new PbandaiRepository(db);

  for (const filePath of files) {
    const name = basename(filePath);
    if (name === PBANDAI_FILE) {
      const { records, skipped } = parsePbandaiCsv(readFileSync(filePath, 'utf-8'));
      const result = importPbandaiItems(pbandaiRepo, records);
      logger.info(
        { file: name, imported: result.rowCount, skipped },
        'pbandai import finished',
      );
      continue;
    }
    const match = FILE_PATTERN.exec(name);
    if (!match) {
      logger.warn({ filePath }, 'skipping file with unrecognized name');
      continue;
    }
    const shop = match[1] as ShopCode;
    const grade = match[2] as Grade;
    const { records, skipped } = parseProductCsv(readFileSync(filePath, 'utf-8'));
    const result = importProducts(repo, shop, grade, basename(filePath), records, skipped);
    logger.info(
      { file: basename(filePath), shop, grade, imported: result.rowCount, skipped: result.skipped, batchId: result.batchId },
      'import finished',
    );
  }
  db.close();
}

main();
