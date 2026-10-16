<!-- docs/PROGRAM_SPEC.md -->
# Program Specification — Gunpla Price Comparison Dashboard

## 1. File / Directory Structure

```
hobbyland/
├── package.json                 # workspace root: dev/build/test/import:csv/start
├── pnpm-workspace.yaml          # workspaces: backend, frontend
├── tsconfig.base.json           # shared strict TS config
├── .env.example                 # PORT, TLS_CERT_PATH, TLS_KEY_PATH, DATA_DIR, NODE_ENV, CSV_DIR
├── Dockerfile                   # multi-stage (build → runtime, node:24-slim)
├── docker-compose.yml           # single service, ./data + ./certs volumes, port 8089
├── backend/
│   ├── drizzle/0000_init.sql    # schema migration (executed on boot)
│   └── src/
│       ├── index.ts             # bootstrap: config → db → https/http listen (TLS when certs present)
│       ├── config.ts            # env validation (zod)
│       ├── app.ts               # express wiring + static frontend serving
│       ├── cli/import.ts        # CSV folder/file import CLI (`pnpm import:csv`)
│       ├── db/client.ts         # node:sqlite DatabaseSync factory + migrate()
│       ├── types/index.ts       # DTO contracts (shared shapes)
│       ├── repositories/product.repository.ts   # SQL only (products, batches, shops)
│       ├── services/import.service.ts           # CSV parse/validate + transactional upsert
│       ├── services/comparison.service.ts       # group-by-SKU + cheapest computation
│       ├── controllers/product.controller.ts    # comparisons / products / imports
│       ├── controllers/import.controller.ts     # multipart CSV upload
│       ├── routes/index.ts      # /api router
│       ├── middleware/error.middleware.ts       # traceId + ApiErrorResponse
│       └── utils/{logger.ts,app-error.ts}
│   └── tests/                   # vitest: comparison, import, config, api + scrape.api (supertest)
├── frontend/
│   ├── index.html               # data-faction bootstrap (pre-paint theme) + SPA root
│   ├── tests/                   # vitest + RTL (jsdom): components, dashboard, faction, sort-filter, api client,
│   │                            #   comparison-stats, count-up, layout (hero/showcase/gallery/wipe/view toggle)
│   └── src/
│       ├── main.tsx             # React root + QueryClientProvider
│       ├── App.tsx              # shell + page switch + faction theme owner
│       ├── types/index.ts       # mirrors backend DTOs (+ frontend-only Faction / DashboardView / ShopFilterValue / SeriesFilterValue / SortState)
│       ├── shops.ts             # SHOP_LABEL / SHOP_SHORT_LABEL / SHOP_TONE / SHOP_MONOGRAM
│       ├── series.ts            # SERIES_IDS / SERIES_LABEL / seriesLabel — mirrors scripts/jev_series.py SERIES
│       ├── api/client.ts        # fetch wrapper (apiGet / apiUpload)
│       ├── api/comparison.api.ts  api/import.api.ts
│       ├── hooks/useComparisons.ts              # TanStack Query
│       ├── hooks/useFaction.ts                  # localStorage ↔ <html data-faction>
│       ├── hooks/useComparisonSort.ts           # client-side title/price sort, missing shop trails
│       ├── hooks/useImportFreshness.ts          # last-import timestamp per shop, grade-scoped
│       ├── hooks/usePrefersReducedMotion.ts     # matchMedia listener (cleaned up on unmount)
│       ├── hooks/useCountUp.ts                  # rAF tween for stat numbers; instant under reduced motion
│       ├── utils/productImage.ts                # first shop (SHOP_CODES order) with a photo
│       ├── utils/comparisonStats.ts             # summarizeComparisons → hero stat counts
│       ├── utils/seriesStats.ts                 # countBySeries → series filter options + stat chips
│       ├── utils/showcase.ts                    # selectShowcaseKits → photo strip (top saving, max 16)
│       ├── components/{GradeTabs,SearchBar,ShopFilter,SeriesFilter,ComparisonTable,CheaperBadge}.tsx
│       ├── components/FreshnessBar.tsx                    # last-update readout
│       ├── components/{FactionCrest,FactionToggle,FactionWipe}.tsx   # emblem, theme switch, switch transition
│       ├── components/{ShopLogo,GradeEmblem,MobileSuitArt}.tsx       # inline-SVG logos & original line art
│       ├── components/{HeroBanner,StatTile,KitShowcase}.tsx          # mission banner + kit photo strip
│       ├── components/{ViewToggle,ComparisonGallery,ProductImage}.tsx # 表格/圖鑑 switch, card grid, photo w/ fallback
│       ├── pages/{DashboardPage,ImportPage}.tsx
│       └── styles/              # index.css imports tokens, base, header, hero, showcase, toolbar,
│                                #   table, gallery, import, responsive, motion (all animation)
└── docs/
```

## 2. Component Dependency Graph

```
React pages ──▶ hooks/useComparisons ──▶ api/* ──▶ fetch /api/*
                                                   │
Express routes ──▶ controllers ──▶ services ──▶ ProductRepository ──▶ node:sqlite
                     ▲                                ▲
               cli/import.ts ──▶ import.service ──────┘
```

- `product.controller` → `comparison.service` (pure) + `ProductRepository`
- `import.controller` / `cli/import.ts` → `import.service` → `ProductRepository`
- Controllers never touch SQL; repository never sees HTTP types.

## 3. API Contracts

All responses are `ApiResponse<T> = { code: 0, message: 'ok', data: T, timestamp: ISO }`.
Errors are `ApiErrorResponse = { code: <httpStatus>, message, data: null, timestamp, traceId }`.

| Method | Path | Query / Body | Response `data` |
|---|---|---|---|
| GET | `/api/comparisons` | `grade?=hg|mg|rg`, `q?=text`, `cheaper?=<ShopCode>`, `series?=<seriesId>` | `ComparisonRow[]` |
| GET | `/api/products` | `shop?`, `grade?`, `q?`, `series?` | `ProductRow[]` |
| GET | `/api/imports/freshness` | `grade?=hg|mg|rg` | `ImportFreshness` |
| GET | `/api/imports` | — | `ImportBatchDto[]` (latest 20) |
| POST | `/api/import` | multipart: `file` (CSV), fields `shop`, `grade` | `{ batchId, rowCount, skipped }` (201) |

```ts
ImportFreshness = {
  grade: Grade | null;                     // null when the query omitted `grade`
  overall: string | null;                  // ISO-8601; latest across every shop, null if none
  byShop: Record<ShopCode, string | null>; // per-shop MAX(products.imported_at)
}
```

Derived from `products`, not `import_batches`, so it reports what is actually on screen for the
requested grade: a shop never scraped for RG yields `null` rather than inheriting an HG timestamp.
`buildFreshness()` in `import.service` is pure; `ProductRepository.findLatestImportPerShop()` owns
the SQL.

```ts
ComparisonRow = {
  sku: string; grade: Grade; title: string;
  series: string | null;               // Gundam series id (scripts/jev_series.py ids, `unknown` included);
                                       // first non-null across the group; null when no shop row is classified
  offers: Offer[];                       // sorted by price asc, one per shop that stocks the SKU
  cheapestShop: ShopCode | 'tie' | null; // null only when there are no offers
  saving: number|null;                   // null for a single offer; else the gap to the runner-up
  exclusiveShop: ShopCode | null;        // set iff offers.length === 1
}
Offer = { shop, price, regularPrice|null, url, stock|null, sellType|null, imageUrl|null }
```

`ShopCode` and `Grade` derive from the `SHOP_CODES` / `GRADES` constants, which also drive the zod
query enums and the importer's `FILE_PATTERN`. Adding a shop is one array entry plus a `shops` seed
row — the seed is `INSERT OR IGNORE` and re-runs on every boot, so an existing database picks it up
with no migration and no re-import.

`cheapestShop` answers "who would win the `cheaper=` filter"; `exclusiveShop` answers "was there a
race at all". The UI must branch on `exclusiveShop` first — a single-offer SKU renders
「只有 <Shop> 有貨」, never「<Shop> 最平」. See FUNCTION_SPEC §3.

## 4. Dashboard Interaction Contract

All of the following is client-side; one `GET /api/comparisons?grade=&q=` response feeds it, so no
extra round trip is made when the user sorts or filters.

| Control | State owner | Behaviour |
|---|---|---|
| Grade tabs | `DashboardPage` | refetches (server-side `grade` param) |
| Search box | `DashboardPage` | refetches (server-side `q` param) |
| 有售舖頭 select | `DashboardPage` | filters the fetched rows to those whose `offers` include the chosen shop; default `all`. Count reads `N 個 SKU`, or `M / N 個 SKU` while filtered |
| 系列 select | `DashboardPage` (`series`) | client-side filter on `ComparisonRow.series`; options are the series present in the fetched rows with counts (`SeriesFilter` + `countBySeries`), plus 未分類 when any row is `null`; default `all` |
| 系列統計 chips | `DashboardPage` | one chip per series in the visible rows (`countBySeries(visible)`, count desc); clicking a chip filters to that series, clicking the active chip clears back to `all` |
| 系列 column / badge | `ComparisonTable` / `ComparisonGallery` | `seriesLabel(row.series)` — id → 中文系列名 via `frontend/src/series.ts`; `—` when unclassified |
| 判定 badge | `ComparisonTable` / `ComparisonGallery` | `CheaperBadge` —「<Shop> 最平」/「同價」/「只有 <Shop> 有貨」/`—`. In the table it sits **under the thumbnail inside the 產品 cell** (`.thumb-stack`), not in its own column: it is a property of the kit rather than a comparable field, and a column of one-chip cells cost more width than it carried meaning |
| Column sort | `useComparisonSort` (inside `ComparisonTable`) | `title` and each shop's price are sortable; click cycles asc → desc. `null` sort = the backend's SKU order. A shop that does not carry the SKU has no price and always sorts last, in both directions |
| 表格 / 圖鑑 toggle | `DashboardPage` (`view`) | swaps `ComparisonTable` ↔ `ComparisonGallery` over the same filtered rows; default `table`. Gallery keeps the incoming order (column sort is table-only) |
| Hero stats | `HeroBanner` | `summarizeComparisons(rows)` over the fetched (unfiltered) rows: total, cheapest-wins per shop, exclusives; numbers count up via `useCountUp` |
| Kit showcase | `KitShowcase` | up to 16 rows with a photo, largest `saving` first; each links to the lowest-priced offer; a photo that fails to load drops its kit |
| Last-update readout | `useImportFreshness` | refetches with the grade; one `<time dateTime>` per shop, 「冇紀錄」for a shop never imported at that grade, and separate loading / failed states |

Sorting is announced through `aria-sort` on the `<th>`, and the clickable region is a real `<button>`
inside the header cell so it stays keyboard-reachable. The header row is frozen: `.table-wrapper` is
the scroll container (`overflow:auto` + `max-height`) and `th` is `position:sticky; top:0` with an
opaque fill. The table uses `border-collapse:separate; border-spacing:0` because collapsing borders
are unreliable on a sticky cell; cells only draw bottom/left rules, so the look is unchanged.
