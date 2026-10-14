#!/usr/bin/env python3
"""Unit tests for scripts/hobbyland_scraper.py — stdlib unittest, no extra deps.

Covers the HobbyDigi browser-retry orchestration: Cloudflare's per-cookie-jar
budget is only reset by a brand-new browser, so the retry has to relaunch rather
than wait inside the challenged one. Also covers the Turnstile ghost click —
where the tick box is measured, which CDP events are dispatched, and when the
attempt loop gives up.

Run: scripts/venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
"""

import builtins
import functools
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hobbyland_scraper as hs

URL = "https://www.hobbydigi.com/zh_hant_hk/model-kit/theme/gundam?p=1"

# Pin the branded channel off so launch kwargs stay deterministic across
# machines; ChannelTest exercises the resolution logic directly.
os.environ["HD_BROWSER_CHANNEL"] = "0"


# The UA a real headed Chrome reports. Jars are only replayed into a browser
# that reports exactly this, because cf_clearance is bound to it.
REAL_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")


class FakeUaPage:
    """The about:blank page a fresh context starts on, good for reading the UA."""

    url = "about:blank"

    def __init__(self, user_agent=REAL_UA):
        self.user_agent = user_agent
        self.evaluations = []

    def evaluate(self, expression, arg=None):
        self.evaluations.append((expression, arg))
        if expression == "navigator.userAgent":
            return self.user_agent
        raise AssertionError(f"unexpected evaluate: {expression!r}")


class FakeBrowser:
    def __init__(self, cookies=()):
        self.cookies = cookies
        self.log = []
        self.closed = False
        self.context = None

    def new_context(self, **kwargs):
        self.log.append(("context", kwargs))
        self.context = FakeContext(cookies=self.cookies)
        return self.context

    def close(self):
        self.closed = True
        self.log.append(("close",))


class FakeContext:
    """A cookie jar; `cookies` is what a clearance save would persist."""

    def __init__(self, storage_state=None, cookies=(), pages=None):
        self.storage_state_path = None
        self.replayed_state = storage_state
        self.cookies_list = list(cookies)
        self.added_cookies = []
        self.closed = False
        self._pages = [FakeUaPage()] if pages is None else list(pages)

    @property
    def pages(self):
        return self._pages

    def new_page(self):
        page = FakeUaPage()
        self._pages.append(page)
        return page

    def add_cookies(self, cookies):
        """Mirror Playwright: seeded cookies join the jar this context sends."""
        self.added_cookies.extend(cookies)
        self.cookies_list.extend(cookies)

    def new_cdp_session(self, page):
        return FakeCdpSession(page)

    def cookies(self):
        return self.cookies_list

    def storage_state(self, path=None):
        """Mirror Playwright: a path argument means the jar is written to disk."""
        self.storage_state_path = path
        state = {"cookies": self.cookies_list, "origins": []}
        if path is not None:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f)
        return state

    def close(self):
        self.closed = True


CLEARANCE = ({"name": "cf_clearance", "value": "abc123",
              "domain": ".hobbydigi.com", "path": "/"},)
NO_CLEARANCE = ({"name": "PHPSESSID", "value": "x",
                 "domain": ".hobbydigi.com", "path": "/"},)
THIRD_PARTY = (
    {"name": "YSC", "value": "y", "domain": ".youtube.com", "path": "/"},
    {"name": "IDE", "value": "i", "domain": ".doubleclick.net", "path": "/"},
    {"name": "_ga", "value": "g", "domain": ".hobbydigi.com", "path": "/"},
)


def make_jar(cookies=CLEARANCE, user_agent=REAL_UA, saved_at=None, **extra):
    """A jar shaped the way `_hobbydigi_save_state` writes it."""
    jar = {"cookies": [dict(c) for c in cookies], "origins": [],
           "user_agent": user_agent,
           "saved_at": time.time() if saved_at is None else saved_at}
    jar.update(extra)
    return jar


class FakeCdpSession:
    """Records CDP events on the page; a released press counts as one tick."""

    def __init__(self, page):
        self.page = page

    def send(self, method, params):
        self.page.events.append((method, params))
        if (method == "Input.dispatchMouseEvent"
                and params.get("type") == "mouseReleased"):
            self.page.on_tick()

    def detach(self):
        self.page.events.append(("detach", {}))


class FakeElement:
    def __init__(self, box):
        self._box = box

    def bounding_box(self):
        return self._box


class FakeTurnstileFrame:
    """The widget frame: its own box plus selector -> box (None when absent)."""

    def __init__(self, frame_box, boxes):
        self.url = "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile"
        self.frame_box = frame_box
        self.boxes = boxes

    def frame_element(self):
        return FakeElement(self.frame_box)

    def query_selector(self, selector):
        box = self.boxes.get(selector)
        return FakeElement(box) if box else None


class FakeTurnstilePage:
    """A challenged listing page whose interstitial clears after N ticks.

    `widget` is (frame box, inner boxes) or None when Cloudflare has not
    injected the iframe yet; `on_each_tick` optionally mutates the widget
    between ticks, which is how a re-armed challenge is simulated. The frame is
    exposed through `frames` — never through a selector — because the real
    widget is shadow-encapsulated.
    """

    def __init__(self, widget, clears_after=1, on_each_tick=None):
        self.widget = widget
        self.clears_after = clears_after
        self.on_each_tick = on_each_tick
        self.context = FakeContext()
        self.events = []
        self.waits = []
        self.clicks = 0
        self.url = "https://www.hobbydigi.com/challenge"

    def title(self):
        return "請稍候…" if self.clicks < self.clears_after else "高達模型"

    def on_tick(self):
        self.clicks += 1
        if self.on_each_tick is not None:
            self.on_each_tick(self)

    @property
    def frames(self):
        if self.widget is None:
            return [FakeListingFrame()]
        frame_box, inner = self.widget
        return [FakeListingFrame(), FakeTurnstileFrame(frame_box, inner)]

    def wait_for_timeout(self, ms):
        self.waits.append(ms)


class FakeListingFrame:
    url = "https://www.hobbydigi.com/zh_hant_hk/model-kit/theme/gundam?p=1"


class FakePlaywright:
    """Counts browser launches and closes; the page load itself is stubbed."""

    def __init__(self, cookies=()):
        self.cookies = list(cookies)
        self.browsers = []
        self.contexts = []
        self.profile_dirs = []
        self.headless = None
        self.args = None
        self.channel = "unset"

        outer = self

        class Chromium:
            def launch(self, headless=True, args=None, channel=None):
                outer.headless = headless
                outer.args = args
                outer.channel = channel
                browser = FakeBrowser(outer.cookies)
                outer.browsers.append(browser)
                return browser

            def launch_persistent_context(self, user_data_dir, headless=True,
                                          args=None, channel=None, **kwargs):
                outer.headless = headless
                outer.args = args
                outer.channel = channel
                outer.profile_dirs.append(user_data_dir)
                context = FakeContext(cookies=outer.cookies)
                outer.contexts.append(context)
                return context

        self.chromium = Chromium()


IFRAME_BOX = {"x": 100.0, "y": 200.0, "width": 300.0, "height": 65.0}
CHECKBOX_BOX = {"x": 110.0, "y": 215.0, "width": 30.0, "height": 30.0}
RELOCATED_BOX = {"x": 140.0, "y": 215.0, "width": 30.0, "height": 30.0}


class HobbydigiRetryTest(unittest.TestCase):
    def setUp(self):
        self._saved = (hs.HD_BROWSER_ATTEMPTS, hs.HD_BROWSER_BACKOFF_S,
                       hs._hobbydigi_page, hs._search_dirs)
        hs.HD_BROWSER_BACKOFF_S = 0  # keep the suite fast
        hs._search_dirs = lambda: (os.getcwd(),)
        self.playwright = FakePlaywright()

    def tearDown(self):
        (hs.HD_BROWSER_ATTEMPTS, hs.HD_BROWSER_BACKOFF_S,
         hs._hobbydigi_page, hs._search_dirs) = self._saved

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


class CheckboxPointTest(unittest.TestCase):
    def test_measures_the_tick_box_inside_the_widget_frame(self):
        page = FakeTurnstilePage((IFRAME_BOX, {'input[type="checkbox"]': CHECKBOX_BOX}))
        self.assertEqual(hs._hobbydigi_checkbox_point(page), (125.0, 230.0))

    def test_falls_back_to_the_widget_geometry_for_a_passive_canvas_widget(self):
        """The production case: a managed challenge exposes no checkbox element."""
        page = FakeTurnstilePage((IFRAME_BOX, {}))
        self.assertEqual(hs._hobbydigi_checkbox_point(page),
                         (100.0 + hs.HD_CHECKBOX_INSET_X, 232.5))

    def test_no_widget_rendered_yet_is_not_a_clickable_point(self):
        self.assertIsNone(hs._hobbydigi_checkbox_point(FakeTurnstilePage(None)))

    def test_a_detached_frame_is_not_a_clickable_point(self):
        page = FakeTurnstilePage((None, {'input[type="checkbox"]': CHECKBOX_BOX}))
        self.assertIsNone(hs._hobbydigi_checkbox_point(page))


class GhostClickTest(unittest.TestCase):
    def test_dispatches_a_trusted_hover_press_release_and_detaches(self):
        page = FakeTurnstilePage((IFRAME_BOX, {}), clears_after=1)
        hs._hobbydigi_ghost_click(page, (125.0, 230.0))

        events = [event for event in page.events
                  if event[0] == "Input.dispatchMouseEvent"]
        self.assertEqual([params["type"] for _, params in events],
                         ["mouseMoved", "mousePressed", "mouseReleased"])
        self.assertTrue(all(params["x"] == 125.0 and params["y"] == 230.0
                            for _, params in events))
        self.assertEqual(events[1][1]["button"], "left")
        self.assertEqual(page.events[-1], ("detach", {}))


class SolveChallengeTest(unittest.TestCase):
    def setUp(self):
        self._saved = (hs.HD_CLICK_ATTEMPTS, hs.HD_CLICK_SETTLE_MS,
                       hs.HD_CLICK_POLL_MS)
        hs.HD_CLICK_ATTEMPTS = 3
        hs.HD_CLICK_SETTLE_MS = 0
        hs.HD_CLICK_POLL_MS = 0

    def tearDown(self):
        (hs.HD_CLICK_ATTEMPTS, hs.HD_CLICK_SETTLE_MS,
         hs.HD_CLICK_POLL_MS) = self._saved

    def test_one_tick_clears_the_interstitial(self):
        page = FakeTurnstilePage((IFRAME_BOX, {'input[type="checkbox"]': CHECKBOX_BOX}))
        self.assertTrue(hs._hobbydigi_solve_challenge(page, 20))
        self.assertEqual(page.clicks, 1)

    def test_a_rearmed_widget_is_re_measured_before_the_second_tick(self):
        """Cloudflare relocates the tick box after a wrong answer."""
        def relocate(target):
            target.widget = (IFRAME_BOX, {'input[type="checkbox"]': RELOCATED_BOX})

        page = FakeTurnstilePage(
            (IFRAME_BOX, {'input[type="checkbox"]': CHECKBOX_BOX}),
            clears_after=2, on_each_tick=relocate)

        self.assertTrue(hs._hobbydigi_solve_challenge(page, 20))
        pressed = [params for method, params in page.events
                   if method == "Input.dispatchMouseEvent"
                   and params["type"] == "mousePressed"]
        self.assertEqual([point["x"] for point in pressed], [125.0, 155.0])

    def test_a_widget_that_never_renders_spends_no_tick(self):
        page = FakeTurnstilePage(None)
        self.assertFalse(hs._hobbydigi_solve_challenge(page, 0.05))
        self.assertEqual(page.clicks, 0)
        self.assertIn(hs.HD_CLICK_POLL_MS, page.waits)

    def test_gives_up_after_the_click_budget(self):
        page = FakeTurnstilePage((IFRAME_BOX, {}), clears_after=99)
        self.assertFalse(hs._hobbydigi_solve_challenge(page, 60))
        self.assertEqual(page.clicks, hs.HD_CLICK_ATTEMPTS)

    def test_an_already_clear_page_is_left_alone(self):
        page = FakeTurnstilePage((IFRAME_BOX, {}), clears_after=0)
        self.assertTrue(hs._hobbydigi_solve_challenge(page, 20))
        self.assertEqual(page.clicks, 0)


class ClearanceStateTest(unittest.TestCase):
    """One human tick has to keep paying off for later pages and later runs."""

    def setUp(self):
        self._cwd = os.getcwd()
        self._search_dirs = hs._search_dirs
        # realpath: macOS hands out /var/... and reports the cwd as /private/var/...
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        os.chdir(self.tmp)
        hs._search_dirs = lambda: (self.tmp,)

    def tearDown(self):
        hs._search_dirs = self._search_dirs
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_state(self):
        path = os.path.join(self.tmp, hs.HOBBYDIGI_STATE_FILENAME)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(make_jar(), f)
        return path

    def test_no_saved_jar_means_no_state_to_replay(self):
        self.assertIsNone(hs._hobbydigi_state_path())

    def test_a_saved_jar_is_found_in_the_working_directory(self):
        saved = self._write_state()
        self.assertEqual(hs._hobbydigi_state_path(), saved)

    def test_a_cleared_jar_is_persisted(self):
        context = FakeContext(cookies=CLEARANCE)
        self.assertTrue(hs._hobbydigi_save_state(context))
        expected = os.path.join(self.tmp, hs.HOBBYDIGI_STATE_FILENAME)
        self.assertTrue(os.path.isfile(expected))

    def test_a_challenged_jar_never_overwrites_a_working_one(self):
        """No cf_clearance is exactly what a failed challenge leaves behind."""
        saved = self._write_state()
        context = FakeContext(cookies=NO_CLEARANCE)

        self.assertFalse(hs._hobbydigi_save_state(context))
        self.assertIsNone(context.storage_state_path)
        self.assertTrue(os.path.isfile(saved))


class ClearanceReplayTest(HobbydigiRetryTest):
    def setUp(self):
        super().setUp()
        self._cwd = os.getcwd()
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def _state_file(self):
        path = os.path.join(self.tmp, hs.HOBBYDIGI_STATE_FILENAME)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(make_jar(), f)
        return path

    def test_a_saved_jar_is_replayed_into_the_fresh_browser(self):
        hs.HD_BROWSER_ATTEMPTS = 1
        self._stub_page([[{"title": "Bandai HG 甲"}]])
        self._state_file()
        playwright = FakePlaywright()

        hs._hobbydigi_page_isolated(playwright, URL)

        self.assertEqual(playwright.browsers[0].context.added_cookies,
                         [dict(c) for c in CLEARANCE])

    def test_a_cleared_page_saves_its_jar_for_the_next_one(self):
        hs.HD_BROWSER_ATTEMPTS = 1
        self._stub_page([[{"title": "Bandai HG 甲"}]])
        playwright = FakePlaywright(cookies=CLEARANCE)

        hs._hobbydigi_page_isolated(playwright, URL)

        self.assertTrue(os.path.isfile(
            os.path.join(self.tmp, hs.HOBBYDIGI_STATE_FILENAME)))

    def test_a_blocked_page_saves_nothing(self):
        hs.HD_BROWSER_ATTEMPTS = 1
        self._stub_page([RuntimeError("Cloudflare challenge did not clear")])
        playwright = FakePlaywright(cookies=NO_CLEARANCE)

        with self.assertRaises(RuntimeError):
            hs._hobbydigi_page_isolated(playwright, URL)

        self.assertFalse(os.path.isfile(
            os.path.join(self.tmp, hs.HOBBYDIGI_STATE_FILENAME)))


class StillChallengedFallbackTest(unittest.TestCase):
    """When 3 ghost clicks do not clear Cloudflare, immediately fall back to cached cards."""

    def setUp(self):
        self._saved = (hs.HD_CLICK_ATTEMPTS, hs.HD_CLICK_SETTLE_MS,
                       hs.HD_CLICK_POLL_MS, hs._search_dirs, builtins.input)
        hs.HD_CLICK_ATTEMPTS = 3
        hs.HD_CLICK_SETTLE_MS = 0
        hs.HD_CLICK_POLL_MS = 0
        self._cwd = os.getcwd()
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        os.chdir(self.tmp)
        hs._search_dirs = lambda: (self.tmp,)
        builtins.input = lambda _prompt="": (_ for _ in ()).throw(
            AssertionError("input() must not be called when still challenged"))

    def tearDown(self):
        (hs.HD_CLICK_ATTEMPTS, hs.HD_CLICK_SETTLE_MS,
         hs.HD_CLICK_POLL_MS, hs._search_dirs, builtins.input) = self._saved
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_still_challenged_after_three_clicks_raises_immediately_without_selector_wait(self):
        page = FakeTurnstilePage((IFRAME_BOX, {}), clears_after=99)
        page.goto = lambda url, **kwargs: None
        page.wait_for_selector = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("wait_for_selector must not run when still challenged"))

        with self.assertRaises(RuntimeError) as caught:
            hs._hobbydigi_page(page, URL, 20)

        self.assertEqual(page.clicks, 3)
        self.assertIn("3 ghost clicks spent", str(caught.exception))

    def test_crawl_falls_back_to_cached_cards_when_still_challenged_after_three_clicks(self):
        cached_cards = [{"title": "Bandai HG Cached", "href": URL}]
        with open(os.path.join(self.tmp, hs.HOBBYDIGI_CARDS_FILENAME),
                  "w", encoding="utf-8") as f:
            json.dump(cached_cards, f)

        page = FakeTurnstilePage((IFRAME_BOX, {}), clears_after=99)
        page.goto = lambda url, **kwargs: None
        page.evaluate = lambda expr, arg=None: REAL_UA
        playwright = FakePlaywright()
        playwright.chromium.launch_persistent_context = (
            lambda *args, **kwargs: FakeContext(pages=[page])
        )

        cards, blocked = hs._hobbydigi_crawl(
            playwright, "https://www.hobbydigi.com/zh_hant_hk/model-kit/theme/gundam")

        self.assertEqual(page.clicks, 3)
        self.assertTrue(blocked)
        self.assertEqual(cards, cached_cards)


class HeadlessFlagTest(HobbydigiRetryTest):
    def test_hobbydigi_launches_headed_by_default(self):
        """Headless provably never clears this shop's passive challenge."""
        hs.HD_BROWSER_ATTEMPTS = 1
        self._stub_page([[{"title": "Bandai HG 甲"}]])

        hs._hobbydigi_page_isolated(self.playwright, URL)

        self.assertIs(self.playwright.headless, hs.HD_HEADLESS)
        self.assertIs(hs.HD_HEADLESS, False)

    def test_the_env_switch_reaches_the_launcher(self):
        """A headless host (Docker) can still force HD_HEADLESS=1."""
        hs.HD_BROWSER_ATTEMPTS = 1
        self._stub_page([[{"title": "Bandai HG 甲"}]])
        original = hs.HD_HEADLESS
        try:
            hs.HD_HEADLESS = True
            hs._hobbydigi_page_isolated(self.playwright, URL)
            self.assertIs(self.playwright.headless, True)
        finally:
            hs.HD_HEADLESS = original

    def test_the_launcher_hides_the_automation_flag(self):
        """navigator.webdriver is what makes Cloudflare score a tick as a bot."""
        hs.HD_BROWSER_ATTEMPTS = 1
        self._stub_page([[{"title": "Bandai HG 甲"}]])
        hs._hobbydigi_page_isolated(self.playwright, URL)
        self.assertEqual(self.playwright.args, hs.HD_BROWSER_ARGS)


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


# --- twinnermodel.com (Shopify products.json) ---

# A real JAN whose EAN-13 check digit passes.
TM_JAN = "4573102650962"


def tw_product(**overrides):
    product = {
        "id": 7458859221181,
        "title": "Bandai 1/144 水星之魔女 HG 019 風靈高達(改修型) 組裝模型",
        "handle": TM_JAN,
        "vendor": "Bandai",
        "variants": [{
            "available": True,
            "price": "102.00",
            "compare_at_price": "126.00",
        }],
        "images": [{"src": "https://cdn.shopify.com/x.jpg"}],
    }
    product.update(overrides)
    return product


class TwinnerKitFilterTest(unittest.TestCase):
    def test_in_stock_bandai_kit_is_kept(self):
        self.assertTrue(hs._is_twinner_kit(tw_product()))

    def test_sold_out_kit_is_dropped(self):
        product = tw_product(variants=[{"available": False, "price": "102.00"}])
        self.assertFalse(hs._is_twinner_kit(product))

    def test_other_vendor_is_dropped(self):
        self.assertFalse(hs._is_twinner_kit(tw_product(vendor="Kotobukiya")))

    def test_decal_accessory_is_dropped(self):
        product = tw_product(title="Bandai 水貼水轉印貼紙")
        self.assertFalse(hs._is_twinner_kit(product))


class TwinnerRowTest(unittest.TestCase):
    def test_maps_products_json_to_the_shared_csv_columns(self):
        row = hs.twinner_row(tw_product(), TM_JAN)
        self.assertEqual(row["sku"], TM_JAN)
        self.assertEqual(row["price"], "102.00")
        self.assertEqual(row["regular_price"], "126.00")
        self.assertEqual(row["url"], f"https://twinnermodel.com/products/{TM_JAN}")
        self.assertEqual(row["image_url"], "https://cdn.shopify.com/x.jpg")
        self.assertEqual(row["sell_type"], "現貨")
        self.assertEqual(set(row), set(hs.FIELDNAMES))

    def test_availability_filter_means_every_row_is_in_stock(self):
        self.assertEqual(hs.twinner_sell_type(tw_product()), "現貨")

    def test_preorder_wording_wins_over_the_in_stock_default(self):
        product = tw_product(title="預訂 Bandai HG 某 kit")
        self.assertEqual(hs.twinner_sell_type(product), "預訂")

    def test_uses_the_first_available_variant_price(self):
        product = tw_product(variants=[
            {"available": False, "price": "999.00"},
            {"available": True, "price": "102.00", "compare_at_price": None},
        ])
        row = hs.twinner_row(product, TM_JAN)
        self.assertEqual(row["price"], "102.00")
        self.assertEqual(row["regular_price"], "")


class TwinnerExclusiveSkuTest(unittest.TestCase):
    def test_keys_by_url_slug(self):
        url = "https://twinnermodel.com/products/some-limited-kit"
        self.assertEqual(hs.twinner_exclusive_sku(url), "TM:some-limited-kit")

    def test_ignores_query_string_and_trailing_slash(self):
        self.assertEqual(hs.twinner_exclusive_sku("https://t/x/slug/?a=1"), "TM:slug")

    def test_empty_url_yields_no_key(self):
        self.assertEqual(hs.twinner_exclusive_sku(""), "")


class FakeTwinnerPage:
    """Stands in for the warmed Playwright page context."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def evaluate(self, script, args):
        self.calls.append((script, tuple(args)))
        return self.results.pop(0)


class TwinnerFetchTest(unittest.TestCase):
    def test_returns_the_product_list(self):
        body = json.dumps({"products": [tw_product()]})
        page = FakeTwinnerPage([{"status": 200, "body": body}])
        products = hs._fetch_twinner_page(page, "high-grade", 1)
        self.assertEqual(len(products), 1)
        self.assertEqual(page.calls[0][1], ("high-grade", 1))

    def test_rate_limit_raises_so_the_retry_loop_waits_it_out(self):
        page = FakeTwinnerPage([{"status": 429, "body": "local_rate_limited"}])
        with self.assertRaises(RuntimeError):
            hs._fetch_twinner_page(page, "high-grade", 1)


class TwinnerResolveTest(unittest.TestCase):
    class FakeCatalogue:
        def __init__(self, answer=""):
            self.answer = answer
            self.queries = []

        def lookup(self, title, grade):
            self.queries.append((title, grade))
            return self.answer, 1.0 if self.answer else 0.0, None

    def test_handle_jan_is_the_first_source_of_trust(self):
        catalogue = self.FakeCatalogue()
        resolved, ambiguous = hs._resolve_twinner([tw_product()], "hg", catalogue)
        self.assertEqual(ambiguous, 0)
        self.assertEqual(resolved[0]["sku"], TM_JAN)
        self.assertEqual(resolved[0]["source"], "handle")
        self.assertEqual(catalogue.queries, [])

    def test_a_jan_in_the_title_rescues_a_slug_handle(self):
        product = tw_product(handle="limited-kit", title=f"Bandai HG ({TM_JAN})")
        resolved, _ = hs._resolve_twinner([product], "hg", self.FakeCatalogue())
        self.assertEqual(resolved[0]["sku"], TM_JAN)
        self.assertEqual(resolved[0]["source"], "name")

    def test_the_catalogue_is_the_last_resort_before_a_provisional_key(self):
        product = tw_product(handle="limited-kit")
        catalogue = self.FakeCatalogue(answer="4573102683175")
        resolved, _ = hs._resolve_twinner([product], "hg", catalogue)
        self.assertEqual(resolved[0]["sku"], "4573102683175")
        self.assertEqual(resolved[0]["source"], "catalogue")
        self.assertEqual(catalogue.queries[0][1], "hg")

    def test_an_unresolved_kit_gets_an_empty_sku_for_the_caller_to_key(self):
        product = tw_product(handle="limited-kit")
        resolved, _ = hs._resolve_twinner([product], "hg", self.FakeCatalogue())
        self.assertEqual(resolved[0]["sku"], "")
        self.assertEqual(
            hs.twinner_exclusive_sku(resolved[0]["url"]), "TM:limited-kit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
