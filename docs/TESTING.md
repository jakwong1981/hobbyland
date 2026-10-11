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

### comparison.service.test.ts (6 tests)

| # | Case | Asserts |
|---|---|---|
| 1 | Two shops, different prices | cheaper shop flagged, saving = diff, offers sorted asc, `exclusiveShop = null` |
| 2 | Equal prices | `cheapestShop = 'tie'`, `saving = 0`, `exclusiveShop = null` |
| 3 | Single-shop SKU | `cheapestShop` = that shop, `saving = null`, 1 offer |
| 4 | Single-shop SKU (exclusive) | `exclusiveShop` = that shop — the flag the badge branches on |
| 5 | Same SKU in different grades | two separate groups |
| 6 | Sorting | rows ordered by SKU |

### import.service.test.ts (8 tests)

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

### api.test.ts (7 tests, supertest + in-memory DB)

| # | Endpoint | Case | Expected |
|---|---|---|---|
| 1 | GET /api/comparisons | grouping + cheapest flag | 200, saving 22, `exclusiveShop` null for two-shop / set for single-shop |
| 2 | GET /api/comparisons | `cheaper=animes-pro` filter | only matching rows |
| 3 | GET /api/comparisons | `grade=pg` (invalid) | 400 + traceId |
| 4 | POST /api/import | valid CSV upload | 201, rowCount 1, row queryable |
| 5 | POST /api/import | missing file | 400 |
| 6 | POST /api/import | CSV with no valid rows | 422 |
| 7 | GET /api/imports | batch list | 200, 2 batches |

### Frontend (`frontend/tests/`, 41 tests)

| File | Cases |
|---|---|
| components.test.tsx (17) | `CheaperBadge` (cheaper + saving, tie, single-shop →「只有 Animes 有貨」and never「平」, hobbyland-exclusive, exclusive outranks a tie verdict, none); `ComparisonTable` (empty state, both prices + badge, missing-shop placeholder + exclusive label, regular price only when higher, pre-order flag, preview image rendered, grade placeholder when no image, `onError` → placeholder); `GradeTabs` (selected state, emits grade); `SearchBar` (emits text) |
| dashboard.test.tsx (6) | api client (unwrap data, `ApiError` on failure, query-string building); `DashboardPage` (default HG load, refetch on grade change, error message) |
| faction.test.tsx (6) | `FactionToggle` (active faction `aria-checked`, emits clicked faction); `useFaction` (federation default + `<html data-faction>`, persist & restore across mounts, unknown stored value → federation); `App` (header toggle flips the document faction) |
| sort-filter.test.tsx (12) | `useComparisonSort` (incoming order kept while unsorted, title asc/desc, per-shop price asc/desc with the non-carrying shop always last, input array not mutated); `ComparisonTable` (three sortable headers start `aria-sort="none"`, verdict header has no button, click reorders rows + flips `aria-sort`, price header reorders); `ShopFilter` (defaults to `all` with 3 options, emits choice); `DashboardPage` (all-by-default count, filtered `M / N` count with the other shop's rows hidden, filter-specific empty state) |

`fetch` is stubbed per test; `QueryClient` retries are disabled.

Current status: **backend 21/21, frontend 41/41 passing**; `pnpm build` clean under strict TS.

## 2. Functional / Integration Test Matrix

| Test Case ID | Scenario | Preconditions | Input Payload | Expected Status & Response | Pass/Fail Criteria |
|---|---|---|---|---|---|
| IT-01 | CLI bulk import | 6 scraper CSVs present | `pnpm import:csv` | 6 batches; HG 252+139, MG 100+143, RG 26+22 rows | row counts match CSV line counts minus skipped |
| IT-02 | Skip SKU-less rows | animes-pro_mg.csv contains Ultraman items w/o JAN | IT-01 | skipped=103 for that file | skipped count matches rows with empty sku |
| IT-03 | Dashboard grouping | IT-01 done | `GET /api/comparisons?grade=hg` | 280 rows, 111 with 2 offers, 169 exclusive | counts match |
| IT-04 | Cheaper badge | IT-01 done | `cheaper=hobbyland` / `cheaper=animes-pro` | 200 / 64 rows (HG) | each row's `cheapestShop` equals filter — **note** the filter also matches single-shop rows (141 / 28 of those totals); see §4 |
| IT-05 | UI upload | server running | multipart CSV via「匯入」page | 201 + visible in grid | product appears in dashboard |
| IT-06 | Invalid grade | — | `GET /api/comparisons?grade=pg` | 400 ApiErrorResponse + traceId | zod message present |
| IT-07 | Empty/invalid CSV upload | server running | `bad.csv` no valid rows | 422 | no batch written |
| IT-08 | Malformed CSV upload | server running | column-count mismatch | 400 | transaction rolled back |
| IT-09 | SPA serving | `pnpm build` done | `GET /` | index.html | title「Gunpla 格價 // Price Recon」, `<html data-faction>` bootstrap present |
| IT-10 | Re-import idempotency | IT-01 done | run IT-01 again | same product count, +6 batches | no duplicate (shop, sku, grade) |
| IT-11 | Docker e2e | image built | `docker compose up` | UI on :8080 with data volume | IT-03 repeatable in container |
| IT-12 | Exclusive verdict end-to-end | IT-01 done | `GET /api/comparisons?grade=hg` | 169 rows with `exclusiveShop` set | UI shows「只有 <Shop> 有貨」, no「平」badge on those rows |
| IT-13 | Stale CSV cannot strip images | IT-01 done, all rows imaged | re-import a CSV with the `image_url` column removed | that grade keeps 100% image coverage | `SUM(image_url IS NOT NULL)` unchanged; price/stock still refresh |
| IT-14 | Stale container replacement | a non-compose container named `hobbyland-app-1` squats :8080 on an old image | `scripts/docker-deploy.sh` | script logs「Removing leftover container」and recreates from `:latest` | `GET /api/comparisons` afterwards carries the current contract (`exclusiveShop` present) |
| IT-15 | Frozen header + zebra | IT-01 done, :8080 serving | scroll the 280-row HG grid | column header stays pinned; rows alternate shade | `th` computed `position: sticky`; `.table-wrapper` is the scroll container |
| IT-16 | Sort + filter on real data | IT-01 done | click 產品 / price headers; pick Hobbyland in 有售舖頭 | rows reorder client-side with no refetch; count becomes `M / N 個 SKU` | sorting a shop's price puts SKUs that shop does not carry last |
| IT-17 | Preview image sizing | IT-01 done, 682/682 imaged | inspect a row thumbnail | 88px square (60px ≤640px), `object-fit: cover`, no white letterbox | thumbnail box has no padding and a dark `--surface-2` fill |

## 3. Manual Verification Performed (2026-10-11, re-run after the exclusive-verdict + HUD theme work)

- `pnpm build` clean (backend + frontend, strict TS); `pnpm test` → backend 21/21, frontend 41/41.
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

## 4. Known Semantic Caveat (not yet changed)

`GET /api/comparisons?cheaper=<shop>` filters on `cheapestShop`, which is also set for single-shop
SKUs. So the filter returns "this shop is cheaper **or** the only seller" — 200 of the 280 HG rows
for `cheaper=hobbyland`, where only 59 are genuine price wins. Preserved deliberately: the badge bug
was fixed by adding `exclusiveShop` rather than by changing `cheapestShop`, to keep the API stable.
No UI surface currently passes `cheaper=`. If it is ever exposed, decide first whether the filter
should exclude `exclusiveShop != null`.
