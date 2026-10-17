<!-- docs/TESTING.md -->
# Testing Document

Stack: **Vitest 2** — backend in node environment + **supertest** for API-level tests; frontend in **jsdom** + **React Testing Library**.
Pattern: AAA (Arrange-Act-Assert); the database is a fresh in-memory SQLite per test
(`createInMemoryDatabase()`), so no external state is mocked away — SQL runs for real.

Run: `pnpm test` (from repo root) or `cd backend && pnpm test` / `cd frontend && pnpm test`.

> `frontend/tests/setup.ts` installs an in-memory `Storage` shim. Node ≥ 22 exposes an experimental
> `localStorage` global that yields `undefined` without `--localstorage-file`, and it shadows the
> Storage jsdom would otherwise provide — so `useFaction` would otherwise be untestable.

## 1. Unit Test Suites

### comparison.service.test.ts (13 tests)

| # | Case | Asserts |
|---|---|---|
| 1 | Two shops, different prices | cheaper shop flagged, saving = diff, offers sorted asc, `exclusiveShop = null` |
| 2 | Equal prices | `cheapestShop = 'tie'`, `saving = 0`, `exclusiveShop = null` |
| 3 | Single-shop SKU | `cheapestShop` = that shop, `saving = null`, 1 offer |
| 4 | Single-shop SKU (exclusive) | `exclusiveShop` = that shop — the flag the badge branches on |
| 5 | Same SKU in different grades | two separate groups |
| 6 | Sorting | rows ordered by SKU |
| 7 | Group title vs. row order | title comes from the highest-ranked shop in `SHOP_CODES`, not from whichever row `findProducts` happened to return first |
| 8 | Three offers, distinct prices | offers sorted asc, cheapest wins, `saving` = gap to the **runner-up** |
| 9 | Three offers, two level at the bottom | `cheapestShop = 'tie'` even though a dearer third offer exists |
| 10 | Three level offers | `cheapestShop = 'tie'`, `exclusiveShop = null` |
| 11 | Group series | `series` = first non-null across the group (shops enriched at different times) |
| 12 | Five real shops, twinnermodel cheapest | `cheapestShop = 'twinnermodel'`, `saving` = gap to the runner-up, its offer sorts first |
| 13 | Twinnermodel-only SKU | `exclusiveShop = 'twinnermodel'`, `saving = null` |

> Cases 8-10 cast a third shop code that `ShopCode` does not declare. They pin the
> N-way arithmetic without adding a shop that has no data source behind it.

### import.service.test.ts (21 tests)

| # | Case | Asserts |
|---|---|---|
| 1 | BOM header + empty stock | parsed; `stock = null`, prices numeric |
| 2 | Rows missing title/sku/price | all counted as skipped |
| 3 | Fresh import | row inserted, batch recorded |
| 4 | Re-import same SKU | price/stock updated, still 1 row, 2 batches |
| 5 | Same SKU from both shops | 2 rows kept |
| 6 | CSV with `image_url` | column mapped through to the stored product |
| 7 | CSV without `image_url` column | parsed as `null`, stored as `null` (insert path) |
| 8 | Stale re-import over an imaged row | `image_url` **preserved** via COALESCE, price/stock still updated |
| 9 | `buildFreshness`, both shops present | per-shop timestamps kept, `overall` = the later one, `grade` echoed |
| 10 | `buildFreshness`, shops in the other order | `overall` still resolves to the chronologically latest, not the last row |
| 11 | `buildFreshness`, one shop absent | absent shop → `null`; a `null` grade is passed through |
| 12 | `buildFreshness`, no rows | `overall = null`, both shops `null` |
| 13 | `buildFreshness`, a shop outside `SHOP_CODES` | its timestamp still counts towards `overall` — `mapProductRow` casts `shop_code` unchecked, so this reaches the service at runtime |
| 14 | Provisional `HD:` row, then a real JAN for the same URL | the provisional row is replaced — one row left, keyed by the JAN |
| 15 | Provisional `FM:` row (fookle), then a real JAN for the same URL | fookle analogue of case 14 — `deleteProvisionalByUrl` matches any `<PREFIX>:` key, not only `HD:` |
| 15b | Provisional `TM:` row (twinnermodel), then a real JAN for the same URL | twinnermodel analogue of case 14 — the provisional row is replaced, one row left keyed by the JAN |
| 16 | Provisional `HD:` row re-imported unchanged | still one row — a provisional sku never triggers its own deletion |
| 17 | CSV with `series` | column mapped through to the stored product |
| 18 | Stale re-import without `series` over a classified row | stored `series` **preserved** via COALESCE, price still updated |
| 19 | `findProducts({ series })` | only rows of that series returned |
| 20 | Legacy `products` table predating `image_url` / `series` | migrated (columns added) before indexing |

### api.test.ts (12 tests, supertest + in-memory DB)

| # | Endpoint | Case | Expected |
|---|---|---|---|
| 1 | GET /api/comparisons | grouping + cheapest flag | 200, saving 22, `exclusiveShop` null for two-shop / set for single-shop |
| 1b | GET /api/comparisons | fookle as a fourth offer | 200; a 4-offer SKU flags `fookle` cheapest, a fookle-only SKU is a fookle exclusive |
| 2 | GET /api/comparisons | `cheaper=animes-pro` filter | only matching rows |
| 3 | GET /api/comparisons | `grade=pg` (invalid) | 400 + traceId |
| 4 | POST /api/import | valid CSV upload | 201, rowCount 1, row queryable |
| 5 | POST /api/import | missing file | 400 |
| 6 | POST /api/import | CSV with no valid rows | 422 |
| 7 | GET /api/imports | batch list | 200, 2 batches |
| 8 | GET /api/imports/freshness | `grade=hg` | 200, both shops non-null, `overall` = later of the two |
| 9 | GET /api/imports/freshness | `grade=mg` (never imported) | 200, `overall = null`, both shops `null` |
| 10 | GET /api/imports/freshness | no `grade` | 200, `grade = null`, `overall` non-null |
| 11 | GET /api/imports/freshness | `grade=pg` (invalid) | 400 + traceId |

### config.test.ts (6 tests)

| # | Case | Asserts |
|---|---|---|
| 1 | Empty env | `PORT` defaults to 8089; TLS paths unset when no certificate exists |
| 2 | `./certs` pair present (`existsSync` mocked) | falls back to `certs/server.pem` + `certs/server-key.pem` |
| 3 | Only one certificate file present | no fallback — both paths stay unset |
| 4 | Explicit `TLS_CERT_PATH` / `TLS_KEY_PATH` | env wins over the `./certs` fallback |
| 5 | Lone explicit TLS path | passed through for `index.ts` to reject at boot |
| 6 | `PORT=70000` | zod rejects the out-of-range port |

### scrape.api.test.ts (4 tests, supertest + stub scrape script)

| # | Case | Expected |
|---|---|---|
| 1 | Initial status | 200, `idle` |
| 2 | Run the script; second POST while running | 202 start, 409 concurrent run, `completed` with exit code 0 after polling |
| 3 | Script exits non-zero | status `failed` with the exit code surfaced |
| 4 | Script path does not exist | 500 AppError「Scrape script not found」|

### cors.test.ts (5 tests, supertest + in-memory app)

| # | Case | Expected |
|---|---|---|
| 1 | Preflight from the iOS WebView origin | `OPTIONS /api/comparisons` → 204, `access-control-allow-origin: capacitor://localhost` echoed |
| 2 | Actual request from the Android WebView origin | 200, `access-control-allow-origin: https://localhost` echoed |
| 3 | Disallowed origin | 200 but **no** allow-origin header (exact-origin matching, no wildcard echo) |
| 4 | Custom `CORS_ORIGINS` list | listed origin allowed, default WebView origins rejected |
| 5 | Default origins constant | covers both WebView schemes (`capacitor://localhost`, `https://localhost`) |

### pbandai.service.test.ts (7 tests, node + in-memory SQLite)

| # | Case | Asserts |
|---|---|---|
| 1 | BOM header + image column | row parsed; `tcName` / `price = 450` / `status` / `url` / `imageUrl` all mapped |
| 2 | Raw price text | `"HK$1,280.50"` → `1280.5`; `N/A` → `null` |
| 3 | Rows missing name or url | both skipped (`skipped = 2`, 0 records) |
| 4 | CSV exported before the image column existed | tolerated; `imageUrl = null` |
| 5 | Import then read back | `rowCount = 2`, rows returned in insert order, `importedAt` stamped |
| 6 | Second import replaces the snapshot | closed pre-order vanishes — 1 row left, no duplicate |
| 7 | `findAll(q)` | matches on `name` or `tc_name` (English and Chinese) |

### pbandai.api.test.ts (3 tests, supertest + in-memory DB)

| # | Endpoint | Case | Expected |
|---|---|---|---|
| 1 | GET /api/pbandai | snapshot after a service-level import | 200, envelope `code = 0`, import order kept, snake→camel field mapping, missing image → `imageUrl: null` |
| 2 | GET /api/pbandai | empty database | 200, `data = []` |
| 3 | GET /api/pbandai | `?q=乙` | 200, only the row whose `tc_name` matches |

### Frontend (`frontend/tests/`, 118 tests)

| File | Cases |
|---|---|
| components.test.tsx (23) | `CheaperBadge` (cheapest shop named without the saving amount, tie, single-shop →「只有 Animes 有貨」and never「最平」, hobbyland-exclusive, exclusive outranks a tie verdict, **twinnermodel price win →「Twinnermodel 最平」, twinnermodel exclusive →「只有 Twinnermodel 有貨」**, none); `ComparisonTable` (empty state, both prices + badge, missing-shop placeholder + exclusive label, regular price only when higher, pre-order flag, preview image rendered, grade placeholder when no image, `onError` → placeholder); `FreshnessBar` (a `dateTime` per imported shop with the never-imported shops marked「冇紀錄」, no history at all, loading vs. failed); `GradeTabs` (selected state, emits grade); `SearchBar` (emits text) |
| dashboard.test.tsx (9) | api client (unwrap data, `ApiError` on failure, query-string building); `DashboardPage` (default HG load, refetch on grade change, freshness requested grade-scoped, **both timestamps rendered on the page**, error message + freshness failure state) |
| faction.test.tsx (6) | `FactionToggle` (active faction `aria-checked`, emits clicked faction); `useFaction` (federation default + `<html data-faction>`, persist & restore across mounts, unknown stored value → federation); `App` (header toggle flips the document faction) |
| comparison-stats.test.ts (8) | `summarizeComparisons` (per-shop wins, ties, exclusives counted apart, empty input, a fookle win + fookle exclusive); `productImageUrl` (SHOP_CODES preference, null without photo); `selectShowcaseKits` (photo-only, biggest saving first, links lowest offer, cap) |
| count-up.test.tsx (4) | `useCountUp` (reduced motion → target immediately with no frame scheduled, tween 0 → target, continues from shown value on target change, cancels frame on unmount) — rAF and `matchMedia` stubbed |
| layout.test.tsx (9) | `HeroBanner` (stat targets — one tile per DASHBOARD_SHOPS entry incl. twinnermodel, both faction heads rendered); `KitShowcase` (nothing without photos, link to cheapest offer + `aria-hidden` clone, failed photo drops kit); `ComparisonGallery` (empty state, per-shop prices + winner + verdict, placeholders for both shops without an offer); `FactionWipe` (hidden on first render, plays after switch); `DashboardPage` (表格 ↔ 圖鑑 toggle) |
| sort-filter.test.tsx (13) | `useComparisonSort` (incoming order kept while unsorted, title asc/desc, per-shop price asc/desc with the non-carrying shop always last, input array not mutated); `ComparisonTable` (three sortable headers start `aria-sort="none"`, no 判定 column any more, the verdict badge renders under the thumbnail inside the 產品 cell, click reorders rows + flips `aria-sort`, price header reorders); `ShopFilter` (defaults to `all`, listing every shop plus 全部, emits choice); `DashboardPage` (all-by-default count, filtered `M / N` count with the other shop's rows hidden, filter-specific empty state) |
| series-stats.test.ts (5) | `countBySeries` (counts per series sorted desc, unclassified rows excluded, empty when nothing classified); `seriesLabel` (known ids → 中文名, unmapped id passes through, null → `—`) |
| series-filter.test.tsx (5) | `SeriesFilter` (only series present in rows, with counts, plus 未分類); `DashboardPage` (series select narrows the table + `M / N` count, `__none__` filters to unclassified, stat chip toggles the series filter, table column shows the series name / `—`) |
| without-shop.test.ts (7) | `withoutShop` (drops the omitted shop's offers and re-derives the verdict, promotes a lone remaining offer to an exclusive, reports a tie between level remaining offers, drops a row only that shop carried, leaves rows without that shop untouched, re-sorts remaining offers before deriving `cheapestShop`/`saving`, skips omitted shops when picking the product image) |
| scrape-button.test.tsx (2) | `DashboardPage` scrape button (triggers the scrape, greys out while processing, re-enables on completion; surfaces an error when the scrape fails) |
| client.test.ts (3) | api client base-URL resolution (same-origin relative paths by default; effective base resolved **per request** so a settings change applies without reload; `ApiError` with the server message on non-2xx) |
| server-config.test.ts (10) | `normalizeApiBase` (trailing slashes stripped, empty string = same-origin, rejects non-http schemes / paths / junk); `getApiBase` precedence (stored override > build-time env > same-origin); `setApiBase`/`clearApiBase` (normalized persistence, invalid URL throws and persists nothing, clear restores build default, **a failed localStorage write keeps the override effective for the session via the in-memory mirror**) |
| server-settings.test.tsx (7) | `ServerSettings` panel (same-origin default shown, save persists a normalized URL, invalid URL rejected without persisting, 測試 hits `/api/imports/freshness` against the candidate URL with ✓/✗ display, failure message surfaced, reset restores the build default, **saving resets the React Query cache so mounted queries refetch from the new server**) |
| pbandai-page.test.tsx (7) | `fetchPbandaiItems` query-string building; `PbandaiPage` (cards render from the snapshot — lazy `no-referrer` image, whole card links to the item page, PB fallback block on image error; search narrows via `tcName`; status chip filters + 全部 resets; empty state); `App` nav switches 格價表 → P-Bandai → back |

`fetch` is stubbed per test; `QueryClient` retries are disabled. `tests/fixtures.ts` exports
`stubApi(comparisons, freshness?)`, which routes on the requested URL — the dashboard issues two
queries, so a single-payload stub would answer the freshness request with a comparison array.

`tests/setup.ts` also installs a `window.matchMedia` stub (jsdom has none) returning `matches: false`.

Current status: **backend 71/71, frontend 118/118 passing**; Python `scripts/test_*.py` 212/212 (incl. `test_pbandai_scraper_v2.py` 7: `save_csv` writes the image column, a card without an image exports an empty cell, JSON round-trip keeps the image, `_split_delivery_suffix` splits/strips delivery notes, `CATEGORY_URL` pins the model-kits listing at `limit=100`, `EXTRACT_JS` skips the `.o-items-carousel` RECOMMENDATIONS rail; `test_enrich_series.py`: file matching, cache round-trip, title dedupe across CSVs, cache hits skip the API, failures leave `series` empty and uncached, dead key still writes cache-only results, stale series refreshed; and `test_hobbyland_scraper.py` 51: fresh-browser retry per page, Turnstile widget located through the frame list rather than a selector, passive-canvas geometry fallback, CDP hover/press/release sequence and detach, re-measurement after a re-armed widget, click budget, ghost-click failure never prompting without a TTY, headed default plus `HD_HEADLESS` and the automation-flag launch arg, `cf_clearance` jar save/replay and a challenged jar never overwriting a working one, **twinnermodel kit filter / row mapping / sell-type / provisional key / products.json fetch + 429 retry / JAN order-of-trust**, **`hd` dropped from the default category run while the other shops stay**); `pnpm build` clean under strict TS.

## 2. Functional / Integration Test Matrix

| Test Case ID | Scenario | Preconditions | Input Payload | Expected Status & Response | Pass/Fail Criteria |
|---|---|---|---|---|---|
| IT-01 | CLI bulk import | up to 12 scraper CSVs present | `pnpm import:csv -- --dir <abs path>` | one batch per CSV; HG 252+139+18, MG 100+143+8, RG 26+22+1 rows | row counts match CSV line counts minus skipped |
| IT-02 | Skip SKU-less rows | animes-pro_mg.csv contains Ultraman items w/o JAN | IT-01 | skipped=103 for that file | skipped count matches rows with empty sku |
| IT-03 | Dashboard grouping | IT-01 done | `GET /api/comparisons?grade=hg` | 285 rows: 114 with 2 offers, 5 with 3, 166 exclusive | counts match |
| IT-04 | Cheaper badge | IT-01 done | `cheaper=hobbyland` / `animes-pro` / `hobbydigi` | 200 each; HG 202 / 59 / 11 rows | each row's `cheapestShop` equals filter — **note** the filter also matches single-shop rows; see §4 |
| IT-05 | UI upload | server running | multipart CSV via「匯入」page | 201 + visible in grid | product appears in dashboard |
| IT-06 | Invalid grade | — | `GET /api/comparisons?grade=pg` | 400 ApiErrorResponse + traceId | zod message present |
| IT-06b | Invalid shop | — | `GET /api/products?shop=bogus` | 400 | zod enum derives from `SHOP_CODES`, so all four real shops return 200 |
| IT-07 | Empty/invalid CSV upload | server running | `bad.csv` no valid rows | 422 | no batch written |
| IT-08 | Malformed CSV upload | server running | column-count mismatch | 400 | transaction rolled back |
| IT-09 | SPA serving | `pnpm build` done | `GET /` | index.html | title「Gunpla 格價 // Price Recon」, `<html data-faction>` bootstrap present |
| IT-10 | Re-import idempotency | IT-01 done | run IT-01 again | same product count, one extra batch per CSV | no duplicate (shop, sku, grade) |
| IT-11 | Docker e2e | image built | `docker compose up` | UI on :8089 with data volume | IT-03 repeatable in container |
| IT-12 | Exclusive verdict end-to-end | IT-01 done | `GET /api/comparisons?grade=hg` | 166 rows with `exclusiveShop` set | UI shows「只有 <Shop> 有貨」, no「最平」badge on those rows |
| IT-12b | Three-shop verdict | IT-01 done | `GET /api/comparisons?grade=mg` | 5 rows with 3 offers; `saving` is the gap to the **runner-up**, not to one named rival | a tie between the two cheapest still reads「同價」even with a dearer third offer |
| IT-13 | Stale CSV cannot strip images | IT-01 done, all rows imaged | re-import a CSV with the `image_url` column removed | that grade keeps 100% image coverage | `SUM(image_url IS NOT NULL)` unchanged; price/stock still refresh |
| IT-14 | Stale container replacement | a non-compose container named `hobbyland-app-1` squats :8089 on an old image | `scripts/docker-deploy.sh` | script logs「Removing leftover container」and recreates from `:latest` | `GET /api/comparisons` afterwards carries the current contract (`exclusiveShop` present) |
| IT-15 | Frozen header + zebra | IT-01 done, :8089 serving | scroll the 285-row HG grid | column header stays pinned; rows alternate shade | `th` computed `position: sticky`; `.table-wrapper` is the scroll container |
| IT-16 | Sort + filter on real data | IT-01 done | click 產品 / any price header; pick a shop in 有售舖頭 | rows reorder client-side with no refetch; count becomes `M / N 個 SKU` | sorting a shop's price puts SKUs that shop does not carry last |
| IT-17 | Preview image sizing | IT-01 done, 709/709 imaged | inspect a row thumbnail | 88px square (60px ≤640px), `object-fit: cover`, no white letterbox | thumbnail box has no padding and a dark `--surface-2` fill |
| IT-18 | Last-update readout | IT-01 done | `GET /api/imports/freshness?grade=hg` | 200, all four shops non-null, `overall` = the latest timestamp | dashboard renders four `<time dateTime>` elements above the grid; switching grade refetches |
| IT-18b | `overall` counts an unlisted shop | a shop present in `shops` but absent from `SHOP_CODES` has the newest timestamp | `GET /api/imports/freshness` | `overall` reflects that newest timestamp | `buildFreshness` derives from the populated map, not a hardcoded shop list |
| IT-19 | Freshness for an unscraped grade | only HG imported | `GET /api/imports/freshness?grade=rg` | 200, `overall = null`, all shops `null` | readout shows「呢個級別未有匯入紀錄」rather than an HG timestamp |
| IT-20 | Third price column renders | IT-01 done, :8089 serving | inspect the HG grid | HobbyDigi column present with its own neutral tone **and** a left divider | built CSS contains `--shop-c`, `.shop-head.shop-c`, `.price-cell.shop-c .price-link`, and the divider rule keys off `td.price-cell` / `th.shop-head` rather than `nth-child` |
| IT-20b | Fourth price column renders | IT-01 done, :8089 serving | inspect the HG grid | Fookle column present with its own neutral tone **and** a left divider | built CSS contains `--shop-d`, `.shop-head.shop-d`, `.price-cell.shop-d .price-link` |
| IT-20c | Fifth price column renders | IT-01 done, :8089 serving | inspect the HG grid | Twinner Model column present with its own neutral tone | built CSS contains `--shop-e`, `.shop-head.shop-e`, `.price-cell.shop-e .price-link` |
| IT-21 | HobbyDigi variant guard | `hd` scrape done | inspect the resolution report | `variants quashed ≥ 0`; no duplicate `(grade, sku)` inside any `hobbydigi_*.csv` | two differently-titled cards resolving to one barcode are both blanked, so the `UNIQUE (shop_id, sku, grade)` upsert cannot silently swallow one |
| IT-22 | No circular matching | hobbydigi rows already imported | re-run `hd` | the report's `catalogue size` excludes hobbydigi's own rows | `JanCatalogue.from_database(..., exclude_shops=('hobbydigi',))` |
| IT-22b | Fookle cross-script match + no circular matching | `fm` scrape done, catalogue from hobbyland/animes-pro | run `hobbyland_scraper.py fm` | some English fookle titles inherit a real JAN via the Latin/part-number matcher; the rest become `FM:<slug>` exclusives | the report's `catalogue size` excludes fookle's **and** hobbydigi's own rows (`exclude_shops=('fookle','hobbydigi')`); `evaluate()` still reports 0 wrong-SKU matches |
| IT-23 | Fookle `FM:` provisional replaced | a fookle kit stored under `FM:<slug>` | re-import `fookle_hg.csv` after the kit resolves a real JAN | one row for that URL, keyed by the JAN — no `FM:` duplicate | `deleteProvisionalByUrl` deletes any `<PREFIX>:` sku for the URL (covered by `import.service.test.ts` case 15) |
| IT-24 | Twinnermodel scrape + import | `data/hobbyland.db` present, Playwright installed | `hobbyland_scraper.py tm` then `pnpm import:csv` | `twinnermodel_{hg,mg,rg}.csv` written; batches recorded for shop `twinnermodel` | every kit's JAN comes from the handle (report `JAN from handle` ≈ all rows); dashboard badges「Twinnermodel 最平」/「只有 Twinnermodel 有貨」on real data |
| IT-25 | Twinnermodel no circular matching | twinnermodel rows already imported | re-run `tm` | the report's `catalogue size` excludes twinnermodel's, fookle's **and** hobbydigi's own rows | `JanCatalogue.from_database(..., exclude_shops=('twinnermodel','fookle','hobbydigi'))` |
| IT-26 | P-Bandai snapshot import | `pbandai_products.csv` in the import dir | `pnpm import:csv -- --dir <abs path>`, then `GET /api/pbandai` | one `pbandai_items` row per CSV record, in CSV order; price parsed from the raw text; image URL stored | re-import with a row removed leaves **fewer** rows (whole-table replace, no upsert); shop CSVs in the same dir still import normally |

## 3. Manual Verification Performed

### 2026-10-17 — enhancement 8 (P-Bandai HK showcase page)

- Full suite: `pnpm test` → **backend 71/71, frontend 118/118**; Python **208/208**
  (`scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py'`, incl. the new
  `test_pbandai_scraper_v2.py` 5/5 — later 7/7 under the 210/210 total once the model-kits
  category source landed, see below); `pnpm build` clean under strict TS on both packages;
  `bash -n` clean on `scrape-and-import.sh`.
- Import CLI verified end-to-end in a scratch dir: `pbandai_products.csv` (2 rows) imported →
  `pbandai_items` holds 2 rows in CSV order with `price` parsed (`HK$450.00` → 450, `N/A` → null)
  and `image_url` stored; a shop CSV in the same directory still takes the shop/grade path;
  re-import after removing a row leaves 1 row (snapshot replace, no duplicates).
- `GET /api/pbandai` on the seeded in-memory app returns the shared envelope with rows in import
  (newest-first) order; `?q=` matches both `name` and `tc_name`; empty DB → `[]` (covered by
  `pbandai.api.test.ts`).
- `--skip-pbandai` leaves the pipeline byte-identical to before; the default P-Bandai step is
  guarded non-fatal (`|| echo ⚠️ …`) so a P-Bandai outage cannot abort the shop import under
  `set -euo pipefail` — on failure the previous `pbandai_products.csv` re-imports as-is.
- Live P-Bandai scrape + dashboard rendering of the new page not yet re-verified in a browser
  at this point (superseded by the next entry for the scrape; the visual pass remains open);
  the page-level behaviour is pinned by `pbandai-page.test.tsx` (7 tests) against a stubbed query.

### 2026-10-17 — P-Bandai model-kits category source (37 → 63 件)

- Prompt: the model-kits category page shows「63 results」, but the showcase snapshot only had 37
  — the bot-protected search endpoint had failed on the last run, leaving shop-page rows only.
- Live probing (Playwright MCP): `/hk/category/model-kits` is the same 04-004 listing as the
  search URL, server-200 and not bot-protected; its default view = SALES STATUS「Available
  Items (63) + Upcoming Items (0)」, with「No Longer Available (3226)」filtered out by the site.
  Both listing pages render 71 cards for 63 results — the extra 8 are the `.o-items-carousel`
  RECOMMENDATIONS rail, now excluded in `EXTRACT_JS`.
- Scraper now crawls shop page → category page (`?limit=100`, one page for 63) → search top-up,
  via the extracted `_crawl_listing` helper. Live run: **63 products captured** (= the site's
  counter), all with price + image; Python suite 210/210.
- `pnpm import:csv` → `pbandai_products.csv: imported 63, skipped 0`; `pbandai_items` holds 63
  rows (0 missing image / price).
- **Ops note:** the Docker container bind-mounts `./data`, but its long-lived SQLite connection
  kept serving the pre-import 37 rows until `docker compose restart app` — after a host-side
  import, restart the container (or use `scrape-and-import.sh --docker`, which recreates it).
  Post-restart `GET /api/pbandai` serves all 63 items.
- Page verified live via `pnpm dev` (vite :5173 → proxied API): 63 cards, 「63 件」, status chips
  全部/PRE-ORDER, lazy images loading per viewport — desktop + 390px device widths.
- Follow-ups the same day: the hero gained a decorative booth illustration
  (`frontend/src/assets/pbandai-hero.jpg`, downscaled 2752→1600px, 3.6MB→540KB, `alt=""`), and
  HobbyDigi (`hd`) moved behind `DISABLED_BY_DEFAULT` in `hobbyland_scraper.py` — a bare run
  scrapes the other four shops and prints the skip notice; `hd` explicitly still works.

### 2026-10-16 — enhancement 7 (hybrid mobile app) + pre-push review fixes

- Full suite after the review round: `pnpm test` → **backend 61/61, frontend 111/111**;
  `tsc --noEmit` clean on both packages; `bash -n` clean on the three mobile scripts.
- Code review of the uncommitted Capacitor increment found and fixed:
  - `queryClient.clear()` after a server switch left mounted observers showing old-server
    data (fetch count stayed 1) → `resetQueries()` + a regression test that mounts a probe
    query and asserts it refetches from the new URL.
  - A failed `localStorage` write in `setApiBase` silently reverted requests to the previously
    stored server → an in-memory mirror keeps the choice effective for the session
    (MOB-15).
  - `allowMixedContent` missing blocked the documented HTTP-LAN-backend workflow on Android
    (WebView served from `https://localhost`); committed the public dev cert
    (`dev_server_cert.pem`) so debug builds link on a clean checkout; `mobile/ios/build/`
    added to `.gitignore` (4,797 build artifacts were about to be committed).
  - Build script honesty: the release APK is now always signed (debug keystore by default,
    `ANDROID_KEYSTORE*` for store signing); a failed **signed** iOS archive/export is an
    error unless `ALLOW_UNSIGNED_IPA=1`; `EXPORT_TEAM_ID` reaches the archive step
    (`DEVELOPMENT_TEAM`), not just the export options.
- `git status --untracked-files=all mobile/` dropped from 4,872 to 76 files after the ignore
  fix; `git check-ignore` confirms `mobile/ios/build/`, `mobile/android/**/build/`,
  `mobile/node_modules/`, and `dist-mobile/` are all excluded.

### 2026-10-14 — fifth shop (Twinner Model 千里達) + Shopify products.json via warmed browser

- `pnpm build` clean under strict tsc (frontend 110 modules). `pnpm test` → **backend 45/45,
  frontend 87/87**. Python: **200/200** (`scripts/venv/bin/python -m unittest test_hobbyland_scraper`
  alone: 49, incl. 17 new twinnermodel cases).
- Probed the shop first: plain `curl` (even with a browser UA) 429s `local_rate_limited` on every
  endpoint, but headless Chromium renders the listing with **no interactive challenge**, and once
  the page is warm, same-origin `fetch('/collections/<handle>/products.json?limit=250&page=N')`
  answers 200 — so the branch reads structured JSON instead of DOM cards (unlike animes-pro).
- Currency verified before trusting prices: the storefront renders TWD (`Shopify.currency.active =
  'TWD'`, rate 4.1775) while `products.json` returns the shop's base currency — spot-checked
  against hobbyland's HKD price for JAN `4573102650962` (json `102.00` × 4.1775 ≈ DOM `427.00
  TWD`), confirming the JSON figures are HKD and directly comparable.
- Live `tm` run: HG collection 465 products → **196 in-stock Bandai kits**, MG **57**, RG **21**
  (274 total); **all 274 JANs came from the product handle** (`JAN from handle: 274`, 0 catalogue,
  0 provisional `TM:`), 0 variants quashed.
- `enrich_series.py` classified **270/270 distinct titles** via the JEV API (0 failed); import into
  the existing database added the shop through the `INSERT OR IGNORE` seed — **no migration** —
  batches 195-197, **0 skipped**.
- Cross-shop verification on real data: **229** `(grade, sku)` groups join twinnermodel with at
  least one other shop; in **49** multi-shop groups twinnermodel is the sole cheapest offer (would
  badge「Twinnermodel 最平」) and **45** groups are twinnermodel-only (badge「只有 Twinnermodel
  有貨」). `GET /api/comparisons?grade=hg&cheaper=twinnermodel` → 82 rows; freshness includes a
  `twinnermodel` timestamp.

### 2026-10-13 — fourth shop (Fookle Model) + WooCommerce Store API + Latin/part-number matcher

- `pnpm --filter frontend build` clean under strict tsc (106 modules). `pnpm test` →
  **backend 38/38, frontend 68/68**. Python: **93/93**
  (`scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py'`), including the
  `jan_lookup.evaluate()` harness still asserting **0 wrong-SKU matches / precision 1.0** after the
  Latin-scoring + part-number-strip change.
- Crawled fooklemodel.com live over the open WooCommerce Store API (plain `urllib`, **no browser,
  no bot challenge**): 12 pages / 1042 products across the three grade categories (hg=27, mg=35,
  rg=32), filtered to **331 Bandai in-stock kits** → `fookle_hg.csv` 224, `fookle_mg.csv` 83,
  `fookle_rg.csv` 24. Prices are integer minor units (`int(price)/10**minor_unit`); spot-checked
  HK$110 HG / HK$198 MG / HK$1180 MGEX against the live product pages.
- Resolution (the shop publishes **no** identity — `sku` empty, no 13-digit JAN in name or URL):
  JAN from shop sku **0**, from name **0**, from URL **0**, **inherited from the trusted catalogue
  71**, variant collisions quashed **8**, and **260** stored Fookle-only under a provisional
  `FM:<slug>` key. `exclude_shops=('fookle','hobbydigi')` so matches inherit only from
  hobbyland/animes-pro.
- Import on an existing database: the `INSERT OR IGNORE` shops seed added `fookle` (id 130) on boot
  — **no migration, no re-import**; 331 fookle rows imported, **0 skipped** (a provisional `FM:` key
  is a valid sku).
- Fookle is a real 4th comparator, not just exclusives: **71** of its `(grade, sku)` groups join at
  least one other shop, and in **32** of them Fookle is the cheapest offer (would badge 「Fookle
  最平」). Concrete group — MG RX-78-2, JAN `4543112836557`: **fookle HK$198 < animes-pro HK$234 <
  hobbydigi HK$389.90**; the English fookle title matched two CJK titles onto the same barcode.
- **Deviation from plan §3 (recorded deliberately):** the plan said import.service.ts /
  product.repository.ts needed no change, but provisional cleanup was hard-coded to `HD:`, so a
  fookle kit that later resolved a real JAN would leave a stale `FM:` duplicate surfacing as a false
  exclusive. Generalised to `PROVISIONAL_SKU_PREFIXES = ['HD:','FM:']` and `deleteProvisionalByUrl`
  → `sku LIKE '%:%'` (a real JAN is 13 digits, never carries a colon). Covered by
  `import.service.test.ts` case 15 (FM: row replaced by URL once a JAN arrives) and IT-23.

### 2026-10-13 — enhancement 3 layout (hero, showcase, gallery, motion)

Headless Chrome against the live backend (285 HG SKUs) at 1280px and 390px, both factions:
hero stats populated (285 / 69 / 31 / 6 / 166) and counted up; showcase scrolled with real kit photos
and paused on hover; gallery cards rendered with the winner row highlighted; 自護 swapped art, palette
and copy. HobbyDigi photos blocked by the shop's cross-origin policy (`ERR_BLOCKED_BY_RESPONSE`)
fell back to the grade placeholder / were dropped from the showcase as designed.

### 2026-10-12 — third shop (HobbyDigi) + N-shop generalization

- `pnpm -r run build` clean; `pnpm test` → **backend 34/34, frontend 47/47**. Python: **68/68**
  (`scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py'`).
- Crawled HobbyDigi with a fresh browser context per page: **28 pages / 784 cards, zero blocks**.
  A single reused context dies on page 3, and the Cloudflare budget does not recover with time
  (retested at +60 s and +120 s).
- Resolution: 519/784 graded in scope (265 correctly rejected as PG/SD/EG/1:100), JAN from
  URL key 14, from model-code match 13, **1 variant group quashed**, 492 left for review.
- IT-21 reproduced for real: two GP02A kits (an MLRS and a Psalis) both matched the catalogue's
  single GP02A row, and the `UNIQUE (shop_id, sku, grade)` upsert silently swallowed one —
  20 CSV rows became 19. The collision guard now blanks both.
- IT-22 reproduced for real: after the first import, HobbyDigi's own titles appeared in the
  candidate pool (`Bandai MG 組裝模型 - 1/100 …` alongside `[現貨] MG 1/100【…】`), and the review
  queue shrank 492 → 490 because cards matched their own imported rows. Fixed with `exclude_shops`.
- Import on an existing database: the `INSERT OR IGNORE` shops seed added `hobbydigi` on boot —
  **no migration, no re-import**, the other 682 rows untouched.
- `GET /api/comparisons?grade=mg` → 171 rows, offers-per-row `{1: 96, 2: 70, 3: 5}`,
  `cheapestShop {animes-pro: 85, hobbyland: 81, tie: 4, hobbydigi: 1}`,
  `exclusiveShop {animes-pro: 69, null: 75, hobbyland: 26, hobbydigi: 1}`.
- `GET /api/imports/freshness?grade=hg` → `byShop` has three keys and `overall` equals the newest,
  which is HobbyDigi's; under the old hardcoded-shop-list code that timestamp was dropped.
- `GET /api/products?shop=hobbydigi` → 200; `shop=bogus` → 400.
- Built bundle verified: `--shop-c: #b8c3d0`, `.shop-head.shop-c`, `.price-cell.shop-c .price-link`
  all present, and the divider rule is `.comparison-table td.price-cell, …th.shop-head` — the old
  `nth-child(2)/(3)` form is gone.
- **Caution recorded:** running `pnpm -r run build` in parallel with a server started from
  `backend/dist` produced a false `shop=hobbydigi → 400`. Build and run sequentially.

### 2026-10-11 — exclusive verdict + HUD theme

- `pnpm build` clean (backend + frontend, strict TS); `pnpm test` → backend 34/34, frontend 47/47.
- Re-scraped HG/MG for both shops with the image-aware scraper, then `pnpm import:csv` →
  682 products, **682/682 with an absolute `image_url`** (was 48/682 before the re-scrape).
  All 6 CSVs now carry the `image_url` column at 100% coverage; 0 relative URLs —
  `_hobbyland_image_url()` prefixes the static CDN and the animes-pro DOM extractor upgrades
  protocol-relative `//` and substitutes `{width}`.
- Both image CDNs answer `200 image/jpeg` to a referer-less HEAD → no hotlink blocking.
- `GET /api/comparisons` per grade: HG 280 rows (111 both / 169 exclusive), MG 170 (73 / 97),
  RG 31 (17 / 14); every row has ≥1 image.
- Verdict split: HG 59 hobbyland-cheaper / 36 animes-cheaper / 16 tie; MG 52 / 17 / 4; RG 13 / 3 / 1.
- IT-13's failure mode reproduced against a **copy** of the live DB: stripping `image_url` from
  `hobbyland_rg.csv` and re-importing dropped RG from 26 images to 0 on the pre-COALESCE code.
  The fix itself is covered by `import.service.test.ts` case 8 (image preserved, price/stock still
  refreshed) — the live-DB replay was not re-run after the fix.
- IT-14 reproduced: an old-image container squatting `hobbyland-app-1`/:8080 served 0 `exclusiveShop`
  occurrences; `scripts/docker-deploy.sh` removed it and recreated from `:latest`, healthy in 2s.
- Served bundle verified on :8080 — CSS carries `html[data-faction=federation|zeon]` palettes,
  `.crest[data-crest=…]`, `--clip-panel`, `.badge-exclusive`, `.product-thumb-fallback`,
  `color-scheme:dark`; the old light palette tokens (`badge-hobbyland`, `badge-animes`, `#fafaf8`)
  are gone; JS carries `只有 … 有貨`, `exclusiveShop`, and the `hobbyland:faction` key.
- Served bundle re-verified after the `enhancement.md` items: CSS has `.comparison-table th
  {position:sticky;top:0;z-index:2}` with an opaque `--surface-2` fill and an `inset` bottom rule,
  `.table-wrapper{overflow:auto;max-height:max(340px,calc(100vh - 260px))}` (`72vh` ≤640px),
  zebra `tbody tr:nth-child(odd)` / `nth-child(2n)`, `.sort-btn`, `.shop-filter`, and
  `.product-thumb{width:88px;height:88px;object-fit:cover}` (60px ≤640px). No opaque white
  background survives anywhere in the sheet — the only `#fff…` values are the translucent
  zebra (`#ffffff05`) and hover (`#ffffff0f`) fills. JS carries `有售舖頭`, `aria-sort`,
  `localeCompare`, and the filter-specific empty state.
- IT-18 verified live on :8080 after redeploy: `grade=hg` → both shops
  `2026-10-11T11:46:10.8xxZ` with `overall` = the later of the two; `mg` and `rg` return their own
  timestamps (not HG's); no `grade` returns `grade: null` with the global latest; `grade=pg` → 400.
  `GET /api/imports` still returns 200, so the new sub-path did not shadow it.
- IT-19's null shape is covered by `api.test.ts` case 9 (MG never imported in that fixture); it was
  **not** reproduced live, because every grade has been imported on this database.
- Served bundle re-checked after the freshness work: CSS carries `.freshness*`, `.status-row` and the
  accent left-border; JS carries the `/api/imports/freshness?grade=` call, the `import-freshness`
  query key, the `zh-HK` formatter, and all four readout strings.

## 4. Known Semantic Caveat (not yet changed)

`GET /api/comparisons?cheaper=<shop>` filters on `cheapestShop`, which is also set for single-shop
SKUs. So the filter returns "this shop is cheaper **or** the only seller" — 200 of the 280 HG rows
for `cheaper=hobbyland`, where only 59 are genuine price wins. Preserved deliberately: the badge bug
was fixed by adding `exclusiveShop` rather than by changing `cheapestShop`, to keep the API stable.
No UI surface currently passes `cheaper=`. If it is ever exposed, decide first whether the filter
should exclude `exclusiveShop != null`.
