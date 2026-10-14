#!/usr/bin/env python3
"""
Gundam series classification through the Jev decision model on OpenRouter,
with a DeepSeek fallback when Jev cannot answer.

Given a mobile suit name or model number (RX-93, 沙煞比, 風靈高達), ask which
of the 23 Gundam series listed in `jev_series.md` it belongs to. The answer
space is fixed and small, which is the shape Jev is built for: one `state`
(the kit name) and one typed `choice` question whose `criteria` map option ids
to descriptions. Jev weighs every option internally, but only the final
result is printed: the series name.

The criteria descriptions carry every alias a listing might use — Chinese and
English series titles, year, and representative mobile suits — because that is
the evidence the model matches against; a bare series name cannot recognise
"沙煞比". `unknown` is a real option, not a failure: a defined way to say
none-of-the-above is preferable to a forced wrong pick.

Jev calls on OpenRouter bill per input token, so an unfunded account answers
HTTP 402 and a dead key answers HTTP 401. The default `--engine auto` treats
both as "Jev cannot answer" and falls back to DeepSeek (`deepseek-chat`) —
the model this repo already uses for grade resolution — which answers the
same fixed choice question; `--engine jev` and `--engine deepseek` pin one
provider explicitly.

Usage:
  python3 scripts/jev_series.py "RX-93 ν高達"
  python3 scripts/jev_series.py "RX-78-2 高達" "沙煞比"
  python3 scripts/jev_series.py --json "巴巴托斯"

JEV_API_KEY is read from the environment or the repository `.env` (see
.env.example) and holds an OpenRouter API key — create one at
https://openrouter.ai/settings/keys.
DEEPSEEK_API_KEY is read the same way and is only needed for the DeepSeek
engine and the auto fallback.

Endpoint contract (openrouter.ai/docs/guides/community/jev): POST
https://openrouter.ai/api/alpha/decisions with `Authorization: Bearer` (an
OpenRouter API key) and `Content-Type: application/json`. Live responses are
flat — `{"model": "typesafe/jev-1.13-<date>", "answers": {"series":
{"type": "choice", "choice": <id>, "probabilities": {...}, "confidence":
<0-1>}}, "usage": {"input_tokens": <n>, "cost": <usd>}, "provider":
"TypeSafe"}` — and the older thejevai.com `data.result` envelope is still
unwrapped if one appears. HTTP 401 is a dead key, 402 an unfunded account,
422 a rejected request body, 429/529 transient retries. Requests carry an
explicit User-Agent: Cloudflare in front of thejevai.com used to answer
urllib's default one with `403 error code: 1010`, and identifying the script
is harmless elsewhere. The fallback posts a single chat completion to
https://api.deepseek.com/chat/completions and reads the message content as
`{"series": "<id>"}`.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

JEV_API_URL = "https://openrouter.ai/api/alpha/decisions"

# The `~typesafe/jev-latest` alias tracks the newest Jev release; the bare
# name without the `~` is rejected with HTTP 400. Overridable via JEV_MODEL.
JEV_MODEL = os.environ.get("JEV_MODEL", "~typesafe/jev-latest")
API_TIMEOUT_S = 30

# An explicit User-Agent rather than urllib's default signature, which
# Cloudflare in front of thejevai.com used to ban with `403 error code:
# 1010`; identifying the script is harmless on OpenRouter.
USER_AGENT = "jev_series/1.0"

# The DeepSeek fallback, mirroring deepseek_resolve.py: same endpoint and
# model, and the same longer timeout, because the chat model reasons over the
# whole 24-option criteria list.
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_TIMEOUT_S = 90

# --engine values; "auto" keeps Jev first and falls back on HTTP 402.
ENGINES = ("auto", "jev", "deepseek")

# The question id is echoed back in the response under `answers`.
QUESTION_ID = "series"

# Jev documents 429 "wait and retry" and 529 "wait and retry". A kit is one
# call — unlike the scraper there is no per-page budget worth defending — so
# the ladder is short and fixed.
RETRY_STATUSES = (429, 529)
RETRY_BACKOFF_S = (1, 2, 4)

# The series list from jev_series.md, in that order. Each entry is
# (id, display name, description): the id is the criteria key Jev echoes back,
# and the description is the evidence — Chinese and English titles, the era
# marker, and the mobile suits a listing might name instead of the series.
SERIES = (
    ("gundam_0079", "初代(0079)",
     "機動戰士高達 Mobile Suit Gundam (1979, UC 0079)：RX-78-2 初代高達、"
     "馬沙專用渣古、紅彗星、吉姆、古夫、德姆、阿寶、白色基地"),
    ("the_08th_ms_team", "08MS小隊",
     "機動戰士高達 第08MS小隊 Mobile Suit Gundam: The 08th MS Team "
     "(1996 OVA, UC 0079)：RX-79[G] 陸戰型高達、陸戰型吉姆、Ez8、古夫特裝型、"
     "阿普薩拉斯、斯羅·亞瑪達"),
    ("gundam_0080", "0080",
     "機動戰士高達0080 口袋裡的戰爭 Mobile Suit Gundam 0080: War in the "
     "Pocket (1989 OVA, UC 0079)：NT-1 亞歷克斯、高機動型渣古II改、"
     "京寶梵 Kampfer、巴尼"),
    ("gundam_0083", "0083",
     "機動戰士高達0083 星塵的回憶 Mobile Suit Gundam 0083: Stardust Memory "
     "(1991 OVA, UC 0083)：GP01、GP02A、GP03、卡圖·奧斯基、星塵作戰"),
    ("zeta", "Z",
     "機動戰士Z高達 Mobile Suit Zeta Gundam (1985, UC 0087)：Z高達 MSZ-006、"
     "百式、高達Mk-II、卡碧尼、漢布拉比、精神感應高達、嘉美尤"),
    ("zz", "ZZ",
     "機動戰士高達ZZ Mobile Suit Gundam ZZ (1986, UC 0088)：ZZ高達 MSZ-010、"
     "京密煞、卡碧尼Mk-II、巴烏、捷度"),
    ("chars_counterattack", "馬沙之反擊",
     "機動戰士高達 馬沙之反擊 Mobile Suit Gundam: Char's Counterattack "
     "(1988 劇場版, UC 0093)：ν高達 RX-93、沙煞比 MSN-04、積根、馬沙、阿寶"),
    ("unicorn", "獨角獸",
     "機動戰士高達UC 獨角獸 Mobile Suit Gundam Unicorn (2010-2014, UC 0096)："
     "獨角獸高達 RX-0、報喪女妖、新安州、剎帝利、傑斯塔、巴納吉"),
    ("hathaways_flash", "閃光凱薩衛",
     "機動戰士高達 閃光之凱薩衛 Mobile Suit Gundam: Hathaway's Flash "
     "(2021- 劇場版, UC 0105)：Ξ高達 Xi Gundam、潘娜洛佩 Penelope、凱薩衛·諾亞"),
    ("f91", "F91",
     "機動戰士高達F91 Mobile Suit Gundam F91 (1991 劇場版, UC 0123)："
     "F91 高達、十字骨先鋒、西布頓·亞諾、貝拉·羅娜"),
    ("victory", "V高達",
     "機動戰士V高達 Mobile Suit Victory Gundam (1993, UC 0153)：V高達、"
     "V2高達、胡索·艾賓、贊斯卡爾帝國"),
    ("seed", "SEED",
     "機動戰士高達SEED Mobile Suit Gundam SEED (2002, C.E. 71)：自由高達、"
     "正義高達、攻擊/突擊高達、天意高達、神盾高達、閃電高達、暴風高達、"
     "決鬥高達、煌·大和"),
    ("seed_destiny", "SEED Destiny",
     "機動戰士高達SEED DESTINY Mobile Suit Gundam SEED Destiny (2004, "
     "C.E. 73)：命運高達、衝擊/脈衝高達、傳說高達、無限正義高達、"
     "突擊自由/強襲自由高達、真·飛鳥"),
    ("seed_freedom", "SEED Freedom",
     "機動戰士高達SEED FREEDOM Mobile Suit Gundam SEED Freedom "
     "(2024 劇場版, C.E. 75)：飛昇自由高達 Rising Freedom、"
     "不朽正義高達 Immortal Justice、命運高達Spec II、黑騎士小隊"),
    ("gundam_00", "高達00",
     "機動戰士高達00 Mobile Suit Gundam 00 (2007, A.D. 2307)：能天使高達 "
     "Exia、力天使高達 Dynames、主天使高達 Kyrios、德天使高達 Virtue、"
     "00高達、剎那·F·清英"),
    ("iron_blooded_orphans", "鐵血的孤兒",
     "機動戰士高達 鐵血的孤兒 Mobile Suit Gundam: Iron-Blooded Orphans "
     "(2015, P.D.)：巴巴托斯/獵魔高達 Barbatos、天狼王型、古辛高達、格雷茲、"
     "三日月·奧格斯"),
    ("witch_from_mercury", "水星的魔女",
     "機動戰士高達 水星的魔女 Mobile Suit Gundam: The Witch from Mercury "
     "(2022, A.S.)：風靈高達 Aerial、迪蘭扎、蘇萊塔·墨丘利、米奧琳涅"),
    ("g_gundam", "機動武鬥傳 G高達",
     "機動武鬥傳G高達 Mobile Fighter G Gundam (1994, F.C.)：閃光高達 Shining、"
     "神高達/王者高達 God Gundam、東方不敗、多門·火州"),
    ("gundam_wing", "新機動戰記 高達W",
     "新機動戰記高達W Mobile Suit Gundam Wing (1995, A.C.)：飛翼高達 Wing、"
     "死神高達 Deathscythe、重裝高達 Heavyarms、沙漠高達 Sandrock、"
     "神龍高達 Shenlong、托爾吉斯 Tallgeese、艾比安 Epyon、希羅·尤爾"),
    ("gundam_x", "機動新世紀 高達X",
     "機動新世紀高達X After War Gundam X (1996, A.W.)：X高達、Double X、"
     "空中霸王、豹式、加洛特·蘭、蒂華"),
    ("turn_a", "(Turn A) 高達",
     "∀高達 Turn A Gundam (1999, C.C. 2345)：鬍鬚高達、蘇莫、羅蘭·瑟亞克、"
     "迪安娜女王、月之民"),
    ("build_fighters", "創戰者",
     "高達創戰者 Gundam Build Fighters (2013)：創建突擊高達 Build Strike、"
     "創建燃燒高達 Build Burning、熊霸 Beargguy、伊織政、模型對戰"),
    ("gquuuuuux", "GQUUUUUUX",
     "機動戰士Gundam GQuuuuuuX Mobile Suit Gundam GQuuuuuuX (2025)："
     "ジークアクス GQuuuuuuX、紅色高達、馬沙、新人類"),
    ("unknown", "無法確定",
     "唔屬於以上任何系列，或無法從機體名稱／型號辨識"),
)

# id -> (display name, description); derived so the two cannot drift apart.
SERIES_BY_ID = {series_id: (name, description)
                for series_id, name, description in SERIES}

_INSTRUCTIONS = (
    "以下係一件高達模型嘅機體名稱或型號。請判斷佢屬於邊個高達系列，"
    "並喺 criteria 入面揀最合適嘅一個選項；無法辨識就揀 unknown。")

_DEEPSEEK_SYSTEM_PROMPT = (
    "You are a Gunpla catalogue assistant. You identify Bandai Gundam model "
    "kits from retailer product titles and assign each kit to its Gundam "
    "series. You answer only what the title actually establishes.")

_DEEPSEEK_USER_TEMPLATE = """\
A Gunpla retailer listing names this kit:

{kit}

Which Gundam series does it belong to? Decide from the mobile suit, its model
number, the series title, or any alias mentioned in the listing.

Reply with JSON only, in exactly this shape:
{{"series": "<series id>"}}

Choose exactly one id from this list; no other value is valid:
{criteria}

Use "unknown" when the listing establishes none of the above. Do not guess."""


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
    directly and docker-compose inlines its own values — so the file is
    resolved relative to this module. A real environment variable wins, which
    keeps cron and CI able to override it.
    """
    return _read_env_file(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     ".env"),
        key)


def load_api_key():
    """JEV_API_KEY from the environment or the repository .env."""
    key = ((os.environ.get("JEV_API_KEY") or "").strip()
           or _env_file_value("JEV_API_KEY"))
    if not key:
        raise AuthError(
            "JEV_API_KEY is not set — create an OpenRouter key at "
            "https://openrouter.ai/settings/keys, then add it to the "
            "repository .env (see .env.example) or export it")
    return key


def _optional_deepseek_key():
    """DEEPSEEK_API_KEY when present, '' otherwise (auto fallback only)."""
    return ((os.environ.get("DEEPSEEK_API_KEY") or "").strip()
            or _env_file_value("DEEPSEEK_API_KEY"))


def load_deepseek_key():
    """DEEPSEEK_API_KEY from the environment or the repository .env."""
    key = _optional_deepseek_key()
    if not key:
        raise AuthError(
            "DEEPSEEK_API_KEY is not set — the DeepSeek engine needs it; "
            "add it to the repository .env (see .env.example) or export it")
    return key


def build_payload(kit_name, model=JEV_MODEL):
    """The OpenRouter Decisions API request body for one kit.

    `criteria` is the whole SERIES table (id -> description), well under the
    documented 255-option limit, and the question id is reused by the response.
    """
    return {
        "model": model,
        "state": kit_name,
        "questions": {
            QUESTION_ID: {
                "type": "choice",
                "instructions": _INSTRUCTIONS,
                "criteria": {series_id: description
                             for series_id, _name, description in SERIES},
            }
        },
    }


def _criteria_text():
    """The series table as prompt lines: id, display name, evidence."""
    return "\n".join(f"- {series_id}: {name} — {description}"
                     for series_id, name, description in SERIES)


def build_chat_payload(kit_name, model=DEEPSEEK_MODEL):
    """The DeepSeek chat request body for one kit.

    The same answer space as the Jev question, serialised for a chat model:
    every series id with its display name and the evidence to match on.
    """
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": _DEEPSEEK_SYSTEM_PROMPT},
            {"role": "user", "content": _DEEPSEEK_USER_TEMPLATE.format(
                kit=kit_name, criteria=_criteria_text())},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }


def _http_error_body(exc):
    """The response body of an HTTPError, collapsed, best-effort."""
    try:
        body = exc.read().decode("utf-8", "replace")
    except Exception:
        return ""
    return " ".join(body.split())[:300]


def _post(payload, api_key):
    """One Decisions API call, returned as parsed JSON.

    HTTP 401/403 is a dead key and raises AuthError before any retry can burn
    quota; a 422 is the endpoint rejecting the request shape and its body
    names the offending field, so it is surfaced rather than swallowed.
    """
    request = urllib.request.Request(
        JEV_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            detail = _http_error_body(exc)
            raise AuthError(
                f"OpenRouter rejected the API key (HTTP {exc.code})"
                + (f": {detail}" if detail else "")) from exc
        if exc.code == 422:
            raise RuntimeError(
                "OpenRouter rejected the request (HTTP 422): "
                f"{_http_error_body(exc)}") from exc
        raise


def _post_with_retry(payload, api_key):
    """POST the decision, waiting out 429/529 between attempts."""
    attempts = len(RETRY_BACKOFF_S) + 1
    for attempt in range(1, attempts + 1):
        try:
            return _post(payload, api_key)
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUSES or attempt == attempts:
                raise
            wait = RETRY_BACKOFF_S[attempt - 1]
            print(f"   ⚠️  OpenRouter returned HTTP {exc.code} (attempt "
                  f"{attempt}/{attempts}) — waiting {wait}s")
            time.sleep(wait)
    return None  # unreachable


def _post_chat(payload, api_key):
    """One DeepSeek chat completion, returned as the model's parsed JSON.

    Same failure mapping as the Jev call — 401/403 is a dead key — and no
    retry ladder, matching deepseek_resolve.py. The completion content is the
    model's answer document, e.g. `{"series": "build_fighters"}`.
    """
    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request,
                                    timeout=DEEPSEEK_TIMEOUT_S) as response:
            document = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            detail = _http_error_body(exc)
            raise AuthError(
                f"DeepSeek rejected the API key (HTTP {exc.code})"
                + (f": {detail}" if detail else "")) from exc
        raise
    try:
        return json.loads(document["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "DeepSeek response carries no usable completion: "
            f"{json.dumps(document, ensure_ascii=False)[:300]}") from exc


def _unwrap(document):
    """The decision payload out of a response envelope, when there is one.

    The OpenRouter Decisions API answers flat — `answers`, `usage`, and
    `provider` at the top level — so those documents pass through unchanged.
    The older thejevai.com surface nested the body under `data.result` with
    `data.creditsUsed` as its sibling; that envelope is still unwrapped. A
    non-zero `code` is an API-level failure even though the HTTP status was
    200.
    """
    if not isinstance(document, dict):
        return document
    code = document.get("code")
    if code is not None and code != 0:
        raise RuntimeError(
            f"Jev returned code {code}: {document.get('message')!r}")
    data = document.get("data")
    if isinstance(data, dict) and isinstance(data.get("result"), dict):
        return data["result"]
    return document


def _extract_choice(document):
    """Jev response -> the chosen series id for the `series` question."""
    answers = document.get("answers") if isinstance(document, dict) else None
    answer = answers.get(QUESTION_ID) if isinstance(answers, dict) else None
    if not isinstance(answer, dict):
        raise RuntimeError(
            f"Jev response carries no '{QUESTION_ID}' answer: "
            f"{json.dumps(document, ensure_ascii=False)[:300]}")
    choice = answer.get("choice")
    if choice not in SERIES_BY_ID:
        raise RuntimeError(
            f"Jev picked a series id outside the criteria: {choice!r}")
    return choice


def _extract_deepseek_choice(document):
    """DeepSeek completion -> the chosen series id."""
    choice = document.get("series") if isinstance(document, dict) else None
    if choice not in SERIES_BY_ID:
        raise RuntimeError(
            f"DeepSeek picked a series id outside the criteria: {choice!r}")
    return choice


def classify(kit_name, api_key, model=JEV_MODEL):
    """One kit name -> the final series decision.

    Jev weighs every option internally; only the result is returned — the
    input, the chosen series id, and its display name. Failure mapping
    (AuthError / HTTPError / RuntimeError) happens below and is left for the
    caller to report.
    """
    document = _post_with_retry(build_payload(kit_name, model), api_key)
    result = _unwrap(document)
    choice = _extract_choice(result)
    name, _description = SERIES_BY_ID[choice]
    return {"input": kit_name, "series": choice, "name": name}


def classify_deepseek(kit_name, api_key, model=DEEPSEEK_MODEL):
    """One kit name -> the final series decision, via DeepSeek.

    Same result shape as `classify`; selected with `--engine deepseek` or
    automatically when Jev answers HTTP 402 in `--engine auto`.
    """
    document = _post_chat(build_chat_payload(kit_name, model), api_key)
    choice = _extract_deepseek_choice(document)
    name, _description = SERIES_BY_ID[choice]
    return {"input": kit_name, "series": choice, "name": name}


USAGE = """\
Usage: python3 scripts/jev_series.py [options] <機體名稱或型號> [more ...]

Ask Jev (or DeepSeek) which Gundam series each kit belongs to and print the
series name. Example: python3 scripts/jev_series.py "RX-93 ν高達" "沙煞比"

Options:
      --json       print one JSON object per kit ({{input, series, name}})
      --engine E   auto | jev | deepseek (default auto). auto tries Jev
                   first and falls back to DeepSeek when Jev cannot answer
                   (no credits or a rejected key)
      --model ID   Jev model id (default {model})
  -h, --help       show this help

JEV_API_KEY (an OpenRouter API key) and DEEPSEEK_API_KEY are read from the
environment or the repository .env. Create the OpenRouter key at
https://openrouter.ai/settings/keys
""".format(model=JEV_MODEL)


def _parse_args(argv):
    """argv -> (names, options).

    A hand-rolled parse: four flags do not justify argparse's surface, and
    the sibling scraper CLI reads sys.argv the same way.
    """
    names = []
    options = {"json": False, "help": False, "model": JEV_MODEL,
               "engine": "auto"}
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--json":
            options["json"] = True
        elif arg in ("-h", "--help"):
            options["help"] = True
        elif arg == "--engine":
            if not rest:
                raise ValueError(
                    "--engine needs a value: auto, jev or deepseek")
            engine = rest.pop(0)
            if engine not in ENGINES:
                raise ValueError(
                    f"unknown engine {engine!r} — use auto, jev or deepseek")
            options["engine"] = engine
        elif arg == "--model":
            if not rest:
                raise ValueError("--model needs a model id")
            options["model"] = rest.pop(0)
        elif arg.startswith("-") and arg != "-":
            raise ValueError(f"unknown option {arg}")
        else:
            names.append(arg)
    return names, options


def _print_result(result, options):
    """The final result — one series name per kit, or one JSON object."""
    if options["json"]:
        print(json.dumps(result, ensure_ascii=False))
        return
    print(result["name"])


def _decide(kit_name, options, jev_key, deepseek_key):
    """Route one kit through the selected engine.

    In auto mode an account-level Jev failure — out of credits (HTTP 402) or
    a rejected key (401/403, mapped to AuthError) — falls back to DeepSeek
    when its key is available; everything else still surfaces.
    """
    if options["engine"] == "deepseek":
        return classify_deepseek(kit_name, deepseek_key)
    try:
        return classify(kit_name, jev_key, model=options["model"])
    except AuthError as exc:
        if options["engine"] != "auto" or not deepseek_key:
            raise
        print(f"   ⚠️  {exc} — falling back to DeepSeek", file=sys.stderr)
        return classify_deepseek(kit_name, deepseek_key)
    except urllib.error.HTTPError as exc:
        if options["engine"] != "auto" or exc.code != 402 or not deepseek_key:
            raise
        print("   ⚠️  Not enough OpenRouter credits for Jev (HTTP 402) — "
              "falling back to DeepSeek", file=sys.stderr)
        return classify_deepseek(kit_name, deepseek_key)


def main(argv):
    """CLI entry point. Returns the process exit code."""
    try:
        names, options = _parse_args(argv)
    except ValueError as exc:
        print(f"❌ {exc}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    if options["help"]:
        print(USAGE)
        return 0
    if not names:
        print(USAGE, file=sys.stderr)
        return 2

    try:
        if options["engine"] == "deepseek":
            jev_key, deepseek_key = "", load_deepseek_key()
        else:
            jev_key = load_api_key()
            deepseek_key = _optional_deepseek_key()
    except AuthError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    failed = False
    for name in names:
        try:
            result = _decide(name, options, jev_key, deepseek_key)
        except AuthError as exc:
            # A dead key fails every remaining kit; stop instead of repeating.
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        except urllib.error.HTTPError as exc:
            print(f"❌ {name}: HTTP {exc.code} "
                  f"{_http_error_body(exc)}".rstrip(), file=sys.stderr)
            failed = True
            continue
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"❌ {name}: {exc}", file=sys.stderr)
            failed = True
            continue
        _print_result(result, options)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
