CREATE TABLE IF NOT EXISTS shops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_file TEXT NOT NULL,
  shop_code TEXT NOT NULL,
  grade TEXT NOT NULL,
  row_count INTEGER NOT NULL,
  skipped_count INTEGER NOT NULL DEFAULT 0,
  imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shop_id INTEGER NOT NULL REFERENCES shops(id),
  sku TEXT NOT NULL,
  grade TEXT NOT NULL,
  title TEXT NOT NULL,
  price REAL NOT NULL,
  regular_price REAL,
  url TEXT NOT NULL,
  stock TEXT,
  sell_type TEXT,
  image_url TEXT,
  series TEXT,
  batch_id INTEGER REFERENCES import_batches(id),
  imported_at TEXT NOT NULL,
  UNIQUE (shop_id, sku, grade)
);

CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_grade ON products(grade);

-- P-Bandai HK showcase snapshot: not part of price comparison. Each import
-- replaces the whole table (no JAN/SKU identity to upsert against), so id
-- order preserves the site's NewArrival ordering.
CREATE TABLE IF NOT EXISTS pbandai_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  tc_name TEXT,
  price REAL,
  status TEXT,
  url TEXT NOT NULL UNIQUE,
  image_url TEXT,
  imported_at TEXT NOT NULL
);

INSERT OR IGNORE INTO shops (code, name) VALUES
  ('hobbyland', 'Hobbyland'),
  ('animes-pro', 'Animes-Pro'),
  ('hobbydigi', 'HobbyDigi'),
  ('fookle', 'Fookle Model'),
  ('twinnermodel', 'Twinner Model 千里達');
