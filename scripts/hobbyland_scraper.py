#!/usr/bin/env python3
"""
Hobbyland E-shop / animes-pro.com — Gunpla catalog scraper (HG / MG / RG)

The hobbylandeshop.com frontend is a Vue single-page app: opening a category page such as

    https://www.hobbylandeshop.com/product-category/model_area/gundam_zone/hg_high_grade?page=2

returns only an empty HTML shell, and the browser then POSTs the page number
to the shop's JSON API

    POST https://backend.hobbylandeshop.com/api/products
    {"page": 2, "category": ["model_area", "gundam_zone", "hg_high_grade"],
     "stockStatus": "in_stock"}

This scraper uses that same endpoint instead of a browser. For every
category:
  1. page 1 is fetched and `total_pages` is read — the same number as the
     last button in the pagination bar at the bottom of the landing page;
  2. pages 1..total_pages are then looped, mirroring `?page=x`;
  3. every item's title (description), price, and detail-page hyperlink
     (plus SKU / stock / availability) is collected.

For animes-pro.com (Shopify-based) the scraper walks the rendered HTML
listing instead:

    GET https://animes-pro.com/collections/{handle}?page={n}

Since Sep 2026 the shop sits behind Shopify bot protection: collection
pages answer 302 with a ``__shopify_bv_challenge`` URL and /products.json
hard-429s scripted clients, so plain urllib is no longer enough. A real
browser (Playwright/Chromium, same trick as pbandai_scraper_v2.py) solves
the JS challenge, then each listing page's product cards are parsed from
the DOM. A page with no cards means the collection is exhausted.

The kit identity
(`sku`) is the 13-digit JAN taken from the product name — the same column
Hobbyland fills from its API. animes-pro embeds that code in the title,
e.g. ``Y2700(4573102663849)``.

For hobbydigi.com (Magento 2, also behind a bot challenge) neither identity nor
grade is published on the listing: only ~11% of cards carry a JAN as their
product URL key, and the product detail pages never clear the challenge. A real
browser walks the listing, then ``deepseek_resolve`` supplies the JAN and the
hg/mg/rg grade from the product title. Model answers are gated by an EAN-13
check digit and a Bandai GS1 prefix allowlist, because a wrong JAN would silently
create a false cross-shop match — an unresolvable kit is skipped at import
instead. MGSD counts as ``mg``; PG / SD / EG and anything else is dropped.
Set ``DEEPSEEK_API_KEY`` before scraping the ``hd`` category.

For fooklemodel.com (福利模型, a plain WooCommerce store) the public Store API
serves the same JSON the browser renders, with no bot challenge, so — unlike
hobbydigi — fookle needs no browser. Grade needs no model either: the hg/mg/rg
facet the shop links to is a real product category, so its id *is* the grade.
What fookle never publishes is the JAN — ``sku`` is empty on every product and
the title carries only a Bandai part number (59155) — so, exactly as for
hobbydigi, a kit inherits its JAN from the trusted catalogue (``jan_lookup``)
and an unresolved kit is stored under a provisional ``FM:<slug>`` key rather
than a guessed barcode. No ``DEEPSEEK_API_KEY`` is needed for ``fm``, but
``hobbyland.db`` must exist so there is a catalogue to inherit from.

For twinnermodel.com (千里達模型, Shopify) plain HTTP clients are rate-limited
to death (every urllib request — even a single one with a browser UA — answers
429 ``local_rate_limited``), but a real browser clears the protection without
an interactive challenge and, once the session is warm, the shop's own
``/collections/<handle>/products.json`` endpoint answers normally. The scraper
therefore opens one collection page with Playwright and then pages the JSON
endpoint from inside that page context. The JSON is strictly richer than the
rendered cards: ``handle`` *is* the 13-digit JAN for essentially every kit,
``vendor`` reproduces the site's ``filter.p.vendor=Bandai`` facet,
``variants[].available`` reproduces ``filter.v.availability=1``, and prices are
in the shop's base currency (HKD — the storefront renders TWD at the visitor's
exchange rate), so they are directly comparable with the other shops. Grade is
fixed by the collection (high-grade/master-grade/real-grade), and a kit whose
handle and title carry no JAN falls back to the trusted catalogue, then to a
provisional ``TM:<slug>`` key — the same policy as fookle.

Each category is written to its own CSV:
  hg    -> hobbyland_hg.csv   (model_area > gundam_zone > hg_high_grade)
  mg    -> hobbyland_mg.csv   (model_area > gundam_zone > mg_master_grade)
  rg    -> hobbyland_rg.csv   (model_area > gundam_zone > rg_real_grade)
  ap_hg -> animes-pro_hg.csv  (animes-pro.com Shopify collection)
  ap_mg -> animes-pro_mg.csv
  ap_rg -> animes-pro_rg.csv
  hd    -> hobbydigi_{hg,mg,rg}.csv  (one crawl, bucketed by resolved grade)
  fm    -> fookle_{hg,mg,rg}.csv  (WooCommerce Store API, Bandai hg/mg/rg)
  tm    -> twinnermodel_{hg,mg,rg}.csv  (Shopify products.json, Bandai hg/mg/rg)

Usage:
  python3 hobbyland_scraper.py                 # scrape all categories
  python3 hobbyland_scraper.py hg rg           # scrape selected categories only
  python3 hobbyland_scraper.py ap_hg ap_mg ap_rg
  python3 hobbyland_scraper.py hd              # hobbydigi, needs DEEPSEEK_API_KEY
  python3 hobbyland_scraper.py fm              # fooklemodel, needs hobbyland.db
  python3 hobbyland_scraper.py tm              # twinnermodel, needs hobbyland.db
"""

import csv
import functools
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import deepseek_resolve
import jan_lookup

# --- Site URLs ---
BASE_URL = "https://www.hobbylandeshop.com"
API_URL = "https://backend.hobbylandeshop.com/api/products"
ANIME_PRO_BASE_URL = "https://animes-pro.com"
HOBBYDIGI_BASE_URL = "https://www.hobbydigi.com"

# category key -> (output CSV, path segments under /product-category/)
CATEGORIES = {
    "hg": ("hobbyland_hg.csv",
           ["model_area", "gundam_zone", "hg_high_grade"]),
    "mg": ("hobbyland_mg.csv",
           ["model_area", "gundam_zone", "mg_master_grade"]),
    "rg": ("hobbyland_rg.csv",
           ["model_area", "gundam_zone", "rg_real_grade"]),
}

# animes-pro.com (Shopify) categories: key -> (output CSV, collection handle)
ANIME_PRO_CATEGORIES = {
    "ap_hg": ("animes-pro_hg.csv", "high-grade-hg%E6%A8%A1%E5%9E%8B"),
    "ap_mg": ("animes-pro_mg.csv", "master-grade-mg%E6%A8%A1%E5%9E%8B"),
    "ap_rg": ("animes-pro_rg.csv", "real-grade-rg%E6%A8%A1%E5%9E%8B"),
}

# hobbydigi.com (Magento) categories: key -> (output CSV stem, listing path).
# One crawl of the Gundam theme yields all grades — the per-grade facet URLs
# proved unreliable — so the grade comes from deepseek_resolve and the stem
# becomes hobbydigi_<grade>.csv.
HOBBYDIGI_SHOP_CODE = "hobbydigi"
HOBBYDIGI_EXCLUSIVE_PREFIX = "HD:"
HOBBYDIGI_CATEGORIES = {
    "hd": (HOBBYDIGI_SHOP_CODE, "/zh_hant_hk/model-kit/theme/gundam"),
}

# fooklemodel.com (福利模型) — a plain WooCommerce store. Its public Store API
# (/wp-json/wc/store/v1/products) serves JSON with no bot challenge, so fookle
# uses urllib like hobbyland, not a browser. The hg/mg/rg facet the enhancement
# links to is a real product category, so the category id fixes the grade —
# discovered once from /products/categories (hg=27, mg=35, rg=32).
FOOKLE_BASE_URL = "https://fooklemodel.com"
FOOKLE_STORE_API = FOOKLE_BASE_URL + "/wp-json/wc/store/v1/products"
FOOKLE_SHOP_CODE = "fookle"
FOOKLE_EXCLUSIVE_PREFIX = "FM:"
FOOKLE_BRAND_SLUG = "bandai"
# grade -> WooCommerce product-category id.
FOOKLE_GRADE_CATEGORY_IDS = {"hg": 27, "mg": 35, "rg": 32}
# CLI key -> (shop code, {grade: category id}); one key crawls all three grades.
FOOKLE_CATEGORIES = {"fm": (FOOKLE_SHOP_CODE, FOOKLE_GRADE_CATEGORY_IDS)}
FOOKLE_PER_PAGE = 100      # Store API maximum page size
FOOKLE_MAX_PAGES = 40      # safety guard; the real total is discovered at runtime

# twinnermodel.com (千里達模型) — Shopify. Every plain-HTTP request answers 429
# `local_rate_limited`, so the listing is read from inside a Playwright page
# context that cleared the bot check first. Unlike animes-pro, no DOM parsing
# is needed: `/collections/<handle>/products.json` serves structured JSON with
# the JAN as the product handle, the vendor, per-variant availability and
# base-currency (HKD) prices. Grade is fixed by the collection handle.
TWINNER_BASE_URL = "https://twinnermodel.com"
TWINNER_SHOP_CODE = "twinnermodel"
TWINNER_EXCLUSIVE_PREFIX = "TM:"
TWINNER_VENDOR = "Bandai"
# grade -> Shopify collection handle (the enhancement's three listing URLs).
TWINNER_GRADE_COLLECTIONS = {"hg": "high-grade", "mg": "master-grade",
                             "rg": "real-grade"}
# CLI key -> (shop code, {grade: collection handle}); one key crawls all grades.
TWINNER_CATEGORIES = {"tm": (TWINNER_SHOP_CODE, TWINNER_GRADE_COLLECTIONS)}
TWINNER_PER_PAGE = 250     # products.json maximum page size
TWINNER_MAX_PAGES = 20     # safety guard; the real total is discovered at runtime

# Bandai decals, water-slide transfers and tools share the HG/MG/RG categories
# but are not model kits; skipping them keeps the comparison about kits. An
# unmatched accessory would otherwise just clutter the dashboard as a
# single-shop exclusive.
ACCESSORY_SKIP_RE = re.compile(r"水貼|水贴|貼紙|贴纸|decal|工具|tool", re.IGNORECASE)

# 13-digit JAN in a product name, e.g. Y2700(4573102663849). Same identity
# column as hobbyland_*.csv `sku`.
JAN_RE = re.compile(r"(?<!\d)(4\d{12})(?!\d)")

STOCK_STATUS = "in_stock"   # matches the shop's default listing tab

# CSV columns: the three spec fields first, then helpful extras
FIELDNAMES = ["title", "price", "url",
              "regular_price", "sku", "stock", "sell_type", "image_url"]

# hobbyland 圖片 CDN：API 只回傳相對路徑（pic1），站台前綴見 frontend resource helper
STATIC_BASE_URL = "https://static.hobbylandeshop.com/"

# --- Request tuning ---
PAGE_ATTEMPTS = 6       # retries per page before giving up
RETRY_WAIT_S = 3        # pause between retries when the shop gives no wait
PAGE_WAIT_S = 1.5       # polite delay between page requests
MAX_RETRY_WAIT_S = 90   # cap a hostile Retry-After value

# --- Browser tuning, shared by the two bot-protected shops ---
HEADLESS = True             # set False to watch a challenge being solved
# hobbydigi is the one shop whose challenge cannot be passed headless. Measured
# on the same IP and cookie jar: 24 sequential headed listing loads, zero
# interstitials; the headless run was challenged by page 3 and never cleared,
# because Cloudflare serves it a *passive* managed challenge whose widget
# renders no tick box — there is nothing for a click to hit, and the JS proof
# fails on the headless fingerprint. Headed needs a display, so a headless host
# (Docker, CI) can force it back with HD_HEADLESS=1 and fall back to the cached
# cards the way it does today.
HD_HEADLESS = os.environ.get("HD_HEADLESS", "").strip().lower() not in (
    "", "0", "false", "no")
AP_CHALLENGE_WAIT_S = 45    # budget for Shopify's bv challenge to clear

# --- hobbydigi browser tuning (Cloudflare) ---
# Cloudflare budgets requests per cookie jar, and that budget does not recover
# with time (retested at +60s and +120s, still 403) — so waiting inside a
# challenged browser is wasted effort. Only a brand-new browser resets it. Hence
# several browsers per page with a short selector budget inside each, rather than
# one browser waiting out a block it can never outlast.
HD_BROWSER_ATTEMPTS = 3     # fresh browsers per page before giving up
HD_BROWSER_BACKOFF_S = 8    # pause before relaunching
# HobbyDigi needs its own, longer pause: the shared 1.5s got this IP flagged in
# one session, after which even a headed browser was served a challenge it can
# never pass (measured: 60s wait, zero cookies, no cf_clearance).
HD_PAGE_WAIT_S = 6          # pause between HobbyDigi listing pages
HD_CLEARANCE_COOKIE = "cf_clearance"
HD_CHALLENGE_RETRIES = 2    # interstitial auto-clear checks inside one browser
HD_CHALLENGE_WAIT_S = 20    # selector budget inside one browser
HD_VIEWPORT = {"width": 1920, "height": 1080}
HD_LOCALE = "zh-HK"

# Cloudflare invalidates cf_clearance server-side long before the cookie's own
# nominal expiry, so the expiry field cannot be used to judge a jar. Without an
# age bound a dead jar is replayed into every retry browser on every run, which
# presents as an unexplained challenge loop rather than as a stale credential.
HD_CLEARANCE_MAX_AGE_S = 6 * 60 * 60

# Persistent profile for the crawl session. Unlike a cookie-only storage_state
# replay this also keeps the HTTP cache, IndexedDB and service workers, so a
# returning client looks returning instead of re-fetching Cloudflare's
# challenge orchestration cold on every launch.
HD_PROFILE_DIRNAME = "hobbydigi_profile"
HOBBYDIGI_COOKIE_DOMAIN = "hobbydigi.com"

# --- hobbydigi Turnstile auto-tick ("ghost click") ---
# An interactive challenge has to be ticked, and only a browser-level event is
# accepted for it (see _hobbydigi_ghost_click). Budgets below are per browser.
HD_TURNSTILE_HOST = "challenges.cloudflare.com"
HD_CHECKBOX_INSET_X = 32    # widget tick box centre, from the iframe's left edge
HD_CHECKBOX_SELECTORS = ('input[type="checkbox"]', "label.cb-lb",
                         'div[role="checkbox"]')
HD_CLICK_ATTEMPTS = 3       # Cloudflare re-arms the widget after a wrong tick
HD_CLICK_SETTLE_MS = 2500   # let the widget report the tick before re-checking
HD_CLICK_POLL_MS = 750      # wait for the widget to render before measuring it
# Cloudflare fingerprints navigator.webdriver; without this flag Chromium sets
# it and the tick is scored as a bot no matter how it is dispatched.
HD_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled"]
HD_MAX_PAGES = 40           # safety guard; the real total is discovered at runtime

# A branded Chrome carries the plugin list and the Client Hints that bundled
# Chromium lacks, so it is scored as an ordinary browser rather than as an
# automation shell. HD_BROWSER_CHANNEL=0 pins it off (Docker, CI); any other
# value forces that channel.
CHROME_APP_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
)
CHROME_BINARIES = ("google-chrome", "google-chrome-stable", "chrome")

# Raw cards are persisted so the match-review script can propose candidates
# without re-crawling. `review_matches.py` records every accept/reject decision
# in the matches file, and this scraper reads the accepted ones back.
HOBBYDIGI_CARDS_FILENAME = "hobbydigi_cards.json"
HOBBYDIGI_MATCHES_FILENAME = "hobbydigi_matches.json"
# A cookie jar that already cleared Cloudflare, so one human tick keeps paying
# off for every later page and every later run (cf_clearance is bound to the IP
# and the user agent, and expires on Cloudflare's schedule, not ours).
HOBBYDIGI_STATE_FILENAME = "hobbydigi_state.json"

# The application database holds the trusted JANs that hobbydigi rows inherit.
# The scraper normally runs with the CSV folder as its working directory, which
# is DATA_DIR by default; fall back to the repository's data/ when it does not.
DATABASE_FILENAME = "hobbyland.db"


def _search_dirs():
    """Working directory first, then the repo's data/ folder."""
    repo_data = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    return (os.getcwd(), repo_data)


def _catalogue_path():
    """Locate the application database, or None when it does not exist yet."""
    for directory in _search_dirs():
        candidate = os.path.join(directory, DATABASE_FILENAME)
        if os.path.isfile(candidate):
            return candidate
    return None


def _load_cached_cards():
    """Cards from the last successful HobbyDigi crawl, or None if never crawled."""
    for directory in _search_dirs():
        candidate = os.path.join(directory, HOBBYDIGI_CARDS_FILENAME)
        if os.path.isfile(candidate):
            with open(candidate, encoding="utf-8") as f:
                return json.load(f)
    return None


def _save_json(filename, payload):
    """Persist a side-channel artifact alongside the CSVs."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)
    except OSError as exc:
        print(f"   ⚠️  could not write {filename}: {exc}")


def _load_matches():
    """HobbyDigi match decisions, keyed by product URL.

    Written by `review_matches.py`. Rejected entries carry a null `sku`, so they
    simply fall through to the next JAN source. An absent or unreadable file is
    not an error — it means nothing has been reviewed yet.
    """
    try:
        with open(HOBBYDIGI_MATCHES_FILENAME, encoding="utf-8") as f:
            loaded = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"   ⚠️  ignoring unreadable {HOBBYDIGI_MATCHES_FILENAME}: {exc}")
        return {}
    return loaded if isinstance(loaded, dict) else {}


# Only for the shops that serve plain HTTP (hobbyland's JSON API, fookle's Store
# API) and for the Shopify-protected animes-pro context. Deliberately NOT used
# for hobbydigi: Playwright rewrites the User-Agent header and navigator.userAgent
# but not the sec-ch-ua Client Hints, so a pinned string here makes one request
# claim two different browser versions at once — a tampering signal Cloudflare
# scores. hobbydigi reads its real UA from the engine instead
# (_hobbydigi_real_user_agent).
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/152.0.0.0 Safari/537.36")


def jan_from_name(title):
    """13-digit JAN embedded in a product name, or '' if there is none."""
    match = JAN_RE.search(title or "")
    return match.group(1) if match else ""


def animes_pro_row(card):
    """One rendered listing card -> the same columns as a Hobbyland CSV row.

    `card` comes from the browser-side extraction in
    `_ANIME_PRO_CARD_JS` ({title, href, price, compare, img}). `sku` comes from
    the product name, matching hobbyland_*.csv.
    """
    title = (card.get("title") or "").strip()
    href = card.get("href") or ""
    handle = re.search(r"/products/([^?#]+)", href)
    if "【預訂" in title:
        sell_type = "預訂"
    elif "【現貨" in title:
        sell_type = "現貨"
    else:
        sell_type = ""
    return {
        "title": title,
        "price": card.get("price") or "",
        "url": (f"{ANIME_PRO_BASE_URL}/products/{handle.group(1)}"
                if handle else ANIME_PRO_BASE_URL + href),
        "regular_price": card.get("compare") or "",
        "sku": jan_from_name(title),
        "stock": "",
        "sell_type": sell_type,
        "image_url": card.get("img") or "",
    }


def _hobbyland_image_url(pic):
    """API 的 pic1 是相對路徑（storage/...），補上 static CDN 前綴。"""
    pic = (pic or "").strip()
    if not pic:
        return ""
    if pic.startswith(("http://", "https://")):
        return pic
    return STATIC_BASE_URL + pic.lstrip("/")


def _category_url(segments):
    return BASE_URL + "/product-category/" + "/".join(segments)


def retry_wait_seconds(exc, fallback=RETRY_WAIT_S):
    """Seconds to wait before the next attempt.

    Shopify answers HTTP 429 with ``Retry-After: 60``. Sleeping the old
    fixed 3 seconds burns the remaining attempts and the scrape dies.
    """
    headers = getattr(exc, "headers", None)
    raw = headers.get("Retry-After") if headers is not None else None
    try:
        wait = int(str(raw))
    except (TypeError, ValueError):
        wait = fallback
    return min(max(wait, 1), MAX_RETRY_WAIT_S)


def _fetch_page(segments, page):
    """POST /api/products for `page`; returns the parsed `data` dict."""
    body = json.dumps({
        "page": page,
        "category": segments,
        "stockStatus": STOCK_STATUS,
    }).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != 0:
        raise RuntimeError(f"API error code {payload.get('code')}: "
                           f"{payload.get('message')}")
    return payload["data"]


def fetch_page_with_retry(segments, page):
    """Fetch one page, retrying transient network/API failures."""
    return _with_retry(lambda: _fetch_page(segments, page), f"Page {page}")


def _with_retry(fn, what):
    """Call fn(), waiting out HTTP 429 Retry-After between attempts."""
    for attempt in range(1, PAGE_ATTEMPTS + 1):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError,
                json.JSONDecodeError, RuntimeError) as exc:
            if attempt == PAGE_ATTEMPTS:
                raise
            wait = retry_wait_seconds(exc)
            print(f"   ⚠️  {what} failed (attempt {attempt}/"
                  f"{PAGE_ATTEMPTS}): {exc} — waiting {wait}s")
            time.sleep(wait)
    return None  # unreachable


def _goto_with_retry(page, url, timeout_ms, what="Navigation"):
    """page.goto, retrying transient failures (flaky container DNS/network).

    Playwright's TimeoutError is not the builtin TimeoutError, so _with_retry
    cannot wrap browser navigations; without this a single blip kills the run.
    """
    for attempt in range(1, PAGE_ATTEMPTS + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            return
        except Exception as exc:
            if attempt == PAGE_ATTEMPTS:
                raise
            wait = retry_wait_seconds(exc)
            print(f"   ⚠️  {what} failed (attempt {attempt}/"
                  f"{PAGE_ATTEMPTS}): {exc} — waiting {wait}s")
            time.sleep(wait)


def scrape_category(segments, max_pages=None):
    """Loop pages 1..max for one category and return one dict per product.

    `max_pages` defaults to the shop's own page count (`total_pages`,
    reported by page 1 — the last number of the bottom pagination bar).
    """
    # Page 1 discovers the total / max page count
    data = fetch_page_with_retry(segments, 1)
    total = data.get("total")
    total_pages = data.get("total_pages")
    if max_pages is None:
        max_pages = total_pages
    print(f"📄 Page 1: {len(data.get('list', []))} items "
          f"({total} total, {total_pages} pages)")

    products = []
    seen_urls = set()

    for page in range(1, max_pages + 1):
        if page > 1:
            data = fetch_page_with_retry(segments, page)
            time.sleep(PAGE_WAIT_S)
        batch = data.get("list", [])
        added = 0
        for item in batch:
            url = BASE_URL + item.get("link", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            products.append({
                "title": item.get("title", "").strip(),
                "price": item.get("price", ""),
                "url": url,
                "regular_price": item.get("regular_price", ""),
                "sku": item.get("sku", ""),
                "stock": item.get("stock", ""),
                "sell_type": item.get("sell_type", ""),
                "image_url": _hobbyland_image_url(item.get("pic1", "")),
            })
            added += 1
        print(f"   Page {page}/{max_pages}: {len(batch)} items "
              f"(+{added} new)")
        if not batch:
            print("   ⚠️  Empty page — listing exhausted early")
            break
        if len(batch) < 28:
            print("   — final page reached")

    return products


# Browser-side extraction of one listing page's product cards.
# Selectors match the shop's current Shopify theme (.product-block grid).
_ANIME_PRO_CARD_JS = """() => [...document.querySelectorAll('.product-block')].map(c => {
  const a = c.querySelector('.product-block__title-link');
  const money = sel => {
    const el = c.querySelector(sel);
    return el ? el.innerText.replace(/[^0-9.]/g, '') : '';
  };
  const img = c.querySelector('.product-block__image img, .product-block img');
  let imgSrc = '';
  if (img) {
    // Shopify lazy-load：未載入的圖 src 係 data: placeholder，真網址喺 data-src / srcset
    const srcset = (img.getAttribute('data-srcset') || img.getAttribute('srcset') || '')
      .split(',')[0].trim().split(' ')[0];
    const candidates = [img.currentSrc, img.src, img.getAttribute('data-src'), srcset];
    imgSrc = candidates.find(u => u && !u.startsWith('data:')) || '';
    if (imgSrc.startsWith('//')) imgSrc = 'https:' + imgSrc;
    // 部分主題用 {width} 模板位，換返個實際寬度先用得
    imgSrc = imgSrc.replace('{width}', '300');
  }
  return {
    title: a ? a.innerText.trim() : '',
    href: a ? a.getAttribute('href') : '',
    price: money('.product-price__reduced')
        || money('.product-price__regular')
        || money('.theme-money'),
    compare: money('.product-price__compare'),
    img: imgSrc,
  };
})"""


def _solve_animes_pro_challenge(page, collection_handle):
    """Open the collection page and wait out Shopify's bv challenge.

    The challenge page auto-submits its JS proof and reloads the real
    listing, so success = product cards appear within the wait budget.
    """
    url = f"{ANIME_PRO_BASE_URL}/collections/{collection_handle}"
    _goto_with_retry(page, url, 30000, what="Collection goto")
    if not _wait_animes_pro_listing(page):
        raise RuntimeError(
            f"Shopify bot challenge did not clear for {url} "
            f"(now at {page.url}) — set HEADLESS = False to watch")


def _wait_animes_pro_listing(page, timeout_s=AP_CHALLENGE_WAIT_S):
    """True once listing cards render; False on timeout (challenge/empty)."""
    try:
        page.wait_for_selector(".product-block", timeout=timeout_s * 1000)
        return True
    except Exception:
        return False


def scrape_animes_pro_category(collection_handle):
    """Scrape all pages from an animes-pro.com Shopify collection.

    The shop is behind Shopify bot protection and /products.json is
    rate-limited to death for scripted clients, so a real browser solves
    the JS challenge and then walks the rendered HTML listing pages
    (?page=N) — exactly what a human visitor sees. A page with no cards
    means the collection is exhausted.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "animes-pro.com requires a real browser (Shopify bot "
            "protection) — install Playwright: pip install playwright && "
            "python3 -m playwright install chromium") from exc

    products = []
    seen_urls = set()
    base = f"{ANIME_PRO_BASE_URL}/collections/{collection_handle}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="zh-HK",
        )
        page = context.new_page()
        _solve_animes_pro_challenge(page, collection_handle)

        page_num = 1
        while True:
            if page_num > 1:
                _goto_with_retry(page, f"{base}?page={page_num}", 30000,
                                 what=f"Page {page_num} goto")
                if not _wait_animes_pro_listing(page, timeout_s=15):
                    # past the last page Shopify renders an empty grid
                    print(f"   — page {page_num}: no cards, "
                          "collection exhausted")
                    break

            batch = page.evaluate(_ANIME_PRO_CARD_JS)
            if not batch:
                print(f"   — page {page_num}: empty, collection exhausted")
                break

            added = 0
            for card in batch:
                row = animes_pro_row(card)
                if not row["url"] or row["url"] in seen_urls:
                    continue
                seen_urls.add(row["url"])
                products.append(row)
                added += 1

            print(f"   Page {page_num}: {len(batch)} items (+{added} new)")
            if added == 0:
                print("   ⚠️  No new items — pagination wrapped, stopping")
                break

            page_num += 1
            time.sleep(PAGE_WAIT_S)

            if page_num > 200:  # safety guard
                print("   ⚠️  Safety limit of 200 pages reached — stopping")
                break

        browser.close()

    return products


def save_csv(products, filename):
    """Save one category to CSV (fixed filename, overwritten on each run)."""
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(products)
    return filename


def _require_playwright():
    """`sync_playwright`, or a clear install instruction instead of a traceback."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "hobbydigi.com requires a real browser (Cloudflare bot protection) — "
            "install Playwright: pip install playwright && "
            "python3 -m playwright install chromium") from exc
    return sync_playwright


# Browser-side extraction of one HobbyDigi listing page. Selectors match the
# shop's Magento 2 theme. `data-price-amount` is read instead of the rendered
# "HK$ 2,359.90" text because the backend parses prices with a bare Number() and
# a thousands separator would silently skip the row.
#
# `root` is the document to search and `text` how to read a link's label: the
# live DOM uses innerText, a DOMParser document has no layout so it must use
# textContent. Whitespace normalisation makes the two equivalent here.
_HOBBYDIGI_CARD_MAP_JS = """(root, text) => [...root.querySelectorAll('li.product-item')].map(li => {
  const a = li.querySelector('a.product-item-link');
  const money = sel => {
    const el = li.querySelector(sel);
    return el ? (el.getAttribute('data-price-amount') || '').trim() : '';
  };
  const img = li.querySelector('img.product-image-photo, img');
  let imgSrc = '';
  if (img) {
    const srcset = (img.getAttribute('data-srcset') || img.getAttribute('srcset') || '')
      .split(',')[0].trim().split(' ')[0];
    const candidates = [img.currentSrc, img.src, img.getAttribute('data-src'), srcset];
    imgSrc = candidates.find(u => u && !u.startsWith('data:')) || '';
    if (imgSrc.startsWith('//')) imgSrc = 'https:' + imgSrc;
  }
  return {
    title: a ? text(a).replace(/\\s+/g, ' ').trim() : '',
    href: a ? a.href : '',
    price: money('.price-box.price-final_price [data-price-amount]')
        || money('[data-price-amount]'),
    regular: money('.price-box.price-old_price [data-price-amount]'),
    img: imgSrc,
  };
})"""

_HOBBYDIGI_CARD_JS = "() => (" + _HOBBYDIGI_CARD_MAP_JS + \
    ")(document, el => el.innerText)"

# Same extraction over a listing fetched in-page rather than navigated to. The
# `<base>` element is what makes `a.href` and `img.src` absolute again: a
# DOMParser document's baseURI is about:blank, so relative URLs would otherwise
# come back unresolved and change the product keys.
_HOBBYDIGI_FETCH_JS = """async ({url}) => {
  const response = await fetch(url, {credentials: 'same-origin', redirect: 'follow'});
  const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
  const base = doc.createElement('base');
  base.href = url;
  doc.head.prepend(base);
  const cards = (""" + _HOBBYDIGI_CARD_MAP_JS + """)(doc, el => el.textContent);
  return {status: response.status, title: doc.title || '', cards: cards};
}"""


def hobbydigi_sell_type(title):
    """HobbyDigi's stock wording -> the 現貨/預訂 vocabulary the frontend expects."""
    text = title or ""
    if re.search(r"預訂|預購|訂貨|pre-?order|backorder", text, re.IGNORECASE):
        return "預訂"
    if re.search(r"保証有貨|保證有貨|現貨|有貨|in stock", text, re.IGNORECASE):
        return "現貨"
    return ""


def hobbydigi_exclusive_sku(url):
    """Provisional key for a kit no other shop was matched to: HD:<url slug>.

    It is not a 13-digit JAN, so it can never join another shop's row, and it
    stays stable for as long as the product URL does. The importer replaces it
    by URL once a real JAN is found.
    """
    slug = (url or "").split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return f"{HOBBYDIGI_EXCLUSIVE_PREFIX}{slug}" if slug else ""


def hobbydigi_row(card, sku):
    """One HobbyDigi listing card -> the same columns as a Hobbyland CSV row."""
    title = (card.get("title") or "").strip()
    return {
        "title": title,
        "price": card.get("price") or "",
        "url": card.get("href") or "",
        "regular_price": card.get("regular") or "",
        "sku": sku,
        "stock": "",
        "sell_type": hobbydigi_sell_type(title),
        "image_url": card.get("img") or "",
    }


def _hobbydigi_title_challenged(title):
    """True when a document title is Cloudflare's interstitial.

    Shared by the navigated page (`page.title()`) and the in-page fetch (a
    parsed `<title>`), so the two crawl paths cannot drift on what counts as a
    challenge. The shop serves the interstitial in zh-HK and in English.
    """
    text = title or ""
    return "稍候" in text or "moment" in text.lower()


def _hobbydigi_challenged(page):
    """True while Cloudflare is still serving its interstitial."""
    try:
        title = page.title() or ""
    except Exception:
        return True
    return _hobbydigi_title_challenged(title)


def _hobbydigi_widget_frame(page):
    """The Turnstile child frame, or None while it has not been injected.

    Cloudflare puts the widget iframe inside a shadow root, so no selector
    query on the page can see it; the frame list is the one handle that
    survives that encapsulation.
    """
    for frame in page.frames:
        if HD_TURNSTILE_HOST in frame.url:
            return frame
    return None


def _hobbydigi_checkbox_point(page):
    """Viewport coordinates of the Turnstile tick box, or None if not rendered.

    Bounding boxes are reported relative to the top-level viewport, which is
    exactly what a CDP mouse event expects. An interactive widget exposes a
    real checkbox element and that wins; a passive (managed) widget paints its
    tick on a canvas and exposes nothing, so the widget's fixed geometry is
    used instead — its tick box is the 30x30 square inset from the left edge.
    """
    frame = _hobbydigi_widget_frame(page)
    if frame is None:
        return None
    try:
        handle = frame.frame_element()
        frame_box = handle.bounding_box() if handle is not None else None
    except Exception:
        return None
    if not frame_box:
        return None
    for selector in HD_CHECKBOX_SELECTORS:
        inner = frame.query_selector(selector)
        box = inner.bounding_box() if inner is not None else None
        if box:
            return (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    return (frame_box["x"] + HD_CHECKBOX_INSET_X,
            frame_box["y"] + frame_box["height"] / 2)


def _hobbydigi_ghost_click(page, point):
    """Click viewport `point` with a trusted, browser-level mouse event.

    `element.click()` and Playwright's own click are both ignored here:
    Cloudflare discards events whose isTrusted is false, which is every event
    synthesised from page scripts. CDP `Input.dispatchMouseEvent` enters the
    renderer's input pipeline instead, so the widget sees a real pointer. The
    hover first keeps the sequence shaped like a human's move-then-press.
    """
    x, y = point
    client = page.context.new_cdp_session(page)
    try:
        client.send("Input.dispatchMouseEvent",
                    {"type": "mouseMoved", "x": x, "y": y, "buttons": 0})
        client.send("Input.dispatchMouseEvent",
                    {"type": "mousePressed", "x": x, "y": y, "button": "left",
                     "buttons": 1, "clickCount": 1})
        client.send("Input.dispatchMouseEvent",
                    {"type": "mouseReleased", "x": x, "y": y, "button": "left",
                     "buttons": 0, "clickCount": 1})
    finally:
        client.detach()


def _hobbydigi_solve_challenge(page, budget_s):
    """Tick the Turnstile checkbox until the interstitial goes away.

    True once the challenge has cleared. A wrong tick makes Cloudflare re-arm
    and sometimes relocate the widget, so every attempt re-measures the
    checkbox rather than replaying the coordinates that just failed.
    """
    deadline = time.monotonic() + budget_s
    clicks = 0
    while time.monotonic() < deadline and clicks < HD_CLICK_ATTEMPTS:
        if not _hobbydigi_challenged(page):
            return True
        point = _hobbydigi_checkbox_point(page)
        if point is None:
            page.wait_for_timeout(HD_CLICK_POLL_MS)
            continue
        _hobbydigi_ghost_click(page, point)
        clicks += 1
        print(f"   🖱️  ghost-clicked the Cloudflare tick box at "
              f"({point[0]:.0f}, {point[1]:.0f}) — "
              f"attempt {clicks}/{HD_CLICK_ATTEMPTS}")
        page.wait_for_timeout(HD_CLICK_SETTLE_MS)
    return not _hobbydigi_challenged(page)


@functools.lru_cache(maxsize=1)
def _chrome_is_installed():
    """True when a branded Chrome is present to launch instead of Chromium."""
    if sys.platform == "darwin":
        return any(os.path.isfile(path) for path in CHROME_APP_PATHS)
    return any(shutil.which(name) for name in CHROME_BINARIES)


def _hobbydigi_channel():
    """Browser channel to launch, or None for Playwright's bundled Chromium."""
    choice = os.environ.get("HD_BROWSER_CHANNEL", "").strip()
    if choice.lower() in ("0", "false", "no", "off", "none", "chromium"):
        return None
    if choice:
        return choice
    return "chrome" if _chrome_is_installed() else None


def _hobbydigi_channel_kwargs():
    """Launch kwargs pinning the branded channel, empty when there is none."""
    channel = _hobbydigi_channel()
    return {"channel": channel} if channel else {}


def _hobbydigi_clearance(cookies):
    """The cf_clearance cookie, or None when the jar never cleared."""
    for cookie in cookies or ():
        if cookie.get("name") == HD_CLEARANCE_COOKIE:
            return cookie
    return None


# Google Analytics and Ads-conversion cookies are set on the shop's own domain,
# so a domain filter alone keeps them; they are named here because they are the
# one first-party-domain family that is pure third-party tracking.
HD_TRACKING_COOKIE_PREFIXES = ("_ga", "_gcl_")


def _hobbydigi_prune_cookies(cookies):
    """Only the shop's own cookies, and none of Google's.

    A crawl page incidentally picks up third-party tracking identifiers
    (.youtube.com, .doubleclick.net, the _ga family). None of them can carry a
    clearance, they bloat the credential file, and writing them to data/ leaks
    identifiers that have nothing to do with this project.
    """
    kept = []
    for cookie in cookies:
        if (cookie.get("name") or "").startswith(HD_TRACKING_COOKIE_PREFIXES):
            continue
        domain = (cookie.get("domain") or "").lstrip(".")
        if domain == HOBBYDIGI_COOKIE_DOMAIN or \
                domain.endswith("." + HOBBYDIGI_COOKIE_DOMAIN):
            kept.append(cookie)
    return kept


def _hobbydigi_jar_is_stale(jar):
    """Why this jar cannot be replayed, or '' when it can."""
    if not isinstance(jar, dict):
        return "malformed"
    if not _hobbydigi_clearance(jar.get("cookies") or []):
        return "no cf_clearance"
    if not jar.get("user_agent"):
        return "saved before the user agent was recorded"
    saved_at = jar.get("saved_at")
    if not isinstance(saved_at, (int, float)):
        return "saved before the age was recorded"
    age_s = time.time() - saved_at
    if age_s > HD_CLEARANCE_MAX_AGE_S:
        return (f"{age_s / 3600:.1f}h old, past the "
                f"{HD_CLEARANCE_MAX_AGE_S // 3600}h bound")
    return ""


def _hobbydigi_valid_jar():
    """`(path, jar)` for a replayable clearance jar, or `(None, None)`.

    Replaying a dead jar is worse than starting clean: Cloudflare scores the
    rejected credential, and every retry browser inherits the same rejection,
    which is the loop this check exists to break.
    """
    for directory in _search_dirs():
        candidate = os.path.join(directory, HOBBYDIGI_STATE_FILENAME)
        if not os.path.isfile(candidate):
            continue
        try:
            with open(candidate, encoding="utf-8") as f:
                jar = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"   ⚠️  ignoring unreadable {candidate}: {exc}")
            return None, None
        stale = _hobbydigi_jar_is_stale(jar)
        if stale:
            print(f"   ⚠️  {candidate} is stale ({stale}) — earning a fresh "
                  f"clearance instead of replaying it")
            return None, None
        return candidate, jar
    return None, None


def _hobbydigi_state_path():
    """A saved Cloudflare-clearing cookie jar, or None when there is none."""
    return _hobbydigi_valid_jar()[0]


def _hobbydigi_real_user_agent(context):
    """The User-Agent this browser actually reports.

    Read from the engine rather than configured, so it can never disagree with
    the `sec-ch-ua` Client Hints sent alongside it in the same request. A
    hardcoded UA string does disagree — Playwright rewrites the header and
    `navigator.userAgent` but not the hints — and that contradiction is exactly
    what a bot score is looking for.
    """
    page = context.pages[0] if context.pages else context.new_page()
    return page.evaluate("navigator.userAgent")


def _hobbydigi_replay_jar(context):
    """Seed a freshly launched context from the jar; return `(page, path)`.

    The jar is only replayed when its recorded User-Agent matches the one this
    browser really sends: `cf_clearance` is bound to that string, so replaying
    it under a different one hands Cloudflare a credential it will reject while
    making the request look tampered with.
    """
    page = context.pages[0] if context.pages else context.new_page()
    if _hobbydigi_clearance(context.cookies()):
        return page, None
    path, jar = _hobbydigi_valid_jar()
    if jar is None:
        return page, None
    if jar["user_agent"] != page.evaluate("navigator.userAgent"):
        print(f"   ⚠️  {path} was earned under a different user agent — "
              f"not replaying it")
        return page, None
    context.add_cookies(jar["cookies"])
    print(f"   🍪 replayed cf_clearance from {path}")
    return page, path


def _hobbydigi_save_state(context):
    """Export a clearance-earning jar for the isolated fallback path.

    Only a context that actually holds cf_clearance is saved; a challenged one
    would overwrite a working jar and cost the next run the tick that bought it.
    The real User-Agent and the save time are recorded alongside the cookies,
    because those two are what `_hobbydigi_valid_jar` needs to retire the jar
    later.
    """
    cookies = context.cookies()
    if not _hobbydigi_clearance(cookies):
        return False
    state = context.storage_state()
    state["cookies"] = _hobbydigi_prune_cookies(state.get("cookies") or [])
    state["origins"] = []
    state["user_agent"] = _hobbydigi_real_user_agent(context)
    state["saved_at"] = time.time()
    path = os.path.join(os.getcwd(), HOBBYDIGI_STATE_FILENAME)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
    except OSError as exc:
        print(f"   ⚠️  could not write {path}: {exc}")
        return False
    print(f"   🍪 cf_clearance saved → {path}")
    return True


def _hobbydigi_quarantine_jar(path):
    """Move a jar Cloudflare keeps rejecting out of the replay path.

    Called only once every attempt that loaded it has failed, so a transient
    block cannot discard a clearance a human paid for.
    """
    quarantined = path + ".quarantined"
    try:
        os.replace(path, quarantined)
    except OSError as exc:
        print(f"   ⚠️  could not quarantine {path}: {exc}")
        return
    print(f"   🚫 rejected cf_clearance quarantined → {quarantined}")


def _hobbydigi_page(page, url, budget_s):
    """Load one listing page past Cloudflare and return its cards.

    An empty list means the listing is exhausted; only an interstitial that
    outlives every retry is an error, so a genuine last page cannot be
    mistaken for a bot block.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if _hobbydigi_challenged(page):
        if not _hobbydigi_solve_challenge(page, budget_s):
            raise RuntimeError(
                f"Cloudflare challenge did not clear for {url} (now at {page.url}) "
                f"— {HD_CLICK_ATTEMPTS} ghost clicks spent")
    for _ in range(HD_CHALLENGE_RETRIES):
        try:
            page.wait_for_selector("li.product-item", timeout=budget_s * 1000)
            return page.evaluate(_HOBBYDIGI_CARD_JS)
        except Exception:
            if not _hobbydigi_challenged(page):
                return []
            page.wait_for_timeout(5000)
    raise RuntimeError(
        f"Cloudflare challenge did not clear for {url} (now at {page.url}) "
        f"— {HD_CLICK_ATTEMPTS} ghost clicks spent")


def _hobbydigi_fetch_page(page, url):
    """Read one listing page without navigating, from an already-cleared page.

    Cloudflare budgets *navigations* per cookie jar. A same-origin `fetch()`
    issued by the page that already holds the clearance rides on that clearance
    instead of spending another one, which is what lets a whole crawl run on a
    single verification. An empty card list still means the listing is
    exhausted; only an interstitial or a non-200 is an error, so a genuine last
    page cannot be mistaken for a block.
    """
    result = page.evaluate(_HOBBYDIGI_FETCH_JS, {"url": url})
    if _hobbydigi_title_challenged(result.get("title")):
        raise RuntimeError(f"Cloudflare re-challenged the in-page fetch of {url}")
    status = result.get("status")
    if status != 200:
        raise RuntimeError(f"{url} returned HTTP {status}")
    return result.get("cards") or []


class _HobbydigiSession:
    """One browser that cleared Cloudflare and now serves in-page fetches."""

    def __init__(self, context, page, cards):
        self.context = context
        self.page = page
        self.cards = cards

    def close(self):
        self.context.close()


def _hobbydigi_profile_dir():
    """The persistent profile holding this host's Cloudflare clearance."""
    return os.path.join(os.getcwd(), HD_PROFILE_DIRNAME)


def _hobbydigi_launch_profile(playwright):
    """Open the persistent profile browser; return `(context, replayed_jar)`.

    The profile is what makes a later run cheap: it keeps the clearance, the
    HTTP cache and the service workers together, so the second page of a crawl
    and the first page of next week's crawl both look like the same returning
    visitor. A cookie-only replay cannot do that.
    """
    directory = _hobbydigi_profile_dir()
    os.makedirs(directory, exist_ok=True)
    context = playwright.chromium.launch_persistent_context(
        directory,
        headless=HD_HEADLESS,
        args=HD_BROWSER_ARGS,
        viewport=HD_VIEWPORT,
        locale=HD_LOCALE,
        **_hobbydigi_channel_kwargs(),
    )
    return context, _hobbydigi_replay_jar(context)[1]


def _hobbydigi_open_session(playwright, url):
    """Clear `url` in the persistent profile and return the live session.

    The jar is quarantined when this fails, because a session that cannot clear
    its first page while replaying a credential is the signature of a credential
    Cloudflare has already revoked.
    """
    context, jar_path = _hobbydigi_launch_profile(playwright)
    try:
        page = context.pages[0] if context.pages else context.new_page()
        cards = _hobbydigi_page(page, url, HD_CHALLENGE_WAIT_S)
        _hobbydigi_save_state(context)
        return _HobbydigiSession(context, page, cards)
    except Exception:
        context.close()
        if jar_path:
            _hobbydigi_quarantine_jar(jar_path)
        raise


def _hobbydigi_page_isolated(playwright, url):
    """Load one listing page in its own browser, relaunching if it gets blocked.

    Cloudflare budgets requests per cookie jar — roughly two or three — and the
    budget does not recover with time (retested at +60s and +120s, still 403).
    A fresh browser gets a fresh budget, which is what turns a 2-page crawl into
    a complete one: measured 8 pages / 224 cards with zero blocks, where a single
    reused context died on page 3.

    This is the recovery path for a crawl whose session was challenged mid-walk;
    `_hobbydigi_crawl` is the one that normally runs, and it navigates once
    rather than once per page.

    The same remedy applies to one page hit by a transient challenge, so the
    relaunch is retried here rather than only across pages. Without it a single
    unlucky interstitial on page 1 aborts the whole crawl — observed in
    production — even though the identical load seconds later returns 28 cards.
    Every transient failure class is reported as a RuntimeError so the caller's
    partial-catalogue salvage still applies.
    """
    last = None
    jar_path = None
    for attempt in range(1, HD_BROWSER_ATTEMPTS + 1):
        browser = playwright.chromium.launch(headless=HD_HEADLESS,
                                             args=HD_BROWSER_ARGS,
                                             **_hobbydigi_channel_kwargs())
        try:
            context = browser.new_context(viewport=HD_VIEWPORT, locale=HD_LOCALE)
            page, replayed = _hobbydigi_replay_jar(context)
            jar_path = replayed or jar_path
            cards = _hobbydigi_page(page, url, HD_CHALLENGE_WAIT_S)
            if cards:
                _hobbydigi_save_state(context)
            return cards
        except Exception as exc:
            last = exc
            if attempt < HD_BROWSER_ATTEMPTS:
                print(f"   ⚠️  blocked on {url} (attempt {attempt}/"
                      f"{HD_BROWSER_ATTEMPTS}) — fresh browser in "
                      f"{HD_BROWSER_BACKOFF_S}s")
                time.sleep(HD_BROWSER_BACKOFF_S)
        finally:
            browser.close()
    if jar_path:
        _hobbydigi_quarantine_jar(jar_path)
    raise RuntimeError(
        f"{url} still blocked after {HD_BROWSER_ATTEMPTS} fresh browsers: {last}"
    ) from last


def _hobbydigi_crawl(playwright, base):
    """Walk the whole listing; return `(cards, blocked)`.

    Clears the challenge once, in one persistent-profile browser, then reads
    every later page with a same-origin in-page fetch from that cleared page.
    Navigating per page instead spent a fresh Cloudflare budget per page, which
    is what forced the browser-per-page isolation this replaces: a 28-page crawl
    launched 28 browsers (up to 84 with retries), each a new TLS handshake and a
    new client profile from one IP. This makes roughly one navigation in total.

    `HD_PAGE_WAIT_S` between pages is kept unchanged — the point of the fetch
    path is fewer requests, not faster ones.

    A page challenged mid-walk is recovered in an isolated browser and the
    session is reopened for the rest. Only when that also fails does the crawl
    fall back to the previous complete crawl's cached cards, exactly as the
    per-page version did, and report `blocked` so the run is visibly stale
    rather than silently partial.
    """
    cards = []
    seen_urls = set()
    page_num = 1
    session = None
    try:
        while page_num <= HD_MAX_PAGES:
            url = f"{base}?p={page_num}"
            if session is None:
                session = _hobbydigi_open_session(playwright, url)
                batch = session.cards
                print(f"   🌐 session cleared — later pages are in-page fetches")
            else:
                try:
                    batch = _hobbydigi_fetch_page(session.page, url)
                except RuntimeError as exc:
                    session.close()
                    session = None
                    print(f"   ⚠️  {exc} — recovering in an isolated browser")
                    batch = _hobbydigi_page_isolated(playwright, url)
            if not batch:
                print(f"   — page {page_num}: no cards, listing exhausted")
                break
            added = 0
            for card in batch:
                href = card.get("href") or ""
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)
                cards.append(card)
                added += 1
            print(f"   Page {page_num}: {len(batch)} cards (+{added} new)")
            if added == 0:
                print("   ⚠️  No new cards — pagination wrapped, stopping")
                break
            page_num += 1
            time.sleep(HD_PAGE_WAIT_S)
    except RuntimeError as exc:
        cached = _load_cached_cards()
        if cached is None:
            raise
        print(f"   ⚠️  page {page_num} blocked by Cloudflare ({exc}) — "
              f"using {len(cached)} cached cards")
        return cached, True
    finally:
        if session is not None:
            session.close()
    if page_num > HD_MAX_PAGES:
        print(f"   ⚠️  Safety limit of {HD_MAX_PAGES} pages reached — stopping")
    return cards, False


def _hobbydigi_grades(cards, api_key):
    """Grade for every card, cache-first, aligned with `cards`."""
    cache = deepseek_resolve.ResolveCache()
    grades = [None] * len(cards)
    pending = []
    for index, card in enumerate(cards):
        cached = cache.get(card.get("title") or "")
        if cached is None:
            pending.append(index)
        else:
            grades[index] = deepseek_resolve.grade_or_none(cached.get("grade"))

    if pending:
        print(f"   🤖 asking DeepSeek to grade {len(pending)} titles "
              f"({cache.hits} served from cache)")
        fresh = deepseek_resolve.resolve_grades(
            [cards[i].get("title") or "" for i in pending], api_key)
        for offset, index in enumerate(pending):
            grades[index] = fresh[offset]
            cache.put(cards[index].get("title") or "", fresh[offset], "deepseek",
                      model=deepseek_resolve.DEEPSEEK_MODEL)
        cache.save()
    return grades, cache.hits


def _resolve_hobbydigi(cards, api_key, catalogue, matches):
    """Grade every card, then establish its JAN.

    Returns `(resolved, stats)`. The JAN comes from, in order of trust: the
    shop's own product URL key, a match a human confirmed on a previous run, or
    a catalogue row sharing a model code. It never comes from the model, which
    fabricates barcodes. `sku` is '' when no source produced one, so the row is
    skipped at import rather than wrongly matched — and the card is left for
    `review_matches.py` to propose.
    """
    grades, cache_hits = _hobbydigi_grades(cards, api_key)

    resolved = []
    for index, card in enumerate(cards):
        url = card.get("href") or ""
        title = card.get("title") or ""
        entry = matches.get(url) or {}

        # A confirmed match may also carry the grade, for kits the model
        # declined to classify.
        grade = (deepseek_resolve.grade_or_none(grades[index])
                 or deepseek_resolve.grade_or_none(entry.get("grade")))

        sku = deepseek_resolve.jan_from_url(url)
        source = "url" if sku else ""
        if not sku and entry.get("sku"):
            # Re-validated even though a human confirmed it: the file is
            # hand-editable, and a malformed entry must not reach the database.
            sku = deepseek_resolve.is_plausible_jan(entry["sku"])[0]
            source = "confirmed" if sku else ""
        if not sku and grade:
            sku = catalogue.lookup(title, grade)[0]
            source = "catalogue" if sku else ""

        resolved.append({"sku": sku, "grade": grade, "source": source,
                         "title": title, "url": url})

    ambiguous = _quash_collisions(resolved)

    stats = {
        "cards": len(cards),
        "cache_hits": cache_hits,
        "catalogue_entries": len(catalogue.entries),
        # The matches file records rejections too, so only count the accepted
        # ones — that is the number that can actually supply a JAN.
        "confirmed_entries": sum(1 for m in matches.values() if m.get("sku")),
        "url_jan": 0,
        "confirmed_jan": 0,
        "catalogue_jan": 0,
        "no_jan": 0,
        "no_grade": 0,
        "ambiguous": ambiguous,
        "grades": {grade: 0 for grade in deepseek_resolve.GRADES},
    }
    for item in resolved:
        if item["grade"] is None:
            stats["no_grade"] += 1
        elif not item["sku"]:
            stats["no_jan"] += 1
        else:
            stats[f"{item['source']}_jan"] += 1
            stats["grades"][item["grade"]] += 1
    return resolved, stats


def _quash_collisions(resolved):
    """Blank the SKU of every card sharing a (grade, sku) with a differently
    titled card, and return how many groups that hit.

    Two different kits resolving to one barcode means the matcher could not
    separate variants — observed in production: two GP02A kits, an MLRS and a
    Psalis, both matched the catalogue's single GP02A row on the shared model
    code. Neither answer is trustworthy, and importing both lets one silently
    overwrite the other through the UNIQUE (shop_id, sku, grade) index, so both
    go back to the review queue instead.

    Identical titles under different URLs are the shop listing one kit twice,
    which the importer's upsert already collapses harmlessly.
    """
    groups = {}
    for item in resolved:
        if item["sku"] and item["grade"]:
            groups.setdefault((item["grade"], item["sku"]), []).append(item)

    quashed = 0
    for group in groups.values():
        if len({deepseek_resolve.cache_key(i["title"]) for i in group}) < 2:
            continue
        for item in group:
            item["sku"] = ""
            item["source"] = ""
        quashed += 1
    return quashed


def _print_hobbydigi_report(stats):
    """Print the resolution report — the evidence for trusting each JAN source."""
    print(f"\n   📊 {stats['cards']} cards, {stats['cache_hits']} grades from cache")
    print(f"      catalogue size     : {stats['catalogue_entries']} trusted JANs")
    print(f"      confirmed matches  : {stats['confirmed_entries']} on file")
    print(f"      JAN from shop URL  : {stats['url_jan']}")
    print(f"      JAN human-confirmed: {stats['confirmed_jan']}")
    print(f"      JAN by model code  : {stats['catalogue_jan']}")
    print(f"      variants quashed   : {stats['ambiguous']}  (one barcode, two kits)")
    print(f"      stored HobbyDigi-only: {stats.get('exclusive', 0)}  "
          f"(no JAN — keyed HD:<slug>; run review_matches.py to link them)")
    print(f"      grade out of scope : {stats['no_grade']}  (PG/SD/EG/1:100/other)")
    print("      written per grade  : " + "  ".join(
        f"{grade.upper()}={stats['grades'][grade]}"
        for grade in deepseek_resolve.GRADES))


def scrape_hobbydigi(listing_path):
    """Crawl one HobbyDigi listing and bucket rows by resolved grade.

    Returns `(buckets, stats)` where `buckets` maps grade -> rows. A kit whose
    grade is not hg/mg/rg is dropped. A kit with no trustworthy JAN is kept under
    a provisional `HD:<slug>` key rather than a guessed JAN, which would silently
    create a false cross-shop match; it shows as HobbyDigi-only.
    """
    api_key = deepseek_resolve.load_api_key()
    db_path = _catalogue_path()
    if db_path is None:
        raise RuntimeError(
            f"{DATABASE_FILENAME} not found — import at least one CSV first, so "
            f"there is a trusted catalogue to inherit JANs from")
    # HobbyDigi's own rows are excluded: their JANs are derived by this very
    # matcher, so including them would let a wrong answer confirm itself.
    catalogue = jan_lookup.JanCatalogue.from_database(
        db_path, exclude_shops=(HOBBYDIGI_SHOP_CODE,))
    print(f"   📚 {len(catalogue.entries)} trusted JANs from {db_path}")
    sync_playwright = _require_playwright()
    matches = _load_matches()

    with sync_playwright() as p:
        cards, blocked = _hobbydigi_crawl(p, HOBBYDIGI_BASE_URL + listing_path)

    if not cards:
        return {}, {}

    if not blocked:
        _save_json(HOBBYDIGI_CARDS_FILENAME, cards)
        print(f"   💾 {len(cards)} raw cards → {HOBBYDIGI_CARDS_FILENAME}")

    resolved, stats = _resolve_hobbydigi(cards, api_key, catalogue, matches)
    stats["blocked_pages"] = blocked

    buckets = {grade: [] for grade in deepseek_resolve.GRADES}
    stats["exclusive"] = 0
    for card, item in zip(cards, resolved):
        if item["grade"] is None:
            continue
        sku = item["sku"]
        if not sku:
            sku = hobbydigi_exclusive_sku(item["url"])
            stats["exclusive"] += bool(sku)
        if sku:
            buckets[item["grade"]].append(hobbydigi_row(card, sku))

    return buckets, stats


def fookle_price(prices, key):
    """WooCommerce money in minor units -> a plain decimal string.

    The Store API returns prices as integers scaled by 10**currency_minor_unit
    (minor_unit=1 here, so "600" is $60.0). The backend parses a price with a
    bare Number(), so hand it an unformatted value, never a thousands separator.
    """
    prices = prices or {}
    raw = prices.get(key)
    if raw in (None, ""):
        return ""
    try:
        value = int(raw) / (10 ** int(prices.get("currency_minor_unit", 0)))
    except (TypeError, ValueError):
        return ""
    return f"{value:.2f}"


def fookle_sell_type(product):
    """Fookle stock/pre-order wording -> the 現貨/預訂 vocabulary the UI expects.

    A pre-order can still report is_in_stock (it is on backorder), so the tag and
    the leading 預訂 wording are checked before the in-stock fallback.
    """
    name = html.unescape(product.get("name") or "")
    tags = {t.get("slug") for t in product.get("tags", [])}
    if "pre-order" in tags or re.match(r"\s*(預訂|預購|訂貨)", name):
        return "預訂"
    if product.get("is_in_stock"):
        return "現貨"
    return ""


def fookle_exclusive_sku(permalink):
    """Provisional key for a kit no other shop matched to: FM:<url slug>.

    Mirrors hobbydigi_exclusive_sku — not a 13-digit JAN, so it can never join
    another shop's row, and stable for as long as the product URL is.
    """
    path = urllib.parse.urlparse(permalink or "").path
    slug = urllib.parse.unquote(path.rstrip("/").rsplit("/", 1)[-1])
    return f"{FOOKLE_EXCLUSIVE_PREFIX}{slug}" if slug else ""


def fookle_row(product, sku):
    """One Store API product -> the same columns as a Hobbyland CSV row."""
    images = product.get("images") or []
    first = images[0] if images else {}
    prices = product.get("prices") or {}
    return {
        "title": html.unescape(product.get("name") or "").strip(),
        "price": fookle_price(prices, "price"),
        "url": product.get("permalink") or "",
        "regular_price": fookle_price(prices, "regular_price"),
        "sku": sku,
        "stock": "",
        "sell_type": fookle_sell_type(product),
        "image_url": first.get("thumbnail") or first.get("src") or "",
    }


def _is_fookle_kit(product):
    """In-stock, Bandai-brand, and not an obvious decal/tool accessory.

    The brand + stock filters reproduce the site's own
    /brand/bandai/?_stockstatus=1&_productcategories=<grade> facet.
    """
    if not product.get("is_in_stock"):
        return False
    brands = {b.get("slug") for b in product.get("brands", [])}
    if FOOKLE_BRAND_SLUG not in brands:
        return False
    name = html.unescape(product.get("name") or "")
    return not ACCESSORY_SKIP_RE.search(name)


def _fetch_fookle_page(category_id, page):
    """GET one Store API page of a category; returns the parsed product list."""
    query = urllib.parse.urlencode({
        "category": category_id,
        "per_page": FOOKLE_PER_PAGE,
        "page": page,
    })
    request = urllib.request.Request(
        f"{FOOKLE_STORE_API}?{query}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError(
            f"unexpected Store API response: {type(payload).__name__}")
    return payload


def fetch_fookle_page(category_id, page):
    """One fookle Store API page, retrying transient network/API failures."""
    return _with_retry(lambda: _fetch_fookle_page(category_id, page),
                       f"Page {page}")


def scrape_fookle_grade(category_id, grade):
    """Page one fookle category, keeping in-stock Bandai kits.

    Returns the raw Store API product dicts. The category id already fixes the
    grade, so no title classification is needed; the listing ends at the first
    page shorter than FOOKLE_PER_PAGE (an out-of-range page returns empty).
    """
    products = []
    seen_ids = set()
    for page in range(1, FOOKLE_MAX_PAGES + 1):
        batch = fetch_fookle_page(category_id, page)
        kept = 0
        for product in batch:
            pid = product.get("id")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            if _is_fookle_kit(product):
                products.append(product)
                kept += 1
        print(f"   [{grade.upper()}] page {page}: {len(batch)} items "
              f"(+{kept} Bandai in-stock kits)")
        if len(batch) < FOOKLE_PER_PAGE:
            break
        time.sleep(PAGE_WAIT_S)
    else:
        print(f"   ⚠️  [{grade.upper()}] safety limit of "
              f"{FOOKLE_MAX_PAGES} pages reached")
    return products


def _resolve_fookle(products, grade, catalogue):
    """Establish a JAN for every fookle kit, in order of trust.

    Same policy as hobbydigi: the JAN comes from the shop's own sku field, a JAN
    embedded in the name or URL, or a catalogue row sharing the kit's identity —
    never from a model, which fabricates barcodes. `sku` is '' when no source
    produced one, so the caller stores it under a provisional FM:<slug> key.
    """
    resolved = []
    for product in products:
        name = html.unescape(product.get("name") or "")
        url = product.get("permalink") or ""
        sku, source = "", ""
        for candidate, label in (
                (deepseek_resolve.is_plausible_jan(product.get("sku"))[0], "sku"),
                (deepseek_resolve.is_plausible_jan(jan_from_name(name))[0], "name"),
                (deepseek_resolve.jan_from_url(url), "url")):
            if candidate:
                sku, source = candidate, label
                break
        if not sku:
            sku = catalogue.lookup(name, grade)[0]
            source = "catalogue" if sku else ""
        resolved.append({"sku": sku, "grade": grade, "source": source,
                         "title": name, "url": url})
    ambiguous = _quash_collisions(resolved)
    return resolved, ambiguous


def scrape_fookle(grade_ids):
    """Crawl fookle's Bandai hg/mg/rg categories and bucket rows by grade.

    Returns `(buckets, stats)` where buckets maps grade -> CSV rows. Grade is
    fixed by the category, so no model call is needed; the JAN is inherited from
    the trusted catalogue (fookle publishes none), and a kit that matches
    nothing is kept under a provisional FM:<slug> key so it shows as Fookle-only
    rather than guessing a barcode.
    """
    db_path = _catalogue_path()
    if db_path is None:
        raise RuntimeError(
            f"{DATABASE_FILENAME} not found — import at least one CSV first, so "
            f"there is a trusted catalogue to inherit JANs from")
    # Fookle's and HobbyDigi's own rows are excluded: their JANs are derived by
    # this matcher, so including them would let a wrong answer confirm itself.
    catalogue = jan_lookup.JanCatalogue.from_database(
        db_path, exclude_shops=(FOOKLE_SHOP_CODE, HOBBYDIGI_SHOP_CODE))
    print(f"   📚 {len(catalogue.entries)} trusted JANs from {db_path}")

    buckets = {grade: [] for grade in deepseek_resolve.GRADES}
    stats = {"cards": 0, "sku": 0, "name": 0, "url": 0, "catalogue": 0,
             "exclusive": 0, "ambiguous": 0}
    for grade in deepseek_resolve.GRADES:
        category_id = grade_ids.get(grade)
        if category_id is None:
            continue
        print(f"\n   🔗 [{grade.upper()}] "
              f"{FOOKLE_STORE_API}?category={category_id}")
        products = scrape_fookle_grade(category_id, grade)
        stats["cards"] += len(products)
        resolved, ambiguous = _resolve_fookle(products, grade, catalogue)
        stats["ambiguous"] += ambiguous
        for product, item in zip(products, resolved):
            sku = item["sku"]
            if sku:
                stats[item["source"]] += 1
            else:
                sku = fookle_exclusive_sku(item["url"])
                stats["exclusive"] += bool(sku)
            if sku:
                buckets[grade].append(fookle_row(product, sku))
    return buckets, stats


def _print_fookle_report(stats):
    """Print the fookle resolution report — how each kit got its JAN."""
    print(f"\n   📊 {stats['cards']} Bandai in-stock kits")
    print(f"      JAN from shop sku  : {stats['sku']}")
    print(f"      JAN in name        : {stats['name']}")
    print(f"      JAN in URL         : {stats['url']}")
    print(f"      JAN by catalogue   : {stats['catalogue']}")
    print(f"      variants quashed   : {stats['ambiguous']}  "
          f"(one barcode, two kits)")
    print(f"      stored Fookle-only : {stats['exclusive']}  "
          f"(no JAN — keyed FM:<slug>)")


# --- twinnermodel.com (千里達模型, Shopify behind bot protection) ---

_TWINNER_FETCH_JS = """async ([handle, pageNumber]) => {
  const url = `/collections/${handle}/products.json?limit=250&page=${pageNumber}`;
  const resp = await fetch(url, {headers: {'Accept': 'application/json'}});
  const text = await resp.text();
  if (!resp.ok) return {status: resp.status, body: text.slice(0, 200)};
  return {status: resp.status, body: text};
}"""


def twinner_available_variant(product):
    """The first purchasable variant, or None when the kit is sold out.

    Reproduces the site's own ``filter.v.availability=1`` facet: products.json
    ignores filter parameters, so availability is applied here instead.
    """
    for variant in product.get("variants") or []:
        if variant.get("available"):
            return variant
    return None


def _is_twinner_kit(product):
    """In-stock, Bandai-vendor, and not an obvious decal/tool accessory.

    The vendor + availability checks reproduce the collection URL's
    ``filter.p.vendor=Bandai&filter.v.availability=1`` facets client-side.
    """
    if (product.get("vendor") or "").strip().lower() != TWINNER_VENDOR.lower():
        return False
    if twinner_available_variant(product) is None:
        return False
    return not ACCESSORY_SKIP_RE.search(product.get("title") or "")


def twinner_product_url(handle):
    return f"{TWINNER_BASE_URL}/products/{handle}"


def twinner_sell_type(product):
    """Twinner titles carry no 預訂/現貨 wording; availability already means 現貨."""
    title = product.get("title") or ""
    if re.match(r"\s*(預訂|預購|訂貨)", title):
        return "預訂"
    return "現貨"


def twinner_exclusive_sku(url):
    """Provisional key for a kit no other shop matched to: TM:<url slug>.

    Mirrors fookle_exclusive_sku — never a 13-digit JAN, so it can't join
    another shop's row, and stable for as long as the product URL is.
    """
    path = urllib.parse.urlparse(url or "").path
    slug = urllib.parse.unquote(path.rstrip("/").rsplit("/", 1)[-1])
    return f"{TWINNER_EXCLUSIVE_PREFIX}{slug}" if slug else ""


def twinner_row(product, sku):
    """One products.json product -> the same columns as a Hobbyland CSV row.

    Prices arrive as plain decimal strings in the shop's base currency (HKD —
    the storefront renders TWD at the visitor's rate), so they pass straight
    through to the backend's bare Number() parser.
    """
    variant = twinner_available_variant(product) or {}
    images = product.get("images") or []
    first = images[0] if images else {}
    handle = product.get("handle") or ""
    return {
        "title": html.unescape(product.get("title") or "").strip(),
        "price": variant.get("price") or "",
        "url": twinner_product_url(handle),
        "regular_price": variant.get("compare_at_price") or "",
        "sku": sku,
        "stock": "",
        "sell_type": twinner_sell_type(product),
        "image_url": first.get("src") or "",
    }


def _fetch_twinner_page(page, handle, page_num):
    """GET one products.json page from inside the warmed browser context.

    A non-200 (typically the 429 the shop serves cold clients) raises so
    _with_retry waits it out.
    """
    result = page.evaluate(_TWINNER_FETCH_JS, [handle, page_num])
    status = result.get("status")
    if status != 200:
        raise RuntimeError(
            f"products.json page {page_num} for {handle}: HTTP {status} "
            f"{(result.get('body') or '')[:120]}")
    payload = json.loads(result.get("body") or "")
    products = payload.get("products")
    if not isinstance(products, list):
        raise RuntimeError(f"unexpected products.json shape for {handle}")
    return products


def fetch_twinner_page(page, handle, page_num):
    """One twinnermodel products.json page, retrying transient failures."""
    return _with_retry(lambda: _fetch_twinner_page(page, handle, page_num),
                       f"[{handle}] page {page_num}")


def scrape_twinner_grade(page, handle, grade):
    """Page one twinnermodel collection, keeping in-stock Bandai kits.

    The collection handle already fixes the grade. The listing ends at the
    first short page (an out-of-range page returns an empty list).
    """
    products = []
    seen_ids = set()
    for page_num in range(1, TWINNER_MAX_PAGES + 1):
        batch = fetch_twinner_page(page, handle, page_num)
        kept = 0
        for product in batch:
            pid = product.get("id")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            if _is_twinner_kit(product):
                products.append(product)
                kept += 1
        print(f"   [{grade.upper()}] page {page_num}: {len(batch)} products "
              f"(+{kept} Bandai in-stock kits)")
        if len(batch) < TWINNER_PER_PAGE:
            break
        time.sleep(PAGE_WAIT_S)
    else:
        print(f"   ⚠️  [{grade.upper()}] safety limit of "
              f"{TWINNER_MAX_PAGES} pages reached")
    return products


def _resolve_twinner(products, grade, catalogue):
    """Establish a JAN for every twinnermodel kit, in order of trust.

    The handle is the JAN for nearly every kit; the fallbacks are the same as
    fookle's — a JAN in the title, then the trusted catalogue, never a model
    guess. `sku` is '' when no source produced one, so the caller stores the
    kit under a provisional TM:<slug> key.
    """
    resolved = []
    for product in products:
        title = html.unescape(product.get("title") or "")
        url = twinner_product_url(product.get("handle") or "")
        sku, source = "", ""
        for candidate, label in (
                (deepseek_resolve.is_plausible_jan(product.get("handle"))[0], "handle"),
                (deepseek_resolve.is_plausible_jan(jan_from_name(title))[0], "name"),
                (deepseek_resolve.jan_from_url(url), "url")):
            if candidate:
                sku, source = candidate, label
                break
        if not sku:
            sku = catalogue.lookup(title, grade)[0]
            source = "catalogue" if sku else ""
        resolved.append({"sku": sku, "grade": grade, "source": source,
                         "title": title, "url": url})
    ambiguous = _quash_collisions(resolved)
    return resolved, ambiguous


def _twinner_warm_up(page, first_handle):
    """Open one collection page so the browser clears Shopify's bot check.

    Cold clients are rate-limited on every endpoint; a rendered listing page
    proves the session, after which products.json answers normally.
    """
    url = f"{TWINNER_BASE_URL}/collections/{first_handle}"
    _goto_with_retry(page, url, 45000, what="Warm-up goto")
    try:
        page.wait_for_selector("product-card", timeout=AP_CHALLENGE_WAIT_S * 1000)
    except Exception:
        raise RuntimeError(
            f"twinnermodel listing did not render for {url} (now at {page.url}) "
            "— set HEADLESS = False to watch") from None


def scrape_twinner(collections):
    """Crawl twinnermodel's Bandai hg/mg/rg collections and bucket rows by grade.

    Returns `(buckets, stats)` like scrape_fookle: grade is fixed by the
    collection, the JAN comes from the handle (or the trusted catalogue), and
    an unresolved kit is kept under a provisional TM:<slug> key so it shows as
    Twinnermodel-only rather than guessing a barcode.
    """
    db_path = _catalogue_path()
    if db_path is None:
        raise RuntimeError(
            f"{DATABASE_FILENAME} not found — import at least one CSV first, so "
            "there is a trusted catalogue to inherit JANs from")
    # Twinnermodel's, Fookle's and HobbyDigi's own rows are excluded: their
    # JANs are derived by this matcher, so including them would let a wrong
    # answer confirm itself.
    catalogue = jan_lookup.JanCatalogue.from_database(
        db_path, exclude_shops=(TWINNER_SHOP_CODE, FOOKLE_SHOP_CODE,
                                HOBBYDIGI_SHOP_CODE))
    print(f"   📚 {len(catalogue.entries)} trusted JANs from {db_path}")

    buckets = {grade: [] for grade in deepseek_resolve.GRADES}
    stats = {"products": 0, "handle": 0, "name": 0, "url": 0, "catalogue": 0,
             "exclusive": 0, "ambiguous": 0}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "twinnermodel.com requires a real browser (Shopify bot protection) "
            "— install Playwright: pip install playwright && "
            "python3 -m playwright install chromium") from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="zh-HK",
        )
        page = context.new_page()
        _twinner_warm_up(page, next(iter(collections.values())))
        for grade in deepseek_resolve.GRADES:
            handle = collections.get(grade)
            if handle is None:
                continue
            print(f"\n   🔗 [{grade.upper()}] "
                  f"{TWINNER_BASE_URL}/collections/{handle}/products.json")
            products = scrape_twinner_grade(page, handle, grade)
            stats["products"] += len(products)
            resolved, ambiguous = _resolve_twinner(products, grade, catalogue)
            stats["ambiguous"] += ambiguous
            for product, item in zip(products, resolved):
                sku = item["sku"]
                if sku:
                    stats[item["source"]] += 1
                else:
                    sku = twinner_exclusive_sku(item["url"])
                    stats["exclusive"] += bool(sku)
                if sku:
                    buckets[grade].append(twinner_row(product, sku))
        browser.close()
    return buckets, stats


def _print_twinner_report(stats):
    """Print the twinnermodel resolution report — how each kit got its JAN."""
    print(f"\n   📊 {stats['products']} Bandai in-stock kits")
    print(f"      JAN from handle    : {stats['handle']}")
    print(f"      JAN in name        : {stats['name']}")
    print(f"      JAN in URL         : {stats['url']}")
    print(f"      JAN by catalogue   : {stats['catalogue']}")
    print(f"      variants quashed   : {stats['ambiguous']}  "
          f"(one barcode, two kits)")
    print(f"      stored Twinner-only: {stats['exclusive']}  "
          f"(no JAN — keyed TM:<slug>)")


def _print_preview(products, limit=3):
    """First few saved rows, as a sanity check that the scrape looks sane."""
    for product in products[:limit]:
        print(f"  • {product['title'][:66]}")
        print(f"    💰 HK${product['price']}   🔗 {product['url'][:70]}")
    if len(products) > limit:
        print(f"\n  ... and {len(products) - limit} more")


def main(argv):
    print("=" * 70)
    print("  HOBBYLAND / ANIMES-PRO / HOBBYDIGI / FOOKLE / TWINNERMODEL "
          "— GUNPLA CATALOG SCRAPER")
    print("=" * 70 + "\n")

    # Merge every category dict for CLI lookup
    all_cats = {**CATEGORIES, **ANIME_PRO_CATEGORIES, **HOBBYDIGI_CATEGORIES,
                **FOOKLE_CATEGORIES, **TWINNER_CATEGORIES}

    # Optional argv selects categories; default = all
    keys = [arg.lower() for arg in argv]
    unknown = [k for k in keys if k not in all_cats]
    if unknown:
        print(f"❌ Unknown category: {', '.join(unknown)}")
        print(f"   Available: {', '.join(all_cats)}")
        return 2
    if not keys:
        keys = list(all_cats)

    exit_code = 0
    for key in keys:
        label = key.upper()

        if key in TWINNER_CATEGORIES:
            # --- twinnermodel.com (Shopify products.json via browser) branch ---
            shop_code, collections = TWINNER_CATEGORIES[key]
            print(f"🔗 [{label}] Collections: "
                  + ", ".join(f"{g}={h}" for g, h in collections.items())
                  + f" (vendor={TWINNER_VENDOR}, in stock)\n")
            try:
                buckets, stats = scrape_twinner(collections)
            except Exception as exc:
                print(f"\n❌ [{label}] Scraping failed: {exc}\n")
                exit_code = 1
                continue
            _print_twinner_report(stats)
            if not any(buckets.values()):
                print(f"\n❌ [{label}] No products resolved — no CSV written.\n")
                exit_code = 1
                continue
            for grade in deepseek_resolve.GRADES:
                rows = buckets.get(grade) or []
                if not rows:
                    print(f"   ⚠️  [{label}] no {grade.upper()} kits — "
                          f"{shop_code}_{grade}.csv not written")
                    continue
                csv_name = save_csv(rows, f"{shop_code}_{grade}.csv")
                print(f"\n✅ [{label}] Saved {len(rows)} {grade.upper()} "
                      f"products → {csv_name}\n")
                _print_preview(rows)
            print()
            continue

        if key in FOOKLE_CATEGORIES:
            # --- fooklemodel.com (WooCommerce Store API) branch ---
            shop_code, grade_ids = FOOKLE_CATEGORIES[key]
            print(f"🔗 [{label}] Store API: {FOOKLE_STORE_API} "
                  f"(brand={FOOKLE_BRAND_SLUG}, in stock)\n")
            try:
                buckets, stats = scrape_fookle(grade_ids)
            except Exception as exc:
                print(f"\n❌ [{label}] Scraping failed: {exc}\n")
                exit_code = 1
                continue
            _print_fookle_report(stats)
            if not any(buckets.values()):
                print(f"\n❌ [{label}] No products resolved — no CSV written.\n")
                exit_code = 1
                continue
            for grade in deepseek_resolve.GRADES:
                rows = buckets.get(grade) or []
                if not rows:
                    print(f"   ⚠️  [{label}] no {grade.upper()} kits — "
                          f"{shop_code}_{grade}.csv not written")
                    continue
                csv_name = save_csv(rows, f"{shop_code}_{grade}.csv")
                print(f"\n✅ [{label}] Saved {len(rows)} {grade.upper()} "
                      f"products → {csv_name}\n")
                _print_preview(rows)
            print()
            continue

        if key in HOBBYDIGI_CATEGORIES:
            # --- HobbyDigi.com (Magento + Cloudflare + DeepSeek) branch ---
            csv_stem, listing_path = HOBBYDIGI_CATEGORIES[key]
            print(f"🔗 [{label}] Listing: "
                  f"{HOBBYDIGI_BASE_URL}{listing_path}\n")
            try:
                buckets, stats = scrape_hobbydigi(listing_path)
            except Exception as exc:
                print(f"\n❌ [{label}] Scraping failed: {exc}\n")
                exit_code = 1
                continue
            if stats:
                _print_hobbydigi_report(stats)
            if not any(buckets.values()):
                print(f"\n❌ [{label}] No products resolved — no CSV written.\n")
                exit_code = 1
                continue
            for grade in deepseek_resolve.GRADES:
                rows = buckets.get(grade) or []
                if not rows:
                    print(f"   ⚠️  [{label}] no {grade.upper()} kits — "
                          f"{csv_stem}_{grade}.csv not written")
                    continue
                csv_name = save_csv(rows, f"{csv_stem}_{grade}.csv")
                print(f"\n✅ [{label}] Saved {len(rows)} {grade.upper()} "
                      f"products → {csv_name}\n")
                _print_preview(rows)
            print()
            continue

        if key in ANIME_PRO_CATEGORIES:
            # --- animes-pro.com (Shopify) branch ---
            csv_name, handle = ANIME_PRO_CATEGORIES[key]
            print(f"🔗 [{label}] Collection: "
                  f"{ANIME_PRO_BASE_URL}/collections/{handle}\n")
            try:
                products = scrape_animes_pro_category(handle)
            except Exception as exc:
                print(f"\n❌ [{label}] Scraping failed: {exc}\n")
                exit_code = 1
                continue
        else:
            # --- Hobbyland (Vue SPA API) branch ---
            csv_name, segments = CATEGORIES[key]
            print(f"🔗 [{label}] Category: {_category_url(segments)}\n")
            try:
                products = scrape_category(segments)
            except Exception as exc:
                print(f"\n❌ [{label}] Scraping failed: {exc}\n")
                exit_code = 1
                continue

        if not products:
            print(f"❌ [{label}] No products found — CSV not written.\n")
            exit_code = 1
            continue

        save_csv(products, csv_name)
        print(f"\n✅ [{label}] Saved {len(products)} products → {csv_name}\n")
        _print_preview(products)
        print()

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
