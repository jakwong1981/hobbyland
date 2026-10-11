#!/usr/bin/env bash
# scripts/scrape-and-import.sh — run the gunpla scraper, then import its CSVs into the database
#
# Usage:
#   scripts/scrape-and-import.sh                # scrape all categories, import on the host
#   scripts/scrape-and-import.sh rg hg          # scrape selected categories only
#   scripts/scrape-and-import.sh --docker       # import into the running container instead
#   scripts/scrape-and-import.sh --docker rg    # both
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRAPER_DIR="${SCRAPER_DIR:-$HOME/github/python_program}"
PY="${SCRAPER_DIR}/venv/bin/python"

DOCKER=0
CATEGORIES=()
for arg in "$@"; do
  case "$arg" in
    --docker) DOCKER=1 ;;
    *)        CATEGORIES+=("$arg") ;;
  esac
done

if [ ! -x "$PY" ]; then
  echo "venv not found at ${PY} — create it with: cd ${SCRAPER_DIR} && python3 -m venv venv" >&2
  exit 1
fi

echo "==> Scraping ${CATEGORIES[*]:-all categories} (this can take several minutes for animes-pro)"
cd "$SCRAPER_DIR"
"$PY" hobbyland_scraper.py ${CATEGORIES[@]+"${CATEGORIES[@]}"}

if [ "$DOCKER" -eq 1 ]; then
  echo "==> Importing into the Docker container"
  cd "$REPO_ROOT"
  CSV_DIR="$SCRAPER_DIR" scripts/docker-deploy.sh --import
else
  echo "==> Importing into the local database"
  cd "$REPO_ROOT"
  pnpm import:csv -- --dir "$SCRAPER_DIR"
fi

echo "==> Scrape + import finished"
