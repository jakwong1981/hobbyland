#!/usr/bin/env python3
"""Unit tests for scripts/enrich_series.py — stdlib unittest, no extra deps.

Run: scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
"""

import csv
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import enrich_series as es
import jev_series as jv

HEADER = ["title", "price", "url", "regular_price", "sku", "stock",
          "sell_type", "image_url"]


def write_csv(directory, name, rows):
    path = os.path.join(directory, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def row(title, sku="4573102000001"):
    return {"title": title, "price": "100", "url": f"https://x/{sku}",
            "regular_price": "120", "sku": sku, "stock": "1",
            "sell_type": "現貨", "image_url": ""}


class ResolveFilesTest(unittest.TestCase):
    def test_matches_only_product_csvs(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("hobbyland_hg.csv", "fookle_rg.csv", "notes.csv",
                         "hobbyland_pg.csv"):
                open(os.path.join(tmp, name), "w").close()
            resolved = es.resolve_files([], tmp)
            self.assertEqual([os.path.basename(p) for p in resolved],
                             ["fookle_rg.csv", "hobbyland_hg.csv"])

    def test_explicit_files_win(self):
        files = ["/tmp/a.csv"]
        self.assertEqual(es.resolve_files(files, "/tmp"), files)


class SeriesCacheTest(unittest.TestCase):
    def test_roundtrip_and_ignore_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cache.json")
            cache = es.SeriesCache(path)
            cache.put("title", "zeta")
            cache.save()
            self.assertEqual(es.SeriesCache(path).get("title"), "zeta")

            with open(path, "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertIsNone(es.SeriesCache(path).get("title"))


class EnrichTest(unittest.TestCase):
    def setUp(self):
        # Silence the progress printing; failures still surface through
        # returned counts and the rewritten CSVs.
        patcher = mock.patch("sys.stdout", new_callable=io.StringIO)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _classify(self, mapping):
        def fake_classify(title, api_key, model=jv.JEV_MODEL):
            if title not in mapping:
                raise RuntimeError(f"no answer for {title}")
            return {"input": title, "series": mapping[title],
                    "name": mapping[title]}
        return fake_classify

    def test_dedupes_titles_across_files_and_rewrites_with_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write_csv(tmp, "hobbyland_hg.csv", [row("Kit A"), row("Kit B", "2")])
            b = write_csv(tmp, "fookle_hg.csv", [row("Kit A")])
            cache = es.SeriesCache(os.path.join(tmp, "cache.json"))
            classify = mock.Mock(side_effect=self._classify(
                {"Kit A": "zeta", "Kit B": "seed"}))
            with mock.patch.object(jv, "classify", classify), \
                 mock.patch.object(jv, "load_api_key", return_value="k"), \
                 mock.patch.object(jv, "_optional_deepseek_key",
                                   return_value=""):
                code = es.enrich([a, b], "jev", cache)
            self.assertEqual(code, 0)
            self.assertEqual(classify.call_count, 2)  # Kit A asked only once

            fields, rows = read_csv(a)
            self.assertEqual(fields, es.FIELDNAMES)
            self.assertEqual([r["series"] for r in rows], ["zeta", "seed"])
            _fields, rows_b = read_csv(b)
            self.assertEqual(rows_b[0]["series"], "zeta")
            self.assertEqual(cache.get("Kit A"), "zeta")

    def test_cached_titles_skip_the_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_csv(tmp, "hobbyland_hg.csv", [row("Kit A")])
            cache = es.SeriesCache(os.path.join(tmp, "cache.json"))
            cache.put("Kit A", "unicorn")
            classify = mock.Mock()
            with mock.patch.object(jv, "classify", classify):
                code = es.enrich([path], "jev", cache)
            self.assertEqual(code, 0)
            classify.assert_not_called()
            self.assertEqual(read_csv(path)[1][0]["series"], "unicorn")

    def test_failure_leaves_series_empty_and_uncached(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_csv(tmp, "hobbyland_hg.csv", [row("Kit A")])
            cache_file = os.path.join(tmp, "cache.json")
            cache = es.SeriesCache(cache_file)
            with mock.patch.object(jv, "classify",
                                   mock.Mock(side_effect=RuntimeError("boom"))), \
                 mock.patch.object(jv, "load_api_key", return_value="k"), \
                 mock.patch.object(jv, "_optional_deepseek_key",
                                   return_value=""):
                code = es.enrich([path], "jev", cache)
            self.assertEqual(code, 0)
            self.assertEqual(read_csv(path)[1][0]["series"], "")
            with open(cache_file, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {})

    def test_auth_error_still_writes_empty_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_csv(tmp, "hobbyland_hg.csv", [row("Kit A")])
            cache = es.SeriesCache(os.path.join(tmp, "cache.json"))
            with mock.patch.object(jv, "classify",
                                   mock.Mock(side_effect=jv.AuthError("dead"))), \
                 mock.patch.object(jv, "load_api_key", return_value="k"), \
                 mock.patch.object(jv, "_optional_deepseek_key",
                                   return_value=""):
                code = es.enrich([path], "jev", cache)
            self.assertEqual(code, 0)
            self.assertEqual(read_csv(path)[1][0]["series"], "")

    def test_existing_series_column_is_refreshed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hobbyland_hg.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=es.FIELDNAMES)
                writer.writeheader()
                writer.writerow({**row("Kit A"), "series": "stale"})
            cache = es.SeriesCache(os.path.join(tmp, "cache.json"))
            with mock.patch.object(jv, "classify",
                                   mock.Mock(side_effect=self._classify(
                                       {"Kit A": "zeta"}))), \
                 mock.patch.object(jv, "load_api_key", return_value="k"), \
                 mock.patch.object(jv, "_optional_deepseek_key",
                                   return_value=""):
                es.enrich([path], "jev", cache)
            self.assertEqual(read_csv(path)[1][0]["series"], "zeta")


if __name__ == "__main__":
    unittest.main()
