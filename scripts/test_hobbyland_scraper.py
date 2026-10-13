#!/usr/bin/env python3
"""Unit tests for scripts/hobbyland_scraper.py — stdlib unittest, no extra deps.

Covers the HobbyDigi browser-retry orchestration: Cloudflare's per-cookie-jar
budget is only reset by a brand-new browser, so the retry has to relaunch rather
than wait inside the challenged one.

Run: scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hobbyland_scraper as hs

URL = "https://www.hobbydigi.com/zh_hant_hk/model-kit/theme/gundam?p=1"


class FakeBrowser:
    def __init__(self):
        self.log = []
        self.closed = False

    def new_context(self, **kwargs):
        self.log.append(("context", kwargs.get("user_agent")))
        return FakeContext()

    def close(self):
        self.closed = True
        self.log.append(("close",))


class FakeContext:
    def new_page(self):
        return object()


class FakePlaywright:
    """Counts browser launches and closes; the page load itself is stubbed."""

    def __init__(self):
        self.browsers = []
        self.headless = None

        outer = self

        class Chromium:
            def launch(self, headless=True):
                outer.headless = headless
                browser = FakeBrowser()
                outer.browsers.append(browser)
                return browser

        self.chromium = Chromium()


class HobbydigiRetryTest(unittest.TestCase):
    def setUp(self):
        self._saved = (hs.HD_BROWSER_ATTEMPTS, hs.HD_BROWSER_BACKOFF_S,
                       hs._hobbydigi_page)
        hs.HD_BROWSER_BACKOFF_S = 0  # keep the suite fast
        self.playwright = FakePlaywright()

    def tearDown(self):
        (hs.HD_BROWSER_ATTEMPTS, hs.HD_BROWSER_BACKOFF_S,
         hs._hobbydigi_page) = self._saved

    def _stub_page(self, outcomes):
        """Queue one result per attempt; an Exception instance is raised."""
        calls = []

        def fake_page(page, url, budget_s):
            calls.append((url, budget_s))
            outcome = outcomes[len(calls) - 1]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        hs._hobbydigi_page = fake_page
        return calls


class RecoversFromTransientBlockTest(HobbydigiRetryTest):
    def test_a_block_on_the_first_browser_is_retried_and_recovers(self):
        """The production failure: one unlucky interstitial must not kill the run."""
        hs.HD_BROWSER_ATTEMPTS = 3
        cards = [{"title": "Bandai HG 甲", "href": URL}]
        self._stub_page([
            RuntimeError("Cloudflare challenge did not clear"),
            cards,
        ])

        self.assertEqual(hs._hobbydigi_page_isolated(self.playwright, URL), cards)
        self.assertEqual(len(self.playwright.browsers), 2)

    def test_every_attempt_gets_its_own_closed_browser(self):
        """A reused jar carries the exhausted budget, so isolation must hold."""
        hs.HD_BROWSER_ATTEMPTS = 3
        cards = [{"title": "Bandai HG 甲"}]
        self._stub_page([RuntimeError("blocked"), RuntimeError("blocked"), cards])

        hs._hobbydigi_page_isolated(self.playwright, URL)

        self.assertEqual(len(self.playwright.browsers), 3)
        self.assertTrue(all(browser.closed for browser in self.playwright.browsers))

    def test_a_navigation_timeout_is_also_retried(self):
        """Not just challenges: any transient failure gets the same fresh-browser remedy."""
        hs.HD_BROWSER_ATTEMPTS = 2
        cards = [{"title": "Bandai HG 甲"}]
        self._stub_page([TimeoutError("net::ERR_TIMED_OUT"), cards])

        self.assertEqual(hs._hobbydigi_page_isolated(self.playwright, URL), cards)

    def test_success_on_the_first_browser_launches_only_one(self):
        hs.HD_BROWSER_ATTEMPTS = 3
        cards = [{"title": "Bandai HG 甲"}]
        calls = self._stub_page([cards])

        self.assertEqual(hs._hobbydigi_page_isolated(self.playwright, URL), cards)
        self.assertEqual(len(self.playwright.browsers), 1)
        self.assertEqual(calls, [(URL, hs.HD_CHALLENGE_WAIT_S)])


class GivesUpTest(HobbydigiRetryTest):
    def test_exhausted_attempts_raise_runtime_error_with_the_last_cause(self):
        """RuntimeError specifically, so the caller's partial-catalogue salvage runs."""
        hs.HD_BROWSER_ATTEMPTS = 2
        cause = RuntimeError("Cloudflare challenge did not clear")
        self._stub_page([cause, cause])

        with self.assertRaises(RuntimeError) as caught:
            hs._hobbydigi_page_isolated(self.playwright, URL)

        self.assertIs(caught.exception.__cause__, cause)
        self.assertIn("2 fresh browsers", str(caught.exception))
        self.assertEqual(len(self.playwright.browsers), 2)

    def test_a_non_runtime_failure_still_surfaces_as_runtime_error(self):
        """A Playwright TimeoutError must not escape and bypass the salvage path."""
        hs.HD_BROWSER_ATTEMPTS = 1
        self._stub_page([TimeoutError("net::ERR_TIMED_OUT")])

        with self.assertRaises(RuntimeError):
            hs._hobbydigi_page_isolated(self.playwright, URL)


class HeadlessFlagTest(HobbydigiRetryTest):
    def test_the_shared_headless_switch_reaches_the_launcher(self):
        hs.HD_BROWSER_ATTEMPTS = 1
        self._stub_page([[{"title": "Bandai HG 甲"}]])
        original = hs.HEADLESS
        try:
            hs.HEADLESS = False
            hs._hobbydigi_page_isolated(self.playwright, URL)
            self.assertIs(self.playwright.headless, False)
        finally:
            hs.HEADLESS = original


class ExclusiveSkuTest(unittest.TestCase):
    def test_keys_by_url_slug(self):
        url = "https://www.hobbydigi.com/zh_hant_hk/model-kit/theme/gundam/bandai-hg-gaplant"
        self.assertEqual(hs.hobbydigi_exclusive_sku(url), "HD:bandai-hg-gaplant")

    def test_ignores_query_string_and_trailing_slash(self):
        self.assertEqual(hs.hobbydigi_exclusive_sku("https://h/x/slug/?a=1"), "HD:slug")

    def test_empty_url_yields_no_key(self):
        self.assertEqual(hs.hobbydigi_exclusive_sku(""), "")

    def test_key_is_never_a_thirteen_digit_jan(self):
        self.assertNotRegex(hs.hobbydigi_exclusive_sku("https://h/x/slug"), r"^4\d{12}$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
