#!/usr/bin/env python3
"""Unit tests for scripts/pbandai_scraper_v2.py — stdlib unittest, no extra deps.

Covers the export shape the import CLI relies on: the image column added for
the P-Bandai showcase page must reach the CSV/JSON untouched, and a card
without a thumbnail must degrade to an empty cell rather than break the
writer. Also pins the listing-source contract: the model-kits category page
is scraped with a single-page limit, and the card extractor skips the
RECOMMENDATIONS rail so captures match the site's result counter.

Run: scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
"""

import csv
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pbandai_scraper_v2 as pb


PRODUCT = {
    "name": "MG 1/100 THE GUNDAM BASE LIMITED RX-78-2 GUNDAM Ver.3.0",
    "tc_name": "MG 1/100 高達基地限定 RX-78-2 高達 Ver.3.0",
    "price": "HK$450.00",
    "status": "PRE-ORDER",
    "url": "https://p-bandai.com/hk/item/A2475067001",
    "image": "https://p-bandai.com/img/x.jpg",
}


class SaveCsvTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _read(self, filename):
        with open(filename, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def test_csv_carries_the_image_column(self):
        rows = self._read(pb.save_csv([PRODUCT], output_dir=self.tmp))
        self.assertEqual(rows[0]["image"], PRODUCT["image"])
        self.assertEqual(rows[0]["name"], PRODUCT["name"])

    def test_a_card_without_a_thumbnail_writes_an_empty_cell(self):
        product = {k: v for k, v in PRODUCT.items() if k != "image"}
        rows = self._read(pb.save_csv([product], output_dir=self.tmp))
        self.assertEqual(rows[0]["image"], "")


class SaveJsonTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_json_round_trips_the_image_field(self):
        filename = pb.save_json([PRODUCT], output_dir=self.tmp)
        with open(filename, encoding="utf-8") as f:
            self.assertEqual(json.load(f)[0]["image"], PRODUCT["image"])


class DeliverySuffixTest(unittest.TestCase):
    def test_trailing_delivery_note_splits_off(self):
        core, suffix = pb._split_delivery_suffix("HG 1/144 某機 [2026年11月發送]")
        self.assertEqual(core, "HG 1/144 某機")
        self.assertEqual(suffix.strip(), "[2026年11月發送]")

    def test_no_bracketed_suffix_leaves_the_name_untouched(self):
        self.assertEqual(pb._split_delivery_suffix("HG 1/144 某機"), ("HG 1/144 某機", ""))


class ListingSourceTest(unittest.TestCase):
    """Pins the source URLs and the extractor scope the 63-item catalogue needs."""

    def test_category_url_targets_the_full_model_kits_listing(self):
        self.assertIn("/hk/category/model-kits", pb.CATEGORY_URL)
        self.assertIn("limit=100", pb.CATEGORY_URL)

    def test_extract_js_skips_the_recommendations_carousel(self):
        # The RECOMMENDATIONS rail adds ~8 off-listing cards on top of the
        # 63 results; the extractor must stay scoped to the result grid.
        self.assertIn(".o-items-carousel", pb.EXTRACT_JS)
        self.assertIn("closest", pb.EXTRACT_JS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
