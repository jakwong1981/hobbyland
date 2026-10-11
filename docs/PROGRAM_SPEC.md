<!-- docs/PROGRAM_SPEC.md -->
# Program Specification — Gunpla Price Comparison Dashboard

## 1. File / Directory Structure

```
hobbyland/
├── package.json                 # workspace root: dev/build/test/import:csv/start
├── pnpm-workspace.yaml          # workspaces: backend, frontend
├── tsconfig.base.json           # shared strict TS config
├── .env.example                 # PORT, DATA_DIR, NODE_ENV, CSV_DIR
├── Dockerfile                   # multi-stage (build → runtime, node:24-slim)
├── docker-compose.yml           # single service, ./data volume, port 8080
├── backend/
│   ├── drizzle/0000_init.sql    # schema migration (executed on boot)
│   └── src/
│       ├── index.ts             # bootstrap: config → db → app.listen
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
│   └── tests/                   # vitest: comparison, import, api (supertest)
├── frontend/
│   ├── index.html               # data-faction bootstrap (pre-paint theme) + SPA root
│   ├── tests/                   # vitest + RTL (jsdom): components, dashboard, faction, sort-filter, api client
│   └── src/
│       ├── main.tsx             # React root + QueryClientProvider
│       ├── App.tsx              # shell + page switch + faction theme owner
│       ├── types/index.ts       # mirrors backend DTOs (+ frontend-only Faction / ShopFilterValue / SortState)
│       ├── api/client.ts        # fetch wrapper (apiGet / apiUpload)
│       ├── api/comparison.api.ts  api/import.api.ts
│       ├── hooks/useComparisons.ts              # TanStack Query
│       ├── hooks/useFaction.ts                  # localStorage ↔ <html data-faction>
│       ├── hooks/useComparisonSort.ts           # client-side title/price sort, missing shop trails
│       ├── hooks/useImportFreshness.ts          # last-import timestamp per shop, grade-scoped
│       ├── components/{GradeTabs,SearchBar,ShopFilter,ComparisonTable,CheaperBadge}.tsx
│       ├── components/FreshnessBar.tsx                    # last-update readout
│       ├── components/{FactionCrest,FactionToggle}.tsx   # inline-SVG emblem + theme switch
│       ├── pages/{DashboardPage,ImportPage}.tsx
│       └── styles.css           # dark HUD cockpit theme, mobile-first
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
| GET | `/api/comparisons` | `grade?=hg|mg|rg`, `q?=text`, `cheaper?=hobbyland|animes-pro` | `ComparisonRow[]` |
| GET | `/api/products` | `shop?`, `grade?`, `q?` | `ProductRow[]` |
| GET | `/api/imports/freshness` | `grade?=hg|mg|rg` | `ImportFreshness` |
| GET | `/api/imports` | — | `ImportBatchDto[]` (latest 20) |
| POST | `/api/import` | multipart: `file` (CSV), fields `shop`, `grade` | `{ batchId, rowCount, skipped }` (201) |

```ts
ImportFreshness = {
  grade: Grade | null;                     // null when the query omitted `grade`
  overall: string | null;                  // ISO-8601; latest across both shops, null if none
  byShop: Record<ShopCode, string | null>; // per-shop MAX(products.imported_at)
}
```

Derived from `products`, not `import_batches`, so it reports what is actually on screen for the
requested grade: a shop never scraped for RG yields `null` rather than inheriting an HG timestamp.
`buildFreshness()` in `import.service` is pure; `ProductRepository.findLatestImportPerShop()` owns
the SQL.

```ts
ComparisonRow = {
  sku: string; grade: 'hg'|'mg'|'rg'; title: string;
  offers: Offer[];                       // sorted by price asc
  cheapestShop: 'hobbyland'|'animes-pro'|'tie'|null;
  saving: number|null;                   // null when only one shop carries the SKU
  exclusiveShop: 'hobbyland'|'animes-pro'|null;  // set iff offers.length === 1
}
Offer = { shop, price, regularPrice|null, url, stock|null, sellType|null, imageUrl|null }
```

`cheapestShop` answers "who would win the `cheaper=` filter"; `exclusiveShop` answers "was there a
race at all". The UI must branch on `exclusiveShop` first — a single-offer SKU renders
「只有 <Shop> 有貨」, never「<Shop> 平」. See FUNCTION_SPEC §3.

## 4. Dashboard Interaction Contract

All of the following is client-side; one `GET /api/comparisons?grade=&q=` response feeds it, so no
extra round trip is made when the user sorts or filters.

| Control | State owner | Behaviour |
|---|---|---|
| Grade tabs | `DashboardPage` | refetches (server-side `grade` param) |
| Search box | `DashboardPage` | refetches (server-side `q` param) |
| 有售舖頭 select | `DashboardPage` | filters the fetched rows to those whose `offers` include the chosen shop; default `all`. Count reads `N 個 SKU`, or `M / N 個 SKU` while filtered |
| Column sort | `useComparisonSort` (inside `ComparisonTable`) | `title` and each shop's price are sortable; click cycles asc → desc. `null` sort = the backend's SKU order. A shop that does not carry the SKU has no price and always sorts last, in both directions |
| Last-update readout | `useImportFreshness` | refetches with the grade; one `<time dateTime>` per shop, 「冇紀錄」for a shop never imported at that grade, and separate loading / failed states |

Sorting is announced through `aria-sort` on the `<th>`, and the clickable region is a real `<button>`
inside the header cell so it stays keyboard-reachable. The header row is frozen: `.table-wrapper` is
the scroll container (`overflow:auto` + `max-height`) and `th` is `position:sticky; top:0` with an
opaque fill. The table uses `border-collapse:separate; border-spacing:0` because collapsing borders
are unreliable on a sticky cell; cells only draw bottom/left rules, so the look is unchanged.
