#!/usr/bin/env bash
# scripts/scrape-and-import.sh — run the gunpla scraper, then import its CSVs into the database
#
# Usage:
#   scripts/scrape-and-import.sh                # scrape all categories, import on the host
#   scripts/scrape-and-import.sh rg hg          # scrape selected categories only
#   scripts/scrape-and-import.sh --docker       # import into the running container instead
#   scripts/scrape-and-import.sh --docker rg    # both
#   scripts/scrape-and-import.sh --skip-series  # skip Gundam series classification
#
# The scraper runs with CSV_DIR as its working directory and writes its fixed-name
# CSVs there, so the import step reads back exactly what this run produced.
# Between the two, enrich_series.py classifies every product title into its
# Gundam series (cached in data/series_cache.json) and adds a `series` column.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PY="${PYTHON:-$SCRIPT_DIR/venv/bin/python}"
CSV_OUT_DIR="${CSV_DIR:-$REPO_ROOT/data}"

DOCKER=0
SKIP_SERIES="${SKIP_SERIES:-0}"
CATEGORIES=()
for arg in "$@"; do
  case "$arg" in
    --docker) DOCKER=1 ;;
    --skip-series) SKIP_SERIES=1 ;;
    *)        CATEGORIES+=("$arg") ;;
  esac
done

if [ ! -x "$PY" ]; then
  echo "venv not found at ${PY} — create it with:" >&2
  echo "  python3 -m venv ${SCRIPT_DIR}/venv" >&2
  echo "  ${SCRIPT_DIR}/venv/bin/pip install playwright" >&2
  echo "  ${SCRIPT_DIR}/venv/bin/playwright install chromium   # needed for the ap_*, hd and tm categories" >&2
  exit 1
fi

echo "==> Scraping ${CATEGORIES[*]:-all categories} (this can take several minutes for animes-pro)"
mkdir -p "$CSV_OUT_DIR"
cd "$CSV_OUT_DIR"
"$PY" "$SCRIPT_DIR/hobbyland_scraper.py" ${CATEGORIES[@]+"${CATEGORIES[@]}"}

cd "$REPO_ROOT"
if [ "$SKIP_SERIES" -eq 1 ]; then
  echo "==> Skipping series classification (--skip-series)"
else
  echo "==> Classifying Gundam series (needs JEV_API_KEY or DEEPSEEK_API_KEY; cached runs are free)"
  "$PY" "$SCRIPT_DIR/enrich_series.py" --dir "$CSV_OUT_DIR" \
    --cache "$CSV_OUT_DIR/series_cache.json" \
    ${SERIES_ENGINE:+--engine "$SERIES_ENGINE"}

  # enrich_series.py exits 0 even when it classified nothing (it falls back to
  # cache-only enrichment so a scrape never dies on classification), so count the
  # series values that actually reached the CSVs. Importing a batch with none
  # would leave every new product NULL and the dashboard 100% 未分類.
  FILLED=$("$PY" -c '
import csv, os, re, sys
pattern = re.compile(r"^(hobbyland|animes-pro|hobbydigi|fookle|twinnermodel)_(hg|mg|rg)\.csv$")
filled = 0
for name in sorted(os.listdir(sys.argv[1])):
    if not pattern.match(name):
        continue
    with open(os.path.join(sys.argv[1], name), newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            filled += bool((row.get("series") or "").strip())
print(filled)
' "$CSV_OUT_DIR")
  echo "==> Series coverage: ${FILLED} CSV rows classified"
  if [ "$FILLED" -eq 0 ]; then
    echo "❌ No CSV row carries a series value — refusing to import an unclassified batch." >&2
    echo "   Check JEV_API_KEY / DEEPSEEK_API_KEY and re-run, or pass --skip-series to" >&2
    echo "   import prices only and keep the series values already in the database." >&2
    exit 1
  fi
fi

if [ "$DOCKER" -eq 1 ]; then
  echo "==> Importing into the Docker container"
  CSV_DIR="$CSV_OUT_DIR" scripts/docker-deploy.sh --import
elif [ -f backend/src/cli/import.ts ] && command -v pnpm >/dev/null 2>&1; then
  echo "==> Importing into the local database"
  pnpm import:csv -- --dir "$CSV_OUT_DIR"
else
  # Inside the runtime container there is no pnpm/source tree — only the
  # compiled backend under /app/backend/dist (see Dockerfile).
  echo "==> Importing into the local database (compiled CLI)"
  node backend/dist/cli/import.js --dir "$CSV_OUT_DIR"
fi

echo "==> Scrape + import finished"
