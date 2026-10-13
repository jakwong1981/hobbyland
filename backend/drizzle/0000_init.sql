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
  batch_id INTEGER REFERENCES import_batches(id),
  imported_at TEXT NOT NULL,
  UNIQUE (shop_id, sku, grade)
);

CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_grade ON products(grade);

INSERT OR IGNORE INTO shops (code, name) VALUES
  ('hobbyland', 'Hobbyland'),
  ('animes-pro', 'Animes-Pro'),
  ('hobbydigi', 'HobbyDigi'),
  ('fookle', 'Fookle Model');
