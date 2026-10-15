FROM node:24-slim AS build
RUN corepack enable
WORKDIR /app

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml tsconfig.base.json ./
COPY backend/package.json backend/
COPY frontend/package.json frontend/
RUN pnpm install --frozen-lockfile

COPY backend backend
COPY frontend frontend
RUN pnpm build

FROM node:24-slim AS runtime
RUN corepack enable
WORKDIR /app
ENV NODE_ENV=production \
    PORT=8080 \
    DATA_DIR=/data \
    CSV_DIR=/data \
    PYTHON=/opt/scraper-venv/bin/python \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Python + Playwright/Chromium so the backend-triggered scrape job can run
# scripts/scrape-and-import.sh inside the container (see ScrapeService).
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && python3 -m venv /opt/scraper-venv \
    && /opt/scraper-venv/bin/pip install --no-cache-dir playwright \
    && /opt/scraper-venv/bin/playwright install --with-deps chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY scripts/scrape-and-import.sh \
     scripts/hobbyland_scraper.py \
     scripts/enrich_series.py \
     scripts/jev_series.py \
     scripts/deepseek_resolve.py \
     scripts/jan_lookup.py \
     scripts/

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY backend/package.json backend/
RUN pnpm --filter backend install --prod --frozen-lockfile

COPY --from=build /app/backend/dist backend/dist
COPY --from=build /app/backend/drizzle backend/drizzle
COPY --from=build /app/frontend/dist frontend/dist

RUN chmod +x scripts/scrape-and-import.sh

# HobbyDigi's Cloudflare challenge can only be solved in a headed browser; the
# container has no X server, so force the headless fallback (cached cards).
# Declared last so earlier layers keep their build cache.
ENV HD_HEADLESS=1

EXPOSE 8080
VOLUME ["/data"]
CMD ["node", "backend/dist/index.js"]
