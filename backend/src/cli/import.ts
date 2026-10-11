// backend/src/cli/import.ts
import { readFileSync, readdirSync } from 'node:fs';
import { basename, join } from 'node:path';
import { loadConfig } from '../config.js';
import { createDatabase } from '../db/client.js';
import { ProductRepository } from '../repositories/product.repository.js';
import { importProducts, parseProductCsv } from '../services/import.service.js';
import type { Grade, ShopCode } from '../types/index.js';
import { logger } from '../utils/logger.js';

const FILE_PATTERN = /^(hobbyland|animes-pro)_(hg|mg|rg)\.csv$/;

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
    .filter((name) => FILE_PATTERN.test(name))
    .map((name) => join(dir, name));
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const config = loadConfig();
  const files = resolveFiles(args);
  if (files.length === 0) {
    logger.error(
      { dir: args.dir ?? null },
      'no CSV files matched — set CSV_DIR or pass --dir <folder> / --file <path> (expected hobbyland_<grade>.csv / animes-pro_<grade>.csv)',
    );
    process.exit(1);
  }

  const db = createDatabase(config.DATA_DIR);
  const repo = new ProductRepository(db);

  for (const filePath of files) {
    const match = FILE_PATTERN.exec(basename(filePath));
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
