#!/usr/bin/env python3
"""
Add a `series` column to the scraper's product CSVs.

Reads every `<shop>_<grade>.csv` in a directory (default `data/`), classifies
each distinct product title into one of the Gundam series ids defined by
`jev_series.py`, and rewrites the CSVs in place with the new column. The
classification is cached in `data/series_cache.json` — Jev bills per input
token, so only genuinely new titles hit the API, and re-runs are free.

Titles that cannot be classified (API failure, no key) get an empty `series`,
which the backend imports as NULL; failures are never cached, so the next run
retries them.

Usage:
  python3 scripts/enrich_series.py                    # enrich data/*.csv
  python3 scripts/enrich_series.py --dir build/csv
  python3 scripts/enrich_series.py --engine deepseek
  python3 scripts/enrich_series.py data/hobbyland_hg.csv

Keys are loaded exactly as in jev_series.py: JEV_API_KEY / DEEPSEEK_API_KEY
from the environment or the repository .env.
"""

import csv
import json
import os
import re
import sys
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import jev_series

REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_CSV_DIR = os.path.join(REPO_ROOT, "data")
DEFAULT_CACHE = os.path.join(DEFAULT_CSV_DIR, "series_cache.json")

FILE_PATTERN = re.compile(
    r"^(hobbyland|animes-pro|hobbydigi|fookle|twinnermodel)_(hg|mg|rg)\.csv$")

FIELDNAMES = ["title", "price", "url", "regular_price", "sku", "stock",
              "sell_type", "image_url", "series"]


class SeriesCache:
    """title -> series id, persisted so repeated runs stay free and stable."""

    def __init__(self, path=DEFAULT_CACHE):
        self.path = path
        self.entries = {}
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(loaded, dict):
            self.entries = loaded

    def get(self, title):
        value = self.entries.get(title)
        return value if isinstance(value, str) else None

    def put(self, title, series_id):
        self.entries[title] = series_id

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=1,
                          sort_keys=True)
        except OSError as exc:
            print(f"   ⚠️  could not write cache {self.path}: {exc}")


def resolve_files(args_files, csv_dir):
    """Explicit file arguments, else every product CSV in csv_dir."""
    if args_files:
        return list(args_files)
    try:
        names = sorted(os.listdir(csv_dir))
    except OSError as exc:
        print(f"❌ cannot read {csv_dir}: {exc}", file=sys.stderr)
        return []
    return [os.path.join(csv_dir, name) for name in names
            if FILE_PATTERN.match(name)]


def read_rows(path):
    """(fieldnames, rows) of one product CSV, or None when unreadable."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            return reader.fieldnames or [], rows
    except OSError as exc:
        print(f"   ⚠️  cannot read {path}: {exc}", file=sys.stderr)
        return None


def write_rows(path, rows):
    """Rewrite one CSV with the enriched fieldnames."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def decide(title, engine, jev_key, deepseek_key):
    """One title -> series id, honouring the --engine routing of jev_series."""
    if engine == "deepseek":
        return jev_series.classify_deepseek(title, deepseek_key)["series"]
    try:
        return jev_series.classify(title, jev_key)["series"]
    except jev_series.AuthError:
        if engine != "auto" or not deepseek_key:
            raise
        print(f"   ⚠️  Jev key rejected — falling back to DeepSeek",
              file=sys.stderr)
        return jev_series.classify_deepseek(title, deepseek_key)["series"]
    except urllib.error.HTTPError as exc:
        if engine != "auto" or exc.code != 402 or not deepseek_key:
            raise
        print("   ⚠️  Not enough OpenRouter credits (HTTP 402) — "
              "falling back to DeepSeek", file=sys.stderr)
        return jev_series.classify_deepseek(title, deepseek_key)["series"]


def classify_pending(titles, engine, cache):
    """Classify every uncached title; returns (classified, failed) counts.

    A dead key (AuthError) fails every remaining title, so it aborts the loop
    instead of burning one request per title.
    """
    if engine == "deepseek":
        jev_key, deepseek_key = "", jev_series.load_deepseek_key()
    else:
        jev_key = jev_series.load_api_key()
        deepseek_key = jev_series._optional_deepseek_key()

    classified = 0
    failed = 0
    for index, title in enumerate(titles, start=1):
        try:
            series_id = decide(title, engine, jev_key, deepseek_key)
        except jev_series.AuthError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return classified, failed + len(titles) - index + 1
        except (urllib.error.HTTPError, OSError, RuntimeError,
                ValueError) as exc:
            print(f"   ⚠️  {title}: {exc}", file=sys.stderr)
            failed += 1
            continue
        cache.put(title, series_id)
        classified += 1
        print(f"   [{index}/{len(titles)}] {title} → {series_id}")
    return classified, failed


def enrich(files, engine, cache):
    """Add/refresh the series column of every CSV. Returns an exit code."""
    loaded = []
    all_titles = []
    for path in files:
        result = read_rows(path)
        if result is None:
            continue
        _fieldnames, rows = result
        loaded.append((path, rows))
        for row in rows:
            title = (row.get("title") or "").strip()
            if title and cache.get(title) is None and title not in all_titles:
                all_titles.append(title)

    if not loaded:
        print("❌ no readable product CSVs found", file=sys.stderr)
        return 1

    cached = sum(1 for path, rows in loaded for row in rows
                 if cache.get((row.get("title") or "").strip()) is not None)
    classified = failed = 0
    if all_titles:
        print(f"==> classifying {len(all_titles)} new titles "
              f"({cached} rows served from cache)")
        try:
            classified, failed = classify_pending(all_titles, engine, cache)
        except jev_series.AuthError as exc:
            # No usable key: warn and fall through to cache-only enrichment so
            # the scrape pipeline never dies on classification.
            print(f"   ⚠️  {exc} — keeping cached series only", file=sys.stderr)
            failed = len(all_titles)
        cache.save()
    else:
        print(f"==> all titles cached ({cached} rows)")

    for path, rows in loaded:
        for row in rows:
            row["series"] = cache.get((row.get("title") or "").strip()) or ""
        write_rows(path, rows)
        print(f"   ✏️  {os.path.basename(path)}: {len(rows)} rows")

    print(f"==> enriched {len(loaded)} files: {classified} classified, "
          f"{cached} cached, {failed} failed")
    return 0


def parse_args(argv):
    files = []
    csv_dir = DEFAULT_CSV_DIR
    cache_path = DEFAULT_CACHE
    engine = "auto"
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--dir":
            if not rest:
                raise ValueError("--dir needs a path")
            csv_dir = rest.pop(0)
        elif arg == "--cache":
            if not rest:
                raise ValueError("--cache needs a path")
            cache_path = rest.pop(0)
        elif arg == "--engine":
            if not rest:
                raise ValueError("--engine needs auto, jev or deepseek")
            engine = rest.pop(0)
            if engine not in jev_series.ENGINES:
                raise ValueError(f"unknown engine {engine!r}")
        elif arg in ("-h", "--help"):
            raise ValueError("help")
        elif arg.startswith("-") and arg != "-":
            raise ValueError(f"unknown option {arg}")
        else:
            files.append(arg)
    return files, csv_dir, cache_path, engine


USAGE = __doc__


def main(argv):
    try:
        files, csv_dir, cache_path, engine = parse_args(argv)
    except ValueError as exc:
        if str(exc) != "help":
            print(f"❌ {exc}\n", file=sys.stderr)
        print(USAGE)
        return 2 if str(exc) != "help" else 0
    resolved = resolve_files(files, csv_dir)
    if not resolved:
        print(f"❌ no CSV files matched in {csv_dir}", file=sys.stderr)
        return 1
    return enrich(resolved, engine, SeriesCache(cache_path))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
