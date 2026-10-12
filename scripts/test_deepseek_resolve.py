#!/usr/bin/env python3
"""Unit tests for scripts/deepseek_resolve.py — stdlib unittest, no extra deps.

Run: scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
"""

import json
import os
import tempfile
import unittest

import deepseek_resolve as dr


# Real JANs observed in the trusted shop catalogues and HobbyDigi product URLs.
PG_RX78_JAN = "4573102607652"
EPYON_JAN = "4573102654427"
HOBBYDIGI_URL_JAN = "4580886841165"

PROMO_TITLE = ("[保証有貨] Bandai MGSD 組裝模型 - 高達00 Raiser "
               "(輸入優惠碼以$379.9換購 | 需購買模型工具滿$400及把優惠產品置於同一購物車結帳)")


class CheckDigitTest(unittest.TestCase):
    def test_accepts_real_barcodes(self):
        for code in (PG_RX78_JAN, EPYON_JAN, HOBBYDIGI_URL_JAN):
            with self.subTest(code=code):
                self.assertTrue(dr.ean13_check_digit_ok(code))

    def test_rejects_single_digit_alteration(self):
        for code in (PG_RX78_JAN, EPYON_JAN, HOBBYDIGI_URL_JAN):
            for position in range(13):
                altered = (code[:position]
                           + str((int(code[position]) + 1) % 10)
                           + code[position + 1:])
                if altered != code:
                    with self.subTest(code=code, position=position):
                        self.assertFalse(dr.ean13_check_digit_ok(altered))

    def test_rejects_wrong_length_and_non_digits(self):
        for bad in ("", "457310260765", "45731026076521", "457310260765X", None):
            with self.subTest(bad=bad):
                self.assertFalse(dr.ean13_check_digit_ok(bad or ""))


class PlausibleJanTest(unittest.TestCase):
    def test_accepts_a_check_digit_valid_jan(self):
        self.assertEqual(dr.is_plausible_jan(EPYON_JAN), (EPYON_JAN, ""))

    def test_rejects_check_digit_failure(self):
        code, reason = dr.is_plausible_jan(PG_RX78_JAN[:-1] + "3")
        self.assertEqual(code, "")
        self.assertEqual(reason, "check digit failed")

    def test_rejects_non_jan_shapes(self):
        for bad in ("", None, "1234567890123", "457310260765", "not-a-jan"):
            with self.subTest(bad=bad):
                self.assertEqual(dr.is_plausible_jan(bad),
                                 ("", "not a 13-digit Japanese JAN"))

    def test_rejects_a_fabricated_sequential_code(self):
        """The model invented these when asked for barcodes; the gate must not
        admit them even though they carry a genuine Bandai prefix."""
        for fabricated in ("4573102656789", "4573102656796", "4573102656802",
                           "4543112000000"):
            with self.subTest(fabricated=fabricated):
                self.assertEqual(dr.is_plausible_jan(fabricated)[0], "")


class JanFromUrlTest(unittest.TestCase):
    def test_extracts_jan_url_key(self):
        url = ("https://www.hobbydigi.com/zh_hant_hk/model-kit/theme/gundam/"
               + HOBBYDIGI_URL_JAN)
        self.assertEqual(dr.jan_from_url(url), HOBBYDIGI_URL_JAN)

    def test_extracts_jan_before_query_string(self):
        url = "https://www.hobbydigi.com/x/gundam/" + HOBBYDIGI_URL_JAN + "?p=2"
        self.assertEqual(dr.jan_from_url(url), HOBBYDIGI_URL_JAN)

    def test_slug_url_yields_nothing(self):
        url = ("https://www.hobbydigi.com/zh_hant_hk/model-kit/theme/gundam/"
               "bandai-mgsd-model-kits-gundam-aerial")
        self.assertEqual(dr.jan_from_url(url), "")

    def test_digits_embedded_in_a_longer_run_are_not_a_jan(self):
        self.assertEqual(dr.jan_from_url("https://x/y/99" + EPYON_JAN + "00"), "")

    def test_url_jan_with_bad_check_digit_is_rejected(self):
        self.assertEqual(
            dr.jan_from_url("https://x/y/" + PG_RX78_JAN[:-1] + "3"), "")


class CleanTitleTest(unittest.TestCase):
    def test_strips_stock_bracket_and_promo_parenthetical(self):
        self.assertEqual(dr.clean_title_for_prompt(PROMO_TITLE),
                         "Bandai MGSD 組裝模型 - 高達00 Raiser")

    def test_keeps_a_clean_title_unchanged(self):
        title = "Bandai PG Unleashed 組裝模型 - 1/60 RX-78-2 高達"
        self.assertEqual(dr.clean_title_for_prompt(title), title)

    def test_collapses_runs_of_whitespace(self):
        self.assertEqual(dr.clean_title_for_prompt("Bandai   HG\n  Gundam  "),
                         "Bandai HG Gundam")

    def test_handles_empty(self):
        self.assertEqual(dr.clean_title_for_prompt(""), "")


class NormalizeTitleTest(unittest.TestCase):
    def test_is_case_and_punctuation_insensitive(self):
        self.assertEqual(dr.normalize_title("Bandai MGSD - 高達00 Raiser"),
                         dr.normalize_title("bandai mgsd 高達00 raiser"))

    def test_distinguishes_different_products(self):
        self.assertNotEqual(dr.normalize_title("Bandai MG 高達"),
                            dr.normalize_title("Bandai HG 高達"))

    def test_cache_key_ignores_stock_decoration(self):
        """The same kit listed with and without a stock bracket shares an entry."""
        self.assertEqual(dr.cache_key("[保証有貨] Bandai MG 風靈高達"),
                         dr.cache_key("Bandai MG 風靈高達"))


class GradeTest(unittest.TestCase):
    def test_accepts_known_grades_case_insensitively(self):
        for raw, expected in ((" hg ", "hg"), ("MG", "mg"), ("rg", "rg"),
                              ("\tRg\n", "rg")):
            with self.subTest(raw=raw):
                self.assertEqual(dr.grade_or_none(raw), expected)

    def test_rejects_out_of_scope_grades(self):
        """PG / SD / EG / MGSD are dropped by product decision."""
        for raw in ("pg", "sd", "eg", "mgsd", "1/60", "", None, "high grade"):
            with self.subTest(raw=raw):
                self.assertIsNone(dr.grade_or_none(raw))


class ParseResultsTest(unittest.TestCase):
    def test_parses_expected_shape(self):
        document = {"results": [{"id": 1, "grade": "rg"},
                                {"id": 2, "grade": None}]}
        self.assertEqual(dr._parse_results(document, {1, 2}),
                         {1: "rg", 2: None})

    def test_ignores_ids_outside_the_requested_range(self):
        document = {"results": [{"id": 99, "grade": "rg"}]}
        self.assertEqual(dr._parse_results(document, {1, 2}), {})

    def test_tolerates_a_bare_list(self):
        self.assertEqual(dr._parse_results([{"id": 1, "grade": "hg"}], {1}),
                         {1: "hg"})

    def test_rejects_unusable_shapes(self):
        for document in ({}, {"results": "nope"}, {"results": 5}):
            with self.subTest(document=document):
                with self.assertRaises(ValueError):
                    dr._parse_results(document, {1})

    def test_skips_malformed_entries(self):
        document = {"results": [{"id": "abc"}, "junk", {"id": 2, "grade": "mg"}]}
        self.assertEqual(dr._parse_results(document, {1, 2}), {2: "mg"})

    def test_out_of_scope_grade_becomes_none(self):
        document = {"results": [{"id": 1, "grade": "PG"}]}
        self.assertEqual(dr._parse_results(document, {1}), {1: None})


class ResolveGradesTest(unittest.TestCase):
    def test_batches_and_aligns_results(self):
        titles = [f"title {i}" for i in range(dr.BATCH_SIZE + 3)]
        calls = []

        def fake_batch(chunk, api_key):
            calls.append(list(chunk))
            return {i: "hg" for i in range(len(chunk))}

        original = dr.resolve_batch
        dr.resolve_batch = fake_batch
        try:
            grades = dr.resolve_grades(titles, "test-key")
        finally:
            dr.resolve_batch = original

        self.assertEqual([len(c) for c in calls], [dr.BATCH_SIZE, 3])
        self.assertEqual(grades, ["hg"] * len(titles))

    def test_omitted_entries_abstain_to_none(self):
        original = dr.resolve_batch
        dr.resolve_batch = lambda chunk, api_key: {}
        try:
            grades = dr.resolve_grades(["a", "b"], "test-key")
        finally:
            dr.resolve_batch = original
        self.assertEqual(grades, [None, None])

    def test_alignment_survives_a_partially_answered_batch(self):
        original = dr.resolve_batch
        dr.resolve_batch = lambda chunk, api_key: {1: "rg"}
        try:
            grades = dr.resolve_grades(["a", "b", "c"], "test-key")
        finally:
            dr.resolve_batch = original
        self.assertEqual(grades, [None, "rg", None])


class ApiKeyTest(unittest.TestCase):
    def test_env_var_wins(self):
        original = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = "from-env"
        try:
            self.assertEqual(dr.load_api_key(), "from-env")
        finally:
            if original is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = original

    def test_falls_back_to_the_repo_env_file(self):
        """Nothing in this repo loads .env, so the module must read it itself."""
        original = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            self.assertTrue(dr.load_api_key().startswith("sk-"))
        finally:
            if original is not None:
                os.environ["DEEPSEEK_API_KEY"] = original

    def test_missing_key_raises_auth_error(self):
        original = os.environ.pop("DEEPSEEK_API_KEY", None)
        real = dr._env_file_value
        dr._env_file_value = lambda key: ""
        try:
            with self.assertRaises(dr.AuthError) as ctx:
                dr.load_api_key()
            self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))
        finally:
            dr._env_file_value = real
            if original is not None:
                os.environ["DEEPSEEK_API_KEY"] = original

    def test_env_file_parser_skips_comments_blanks_and_strips_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comment\n\nOTHER=1\nDEEPSEEK_API_KEY=\"sk-quoted\"\n")
            self.assertEqual(dr._read_env_file(path, "DEEPSEEK_API_KEY"), "sk-quoted")
            self.assertEqual(dr._read_env_file(path, "OTHER"), "1")
            self.assertEqual(dr._read_env_file(path, "ABSENT"), "")

    def test_env_file_parser_tolerates_a_missing_file(self):
        self.assertEqual(dr._read_env_file("/no/such/.env", "DEEPSEEK_API_KEY"), "")

    def test_auth_error_is_not_retryable(self):
        """_with_retry in hobbyland_scraper catches RuntimeError; a 401 must not
        be retried six times, so AuthError must not subclass it."""
        self.assertFalse(issubclass(dr.AuthError, RuntimeError))


class CacheTest(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cache.json")
            cache = dr.ResolveCache(path)
            self.assertIsNone(cache.get(PROMO_TITLE))
            cache.put(PROMO_TITLE, "mg", "deepseek", model=dr.DEEPSEEK_MODEL)
            cache.save()

            reloaded = dr.ResolveCache(path)
            entry = reloaded.get(dr.clean_title_for_prompt(PROMO_TITLE))
            self.assertEqual(entry, {"grade": "mg", "source": "deepseek",
                                     "model": dr.DEEPSEEK_MODEL})
            self.assertEqual((reloaded.hits, reloaded.misses), (1, 0))

    def test_corrupt_cache_is_ignored_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cache.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{not json")
            cache = dr.ResolveCache(path)
            self.assertEqual(cache.entries, {})
            self.assertIsNone(cache.get("anything"))

    def test_save_survives_an_unwritable_path(self):
        cache = dr.ResolveCache(os.path.join(tempfile.gettempdir(),
                                             "no-such-dir", "cache.json"))
        cache.put("x", "hg", "deepseek")
        cache.save()  # warns rather than raising


if __name__ == "__main__":
    unittest.main(verbosity=2)
