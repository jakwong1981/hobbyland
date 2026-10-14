# HobbyDigi / Cloudflare — Diagnosis and Remediation Plan

Status: **proposed**, not implemented. Owner: scraper (`scripts/hobbyland_scraper.py`).

---

## 1. The question that was asked

> Can we bypass Cloudflare by resolving browser and extension conflicts:
> 1. disable ad blockers / extensions that modify User-Agent or canvas fingerprint,
> 2. enable JavaScript and cookies,
> 3. try incognito / clear site cache?

### Answer: no, not by itself — but two of the three expose real bugs worth fixing.

That list is Cloudflare's **end-user** troubleshooting guidance for a *human* browser. The scraper
is not a human browser. Each step maps onto the automation as follows.

| # | Proposed step | Automation analogue | Status in this repo |
|---|---|---|---|
| 1 | Disable extensions that modify User-Agent / fingerprint | Stop overriding `user_agent`; let the engine report one coherent identity | **Real bug.** See §2.1 |
| 2 | Enable JavaScript and cookies | Playwright defaults | Already satisfied. No route interception, no `java_script_enabled=False`, cookies on. Nothing to do |
| 3 | Incognito / clear site cache to escape the challenge loop | Persistent profile + invalidate a stale `cf_clearance` jar | **Real bug.** See §2.2. Note "incognito" is the *wrong* direction: it discards the clearance |

Fixing 1 and 3 removes self-inflicted penalties and stops the loop symptom. It does **not** make
Cloudflare accept the automation — see §3.

---

## 2. Evidence

### 2.1 The browser contradicts itself (measured, not assumed)

A local HTTP echo server was requested from the exact context the scraper builds
(`args=HD_BROWSER_ARGS`, `user_agent=USER_AGENT`, `locale="zh-HK"`, 1920×1080). What the server
received:

```
User-Agent                  : ... Chrome/152.0.0.0 Safari/537.36        <- overridden
sec-ch-ua                   : "HeadlessChrome";v="153", "Not_A Brand";v="8", "Chromium";v="153"
sec-ch-ua-full-version-list : (absent)
navigator.userAgentData.getHighEntropyValues -> HeadlessChrome 153.0.8010.12 / Chromium 153.0.8010.12
```

Playwright's `new_context(user_agent=...)` rewrites the `User-Agent` header and
`navigator.userAgent`, but **not** the Client Hints headers or `navigator.userAgentData`. The
result is one request that simultaneously claims:

- Chrome 152 (User-Agent header)
- Chromium 153 (`sec-ch-ua`)
- **HeadlessChrome** 153 (`sec-ch-ua` brand list — leaks headlessness the flag was meant to hide)

A User-Agent that disagrees with the Client Hints in the same request is a textbook tampering
signal, and it is scored as such. This is precisely the failure mode the proposed step 1 describes,
produced by our own code rather than by an extension.

Secondary signals from the same measurement:

```
navigator.plugins.length : 0     (real Chrome on macOS: 5, incl. the PDF viewers)
navigator.webdriver      : False (the launch arg does work)
```

Affected call sites — only **one** is in a Cloudflare zone:

| Line | Context | Zone | UA override matters? |
|---|---|---|---|
| 366 | `_fetch_page` headers | hobbylandeshop.com — README: no bot challenge | No |
| 529 | `scrape_animes_pro_category` context | animes-pro.com — Shopify `__shopify_bv_challenge`, **not** Cloudflare | Marginal |
| **858** | `_hobbydigi_page_isolated` context | **www.hobbydigi.com — Cloudflare** | **Yes** |
| 1188 | `fetch_fookle_page` headers | WooCommerce Store API — README: no bot challenge | No |

### 2.2 A poisoned jar is replayed forever, with no invalidation path

`_hobbydigi_state_path()` (line 764) returns any existing `data/hobbydigi_state.json`.
`_hobbydigi_page_isolated()` (line 831) replays it into every one of the
`HD_BROWSER_ATTEMPTS = 3` fresh browsers.

`_hobbydigi_save_state()` (line 773) correctly refuses to *overwrite* a working jar with a
challenged one. But nothing ever *retires* a jar that has stopped working. `cf_clearance` is bound
to the IP and the exact User-Agent and expires on Cloudflare's schedule (README). So once the jar
goes stale — IP changed, UA changed, Cloudflare rotated the secret — every attempt inherits the
same dead credential, all three browsers fail identically, and the crawl falls back to cached cards.
That is the "infinite challenge loop" the proposed step 3 describes.

Current jar on disk (`data/hobbydigi_state.json`, 40 KB, 21 cookies):

```
cf_clearance   .hobbydigi.com   expires=1823516083   (nominal expiry far in the future)
_gat           .hobbydigi.com   expires=1791980335   (already expired at read time)
+ mage-cache-storage, hobbydigi_session_id, _ga*, and 6 third-party cookies
  (.youtube.com, .doubleclick.net) captured incidentally
```

Two problems visible here:

- **Nominal expiry is not validity.** `cf_clearance` carries a long `expires` but Cloudflare
  invalidates it server-side long before. A TTL check on the cookie field is necessary but not
  sufficient.
- **`storage_state` replays cookies + localStorage only.** It drops the HTTP cache, IndexedDB,
  service workers, and the profile directory. So every launch re-downloads Cloudflare's challenge
  orchestration script cold — itself a "first visit from a brand-new client" signal, and the
  opposite of what a returning legitimate visitor looks like.

### 2.3 Request volume is the thing that gets the IP flagged

The README records the mechanism: *"Cloudflare budgets roughly two or three requests per cookie
jar, and the budget does not recover with time"*, and the remedy: *"a fresh browser context per
page gets a fresh budget"*.

That remedy works, but it is expensive. A 28-page crawl currently launches **28 browsers**
(up to 84 with retries), each a fresh TLS handshake and a fresh client profile from one IP. The
README also records a far cheaper path that is **not currently used**:

> Same-origin `fetch()` from an already-cleared page also works.

One clearance + 28 in-page `fetch()` calls is roughly an order of magnitude fewer navigations than
28 browser launches. Fewer requests is both the cheapest reliability win and the most
defensible posture.

### 2.4 The operator's intent is explicit

`https://www.hobbydigi.com/robots.txt` was fetched directly. It does **not** return a robots file;
it returns a Cloudflare challenge page with:

```
cType: 'interactive'      cZone: 'www.hobbydigi.com'
cUPMDTk: "/robots.txt?__cf_chl_tk=..."
```

An interactive managed challenge on the robots file means the operator has put a human-verification
wall in front of the machine-readable access policy itself. Combined with the README's findings
(`/graphql` 404, `/rest/V1/products` 403, detail pages never clear), the site is configured to
decline unattended machine access.

This plan therefore treats **permission as the primary fix** (§4, Phase 0) and hygiene as
secondary. It does not treat defeating the challenge as a goal.

---

## 3. What hygiene cannot fix

Even with a perfectly coherent fingerprint, Cloudflare still scores:

| Signal | Fixable by steps 1–3? |
|---|---|
| `HeadlessChrome` in Client Hints | No — requires headed, or a real Chrome channel |
| `navigator.plugins.length === 0` | No |
| No profile history / cold cache on every launch | Partly — Phase 3 |
| **IP reputation** | **No.** README, measured: *"once the IP is flagged, not even a real window passes"* |
| Passive managed challenge with **no tick box** | **No.** `_hobbydigi_ghost_click` has nothing to click; the README already measured this failing |

The last row is decisive. The dominant failure mode documented in the README is a challenge that
**cannot be clicked at all**, served to a browser that has already done everything right. Steps 1–3
address none of that. Anyone promising they "bypass Cloudflare" is describing a different site.

### Out of scope — will not be implemented

Deliberate detection-evasion against a protection the operator enabled:

- stealth / anti-detect browser plugins, `undetected-chromedriver`-style patches
- canvas / WebGL / font fingerprint spoofing
- CAPTCHA- or Turnstile-solving services
- rotating residential / mobile proxy pools to launder IP reputation
- forging `sec-ch-ua` client hints to hide headlessness

Phase 1 below *removes* a false UA. It does not *construct* a fake one. That line is the whole
distinction, and it is the one this plan holds.

---

## 4. Plan

Ordered by (value ÷ risk). Phases 1–3 are independent and can land separately.

### Phase 0 — Get permission or a feed *(primary fix; not code)*

The only change that removes the problem rather than managing it.

- [ ] **P0.1** Email HobbyDigi. Ask for either (a) written permission to crawl the Gundam listing
      at a stated rate, or (b) a product/price feed. They are a retailer; a price-comparison
      dashboard is free referral traffic, and CSV/XML/Google-Shopping feeds are routine in this
      industry. Offer: fixed low frequency (daily), attributed links, immediate opt-out honouring.
- [ ] **P0.2** If a feed arrives, add it as a `hobbydigi` source in `scrape_hobbydigi()` and retire
      the entire Cloudflare section of the scraper. Keep the Playwright path as fallback only.
- [ ] **P0.3** If permission is **refused**, stop crawling. The dashboard already degrades
      gracefully — `_load_cached_cards()` plus the `blocked` flag in `stats["blocked_pages"]`
      render HobbyDigi as stale rather than broken. Document the refusal in README §"HobbyDigi
      matching" and drop Phases 1–3.
- [ ] **P0.4** Record the outcome in `docs/TESTING.md` under a dated entry, as prior findings are.

**Why this is first:** the other three shops are all reached legitimately — Hobbyland's JSON API,
Fookle's WooCommerce Store API, Animes-Pro's rendered listings. HobbyDigi is the sole exception,
and it is the sole one consuming an LLM (`deepseek_resolve`) plus a human-in-the-loop review step
to compensate for the data it cannot get. A feed collapses that whole cost centre.

### Phase 1 — One coherent identity *(low risk, fixes §2.1)*

- [ ] **P1.1** Stop overriding the User-Agent for the HobbyDigi browser context (line 858). Drop
      `user_agent=USER_AGENT` from that `new_context()` call so the `User-Agent` header,
      `sec-ch-ua`, and `navigator.userAgentData` all report the same engine build.
      Leave lines 366 / 529 / 1188 alone — none is a Cloudflare zone (§2.1 table).
- [ ] **P1.2** Record the UA actually used into the state file at save time. `_hobbydigi_save_state`
      already writes `storage_state`; extend it to persist `{"user_agent": <real UA>}` alongside,
      and have `_hobbydigi_state_path` / the replay path pass that same UA back. This keeps the jar
      bound to the identity that earned it, which is what `cf_clearance` requires, without
      hardcoding a version that goes stale every Playwright upgrade.
- [ ] **P1.3** Prefer the real Chrome channel when it is installed: `channel="chrome"` on launch,
      falling back to bundled Chromium. A branded build carries the plugin list and client hints
      that bundled Chromium lacks (§3). This is *using a standard browser*, not spoofing one.
      Gate behind `HD_BROWSER_CHANNEL` so Docker/CI can pin it off.
- [ ] **P1.4** Note the constraint in the docstring: headless and headed report different real UAs
      (`HeadlessChrome/…` vs `Chrome/…`), so a jar earned headed will not replay headless. P1.2 makes
      that detectable instead of mysterious.

Tests: `test_hobbyland_scraper.py` currently asserts the override is passed
(`test_a_saved_jar_is_replayed_into_the_fresh_browser`, line 422; `test_hobbydigi_launches_headed_by_default`,
line 498). Update those two, add:
- a context is built with **no** `user_agent` kwarg when no jar exists
- the jar's recorded UA **is** passed when one exists
- a jar recorded under a different UA is treated as stale (see P3.2)

### Phase 2 — Ten times fewer requests *(highest value, fixes §2.3)*

- [ ] **P2.1** Add `_hobbydigi_fetch_page(page, url)`: same-origin `page.evaluate` issuing
      `fetch(url, {credentials: 'same-origin'})`, returning `response.text`, then parse with the
      existing `_HOBBYDIGI_CARD_JS` logic via `DOMParser`. The README already documents this path
      working from a cleared page.
- [ ] **P2.2** Restructure `scrape_hobbydigi` (line 1018): clear the challenge **once** in one
      browser, then walk `?p=1..n` with in-page `fetch` instead of calling
      `_hobbydigi_page_isolated` per page. Keep `HD_PAGE_WAIT_S = 6` between fetches — the delay is
      the politeness contract, not a workaround.
- [ ] **P2.3** Retain `_hobbydigi_page_isolated` as the fallback for when the long-lived page does
      get challenged mid-crawl: on failure, relaunch, re-clear, resume from the failed page number.
      The existing partial-catalogue salvage (`_load_cached_cards`) stays as the last resort.
- [ ] **P2.4** Detect the mid-crawl block by checking the fetched HTML for the interstitial
      markers already used in `_hobbydigi_challenged` (`稍候`, `moment`), since there is no
      `page.title()` on a fetch response.

Tests: cards parsed identically from a fetched HTML string as from a live DOM; a challenge marker
in a fetched body triggers relaunch-and-resume, not a silent empty page; resume starts at the failed
page, not page 1.

### Phase 3 — Session persistence and jar retirement *(fixes §2.2)*

- [ ] **P3.1** Replace cookie-only `storage_state` with a persistent profile:
      `launch_persistent_context(user_data_dir=<data/hobbydigi_profile>, …)`. This keeps the HTTP
      cache, IndexedDB, service workers, and profile continuity — so a returning client looks
      returning, and Cloudflare's orchestration script is not re-fetched cold on every launch.
      The directory must be gitignored alongside `data/hobbydigi_state.json` (it is a session
      credential bound to this IP and UA — the README already makes that point).
- [ ] **P3.2** Add jar/profile validity checks in `_hobbydigi_state_path`, so a dead credential
      stops being replayed into all three retry browsers:
      - recorded UA ≠ current real UA → stale
      - `cf_clearance` absent → stale (already implied by `_hobbydigi_save_state`)
      - `cf_clearance` older than `HD_CLEARANCE_MAX_AGE_S` (new constant, suggest 6 h) → stale
      - **all three browser attempts failed with the jar loaded** → quarantine: rename to
        `.quarantined`, log, and retry the page once with no jar, so the next run starts clean
        instead of inheriting the loop
- [ ] **P3.3** Surface the decision. `_hobbydigi_page_isolated` should log which jar it used
      (fresh / replayed / quarantined) so a stale-credential loop is legible in the crawl output
      rather than presenting as three identical unexplained blocks.
- [ ] **P3.4** Prune incidental third-party cookies (`.youtube.com`, `.doubleclick.net`, `_ga*`,
      `_gcl_au`) before saving. They are not needed for clearance, they enlarge the credential
      file, and they leak unrelated tracking identifiers into `data/`.

Tests: stale-by-UA and stale-by-age both fall through to a clean context; quarantine renames the
file and the retry runs jar-less; a valid jar is still replayed (regression on line 422's intent);
third-party cookies are absent from a newly saved state file.

### Phase 4 — Documentation

- [ ] **P4.1** README §"HobbyDigi matching": replace the measures table with the post-change
      reality — one clearance per crawl via in-page fetch, persistent profile, jar retirement rules.
      Keep the measured numbers (they are the value of that section) and add the §2.1 Client Hints
      finding, which is new and explains *why* the UA override was removed.
- [ ] **P4.2** README: state the Phase 0 outcome explicitly, including the `/robots.txt`
      interactive-challenge finding (§2.4), so a future contributor does not re-derive it.
- [ ] **P4.3** `docs/TESTING.md`: dated entry with the new integration-test rows.
- [ ] **P4.4** `docs/DEPLOYMENT.md`: document `HD_BROWSER_CHANNEL` and the
      `data/hobbydigi_profile` volume; note that a persistent profile is host-bound, so a Docker
      crawl and a host crawl need separate profiles.

---

## 5. Verification

| ID | Scenario | Preconditions | Action | Pass criteria |
|---|---|---|---|---|
| CF-01 | Identity coherence | Phase 1 | Local echo server + scraper context builder | `User-Agent`, `sec-ch-ua`, `navigator.userAgentData.brands` all report the same brand and major version; no `HeadlessChrome` in headed mode |
| CF-02 | UA binding survives restart | Phase 1, a cleared jar on disk | Save, relaunch, replay | Replay passes the recorded UA; a hand-edited UA in the jar → jar treated as stale |
| CF-03 | Request volume | Phase 2 | Full `hd` crawl, count navigations | ≤ 2 top-level navigations for a 28-page crawl (previously 28–84 browser launches) |
| CF-04 | Mid-crawl block recovery | Phase 2 | Inject an interstitial body into fetch #10 | Browser relaunched, challenge re-cleared, crawl **resumes at page 10**, card total matches the pre-injection run |
| CF-05 | Jar retirement | Phase 3 | Age a jar past `HD_CLEARANCE_MAX_AGE_S` | Crawl logs "stale", starts clean, does not replay the aged jar into any of the 3 attempts |
| CF-06 | Loop broken | Phase 3 | Valid-looking jar that Cloudflare rejects | After 3 failures the jar is quarantined (file renamed) and one jar-less retry runs |
| CF-07 | Profile hygiene | Phase 3 | Inspect a freshly saved state file | No `.youtube.com` / `.doubleclick.net` / `_ga*` / `_gcl_au` cookies; `cf_clearance` present |
| CF-08 | Graceful degradation | none | Crawl with the IP flagged (or `HD_HEADLESS=1` in Docker) | No traceback, no `EOFError`; falls back to `_load_cached_cards()`; `stats["blocked_pages"]` is truthy; CSVs still written |
| CF-09 | Regression | all | `./venv/bin/python -m pytest test_hobbyland_scraper.py` | All existing tests pass, with the two Phase 1 assertions updated rather than deleted |

CF-08 is the one that matters most for unattended runs: the current code already fails safe
(`_hobbydigi_prompt_human` guards on `sys.stdin.isatty()`), and none of Phases 1–3 may regress that.

---

## 6. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Removing the UA override changes which jar is valid, invalidating the current `data/hobbydigi_state.json` on first run | **Certain** | Expected. One human tick re-earns it; P1.2 makes the binding explicit thereafter. Note it in the commit message |
| `channel="chrome"` unavailable in the Docker image | High | P1.3 falls back to bundled Chromium; `HD_BROWSER_CHANNEL` pins it off in `Dockerfile` |
| Persistent profile grows unbounded on disk | Medium | Cap or prune `data/hobbydigi_profile`; document in `docs/DEPLOYMENT.md` |
| In-page fetch returns a partial/`noindex` variant of the listing | Medium | CF-03/CF-04 compare card counts and titles against the navigation path before the navigation path is removed |
| Phases 1–3 raise the pass rate enough to encourage more frequent crawling, which re-flags the IP | Medium | Keep `HD_PAGE_WAIT_S = 6`; do not raise crawl frequency. Phase 2's *purpose* is fewer requests, not faster ones |
| **HobbyDigi declines permission (P0.3)** | **Real possibility** | Honour it. The cached-card fallback already renders the dashboard correctly with stale HobbyDigi data |

---

## 7. Summary

The three proposed steps are correct advice for a person whose browser is stuck on a challenge, and
two of them translate into genuine defects here: a self-contradictory User-Agent (§2.1) and a stale
`cf_clearance` jar with no invalidation path (§2.2). Both are worth fixing, and both are fixes to
*self-inflicted* breakage.

Neither is a bypass. The failure mode the README actually documents — a passive managed challenge
with no tick box, served to a browser that already did everything right, on a flagged IP — is
untouched by browser hygiene. And the operator has challenged `/robots.txt` itself (§2.4), which
reads as a deliberate decline of unattended machine access.

So: **Phase 0 asks the shop.** Phases 1–3 make the scraper coherent, ten times quieter, and unable
to loop on a dead credential — which is worth doing whether or not permission arrives, because it
also reduces load on a third party's server. Evasion tooling is out of scope, and if the answer to
Phase 0 is no, the correct outcome is a stale HobbyDigi column, not a cleverer scraper.
