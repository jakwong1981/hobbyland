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

Each category is written to its own CSV:
  hg    -> hobbyland_hg.csv   (model_area > gundam_zone > hg_high_grade)
  mg    -> hobbyland_mg.csv   (model_area > gundam_zone > mg_master_grade)
  rg    -> hobbyland_rg.csv   (model_area > gundam_zone > rg_real_grade)
  ap_hg -> animes-pro_hg.csv  (animes-pro.com Shopify collection)
  ap_mg -> animes-pro_mg.csv
  ap_rg -> animes-pro_rg.csv
  hd    -> hobbydigi_{hg,mg,rg}.csv  (one crawl, bucketed by resolved grade)

Usage:
  python3 hobbyland_scraper.py                 # scrape all categories
  python3 hobbyland_scraper.py hg rg           # scrape selected categories only
  python3 hobbyland_scraper.py ap_hg ap_mg ap_rg
  python3 hobbyland_scraper.py hd              # hobbydigi, needs DEEPSEEK_API_KEY
"""

import csv
import json
import os
import re
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
HOBBYDIGI_CATEGORIES = {
    "hd": (HOBBYDIGI_SHOP_CODE, "/zh_hant_hk/model-kit/theme/gundam"),
}

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
AP_CHALLENGE_WAIT_S = 45    # budget for Shopify's bv challenge to clear

# --- hobbydigi browser tuning (Cloudflare) ---
# Cloudflare budgets requests per cookie jar, and that budget does not recover
# with time (retested at +60s and +120s, still 403) — so waiting inside a
# challenged browser is wasted effort. Only a brand-new browser resets it. Hence
# several browsers per page with a short selector budget inside each, rather than
# one browser waiting out a block it can never outlast.
HD_BROWSER_ATTEMPTS = 3     # fresh browsers per page before giving up
HD_BROWSER_BACKOFF_S = 8    # pause before relaunching
HD_CHALLENGE_RETRIES = 2    # interstitial auto-clear checks inside one browser
HD_CHALLENGE_WAIT_S = 20    # selector budget inside one browser
HD_MAX_PAGES = 40           # safety guard; the real total is discovered at runtime

# Raw cards are persisted so the match-review script can propose candidates
# without re-crawling. `review_matches.py` records every accept/reject decision
# in the matches file, and this scraper reads the accepted ones back.
HOBBYDIGI_CARDS_FILENAME = "hobbydigi_cards.json"
HOBBYDIGI_MATCHES_FILENAME = "hobbydigi_matches.json"

# The application database holds the trusted JANs that hobbydigi rows inherit.
# The scraper normally runs with the CSV folder as its working directory, which
# is DATA_DIR by default; fall back to the repository's data/ when it does not.
DATABASE_FILENAME = "hobbyland.db"


def _catalogue_path():
    """Locate the application database, or None when it does not exist yet."""
    repo_data = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    for directory in (os.getcwd(), repo_data):
        candidate = os.path.join(directory, DATABASE_FILENAME)
        if os.path.isfile(candidate):
            return candidate
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
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
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
                page.goto(f"{base}?page={page_num}",
                          wait_until="domcontentloaded", timeout=30000)
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
_HOBBYDIGI_CARD_JS = """() => [...document.querySelectorAll('li.product-item')].map(li => {
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
    title: a ? a.innerText.replace(/\\s+/g, ' ').trim() : '',
    href: a ? a.href : '',
    price: money('.price-box.price-final_price [data-price-amount]')
        || money('[data-price-amount]'),
    regular: money('.price-box.price-old_price [data-price-amount]'),
    img: imgSrc,
  };
})"""


def hobbydigi_sell_type(title):
    """HobbyDigi's stock wording -> the 現貨/預訂 vocabulary the frontend expects."""
    text = title or ""
    if re.search(r"預訂|預購|訂貨|pre-?order|backorder", text, re.IGNORECASE):
        return "預訂"
    if re.search(r"保証有貨|保證有貨|現貨|有貨|in stock", text, re.IGNORECASE):
        return "現貨"
    return ""


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


def _hobbydigi_challenged(page):
    """True while Cloudflare is still serving its interstitial."""
    try:
        title = page.title() or ""
    except Exception:
        return True
    return "稍候" in title or "moment" in title.lower()


def _hobbydigi_page(page, url, budget_s):
    """Load one listing page past Cloudflare and return its cards.

    An empty list means the listing is exhausted; only an interstitial that
    outlives every retry is an error, so a genuine last page cannot be
    mistaken for a bot block.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
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
        f"— set HEADLESS = False to watch")


def _hobbydigi_page_isolated(playwright, url):
    """Load one listing page in its own browser, relaunching if it gets blocked.

    Cloudflare budgets requests per cookie jar — roughly two or three — and the
    budget does not recover with time (retested at +60s and +120s, still 403).
    A fresh browser gets a fresh budget, which is what turns a 2-page crawl into
    a complete one: measured 8 pages / 224 cards with zero blocks, where a single
    reused context died on page 3.

    The same remedy applies to one page hit by a transient challenge, so the
    relaunch is retried here rather than only across pages. Without it a single
    unlucky interstitial on page 1 aborts the whole crawl — observed in
    production — even though the identical load seconds later returns 28 cards.
    Every transient failure class is reported as a RuntimeError so the caller's
    partial-catalogue salvage still applies.
    """
    last = None
    for attempt in range(1, HD_BROWSER_ATTEMPTS + 1):
        browser = playwright.chromium.launch(headless=HEADLESS)
        try:
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="zh-HK",
            )
            return _hobbydigi_page(context.new_page(), url, HD_CHALLENGE_WAIT_S)
        except Exception as exc:
            last = exc
            if attempt < HD_BROWSER_ATTEMPTS:
                print(f"   ⚠️  blocked on {url} (attempt {attempt}/"
                      f"{HD_BROWSER_ATTEMPTS}) — fresh browser in "
                      f"{HD_BROWSER_BACKOFF_S}s")
                time.sleep(HD_BROWSER_BACKOFF_S)
        finally:
            browser.close()
    raise RuntimeError(
        f"{url} still blocked after {HD_BROWSER_ATTEMPTS} fresh browsers: {last}"
    ) from last


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
    print(f"      awaiting review    : {stats['no_jan']}  (no JAN — run review_matches.py)")
    print(f"      grade out of scope : {stats['no_grade']}  (PG/SD/EG/1:100/other)")
    print("      written per grade  : " + "  ".join(
        f"{grade.upper()}={stats['grades'][grade]}"
        for grade in deepseek_resolve.GRADES))


def scrape_hobbydigi(listing_path):
    """Crawl one HobbyDigi listing and bucket rows by resolved grade.

    Returns `(buckets, stats)` where `buckets` maps grade -> rows. A kit with no
    trustworthy JAN, or one whose grade is not hg/mg/rg, is dropped: the importer
    skips a row without a `sku` anyway, and a guessed JAN would silently create a
    false cross-shop match.
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

    cards = []
    seen_urls = set()
    base = HOBBYDIGI_BASE_URL + listing_path
    page_num = 1
    blocked = False

    with sync_playwright() as p:
        while page_num <= HD_MAX_PAGES:
            try:
                batch = _hobbydigi_page_isolated(p, f"{base}?p={page_num}")
            except RuntimeError:
                if not cards:
                    raise
                # A partial catalogue still beats none: keep what we collected.
                print(f"   ⚠️  page {page_num} blocked by Cloudflare — keeping "
                      f"the {len(cards)} cards already collected")
                blocked = True
                break
            if not batch:
                print(f"   — page {page_num}: no cards, listing exhausted")
                break
            added = 0
            for card in batch:
                url = card.get("href") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                cards.append(card)
                added += 1
            print(f"   Page {page_num}: {len(batch)} cards (+{added} new)")
            if added == 0:
                print("   ⚠️  No new cards — pagination wrapped, stopping")
                break
            page_num += 1
            time.sleep(PAGE_WAIT_S)

    if page_num > HD_MAX_PAGES:
        print(f"   ⚠️  Safety limit of {HD_MAX_PAGES} pages reached — stopping")
    if not cards:
        return {}, {}

    _save_json(HOBBYDIGI_CARDS_FILENAME, cards)
    print(f"   💾 {len(cards)} raw cards → {HOBBYDIGI_CARDS_FILENAME}")

    resolved, stats = _resolve_hobbydigi(cards, api_key, catalogue, matches)
    stats["blocked_pages"] = blocked

    buckets = {grade: [] for grade in deepseek_resolve.GRADES}
    for card, item in zip(cards, resolved):
        if item["grade"] is not None and item["sku"]:
            buckets[item["grade"]].append(hobbydigi_row(card, item["sku"]))

    return buckets, stats


def _print_preview(products, limit=3):
    """First few saved rows, as a sanity check that the scrape looks sane."""
    for product in products[:limit]:
        print(f"  • {product['title'][:66]}")
        print(f"    💰 HK${product['price']}   🔗 {product['url'][:70]}")
    if len(products) > limit:
        print(f"\n  ... and {len(products) - limit} more")


def main(argv):
    print("=" * 70)
    print("  HOBBYLAND / ANIMES-PRO / HOBBYDIGI — GUNPLA CATALOG SCRAPER")
    print("=" * 70 + "\n")

    # Merge every category dict for CLI lookup
    all_cats = {**CATEGORIES, **ANIME_PRO_CATEGORIES, **HOBBYDIGI_CATEGORIES}

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
