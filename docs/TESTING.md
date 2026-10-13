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

### comparison.service.test.ts (10 tests)

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

> Cases 8-10 cast a third shop code that `ShopCode` does not declare. They pin the
> N-way arithmetic without adding a shop that has no data source behind it.

### import.service.test.ts (16 tests)

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
| 16 | Provisional `HD:` row re-imported unchanged | still one row — a provisional sku never triggers its own deletion |

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

### Frontend (`frontend/tests/`, 68 tests)

| File | Cases |
|---|---|
| components.test.tsx (21) | `CheaperBadge` (cheapest shop named without the saving amount, tie, single-shop →「只有 Animes 有貨」and never「最平」, hobbyland-exclusive, exclusive outranks a tie verdict, none); `ComparisonTable` (empty state, both prices + badge, missing-shop placeholder + exclusive label, regular price only when higher, pre-order flag, preview image rendered, grade placeholder when no image, `onError` → placeholder); `FreshnessBar` (a `dateTime` per imported shop with the never-imported shops marked「冇紀錄」, no history at all, loading vs. failed); `GradeTabs` (selected state, emits grade); `SearchBar` (emits text) |
| dashboard.test.tsx (8) | api client (unwrap data, `ApiError` on failure, query-string building); `DashboardPage` (default HG load, refetch on grade change, freshness requested grade-scoped, **both timestamps rendered on the page**, error message + freshness failure state) |
| faction.test.tsx (6) | `FactionToggle` (active faction `aria-checked`, emits clicked faction); `useFaction` (federation default + `<html data-faction>`, persist & restore across mounts, unknown stored value → federation); `App` (header toggle flips the document faction) |
| comparison-stats.test.ts (8) | `summarizeComparisons` (per-shop wins, ties, exclusives counted apart, empty input, a fookle win + fookle exclusive); `productImageUrl` (SHOP_CODES preference, null without photo); `selectShowcaseKits` (photo-only, biggest saving first, links lowest offer, cap) |
| count-up.test.tsx (4) | `useCountUp` (reduced motion → target immediately with no frame scheduled, tween 0 → target, continues from shown value on target change, cancels frame on unmount) — rAF and `matchMedia` stubbed |
| layout.test.tsx (9) | `HeroBanner` (stat targets, both faction heads rendered); `KitShowcase` (nothing without photos, link to cheapest offer + `aria-hidden` clone, failed photo drops kit); `ComparisonGallery` (empty state, per-shop prices + winner + verdict); `FactionWipe` (hidden on first render, plays after switch); `DashboardPage` (表格 ↔ 圖鑑 toggle) |
| sort-filter.test.tsx (12) | `useComparisonSort` (incoming order kept while unsorted, title asc/desc, per-shop price asc/desc with the non-carrying shop always last, input array not mutated); `ComparisonTable` (three sortable headers start `aria-sort="none"`, verdict header has no button, click reorders rows + flips `aria-sort`, price header reorders); `ShopFilter` (defaults to `all`, listing every shop plus 全部, emits choice); `DashboardPage` (all-by-default count, filtered `M / N` count with the other shop's rows hidden, filter-specific empty state) |

`fetch` is stubbed per test; `QueryClient` retries are disabled. `tests/fixtures.ts` exports
`stubApi(comparisons, freshness?)`, which routes on the requested URL — the dashboard issues two
queries, so a single-payload stub would answer the freshness request with a comparison array.

`tests/setup.ts` also installs a `window.matchMedia` stub (jsdom has none) returning `matches: false`.

Current status: **backend 38/38, frontend 68/68 passing**; Python `scripts/test_*.py` 93/93; `pnpm build` clean under strict TS.

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
| IT-11 | Docker e2e | image built | `docker compose up` | UI on :8080 with data volume | IT-03 repeatable in container |
| IT-12 | Exclusive verdict end-to-end | IT-01 done | `GET /api/comparisons?grade=hg` | 166 rows with `exclusiveShop` set | UI shows「只有 <Shop> 有貨」, no「最平」badge on those rows |
| IT-12b | Three-shop verdict | IT-01 done | `GET /api/comparisons?grade=mg` | 5 rows with 3 offers; `saving` is the gap to the **runner-up**, not to one named rival | a tie between the two cheapest still reads「同價」even with a dearer third offer |
| IT-13 | Stale CSV cannot strip images | IT-01 done, all rows imaged | re-import a CSV with the `image_url` column removed | that grade keeps 100% image coverage | `SUM(image_url IS NOT NULL)` unchanged; price/stock still refresh |
| IT-14 | Stale container replacement | a non-compose container named `hobbyland-app-1` squats :8080 on an old image | `scripts/docker-deploy.sh` | script logs「Removing leftover container」and recreates from `:latest` | `GET /api/comparisons` afterwards carries the current contract (`exclusiveShop` present) |
| IT-15 | Frozen header + zebra | IT-01 done, :8080 serving | scroll the 285-row HG grid | column header stays pinned; rows alternate shade | `th` computed `position: sticky`; `.table-wrapper` is the scroll container |
| IT-16 | Sort + filter on real data | IT-01 done | click 產品 / any price header; pick a shop in 有售舖頭 | rows reorder client-side with no refetch; count becomes `M / N 個 SKU` | sorting a shop's price puts SKUs that shop does not carry last |
| IT-17 | Preview image sizing | IT-01 done, 709/709 imaged | inspect a row thumbnail | 88px square (60px ≤640px), `object-fit: cover`, no white letterbox | thumbnail box has no padding and a dark `--surface-2` fill |
| IT-18 | Last-update readout | IT-01 done | `GET /api/imports/freshness?grade=hg` | 200, all four shops non-null, `overall` = the latest timestamp | dashboard renders four `<time dateTime>` elements above the grid; switching grade refetches |
| IT-18b | `overall` counts an unlisted shop | a shop present in `shops` but absent from `SHOP_CODES` has the newest timestamp | `GET /api/imports/freshness` | `overall` reflects that newest timestamp | `buildFreshness` derives from the populated map, not a hardcoded shop list |
| IT-19 | Freshness for an unscraped grade | only HG imported | `GET /api/imports/freshness?grade=rg` | 200, `overall = null`, all shops `null` | readout shows「呢個級別未有匯入紀錄」rather than an HG timestamp |
| IT-20 | Third price column renders | IT-01 done, :8080 serving | inspect the HG grid | HobbyDigi column present with its own neutral tone **and** a left divider | built CSS contains `--shop-c`, `.shop-head.shop-c`, `.price-cell.shop-c .price-link`, and the divider rule keys off `td.price-cell` / `th.shop-head` rather than `nth-child` |
| IT-20b | Fourth price column renders | IT-01 done, :8080 serving | inspect the HG grid | Fookle column present with its own neutral tone **and** a left divider | built CSS contains `--shop-d`, `.shop-head.shop-d`, `.price-cell.shop-d .price-link` |
| IT-21 | HobbyDigi variant guard | `hd` scrape done | inspect the resolution report | `variants quashed ≥ 0`; no duplicate `(grade, sku)` inside any `hobbydigi_*.csv` | two differently-titled cards resolving to one barcode are both blanked, so the `UNIQUE (shop_id, sku, grade)` upsert cannot silently swallow one |
| IT-22 | No circular matching | hobbydigi rows already imported | re-run `hd` | the report's `catalogue size` excludes hobbydigi's own rows | `JanCatalogue.from_database(..., exclude_shops=('hobbydigi',))` |
| IT-22b | Fookle cross-script match + no circular matching | `fm` scrape done, catalogue from hobbyland/animes-pro | run `hobbyland_scraper.py fm` | some English fookle titles inherit a real JAN via the Latin/part-number matcher; the rest become `FM:<slug>` exclusives | the report's `catalogue size` excludes fookle's **and** hobbydigi's own rows (`exclude_shops=('fookle','hobbydigi')`); `evaluate()` still reports 0 wrong-SKU matches |
| IT-23 | Fookle `FM:` provisional replaced | a fookle kit stored under `FM:<slug>` | re-import `fookle_hg.csv` after the kit resolves a real JAN | one row for that URL, keyed by the JAN — no `FM:` duplicate | `deleteProvisionalByUrl` deletes any `<PREFIX>:` sku for the URL (covered by `import.service.test.ts` case 15) |

## 3. Manual Verification Performed

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
