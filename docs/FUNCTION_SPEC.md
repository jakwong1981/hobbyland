<!-- docs/FUNCTION_SPEC.md -->
# Functional Specification

## 1. Business Flow

1. Scheduled cron job runs `scripts/hobbyland_scraper.py`, producing up to 9 CSVs
   (`hobbyland_{hg,mg,rg}.csv`, `animes-pro_{hg,mg,rg}.csv`, `hobbydigi_{hg,mg,rg}.csv`) with header
   `title,price,url,regular_price,sku,stock,sell_type,image_url` (UTF-8 BOM). Older CSVs without
   `image_url` still import — the field is `NULL` on insert and left untouched on re-import.
   HobbyDigi writes only the grades it actually resolved, so a run may produce fewer than 9.
2. Import (CLI `pnpm import:csv` or dashboard upload) parses CSV, validates rows, and upserts
   products keyed by `(shop_id, sku, grade)` inside a single transaction per file; each file
   produces one `import_batches` record.
3. Dashboard queries `/api/comparisons`; the backend joins every shop's products, groups by
   `(grade, sku)`, and computes the cheapest shop, the saving against the runner-up, and whether
   only one shop carries the SKU. The UI badges the verdict —「<Shop> 最平」,「同價」, or
   「只有 <Shop> 有貨」.
4. Dashboard also queries `/api/imports/freshness?grade=` and shows one last-import timestamp per
   shop above the grid. The shops are scraped independently and drift apart, so freshness is
   reported per shop rather than as a single global number — a stale part of the comparison should
   be visible without inspecting the CSVs.

## 2. Validation Rules

- **CSV row valid** iff: `title` non-empty, `sku` non-empty, `price` numeric ≥ 0.
  Invalid rows are counted as `skipped` (not fatal). Rows without a JAN SKU (e.g. non-Gunpla
  Ultraman items in animes-pro_mg.csv) are skipped by design — they can never match across shops.
- **Upload** requires multipart `file` + `shop ∈ SHOP_CODES` + `grade ∈ GRADES`;
  a CSV with zero valid rows → 422; a malformed CSV (column-count mismatch etc.) → 400.
- **Query params** validated with zod; invalid values → 400 with field-level messages. The zod
  enums are built from `SHOP_CODES` / `GRADES`, so a new shop is accepted without a second edit.

## 3. Comparison Semantics

- Group key = `(grade, sku)` — the same JAN in HG and MG listings stays separate.
- `offers` sorted ascending by price, one per shop that stocks the SKU.
- Two or more offers, one uniquely lowest → `cheapestShop` = that shop, `saving` = the gap to the
  **runner-up** (rounded to 2 dp), `exclusiveShop = null`. Badge:「<Shop> 最平」. `saving` stays in the
  API but is not rendered: the verdict names the winner only. With two shops the runner-up is the only
  rival; with three it is the next-best alternative, which is the number a buyer actually cares about.
- More than one offer at the lowest price → `cheapestShop = 'tie'`, `saving = 0`,
  `exclusiveShop = null`. Badge:「同價」. The test counts every offer level with the lowest price
  rather than comparing the top two, so a tie between the first and a later shop is still a tie.
- Single-shop SKU → `exclusiveShop` = that shop, `saving = null`. Badge:「只有 <Shop> 有貨」.
  `cheapestShop` still carries that shop so the `cheaper=` filter keeps matching it, but the UI must
  not render a price-comparison verdict: a lone offer never won anything, so「<Shop> 最平」is wrong.
  `exclusiveShop` exists so the badge reads the verdict instead of inferring it from `saving === null`.
  This is the majority case — 276 of 487 groups as of 2026-10-12.
- A SKU carried by exactly two of three shops yields `exclusiveShop = null`; the grid already shows
  the empty column, so there is no separate "2 of 3" field.
- `title` is taken from the highest-ranked shop in `SHOP_CODES`. `findProducts` orders by `sku`
  alone, so within a group the row order is unspecified and the shops word the same kit differently
  — an explicit pick keeps the displayed title stable across runs.

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

The dashboard is a dark mobile-suit HUD skin with one global faction theme, switched from the header
between 聯邦 (Federation — RX tricolour: white `#f4f7fb`, blue `#2f8cf0`, red `#e8414a`, yellow
`#f5c518`) and 自護 (Zeon — red `#e0402f`, Zaku green `#6a9a43`, gold `#d4ae3e`, mono-eye pink
`#ff3d7f`). Each faction exposes four accents (`--accent` … `--accent-4`) plus two glows. The choice
persists to `localStorage` under `hobbyland:faction` and is mirrored onto `<html data-faction>`; the
inline bootstrap in `index.html` applies it before first paint. A diagonal colour wipe plays on a
real switch only (never on first load).

Layout, top to bottom:
1. **Header** — animated crest (rotating frame, pulsing mark) and a four-colour faction stripe with a
   travelling light bar.
2. **Hero** — original SVG mobile-suit head per faction (V-fin glint / sweeping mono-eye; both are
   rendered and CSS cross-fades), faction copy, and stat tiles that count up.
3. **Kit showcase** — infinite marquee of kit photos (from the scraped `image_url`), pauses on
   hover/focus. Titles are exposed via `aria-label`/`title` only, not as visible text.
4. **Toolbar** — grade tabs with coloured grade emblems (HG blue, MG amber, RG red), shop filter,
   search, 表格/圖鑑 view toggle.
5. **Content** — table (shop logos in headers, staggered row entrance, thumbnail zoom, shining 最平
   badge) or gallery cards (large photo, per-shop price list, winner highlighted).

Logos: every shop has an SVG monogram chip (`HL` hexagon, `AP` circle, `HD` diamond) tinted with its
`--shop-*` colour. Shop colour tints logos only — price text stays neutral so the faction accent
keeps meaning "the winner".

Motion is confined to `styles/motion.css` inside `@media (prefers-reduced-motion: no-preference)`.
With reduced motion: no animation or transitions, count-ups show the final value immediately, and
the marquee becomes a plain horizontally scrollable strip without its duplicate copy.

No official artwork is bundled: kit photos are hot-linked from the shops (`referrerPolicy=no-referrer`),
and mobile-suit art is original line drawing.
