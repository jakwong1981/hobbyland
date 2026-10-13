# Gunpla Price Comparison Dashboard

A self-hosted dashboard that answers one question: **for a given Bandai Gunpla kit, which of the
Hong Kong hobby shops is cheapest — and does only one of them actually stock it?**

It ingests scraper output from [Hobbyland E-Shop](https://www.hobbylandeshop.com),
[Animes-Pro](https://animes-pro.com) and [HobbyDigi](https://www.hobbydigi.com), matches listings
across the shops by JAN barcode, and renders a per-SKU verdict.

```
709 products · 487 comparison groups · HG 285 / MG 171 / RG 31   (as of 2026-10-12)
```

---

## 1. Purpose

The shops sell overlapping Bandai catalogue, but they price independently, run different
promotions, and — critically — **carry different subsets of the catalogue**. Of the 487 matched
`(grade, sku)` groups, 211 are sold by more than one shop; **276 are exclusive to one**.

That distribution drives the central design constraint: a naive "cheapest shop" badge is wrong more
often than it is right, because a lone offer cannot win a price comparison. Saying「Animes 最平」
("Animes is cheapest") for a kit Hobbyland does not even list is not a rounding error, it is a
different claim. The verdict model is therefore explicit about which situation it is in
(see [§4.2](#42-the-verdict-contract)).

> **HobbyDigi coverage is partial by design.** The shop publishes no JAN for ~94% of its listings,
> and no automatic name matcher exceeds ~92% precision on this catalogue — the residue is genuine
> ambiguity (re-releases, P-Bandai vs. retail, dual transliterations). So only barcodes from the
> shop's own product URL key, a model-code match, or a human-confirmed match are imported; the rest
> are held for review rather than guessed. See [HobbyDigi matching](#hobbydigi-matching).

Secondary goals:

- **Zero infrastructure.** Embedded SQLite, no database server, no queue, no cloud dependency.
  One container, one bind-mounted volume.
- **Auditable imports.** Every CSV load leaves an append-only batch record; re-imports are
  idempotent.
- **Re-runnable data pipeline.** Scrape → CSV → import is a single cron-able command.

---

## 2. What it does

| Area | Behaviour |
|---|---|
| **Comparison grid** | One row per `(grade, sku)`, every shop's price side by side, sale vs. regular price, stock / pre-order note, product thumbnail |
| **Verdict badge** | 「<Shop> 最平」when several sell it and prices differ, 「同價」when the lowest is shared, 「只有 <Shop> 有貨」when only one carries it |
| **Frozen, sortable header** | Column header stays pinned while the grid scrolls; 產品 and every price column sort asc/desc |
| **Shop filter** | 有售舖頭 select narrows to the SKUs a given shop carries (default 全部) |
| **Last-update readout** | Per-shop import timestamp for the grade being viewed, so a stale scrape is visible at a glance |
| **Grade tabs + search** | HG / MG / RG switch and a title-or-SKU search, both server-side |
| **CSV import** | Upload through the「匯入」page, or bulk-import a folder via CLI |
| **Theme** | Dark HUD cockpit skin, switchable between 聯邦 (Federation) and 自護 (Zeon) palettes; the choice persists across reloads |

---

## 3. Technology

### Runtime

| Layer | Choice | Why |
|---|---|---|
| Language | TypeScript 5.7, `strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` | The last two are what catch the `undefined`-vs-missing-key class of bug in DTO construction |
| Runtime | Node.js ≥ 22.13 | `node:sqlite` is a builtin — no native module to compile, no better-sqlite3 rebuild pain |
| Package manager | pnpm 11 (workspace: `backend`, `frontend`) | Single lockfile, per-package scripts |

### Backend

| Dependency | Version | Role |
|---|---|---|
| `express` | 4.21.2 | HTTP + static SPA serving |
| `node:sqlite` | builtin | `DatabaseSync`, WAL mode |
| `zod` | 3.24.1 | Query-param and env validation at the boundary |
| `csv-parse` | 5.6.0 | CSV parsing (`bom: true`, `columns: true`) |
| `multer` | 2.0.1 | Multipart upload, memory storage, 10 MB cap |
| `pino` | 9.6.0 | Structured JSON logs |
| `tsx` / `vitest` / `supertest` | dev | Watch mode, unit + API-level tests |

No ORM. SQL is hand-written and confined to `ProductRepository`. The schema in
`backend/drizzle/0000_init.sql` is `CREATE TABLE IF NOT EXISTS` DDL executed on every boot, plus one
in-place guard that adds `image_url` to databases created before that column existed — so an
existing `data/hobbyland.db` upgrades itself rather than failing.

### Frontend

| Dependency | Version | Role |
|---|---|---|
| `react` / `react-dom` | 18.3.1 | Function components + hooks only |
| `@tanstack/react-query` | 5.62.11 | Server state, caching, refetch-on-filter |
| `vite` | 6.0.7 | Dev server (`/api` proxied to :8080) + production build |
| `@testing-library/react` / `jsdom` / `vitest` | dev | Component and hook tests |

Local UI state stays in `useState`; only server data goes through React Query. No global store —
the app has exactly two pages and one shared preference (the faction theme).

---

## 4. Design

### 4.1 Layering

Strict one-way layering; skipping a layer is not done anywhere in the codebase.

```mermaid
flowchart TD
    subgraph FE["Frontend (React 18 + Vite)"]
        P["pages/ DashboardPage · ImportPage"]
        H["hooks/ useComparisons · useComparisonSort · useFaction"]
        C["components/ ComparisonTable · CheaperBadge · ShopFilter · FactionToggle"]
        A["api/ client · comparison.api · import.api"]
        P --> H --> A
        P --> C
    end

    subgraph BE["Backend (Express)"]
        R["routes/"]
        CTRL["controllers/ — routing, zod validation, status codes"]
        SVC["services/ — comparison.service (pure) · import.service"]
        REPO["repositories/ ProductRepository — the only SQL"]
        MW["middleware/ traceId · notFound · error"]
        R --> CTRL --> SVC --> REPO
        R --> MW
    end

    DB[("SQLite — products · shops · import_batches")]
    CLI["cli/import.ts"]
    SCRAPE["hobbyland_scraper.py — external repo"]

    A -->|"fetch /api/*"| R
    REPO --> DB
    CLI --> SVC
    SCRAPE -->|"9 CSV files"| CLI
```

- Controllers never see SQL; the repository never sees HTTP types.
- `comparison.service.buildComparisons()` is a **pure function** (`ProductRow[] → ComparisonRow[]`),
  which is why it is trivially unit-testable without a database.
- The CLI and the upload controller share the same `import.service` — one import path, two entry
  points.

### 4.2 The verdict contract

This is the one design decision worth reading before touching the comparison logic.

```ts
ComparisonRow = {
  sku, grade, title,
  offers: Offer[],                       // sorted by price ascending, one per shop that stocks it
  cheapestShop: ShopCode | 'tie' | null, // null only when there are no offers at all
  saving: number | null,                 // null when one shop carries the SKU;
                                         // otherwise the gap to the runner-up
  exclusiveShop: ShopCode | null,        // set iff offers.length === 1
}
```

`cheapestShop` and `exclusiveShop` answer **different questions**, and both are needed:

- `cheapestShop` → *"who would win a `?cheaper=` filter?"*
- `exclusiveShop` → *"was there a race at all?"*

```mermaid
flowchart TD
    S["offers.length"] -->|"0"| N["cheapestShop = null<br/>badge: —"]
    S -->|"1"| E["exclusiveShop = that shop<br/>saving = null<br/>badge:「只有 &lt;Shop&gt; 有貨」"]
    S -->|"≥2"| Q{"more than one offer<br/>at the lowest price?"}
    Q -->|yes| T["cheapestShop = 'tie'<br/>saving = 0<br/>badge:「同價」"]
    Q -->|no| W["cheapestShop = lowest shop<br/>saving = gap to runner-up<br/>badge:「&lt;Shop&gt; 最平」"]
```

`saving` therefore means *"versus the next-best alternative"*, not *"versus one specific rival"*.
With two shops those are the same thing; with three they are not, and the runner-up reading is the
one that answers the question a buyer actually has. `exclusiveShop` is set only when a single shop
carries the SKU — at three shops a kit sold by exactly two yields `null`, and the grid already shows
which column is empty, so no separate "2 of 3" field is needed.

The tie test counts every offer level with the lowest price rather than comparing the top two.
Because `offers` is sorted ascending those are equivalent today, but the count says what it means
and keeps holding if the sort is ever removed.

The single-shop branch **also** sets `cheapestShop` to that shop. That is deliberate: it keeps
`?cheaper=<shop>` matching exclusive listings, preserving the existing API contract. The UI must
branch on `exclusiveShop` *first* — `CheaperBadge` does exactly that.

The rejected alternative was letting the badge infer exclusivity from `saving === null`. It works
until someone adds a case where saving is legitimately null, and then it fails silently and
invisibly. Making the state a named field costs one line in the service and removes the coupling.

`title` comes from the highest-ranked shop in `SHOP_CODES`, not from whichever row the query
returned first: `findProducts` orders by `sku` alone, so the order *within* a group is unspecified
and the shops word the same kit differently. Without an explicit pick the displayed title depended
on row insertion order.

### 4.3 Data model

```
shops(id, code UNIQUE, name)                        -- seeded: hobbyland, animes-pro
import_batches(id, source_file, shop_code, grade,
               row_count, skipped_count, imported_at)
products(id, shop_id FK, sku, grade, title, price,
         regular_price, url, stock, sell_type,
         image_url, batch_id FK, imported_at,
         UNIQUE (shop_id, sku, grade))              -- the upsert key
```

- **Identity is the 13-digit JAN barcode** (`sku`), extracted from the product title for Animes-Pro
  and supplied directly by Hobbyland's API.
- The group key is `(grade, sku)`, **not** `sku` alone: the same JAN appearing in both an HG and an
  MG listing stays two separate comparison rows, because they are different kits at different price
  points.
- Indexes on `sku` and `grade` back the comparison query.
- Rows without a JAN (e.g. non-Gunpla figures in Animes-Pro's MG collection) are skipped at import —
  they can never match across shops, so storing them would only add noise. 103 of 246 rows in
  `animes-pro_mg.csv` fall into this category.

### 4.4 Import semantics

```
absent → imported (batch N) → re-imported (batch N+1): price / url / stock overwritten
```

`import_batches` is append-only; it is an audit trail, not a cache. One file = one batch = one
transaction, so a failure mid-file rolls back completely with no partial rows and no batch record.

**One field is exempt from overwrite:**

```sql
image_url = COALESCE(excluded.image_url, products.image_url)
```

The importer sweeps *every* matching CSV in its directory, but the scraper may only have regenerated
some of them. A CSV that predates the `image_url` column parses that field as `null`, so a plain
overwrite would null out thumbnails that are already on file — a partial scrape of one grade
silently wiped a whole grade's images. `COALESCE` makes re-import non-destructive for images while
leaving price and stock to refresh normally.

A shop delisting a product does **not** delete the row; the last known price persists.

### 4.5 Frontend state boundaries

| Concern | Owner | Transport |
|---|---|---|
| Grade, search text | `DashboardPage` | **Server-side** (`?grade=`, `?q=`) — refetches |
| Last-update readout | `useImportFreshness` | **Server-side** (`?grade=`) — refetches with the grade |
| Shop filter, column sort | `DashboardPage` / `useComparisonSort` | **Client-side** — no extra round trip |
| Faction theme | `useFaction` | `localStorage` → `<html data-faction>` |

One `GET /api/comparisons?grade=&q=` response (≤ 280 rows) feeds sorting and filtering, so those
interactions are instant and never re-hit the network.

A shop that does not carry a SKU has no price to rank, so it **always sorts last in both
directions** — flipping a descending sort should not suddenly pile all the "not sold here" cells at
the top.

### 4.6 Theme

A single global faction theme, switched in the header:

| Faction | Accent | Highlight |
|---|---|---|
| 聯邦 Federation | `#58a6e8` | `#f0c343` |
| 自護 Zeon | `#d9483b` | `#e6e1d7` |

Implemented as CSS custom properties scoped to `html[data-faction=…]`. An inline bootstrap in
`index.html` applies the stored value **before first paint** so the accent never flashes the wrong
faction; `useFaction` owns it thereafter.

The shops are deliberately **not** faction-coloured — they are separated by neutral value only
(`--shop-a` bright, `--shop-b` dim, `--shop-c` between). Painting one shop red and one blue would
imply an allegiance the data does not have; the faction is a skin, not a claim. A new shop needs a
`--shop-*` token plus its two rules; CSS has no compiler, so omitting them fails silently rather
than loudly.

Two CSS details that are load-bearing rather than cosmetic:

- `border-collapse: separate; border-spacing: 0` — collapsing borders are unreliable on a
  `position: sticky` cell in some engines, and the header must stay pinned.
- The sticky `th` fill is opaque and its bottom rule is an `inset box-shadow`, or rows scroll
  visibly through the header.

---

## 5. Quickstart

```bash
corepack enable
pnpm install
pnpm build          # type-check + build both packages
pnpm test           # backend 34 + frontend 47
pnpm dev            # backend :8080 (tsx watch) + frontend :5173 (vite, /api proxied)
```

> **The database is not committed.** `data/` is gitignored, so a fresh clone starts empty and the
> dashboard will read「冇資料 — 請先匯入 CSV」until you import (see [§6](#6-data-pipeline)).

Production-style run (backend serves the built SPA):

```bash
pnpm build && pnpm start        # http://localhost:8080
```

---

## 6. Data pipeline

```mermaid
flowchart LR
    CRON["cron 06:00"] --> SC["hobbyland_scraper.py"]
    SC -->|"HTTP API"| HL["Hobbyland Vue SPA backend"]
    SC -->|"Playwright + Chromium"| AP["Animes-Pro (Shopify)"]
    SC -->|"Playwright, fresh context per page"| HD["HobbyDigi (Magento + Cloudflare)"]
    HL --> CSV[("9 CSV files")]
    AP --> CSV
    HD --> CSV
    CSV -->|"pnpm import:csv"| DB[("SQLite")]
    DB --> UI["Dashboard :8080"]
```

The scraper lives in this repository at `scripts/hobbyland_scraper.py` and runs from
`scripts/venv`, which has its own dependency profile (Playwright plus a Chromium download):

- **Hobbyland** is a Vue SPA whose category pages ship an empty HTML shell, so the scraper POSTs to
  the shop's own JSON API (`backend.hobbylandeshop.com/api/products`) and walks `total_pages`.
  Image paths come back relative to the static CDN and are absolutised before writing.
- **Animes-Pro** sits behind Shopify bot protection — collection pages 302 to a
  `__shopify_bv_challenge` URL and `/products.json` hard-429s scripted clients. A real Chromium
  solves the challenge, then listing pages are walked and product cards read from the DOM
  (handling lazy-load `data-src` / `srcset`, protocol-relative `//`, and `{width}` templates).
- **HobbyDigi** is Magento 2 behind Cloudflare. See below.

CSV contract (UTF-8 BOM):

```
title,price,url,regular_price,sku,stock,sell_type,image_url
```

Import:

```bash
pnpm import:csv                                        # every matching CSV in CSV_DIR
pnpm import:csv -- --dir /path/to/csvs                 # explicit folder
pnpm import:csv -- --file /path/to/hobbyland_hg.csv    # single file
```

`CSV_DIR` or `--dir` / `--file` is **required**; with none of them the CLI exits 1 with an
actionable error rather than guessing a location. Filenames must match
`<shop>_<grade>.csv` for a shop in `SHOP_CODES` and a grade in `GRADES` — the pattern is derived
from those constants, so adding a shop needs no second edit. The shop and grade are taken from the
filename.

> `pnpm import:csv` delegates through `pnpm --filter backend`, so the process CWD is `backend/`.
> Pass an **absolute** `--dir`; a relative one resolves against `backend/` and fails with `ENOENT`.

Scrape-and-import in one step:

```bash
pnpm scrape                                  # host mode, all categories
scripts/scrape-and-import.sh rg hg           # selected categories only
scripts/scrape-and-import.sh hd              # hobbydigi (needs DEEPSEEK_API_KEY)
scripts/scrape-and-import.sh --docker        # import into the running container
```

### HobbyDigi matching

HobbyDigi is the reason this project has a human-in-the-loop step, and the numbers behind that
decision are worth recording because each was measured rather than assumed.

**The crawl is solved.** Cloudflare budgets roughly two or three requests per cookie jar, and the
budget does *not* recover with time (retested at +60 s and +120 s, still 403). A **fresh browser
context per page** gets a fresh budget: 28 pages / 784 cards with zero blocks, where a single reused
context died on page 3. Same-origin `fetch()` from an already-cleared page also works.

**The identity problem is not.** Only ~6% of listings carry a JAN as the Magento URL key.
`/graphql` 404s, `/rest/V1/products` 403s, product detail pages never clear the challenge, and the
`"sku"` strings in the listing HTML are Knockout autocomplete template noise.

Asking an LLM for the barcode does not work — measured **0 correct out of 44 ground-truth trials**.
`deepseek-chat` scored 0/20 twice on titles whose JAN was known, and `deepseek-reasoner` fabricated
even when explicitly offered "answer NONE". The inventions mimic genuine Bandai prefixes, and an
EAN-13 check digit is *not* a safety net: across two identical calls the share of fabrications
passing it went from 11/20 to 1/20, so output is non-deterministic even at temperature 0.

Matching on product names caps out at **~92% precision** (201 labeled cross-shop pairs):

| method | precision | recall |
|---|---|---|
| model-code exact match | **97.0%** | 31.8% |
| LLM-extracted attribute tuple | 89.5% | 42.3% |
| cascade: code → attribute | 91.6% | 59.7% |
| LLM pick from pre-filtered candidates | 86.8% | 91.7% of answerable |
| CJK-bigram similarity alone | ~85% | ~30% |

The ceiling is not an algorithm failure — it is genuine ambiguity. Eight of 368
`(grade, suit, variant)` keys in the catalogue map to more than one distinct SKU (re-releases,
P-Bandai versus retail), and dual transliterations exist (`麥拉薩` and `梅薩拉` are both Messala).
The errors are the dangerous kind: `泰坦斯配色` versus `奧干配色` are different colourways of the
same mobile suit, and a false match yields a confidently wrong「最平」badge.

So the pipeline accepts a JAN only from three sources, in order of trust:

1. **The shop's own URL key** — authoritative, ~6% of listings.
2. **A human-confirmed match** — `scripts/review_matches.py` proposes, a person decides once, and
   the decision is cached by product URL so later runs are deterministic and free.
3. **A model-code match** against the trusted catalogue (`jan_lookup.py`, threshold 0.72, which
   arithmetically requires a shared mech designation — 94% recall at 100% precision on labeled
   pairs).

Everything else is left for review. Two guards make the residue safe:

- **Variant collision.** If two differently-titled cards resolve to one `(grade, sku)`, *both* are
  blanked and returned to the review queue. Without this, two GP02A kits (an MLRS and a Psalis)
  matched the catalogue's single GP02A row and the `UNIQUE (shop_id, sku, grade)` index silently
  swallowed one.
- **No circular matching.** HobbyDigi's own rows are excluded from the catalogue
  (`exclude_shops=`), because its JANs are *derived* by this matcher — offering them back would let
  a wrong answer confirm itself on the next run.

```bash
scripts/venv/bin/python scripts/review_matches.py --list     # what is pending, no API calls
scripts/venv/bin/python scripts/review_matches.py            # review; y / 0-9 / n / s / q
```

DeepSeek *is* used for one thing it is genuinely good at: **grade classification**, because that is
recognition rather than recall. It graded 519 of 784 cards into hg/mg/rg and correctly rejected
265 PG / SD / EG / 1:100 kits. MGSD folds into `mg` by product decision.

---

## 7. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | HTTP listen port |
| `DATA_DIR` | `<repo>/data` | SQLite directory (`/data` inside Docker) |
| `NODE_ENV` | `development` | Express mode |
| `CSV_DIR` | *(none)* | Default `--dir` for the import CLI |
| `LOG_LEVEL` | `info` | pino level |
| `DEEPSEEK_API_KEY` | *(none)* | Scraper-only: classifies grade for the `hd` (hobbydigi.com) category and powers `review_matches.py`. The backend never reads it. |

Copy `.env.example` to `.env` and adjust. SQLite is embedded, so there is no connection pool to
tune. `createDatabase()` sets `PRAGMA journal_mode = WAL` (reads continue during an import) and
`PRAGMA foreign_keys = ON`.

---

## 8. API

All responses use one envelope:

```jsonc
// success
{ "code": 0, "message": "ok", "data": <T>, "timestamp": "<ISO-8601>" }
// error — also returned as the x-trace-id response header
{ "code": <httpStatus>, "message": "<reason>", "data": null, "timestamp": "<ISO>", "traceId": "<id>" }
```

| Method | Path | Query / Body | `data` |
|---|---|---|---|
| `GET` | `/api/comparisons` | `grade?=hg\|mg\|rg`, `q?=text`, `cheaper?=hobbyland\|animes-pro` | `ComparisonRow[]` |
| `GET` | `/api/products` | `shop?`, `grade?`, `q?` | `ProductRow[]` |
| `GET` | `/api/imports/freshness` | `grade?=hg\|mg\|rg` | `ImportFreshness` |
| `GET` | `/api/imports` | — | latest 20 `ImportBatchDto[]` |
| `POST` | `/api/import` | multipart `file` (CSV) + fields `shop`, `grade` | `{ batchId, rowCount, skipped }` (201) |

```ts
ImportFreshness = {
  grade: 'hg' | 'mg' | 'rg' | null,        // null when unscoped
  overall: string | null,                  // ISO-8601, latest across every shop
  byShop: Record<ShopCode, string | null>, // one key per SHOP_CODES entry
}
```

Freshness is `MAX(products.imported_at)` grouped by shop, scoped to `grade` when given. It is
derived from the product rows rather than from `import_batches` so that it reflects what is actually
on screen for that grade — a shop that has never been scraped for RG reports `null` instead of
inheriting an HG timestamp. Declared before `/api/imports` in the router; the two paths do not
overlap, but the specific route is listed first for readability.

Query params are validated with zod; an invalid `grade` is a `400` with field-level messages and a
`traceId`. Uploads: zero valid rows → `422`, malformed CSV → `400`.

Any non-`/api/*` path falls through to `frontend/dist/index.html` when that directory exists, so
the SPA routes work in production.

---

## 9. Docker

```bash
scripts/docker-build.sh              # tags :latest and :<timestamp>
scripts/docker-deploy.sh             # recreate + health-check
scripts/docker-deploy.sh --build     # rebuild the image first
scripts/docker-deploy.sh --import    # also import CSVs inside the container
```

The deploy script is defensive about two failure modes that both occurred in practice:

1. **The daemon is not running** — it detects an unresponsive daemon and starts Docker Desktop /
   OrbStack on macOS (or the `docker` service via `systemctl` on Linux), then waits for readiness.
2. **A stale container holds the port** — it runs `docker compose down --remove-orphans`, then
   removes any leftover container squatting the compose-generated name (a container started outside
   this compose project will not be reclaimed by `down` alone), then `up -d --force-recreate`.
   Without this, an old image keeps serving an outdated API contract on `:8080` and the health check
   passes anyway.

Image: multi-stage `node:24-slim` — stage 1 builds both packages, stage 2 installs backend
production deps only and copies `backend/dist`, `backend/drizzle`, `frontend/dist`. Schema migration
runs on boot and is idempotent.

Volumes: `./data:/data` persists the database; `${CSV_DIR:-./data}:/csvs:ro` exposes CSVs for
in-container import.

---

## 10. Testing

```bash
pnpm test        # backend 34/34 · frontend 47/47
```

| Suite | Environment | Covers |
|---|---|---|
| `comparison.service.test.ts` | node | Verdict computation: cheaper + saving, tie, single-shop, `exclusiveShop`, grade separation, SKU ordering, deterministic group title, and N-way offers (runner-up saving, bottom-two tie, three-way tie) |
| `import.service.test.ts` | node + in-memory SQLite | CSV parsing, validation/skip rules, batch records, upsert idempotency, `image_url` mapping and **preservation**, `buildFreshness` (per-shop, latest-overall, absent shop → null, shop outside `SHOP_CODES` still counted) |
| `api.test.ts` | node + supertest | All five endpoints, status codes, `traceId` on validation failure, freshness scoping by grade and the unscoped case |
| `components.test.tsx` | jsdom + RTL | Badge wording (including that an exclusive SKU never renders「最平」), preview image and its error fallback, pre-order flag, `FreshnessBar` states (every shop listed, one or more missing, no history, loading, failed), tabs, search |
| `sort-filter.test.tsx` | jsdom + RTL | Sort hook (ordering, nulls-last, non-mutation), `aria-sort`, shop filter (option count derived from `SHOP_CODES.length + 1`), filtered counts, filter-specific empty state |
| `faction.test.tsx` | jsdom + RTL | Theme default, persistence across mounts, `<html data-faction>` mirroring, unknown-value fallback |
| `dashboard.test.tsx` | jsdom + RTL | API client unwrapping and `ApiError`, query-string building, refetch on grade change, the freshness request is grade-scoped and its timestamps render on the page, error surfacing |

The database is a **fresh in-memory SQLite per test** — SQL runs for real rather than being mocked
away. `fetch` is stubbed per test and React Query retries are disabled.

`frontend/tests/setup.ts` installs an in-memory `Storage` shim: Node ≥ 22 exposes an experimental
`localStorage` global that yields `undefined` without `--localstorage-file`, and it shadows the
Storage jsdom would otherwise provide.

Full matrix and manual-verification log: [`docs/TESTING.md`](docs/TESTING.md).

---

## 11. Project layout

```
backend/
  drizzle/0000_init.sql           schema (executed idempotently on boot)
  src/
    index.ts                      bootstrap: config → db → listen
    app.ts                        express wiring + SPA static serving
    config.ts                     zod-validated env
    routes/                       /api router + multer upload
    controllers/                  product · import
    services/                     comparison (pure) · import
    repositories/                 ProductRepository — the only SQL
    middleware/                   traceId · notFound · error
    cli/import.ts                 bulk CSV importer
    utils/                        logger (pino) · AppError
    types/index.ts                DTO contracts
  tests/
frontend/
  index.html                      pre-paint faction bootstrap
  src/
    App.tsx                       shell + page switch + theme owner
    pages/                        DashboardPage · ImportPage
    components/                   ComparisonTable · CheaperBadge · ShopFilter · FreshnessBar ·
                                  GradeTabs · SearchBar · FactionToggle · FactionCrest
    hooks/                        useComparisons · useComparisonSort · useFaction ·
                                  useImportFreshness
    api/                          client · comparison.api · import.api
    types/index.ts                mirrors backend DTOs (+ frontend-only types)
    styles/                       dark mobile-suit HUD theme (tokens, layout, motion), mobile-first
  tests/
scripts/                          docker-build · docker-deploy · scrape-and-import
docs/                             see below
data/                             SQLite (gitignored)
```

---

## 12. Documentation

| Document | Contents |
|---|---|
| [`docs/PROGRAM_SPEC.md`](docs/PROGRAM_SPEC.md) | File map, dependency graph, API contracts, dashboard interaction contract |
| [`docs/FUNCTION_SPEC.md`](docs/FUNCTION_SPEC.md) | Business flow, validation rules, comparison semantics, state transitions, boundary conditions, theme |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Mermaid: request sequences, class hierarchy, ER diagram, deployment topology |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Runtime requirements, env vars, local dev, Docker, cron chaining |
| [`docs/TESTING.md`](docs/TESTING.md) | Unit suites, integration matrix, manual-verification log, known caveats |
| [`AGENT.md`](AGENT.md) | Original project objective and intended flow |

---

## 13. Known limitations

- **`?cheaper=` includes exclusive listings.** The filter matches on `cheapestShop`, which is also
  set for single-shop SKUs — so `cheaper=hobbyland` on HG returns 200 rows, of which only 59 are
  genuine price wins and 141 are "only Hobbyland stocks it". Preserved deliberately to keep the API
  stable when `exclusiveShop` was added. No UI surface currently exposes the filter; if one ever
  does, decide first whether it should exclude `exclusiveShop != null`.
- **Stock does not affect the verdict.** A pre-order (預訂) offer is compared at face value against
  an in-stock offer. It is flagged visually but not ranked differently.
- **Delisted products persist.** A shop removing a listing does not delete the row, so a stale price
  can survive until the next scrape overwrites it. Full-replacement semantics are not implemented.
- **The scraper is external.** Reproducing the pipeline end to end requires the separate
  `hobbyland_scraper.py` plus its Python `venv` and Playwright Chromium install. Both shops'
  selectors and endpoints can break without notice.
- **No CI.** Tests are run locally; nothing enforces them on push.
