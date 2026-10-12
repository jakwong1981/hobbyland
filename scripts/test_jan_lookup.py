#!/usr/bin/env python3
"""Unit tests for scripts/jan_lookup.py — stdlib unittest, no extra deps.

Run: scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
"""

import os
import unittest

import jan_lookup as jl

# A real labeled pair from the database: two shops' wording of the same kit,
# identified by a shared model code (GN-001REII) rather than by prose.
HL_TITLE = "[現貨] HG00 44 1/144【機動戰士高達00】GN-001REII 能天使高達Repair II"
AP_TITLE = ("Bandai - 1/1HG GN-001REII 能天使高達 修補型 R2 Y1400 (BAN557339) "
            "(4573102557339)【現貨】")
SHARED_JAN = "4573102557339"

# A kit whose two shop titles share no model code and differ in transliteration
# (維達爾 vs 維度爾). Matching these would need prose similarity, which the
# threshold deliberately refuses to trust.
HL_NO_CODE = "[現貨] HGIBO 027 1/144【機動戰士高達 鐵血的孤兒】高達維達爾"
AP_NO_CODE = "Bandai - HG 1/144 高達維度爾 Y1400 (BAN554482) (4573102554482)【現貨】"

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "hobbyland.db")


class NormalizeTitleTest(unittest.TestCase):
    def test_strips_stock_tags_brand_grade_scale_and_codes(self):
        cleaned = jl.normalize_title(AP_TITLE)
        for noise in ("bandai", "y1400", "ban557339", "4573102557339", "現貨",
                      "hg", "1/144"):
            with self.subTest(noise=noise):
                self.assertNotIn(noise, cleaned)

    def test_keeps_the_product_name(self):
        cleaned = jl.normalize_title(HL_TITLE)
        self.assertIn("能天使高達", cleaned)

    def test_handles_empty(self):
        self.assertEqual(jl.normalize_title(""), "")
        self.assertEqual(jl.normalize_title(None), "")


class ModelCodeTest(unittest.TestCase):
    def test_extracts_mech_designations(self):
        codes = jl.model_codes(HL_TITLE)
        self.assertIn("GN-001REII", codes)

    def test_extracts_several_codes(self):
        codes = jl.model_codes("HG 1/144 GAT-X370 獵殺高達 MBF-P02")
        self.assertEqual(codes, {"GAT-X370", "MBF-P02"})

    def test_no_codes_in_prose_only_title(self):
        self.assertEqual(jl.model_codes("Bandai MG 風靈高達 水星的魔女"), set())

    def test_codes_are_case_insensitive_across_titles(self):
        self.assertEqual(jl.model_codes("gn-001reii"),
                         jl.model_codes("GN-001REII"))


class CjkBigramTest(unittest.TestCase):
    def test_bigrams_survive_word_order_changes(self):
        self.assertIn("新安", jl.cjk_bigrams("原石新安州"))
        self.assertIn("新安", jl.cjk_bigrams("新安州原石型"))

    def test_ignores_non_cjk(self):
        self.assertEqual(jl.cjk_bigrams("GN-001REII R2"), set())

    def test_single_character_yields_no_bigram(self):
        self.assertEqual(jl.cjk_bigrams("高"), set())


class ScoreTest(unittest.TestCase):
    def test_shared_model_code_scores_above_threshold(self):
        self.assertGreaterEqual(jl.score(HL_TITLE, AP_TITLE), jl.DEFAULT_THRESHOLD)

    def test_unrelated_titles_score_below_threshold(self):
        self.assertLess(jl.score(HL_TITLE, "Bandai MG 1/100 飛翼高達零式 EW"),
                        jl.DEFAULT_THRESHOLD)

    def test_identical_titles_score_maximum(self):
        self.assertAlmostEqual(jl.score(HL_TITLE, HL_TITLE),
                               jl.CODE_WEIGHT + jl.CJK_WEIGHT)

    def test_cjk_overlap_alone_cannot_reach_the_threshold(self):
        """At DEFAULT_THRESHOLD a match must share a model code: CJK contributes
        at most CJK_WEIGHT, which is below the bar on its own."""
        self.assertLess(jl.CJK_WEIGHT, jl.DEFAULT_THRESHOLD)
        prose_only = jl.score(HL_NO_CODE, AP_NO_CODE)
        self.assertLess(prose_only, jl.DEFAULT_THRESHOLD)


class LookupTest(unittest.TestCase):
    def setUp(self):
        self.catalogue = jl.JanCatalogue([
            ("hg", SHARED_JAN, HL_TITLE),
            ("hg", "4573102554482", HL_NO_CODE),
            ("mg", "4573102635602", "[現貨] MG 1/100 GN-001REII 無關套件"),
        ])

    def test_inherits_the_verified_jan_within_the_same_grade(self):
        sku, score, matched = self.catalogue.lookup(AP_TITLE, "hg")
        self.assertEqual(sku, SHARED_JAN)
        self.assertGreaterEqual(score, jl.DEFAULT_THRESHOLD)
        self.assertEqual(matched, HL_TITLE)

    def test_grade_isolates_candidates(self):
        """The same title must not match an mg row when asked about hg."""
        self.assertEqual(self.catalogue.lookup(AP_TITLE, "mg")[0], "")

    def test_unknown_grade_abstains(self):
        self.assertEqual(self.catalogue.lookup(AP_TITLE, "rg"), ("", 0.0, None))

    def test_abstains_below_threshold(self):
        self.assertEqual(self.catalogue.lookup("Bandai HG 1/144 一些完全無關的東西", "hg")[0], "")

    def test_abstains_on_a_tie_between_different_skus(self):
        ambiguous = jl.JanCatalogue([
            ("hg", "4573102557339", "HG 1/144 GN-001REII 甲"),
            ("hg", "4573102554482", "HG 1/144 GN-001REII 甲"),
        ])
        self.assertEqual(ambiguous.lookup("HG 1/144 GN-001REII 甲", "hg")[0], "")

    def test_empty_catalogue_abstains(self):
        self.assertEqual(jl.JanCatalogue([]).lookup(AP_TITLE, "hg"), ("", 0.0, None))


class EvaluateOnRealDataTest(unittest.TestCase):
    """Regression guard over the 201 labeled cross-shop pairs in the database.

    Every (grade, sku) held by two shops is a known true match, so this measures
    the matcher on real data rather than on hand-written fixtures.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(DB_PATH):
            raise unittest.SkipTest(f"no database at {DB_PATH}")
        # HobbyDigi excluded: its JANs are produced by this matcher, so scoring
        # the matcher on pairs it created would be circular.
        cls.catalogue = jl.JanCatalogue.from_database(DB_PATH,
                                                     exclude_shops=("hobbydigi",))
        cls.result = jl.evaluate(cls.catalogue)

    def test_catalogue_loaded(self):
        self.assertGreater(len(self.catalogue.entries), 600)

    def test_precision_is_perfect(self):
        """A wrong JAN fabricates a price comparison, so no false match is
        acceptable at any recall level."""
        self.assertEqual(self.result["wrong"], 0,
                         f"wrong-SKU matches: {self.result['wrong_examples']}")
        self.assertEqual(self.result["precision"], 1.0)

    def test_recall_stays_above_the_measured_floor(self):
        self.assertGreaterEqual(self.result["recall"], 0.90)

    def test_runs_on_a_substantial_labeled_population(self):
        # A floor, not an exact count: every import that adds a cross-shop SKU
        # grows this population, and the point is that the evaluation ran on real
        # data rather than on a handful of fixtures.
        self.assertGreaterEqual(self.result["pairs"], 201)


class ExcludeShopsTest(unittest.TestCase):
    """A shop whose JANs are matcher-derived must never seed the matcher.

    Regression guard for circular matching: once HobbyDigi rows are imported,
    an unfiltered catalogue offers them back as candidates, so a wrong answer
    can confirm itself on the next run.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(DB_PATH):
            raise unittest.SkipTest(f"no database at {DB_PATH}")

    def test_exclusion_removes_exactly_that_shops_rows(self):
        import sqlite3
        connection = sqlite3.connect(DB_PATH)
        try:
            excluded = connection.execute(
                "SELECT COUNT(*) FROM products p JOIN shops s ON s.id = p.shop_id "
                "WHERE s.code = 'hobbydigi' AND length(p.sku) = 13").fetchone()[0]
        finally:
            connection.close()

        everything = jl.JanCatalogue.from_database(DB_PATH)
        without = jl.JanCatalogue.from_database(DB_PATH, exclude_shops=("hobbydigi",))
        self.assertEqual(len(everything.entries) - len(without.entries), excluded)

    def test_excluding_an_absent_shop_changes_nothing(self):
        everything = jl.JanCatalogue.from_database(DB_PATH)
        without = jl.JanCatalogue.from_database(DB_PATH, exclude_shops=("no-such-shop",))
        self.assertEqual(len(without.entries), len(everything.entries))


class QuashCollisionsTest(unittest.TestCase):
    """The variant-collision guard, driven through the scraper module."""

    def setUp(self):
        import hobbyland_scraper
        self.scraper = hobbyland_scraper

    def _item(self, title, sku, grade="hg"):
        return {"title": title, "sku": sku, "grade": grade, "source": "catalogue"}

    def test_two_kits_sharing_a_barcode_are_both_quashed(self):
        # Observed in production: GP02A MLRS and GP02A Psalis both matched the
        # catalogue's single GP02A row on the shared model code.
        resolved = [
            self._item("Bandai HG 1/144 GP02A 高達試作2號機 (MLRS 多管火箭炮型)", "4573102557308"),
            self._item("Bandai HG 1/144 GP02A 高達試作2號機（賽薩里斯）", "4573102557308"),
        ]
        self.assertEqual(self.scraper._quash_collisions(resolved), 1)
        self.assertEqual([item["sku"] for item in resolved], ["", ""])
        self.assertEqual([item["source"] for item in resolved], ["", ""])

    def test_identical_titles_under_different_urls_survive(self):
        """The shop listing one kit twice is collapsed by the importer's upsert."""
        resolved = [
            self._item("Bandai HG 1/144 熱帶型大魔", "4573102603937"),
            self._item("Bandai HG 1/144 熱帶型大魔", "4573102603937"),
        ]
        self.assertEqual(self.scraper._quash_collisions(resolved), 0)
        self.assertEqual([i["sku"] for i in resolved],
                         ["4573102603937", "4573102603937"])

    def test_distinct_barcodes_are_untouched(self):
        resolved = [
            self._item("Bandai HG 甲", "4573102603937"),
            self._item("Bandai HG 乙", "4573102579515"),
        ]
        self.assertEqual(self.scraper._quash_collisions(resolved), 0)
        self.assertEqual([i["sku"] for i in resolved],
                         ["4573102603937", "4573102579515"])

    def test_collision_is_scoped_per_grade(self):
        resolved = [
            self._item("Bandai HG 甲", "4573102603937", grade="hg"),
            self._item("Bandai MG 乙", "4573102603937", grade="mg"),
        ]
        self.assertEqual(self.scraper._quash_collisions(resolved), 0)

    def test_cards_without_a_sku_are_ignored(self):
        resolved = [self._item("Bandai HG 甲", ""), self._item("Bandai HG 乙", "")]
        self.assertEqual(self.scraper._quash_collisions(resolved), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
