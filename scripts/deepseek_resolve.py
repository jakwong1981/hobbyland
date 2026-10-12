#!/usr/bin/env python3
"""
DeepSeek-assisted grade resolution.

Some shops publish no grade taxonomy on their listing pages. HobbyDigi.com is
one: its Gundam listing mixes HG, MG, MGSD, PG and 1/100 kits with no facet the
crawler can rely on, and the dashboard groups strictly by hg / mg / rg.

This module resolves that one field from the product title. It deliberately does
**not** resolve JAN barcodes. An LLM asked to recall a 13-digit barcode
fabricates one — measured at 0/3 against ground truth on this catalogue, with
sequential inventions (`…656789`, `…656796`, `…656802`) and a zero-padded
placeholder returned for three different products. Barcodes therefore come only
from a shop's own data (an API field or a product URL key) or from
`jan_lookup`, which inherits a verified JAN by matching against catalogues
already in the database.

Grade answers are cached so repeated runs stay free and deterministic.
"""

import json
import os
import re
import urllib.error
import urllib.request

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
API_TIMEOUT_S = 90

# Exactly 13 digits with a Japanese GS1 prefix, and nothing adjacent.
JAN_RE = re.compile(r"^(4\d{12})$")

GRADES = ("hg", "mg", "rg")

CACHE_FILENAME = "hobbydigi_resolve_cache.json"

BATCH_SIZE = 20

# Bracketed stock prefixes and trailing promotional parentheticals carry no
# product identity and measurably degrade resolution, so they are stripped
# before prompting. The raw title is what gets written to the CSV.
_TITLE_NOISE_RE = re.compile(
    r"^\s*[\[【][^\]】]*[\]】]\s*"          # leading [保証有貨] / 【現貨】
    r"|[（(][^）)]*(?:換購|優惠碼|滿\$|購物車|結帳|贈送|限量)[^）)]*[）)]"
)

_SYSTEM_PROMPT = (
    "You are a Gunpla catalogue assistant. You identify Bandai Gundam model kits "
    "from retailer product titles and classify each kit's grade. You answer only "
    "what the title actually establishes."
)

_USER_PROMPT_TEMPLATE = """\
For each numbered product title, return one entry.

Reply with JSON only, in exactly this shape:
{{"results": [{{"id": 1, "grade": "mg"}}]}}

Rules for "grade":
- "hg" = High Grade 1/144.
- "rg" = Real Grade 1/144.
- "mg" = Master Grade 1/100. Classify MGSD as "mg".
- Return null for PG, PG Unleashed, SD, EG, First Grade, Mega Size, plain 1/100
  or 1/60 kits that are not Master Grade, Figure-rise, completed figures, tools,
  and anything else that is not an HG / RG / MG model kit.
- Return null when the title does not make the grade clear. Do not guess.

Return exactly one entry per id, in the same order.

Titles:
{titles}"""


class AuthError(Exception):
    """Credential failure. Not a RuntimeError, so it is never retried."""


def _read_env_file(path, key):
    """Value of `key` in a dotenv file, or '' when absent or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == key:
                    return value.strip().strip("'\"")
    except OSError:
        return ""
    return ""


def _env_file_value(key):
    """Read `key` from the repository `.env`.

    Nothing else in this repo loads `.env` — the backend reads `process.env`
    directly and docker-compose inlines its own values — and the scraper's
    working directory is the CSV folder rather than the repo root, so the file
    is resolved relative to this module. A real environment variable wins, which
    keeps cron and CI able to override it.
    """
    return _read_env_file(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     ".env"),
        key)


def load_api_key():
    """DEEPSEEK_API_KEY from the environment or the repository .env."""
    key = ((os.environ.get("DEEPSEEK_API_KEY") or "").strip()
           or _env_file_value("DEEPSEEK_API_KEY"))
    if not key:
        raise AuthError(
            "DEEPSEEK_API_KEY is not set — add it to the repository .env "
            "(see .env.example) or export it before running the 'hd' category")
    return key


def ean13_check_digit_ok(code):
    """True when `code` satisfies the EAN-13 mod-10 check digit."""
    if not code or not code.isdigit() or len(code) != 13:
        return False
    digits = [int(c) for c in code]
    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == digits[12]


def is_plausible_jan(code):
    """Validate a JAN by shape and check digit, returning `(code or '', reason)`.

    Every 477 of the real JANs in this catalogue pass, and every single-digit
    alteration of them fails, so the check digit is a strong filter. It is the
    last line of defence whichever source supplied the code.
    """
    code = (code or "").strip()
    if not JAN_RE.match(code):
        return "", "not a 13-digit Japanese JAN"
    if not ean13_check_digit_ok(code):
        return "", "check digit failed"
    return code, ""


def clean_title_for_prompt(title):
    """Strip stock brackets and promotional parentheticals from a title."""
    cleaned = _TITLE_NOISE_RE.sub(" ", title or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_title(title):
    """Case-folded, whitespace-collapsed, punctuation-free."""
    folded = (title or "").casefold()
    return re.sub(r"[\s\-_·・。，,\.]+", "", folded)


def cache_key(title):
    """Key a resolution by what is actually sent to the model.

    Two listings of the same kit that differ only by a stock bracket share one
    entry, and a cached answer always corresponds to the prompt that produced it.
    """
    return normalize_title(clean_title_for_prompt(title))


def jan_from_url(url):
    """JAN used as a Magento URL key, e.g. .../gundam/4580886841165."""
    match = re.search(r"(?:^|/)(4\d{12})(?:$|[?#])", url or "")
    if not match:
        return ""
    code, _ = is_plausible_jan(match.group(1))
    return code


def grade_or_none(value):
    """A known grade, or None."""
    value = (value or "").strip().lower()
    return value if value in GRADES else None


class ResolveCache:
    """Title -> resolved grade, persisted so cron runs stay free and stable."""

    def __init__(self, path=CACHE_FILENAME):
        self.path = path
        self.entries = {}
        self.hits = 0
        self.misses = 0
        self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(loaded, dict):
            self.entries = loaded

    def get(self, title):
        entry = self.entries.get(cache_key(title))
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        return entry

    def put(self, title, grade, source, model=""):
        self.entries[cache_key(title)] = {
            "grade": grade,
            "source": source,
            "model": model,
        }

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, ensure_ascii=False, indent=1,
                          sort_keys=True)
        except OSError as exc:
            print(f"   ⚠️  could not write cache {self.path}: {exc}")


def _post_chat(messages, api_key):
    """One DeepSeek chat completion, returned as parsed JSON."""
    body = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT_S) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthError(
                f"DeepSeek rejected the API key (HTTP {exc.code})") from exc
        raise
    return json.loads(payload["choices"][0]["message"]["content"])


def _parse_results(document, expected_ids):
    """Model output -> {id: grade or None}, tolerating shape drift."""
    items = document.get("results") if isinstance(document, dict) else document
    if not isinstance(items, list):
        raise ValueError(
            f"unexpected DeepSeek response shape: {type(items).__name__}")
    parsed = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if item_id in expected_ids:
            parsed[item_id] = grade_or_none(item.get("grade"))
    return parsed


def resolve_batch(titles, api_key):
    """Resolve up to BATCH_SIZE titles in one call.

    Returns `{index: grade or None}` keyed by position in `titles`. Entries the
    model omitted or misnumbered are simply absent, so the caller abstains.
    """
    numbered = "\n".join(f"{i + 1}. {clean_title_for_prompt(t)}"
                         for i, t in enumerate(titles))
    document = _post_chat(
        [{"role": "system", "content": _SYSTEM_PROMPT},
         {"role": "user",
          "content": _USER_PROMPT_TEMPLATE.format(titles=numbered)}],
        api_key,
    )
    expected = set(range(1, len(titles) + 1))
    return {item_id - 1: grade
            for item_id, grade in _parse_results(document, expected).items()}


def resolve_grades(titles, api_key):
    """Resolve every title in batches, returning a list aligned with `titles`.

    Each element is a grade string or None.
    """
    grades = []
    for start in range(0, len(titles), BATCH_SIZE):
        chunk = titles[start:start + BATCH_SIZE]
        answers = resolve_batch(chunk, api_key)
        grades.extend(answers.get(offset) for offset in range(len(chunk)))
    return grades
