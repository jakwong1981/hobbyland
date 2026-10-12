#!/usr/bin/env bash
# scripts/scrape-and-import.sh — run the gunpla scraper, then import its CSVs into the database
#
# Usage:
#   scripts/scrape-and-import.sh                # scrape all categories, import on the host
#   scripts/scrape-and-import.sh rg hg          # scrape selected categories only
#   scripts/scrape-and-import.sh --docker       # import into the running container instead
#   scripts/scrape-and-import.sh --docker rg    # both
#
# The scraper runs with CSV_DIR as its working directory and writes its fixed-name
# CSVs there, so the import step reads back exactly what this run produced.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PY="${PYTHON:-$SCRIPT_DIR/venv/bin/python}"
CSV_OUT_DIR="${CSV_DIR:-$REPO_ROOT/data}"

DOCKER=0
CATEGORIES=()
for arg in "$@"; do
  case "$arg" in
    --docker) DOCKER=1 ;;
    *)        CATEGORIES+=("$arg") ;;
  esac
done

if [ ! -x "$PY" ]; then
  echo "venv not found at ${PY} — create it with:" >&2
  echo "  python3 -m venv ${SCRIPT_DIR}/venv" >&2
  echo "  ${SCRIPT_DIR}/venv/bin/pip install playwright" >&2
  echo "  ${SCRIPT_DIR}/venv/bin/playwright install chromium   # only needed for the ap_* categories" >&2
  exit 1
fi

echo "==> Scraping ${CATEGORIES[*]:-all categories} (this can take several minutes for animes-pro)"
mkdir -p "$CSV_OUT_DIR"
cd "$CSV_OUT_DIR"
"$PY" "$SCRIPT_DIR/hobbyland_scraper.py" ${CATEGORIES[@]+"${CATEGORIES[@]}"}

cd "$REPO_ROOT"
if [ "$DOCKER" -eq 1 ]; then
  echo "==> Importing into the Docker container"
  CSV_DIR="$CSV_OUT_DIR" scripts/docker-deploy.sh --import
else
  echo "==> Importing into the local database"
  pnpm import:csv -- --dir "$CSV_OUT_DIR"
fi

echo "==> Scrape + import finished"
