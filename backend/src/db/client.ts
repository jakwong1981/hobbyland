// backend/src/db/client.ts
import { createRequire } from 'node:module';
import { readFileSync, mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { DatabaseSync as DatabaseSyncType } from 'node:sqlite';

export type DatabaseSync = DatabaseSyncType;

// node:sqlite is not in Vite 5's builtin list; require() keeps it out of static analysis.
const { DatabaseSync: DatabaseSyncCtor } = createRequire(import.meta.url)('node:sqlite') as {
  DatabaseSync: new (path: string) => DatabaseSyncType;
};

const MIGRATION_PATH = resolve(import.meta.dirname, '../../drizzle/0000_init.sql');

export function createDatabase(dataDir: string): DatabaseSync {
  mkdirSync(dataDir, { recursive: true });
  const db = new DatabaseSyncCtor(join(dataDir, 'hobbyland.db'));
  db.exec('PRAGMA journal_mode = WAL');
  db.exec('PRAGMA foreign_keys = ON');
  migrate(db);
  return db;
}

export function createInMemoryDatabase(): DatabaseSync {
  const db = new DatabaseSyncCtor(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  migrate(db);
  return db;
}

function migrate(db: DatabaseSync): void {
  db.exec(readFileSync(MIGRATION_PATH, 'utf-8'));
  // 0000_init.sql is CREATE IF NOT EXISTS only — existing DBs need the column added in place.
  const columns = db.prepare("SELECT name FROM pragma_table_info('products')").all() as { name: string }[];
  if (!columns.some((c) => c.name === 'image_url')) {
    db.exec('ALTER TABLE products ADD COLUMN image_url TEXT');
  }
}
