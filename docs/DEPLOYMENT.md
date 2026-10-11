<!-- docs/DEPLOYMENT.md -->
# Infrastructure & Deployment

## 1. Runtime Requirements

| Component | Requirement |
|---|---|
| Node.js | ≥ 22.13 (`node:sqlite` builtin; Docker uses node:24-slim) |
| pnpm | 11 (via `corepack enable`) |
| Database | SQLite file (embedded, no server) at `<DATA_DIR>/hobbyland.db` (WAL mode) |
| Browser | Any modern browser |

## 2. Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | HTTP listen port |
| `DATA_DIR` | `<repo>/data` | SQLite directory (absolute in Docker: `/data`) |
| `NODE_ENV` | `development` | Express mode |
| `CSV_DIR` | scraper dir | Default `--dir` for the import CLI |
| `LOG_LEVEL` | `info` | pino level |

SQLite is embedded; connection pooling (HikariCP-style) is not applicable. WAL mode allows
concurrent reads during imports.

## 3. Local Development

```bash
corepack enable
pnpm install
pnpm dev          # backend :8080 (tsx watch) + frontend :5173 (vite, /api proxied)
pnpm build        # type-check + build both packages
pnpm test         # vitest (backend + frontend)
pnpm start        # run built backend (serves frontend/dist)
```

## 4. Data Import

```bash
# all 6 CSVs from the scraper folder (default --dir)
pnpm import:csv

# explicit folder / single file
pnpm import:csv -- --dir /path/to/csvs
pnpm import:csv -- --file /path/to/hobbyland_hg.csv
```

## 5. Docker

Helper scripts (also exposed as pnpm shortcuts):

```bash
scripts/docker-build.sh                 # build image, tags :latest + :<timestamp>
scripts/docker-deploy.sh                # compose up + health check
scripts/docker-deploy.sh --build        # rebuild image first
scripts/docker-deploy.sh --import       # also import CSVs inside the container
pnpm docker:build                       # same as scripts/docker-build.sh
pnpm docker:deploy                      # same as scripts/docker-deploy.sh
```

Manual equivalent:

```bash
docker build -t hobbyland-app .
docker compose up -d          # http://localhost:8080
```

- Multi-stage: stage 1 installs + builds frontend and backend; stage 2 installs backend prod
  deps only and copies `dist` + `drizzle/` + `frontend/dist`.
- Volume `./data:/data` persists the SQLite database.
- `CSV_DIR` (default `./data`) is mounted read-only at `/csvs` so the container can import:
  `CSV_DIR=~/github/python_program docker compose up -d` then
  `docker compose exec app node backend/dist/cli/import.js --dir /csvs`.
  `docker-deploy.sh --import` does both automatically.
- Schema migration runs automatically on container start (idempotent `CREATE TABLE IF NOT EXISTS`).

## 6. Cron Chaining (scraper → import)

`scripts/scrape-and-import.sh` runs the scraper (via the `venv` in `~/github/python_program`)
and then imports the fresh CSVs — host mode by default, container mode with `--docker`:

```bash
scripts/scrape-and-import.sh            # scrape all 6 categories, import on host
scripts/scrape-and-import.sh rg hg      # selected categories only
scripts/scrape-and-import.sh --docker   # scrape all, import into the running container
pnpm scrape                             # shortcut for the host-mode run
```

```cron
# scrape both shops, then refresh the comparison database
# cron runs the command through /bin/sh, so $HOME expands
0 6 * * *  $HOME/github/hobbyland/scripts/scrape-and-import.sh --docker \
  >> $HOME/github/python_program/cron.log 2>&1
```

Inside Docker, import via exec (container has prod deps only, so run the compiled CLI with `node`):

```bash
CSV_DIR=~/github/python_program docker compose up -d
docker compose exec app node backend/dist/cli/import.js --dir /csvs
```

Or upload any CSV through the dashboard「匯入」page (`POST /api/import`).
