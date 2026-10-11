<!-- docs/FUNCTION_SPEC.md -->
# Functional Specification

## 1. Business Flow

1. Scheduled cron job runs `~/github/python_program/hobbyland_scraper.py`, producing 6 CSVs
   (`hobbyland_{hg,mg,rg}.csv`, `animes-pro_{hg,mg,rg}.csv`) with header
   `title,price,url,regular_price,sku,stock,sell_type,image_url` (UTF-8 BOM). Older CSVs without
   `image_url` still import — the field is `NULL` on insert and left untouched on re-import.
2. Import (CLI `pnpm import:csv` or dashboard upload) parses CSV, validates rows, and upserts
   products keyed by `(shop_id, sku, grade)` inside a single transaction per file; each file
   produces one `import_batches` record.
3. Dashboard queries `/api/comparisons`; the backend joins both shops' products, groups by
   `(grade, sku)`, and computes the cheaper shop, the saving, and whether only one shop carries the
   SKU. The UI badges the verdict —「<Shop> 平 HK$N」,「同價」, or「只有 <Shop> 有貨」.
4. Dashboard also queries `/api/imports/freshness?grade=` and shows one last-import timestamp per
   shop above the grid. The two shops are scraped independently and drift apart, so freshness is
   reported per shop rather than as a single global number — a stale half of the comparison should
   be visible without inspecting the CSVs.

## 2. Validation Rules

- **CSV row valid** iff: `title` non-empty, `sku` non-empty, `price` numeric ≥ 0.
  Invalid rows are counted as `skipped` (not fatal). Rows without a JAN SKU (e.g. non-Gunpla
  Ultraman items in animes-pro_mg.csv) are skipped by design — they can never match across shops.
- **Upload** requires multipart `file` + `shop ∈ {hobbyland, animes-pro}` + `grade ∈ {hg,mg,rg}`;
  a CSV with zero valid rows → 422; a malformed CSV (column-count mismatch etc.) → 400.
- **Query params** validated with zod; invalid values → 400 with field-level messages.

## 3. Comparison Semantics

- Group key = `(grade, sku)` — the same JAN in HG and MG listings stays separate.
- `offers` sorted ascending by price.
- Two offers, different prices → `cheapestShop` = lower-priced shop, `saving` = price difference
  (rounded to 2 dp), `exclusiveShop = null`. Badge:「<Shop> 平 HK$N」.
- Equal prices → `cheapestShop = 'tie'`, `saving = 0`, `exclusiveShop = null`. Badge:「同價」.
- Single-shop SKU → `exclusiveShop` = that shop, `saving = null`. Badge:「只有 <Shop> 有貨」.
  `cheapestShop` still carries that shop so the `cheaper=` filter keeps matching it, but the UI must
  not render a price-comparison verdict: a lone offer never won anything, so「<Shop> 平」is wrong.
  `exclusiveShop` exists so the badge reads the verdict instead of inferring it from `saving === null`.
  This is the majority case — 280 of 481 groups as of 2026-10-11 (HG 169, MG 97, RG 14).

## 4. State Transitions

Product row lifecycle: `absent → imported (batch N) → re-imported (batch N+1, price/url/stock
overwritten)`. `image_url` is the one exception: the upsert writes
`COALESCE(excluded.image_url, products.image_url)`, so re-importing a CSV that predates the
`image_url` column keeps the thumbnail already on file rather than nulling it. Without that, a
partial scrape (`scrape-and-import.sh rg`) followed by the importer's whole-directory sweep would
silently strip every image for the un-scraped grades. Import batches are append-only audit records.
A shop delisting a product does not delete the row (last known price persists); full replacement
semantics can be added later if needed.

## 5. Boundary Conditions & Error Recovery

- BOM header: stripped by csv-parse (`bom: true`).
- Empty `stock` / `regular_price` / `sell_type` → stored as `NULL`, rendered as `—`.
- Missing/empty `image_url` → `NULL` on insert, preserved on re-import (see §4). The row renders a
  grade placeholder tile instead of an empty slot, and a remote image that 404s or is hotlink-blocked
  falls back to the same tile through the `<img>` error handler.
- Import failure mid-file → transaction rollback, no partial rows, no batch record.
- Duplicate file re-import → idempotent per `(shop, sku, grade)`; new batch row each run.
- Server errors → `ApiErrorResponse` with `traceId` (also returned as `x-trace-id` header).

## 6. Presentation Theme

The dashboard is a dark HUD cockpit skin with one global faction theme, switched from the header
between 聯邦 (Federation — blue `#58a6e8` / yellow `#f0c343`) and 自護 (Zeon — red `#d9483b` /
off-white `#e6e1d7`). The choice persists to `localStorage` under `hobbyland:faction` and is mirrored
onto `<html data-faction>`; the inline bootstrap in `index.html` applies it before first paint so the
accent never flashes the wrong faction. The two shops are deliberately **not** faction-coloured —
they are separated by neutral value only (`--shop-a` bright, `--shop-b` dim), so the faction stays a
skin rather than a claim about either shop.
