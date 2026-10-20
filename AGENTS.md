# Repository Guidelines

Gunpla HK price-comparison dashboard: pnpm workspace (`backend` Express + `frontend` React/Vite, `mobile` Capacitor shell), embedded SQLite, no ORM. Read `README.md` for design rationale and `docs/` for specs; this file covers only what an agent would otherwise get wrong.

## Commands

- Node **>= 22.13** (uses builtin `node:sqlite` — never add better-sqlite3), pnpm 11 (`corepack enable`).
- `pnpm dev` — tsx watch :8089 + vite :5173 (`/api` proxied). `pnpm build`, `pnpm test` (vitest, both packages).
- Single test: `pnpm --filter backend run test comparison.service.test` / `pnpm --filter frontend run test sort-filter`.
- CSV import: `pnpm import:csv -- --file /abs/path/hobbyland_hg.csv`. **Delegates through `pnpm --filter backend`, so the CWD is `backend/` — always pass absolute `--file`/`--dir`.** `CSV_DIR` or a flag is required.
- Scraper runs from `scripts/venv` (Python + Playwright Chromium) — **not** installed by `pnpm install`. `scripts/scrape-and-import.sh <shop…>`; `hd` (HobbyDigi) needs `DEEPSEEK_API_KEY` and its crawl is disabled by default.
- `scripts/docker-deploy.sh [--build|--import]` — recreate + health-check; it starts the Docker daemon if down and removes stale containers holding :8089.

## Gotchas

- `data/` (SQLite, CSVs, `hobbydigi_state.json`) is gitignored. Fresh clones show 「冇資料」 until CSVs are imported. `hobbydigi_state.json` is a Cloudflare clearance credential — keep `data/` out of git.
- tsconfig is `strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` in every package — array indexing returns `T | undefined`, and object literals cannot assign `undefined` to optional props (`exactOptionalPropertyTypes` violations are the most common build break from DTO construction).
- No lint, formatter, or CI exists — verification is `pnpm build && pnpm test`.
- `enhancement*.md` (gitignored) are past work prompts, not specs; `AGENT.md` is the original objective.

## Architecture

- Strict layering: routes → controllers (zod validation, status codes) → services → repositories. **Repositories are the only hand-written SQL.** Schema: `backend/drizzle/0000_init.sql`, executed idempotently on boot (migrations are not incremental).
- Core logic: `comparison.service.buildComparisons()` is a pure function. The **verdict contract** (README §4.2): the grid group key is `(grade, sku)`, never `sku` alone; `exclusiveShop` is set iff `offers.length === 1`; UI code branches on `exclusiveShop` **before** `cheapestShop`.
- Import semantics: upsert key `UNIQUE(shop_id, sku, grade)`; `image_url` is never overwritten (`COALESCE`); a delisted product's row persists. `pbandai_items` is the exception — whole-table replace per import.
- Adding a shop touches several places: `SHOP_CODES` (`backend/src/types/index.ts`), `<shop>_<grade>.csv` filename convention, and a `--shop-*` CSS token in `frontend/src/styles/` — CSS has no compiler, so a missing token fails silently.
- Matching rule: a kit may only get a JAN from its shop URL key, a human-confirmed match, or the trusted-catalogue matcher — and each shop's own derived rows must stay in `exclude_shops` of `jan_lookup.py` so a wrong match can never confirm itself.
- Frontend: React Query for server data only; everything else is `useState`. Faction theme is `html[data-faction]` CSS custom properties, set pre-paint by a bootstrap in `frontend/index.html`.

## Deploy & domains

- Docker-compose `caddy` reverse-proxies `https://jackstudio.app` → `app:8089` and `https://board.jackstudio.app` → `hk-weather-app:59001` (the separate `hk-live-dashboard` repo's stack, reached via the external `shared-proxy` docker network); the app itself uses a self-signed cert (health check uses `curl -k`). `DOMAIN` is a compose env var. The `shared-proxy` network must pre-exist (`docker network create shared-proxy`) or `docker compose up` fails.

## Commit style

Single-line imperative summaries ("Add …", "Fix …"); no conventional-commit prefixes. Tests are not enforced anywhere — run them yourself.
