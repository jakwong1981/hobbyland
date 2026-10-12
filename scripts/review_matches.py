#!/usr/bin/env python3
"""
scripts/review_matches.py — settle HobbyDigi product matches by hand, once.

The scraper can crawl HobbyDigi completely and grade every kit, but ~94% of its
listings carry no JAN, and no automatic matcher exceeds ~92% precision on this
catalogue (measured over 201 labeled cross-shop pairs). The residue is genuine
ambiguity — re-releases, P-Bandai versus retail, and dual transliterations such
as 麥拉薩 / 梅薩拉 both meaning Messala — which a person settles at a glance and
a model settles at ~90%.

So the model proposes, a human disposes. Decisions are persisted keyed by product
URL, which is stable, so later scraper runs are deterministic and free, and only
genuinely new products ever need review. A wrong match would produce a
confidently incorrect "cheapest shop" verdict, which is why nothing here is
accepted silently.

Usage:
  scripts/venv/bin/python scripts/review_matches.py              # review pending
  scripts/venv/bin/python scripts/review_matches.py --limit 20   # first 20 only
  scripts/venv/bin/python scripts/review_matches.py --list       # count, no API
  scripts/venv/bin/python scripts/review_matches.py --dir data   # explicit folder

Keys: y = accept the suggestion, 0-9 = accept that candidate instead,
      n = no match exists, s = skip (ask again next run), q = quit and save.
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import deepseek_resolve as dr
import hobbyland_scraper as scraper
import jan_lookup as jl

CANDIDATES_PER_ITEM = 12
CANDIDATE_FLOOR = 0.12

PROMPT = """Which ONE candidate is the exact same Bandai kit as the target?

Same kit means the same grade line, the same mobile suit, and the same
variant / colourway / version. Answer null when nothing matches — in particular
for a different colourway, plain versus Ver.Ka, an expansion set, a re-release
with a different barcode, or a different mobile suit.

Answer with JSON only:
{{"id": <candidate index, or null>, "reason": "<the attribute that decided it>"}}

TARGET
  Chinese title : {title}
  URL slug      : {slug}
  grade         : {grade}

CANDIDATES (from shops whose JAN is already trusted)
{candidates}
"""


def repo_data_dir():
    """The folder holding the database and the scraper's side-channel files."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_json(path, default):
    """Parse a JSON file, falling back to `default` when absent or malformed.

    Deliberately imposes no shape: the cards file is a list and the matches file
    is a dict, so each caller validates what it needs.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError) as exc:
        print(f"⚠️  ignoring unreadable {path}: {exc}")
        return default


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)


def slug_of(url):
    """The English product name HobbyDigi puts in its URL key."""
    return (url or "").rstrip("/").rsplit("/", 1)[-1].replace("-", " ")


def candidates_for(item, catalogue):
    """Cheap CJK pre-filter for recall; the model then makes the precise pick."""
    pool = catalogue.rows_for(item["grade"])
    title = item["title"]
    scored = sorted(
        ((jl._dice(jl.cjk_bigrams(title), jl.cjk_bigrams(candidate)), sku, candidate)
         for sku, candidate in pool),
        reverse=True)
    return [(dice, sku, candidate) for dice, sku, candidate in scored[:CANDIDATES_PER_ITEM]
            if dice > CANDIDATE_FLOOR]


def propose(item, candidates, api_key):
    """Ask the model to pick one candidate and justify it.

    It may only choose from the list, or decline. It is never asked for a
    barcode, which is the one thing it reliably fabricates.
    """
    body = "\n".join(f"  {i}. {text}" for i, (_, _, text) in enumerate(candidates))
    text = (PROMPT
            .replace("{title}", item["title"])
            .replace("{slug}", slug_of(item["url"]))
            .replace("{grade}", item["grade"])
            .replace("{candidates}", body or "  (none)"))
    request = urllib.request.Request(
        dr.DEEPSEEK_API_URL,
        data=json.dumps({
            "model": dr.DEEPSEEK_MODEL,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": text}],
        }).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(request, timeout=dr.API_TIMEOUT_S) as response:
        payload = json.loads(response.read().decode("utf-8"))
    document = json.loads(payload["choices"][0]["message"]["content"])
    index = document.get("id")
    try:
        index = int(index)
    except (TypeError, ValueError):
        index = None
    if index is not None and not (0 <= index < len(candidates)):
        index = None
    return index, str(document.get("reason") or "")


def pending_items(cards, grades_by_key, matches, catalogue):
    """Cards that are in scope, undecided, and not already solved by Tier 1."""
    out = []
    for card in cards:
        url = card.get("href") or ""
        title = card.get("title") or ""
        if not url or not title:
            continue
        if url in matches:
            continue
        if dr.jan_from_url(url):
            continue
        grade = dr.grade_or_none((grades_by_key.get(dr.cache_key(title)) or {}).get("grade"))
        if grade is None:
            continue
        if catalogue.lookup(title, grade)[0]:
            continue
        out.append({"url": url, "title": title, "grade": grade,
                    "price": card.get("price") or ""})
    return out


def render(position, total, item, candidates, suggested, reason):
    print("\n" + "─" * 74)
    print(f"[{position}/{total}]  grade={item['grade'].upper()}  "
          f"HK${item['price'] or '?'}")
    print(f"  HobbyDigi : {item['title']}")
    print(f"  slug      : {slug_of(item['url'])}")
    if suggested is None:
        print("  model     : no match — it declined to pick")
    else:
        print(f"  model     : #{suggested} — {reason}")
    print("  candidates:")
    for i, (dice, sku, text) in enumerate(candidates):
        marker = "  ← suggested" if i == suggested else ""
        print(f"    {i}. {sku}  (sim {dice:.2f})  {text[:56]}{marker}")
    if not candidates:
        print("    (none — the pre-filter found nothing similar)")
    print("─" * 74)


def ask(candidates, suggested):
    """One decision, or None to skip. Re-prompts on anything unparseable."""
    while True:
        try:
            raw = input("  [y] accept suggestion   [0-9] pick that candidate   "
                        "[n] no match   [s] skip   [q] quit & save\n  > ").strip().lower()
        except EOFError:
            return "quit"
        if raw in ("q", "quit"):
            return "quit"
        if raw == "s":
            return None
        if raw == "n":
            return "reject"
        if raw == "y":
            if suggested is None:
                print("  nothing was suggested — type a candidate number, or n")
                continue
            return ("accept", suggested)
        if raw.isdigit():
            index = int(raw)
            if 0 <= index < len(candidates):
                return ("accept", index)
            print(f"  no candidate #{index}")
            continue
        print("  y / 0-9 / n / s / q")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dir", default=None,
                        help="folder holding the database and scraper artifacts "
                             "(default: <repo>/data)")
    parser.add_argument("--limit", type=int, default=None,
                        help="review at most this many items")
    parser.add_argument("--list", action="store_true",
                        help="report what is pending without calling the API")
    args = parser.parse_args(argv)

    directory = args.dir or repo_data_dir()
    os.chdir(directory)

    cards = load_json(scraper.HOBBYDIGI_CARDS_FILENAME, [])
    if not isinstance(cards, list) or not cards:
        print(f"no cards in {os.path.join(directory, scraper.HOBBYDIGI_CARDS_FILENAME)}"
              f" — run the scraper first:\n  scripts/scrape-and-import.sh hd")
        return 1

    matches = load_json(scraper.HOBBYDIGI_MATCHES_FILENAME, {})
    if not isinstance(matches, dict):
        print(f"⚠️  {scraper.HOBBYDIGI_MATCHES_FILENAME} is not an object — ignoring it")
        matches = {}
    grades = load_json(dr.CACHE_FILENAME, {})
    if not isinstance(grades, dict):
        grades = {}
    db_path = os.path.join(directory, scraper.DATABASE_FILENAME)
    if not os.path.isfile(db_path):
        print(f"no database at {db_path} — import a CSV first")
        return 1
    # HobbyDigi's own rows are excluded from the candidate pool: their JANs are
    # derived by this matcher, so offering them back would be circular and could
    # let a wrong answer confirm itself.
    catalogue = jl.JanCatalogue.from_database(
        db_path, exclude_shops=(scraper.HOBBYDIGI_SHOP_CODE,))

    items = pending_items(cards, grades, matches, catalogue)
    accepted = sum(1 for m in matches.values() if m.get("sku"))
    rejected = len(matches) - accepted

    print(f"cards            : {len(cards)}")
    print(f"already decided  : {len(matches)}  ({accepted} accepted, {rejected} rejected)")
    print(f"pending review   : {len(items)}")
    print(f"catalogue        : {len(catalogue.entries)} trusted JANs")

    if args.list or not items:
        return 0
    # Captured before --limit slices, so the closing summary reports what is
    # still outstanding overall rather than just within this session.
    pending_total = len(items)
    if args.limit:
        items = items[:args.limit]

    api_key = dr.load_api_key()
    total = len(items)
    decided = accepted_now = rejected_now = 0

    for position, item in enumerate(items, start=1):
        candidates = candidates_for(item, catalogue)
        try:
            suggested, reason = propose(item, candidates, api_key)
        except dr.AuthError as exc:
            print(f"\n❌ {exc}")
            break
        except Exception as exc:
            print(f"\n⚠️  proposal failed for {item['title'][:40]}: {exc} — skipping")
            continue

        render(position, total, item, candidates, suggested, reason)
        decision = ask(candidates, suggested)
        if decision == "quit":
            break
        if decision is None:
            continue

        decided += 1
        if decision == "reject":
            matches[item["url"]] = {
                "status": "rejected", "sku": None, "grade": item["grade"],
                "reason": reason, "decided_at": _now(),
            }
            rejected_now += 1
        else:
            _, index = decision
            dice, sku, text = candidates[index]
            matches[item["url"]] = {
                "status": "accepted", "sku": sku, "grade": item["grade"],
                "matched_title": text, "similarity": round(dice, 3),
                "reason": reason, "decided_at": _now(),
            }
            accepted_now += 1
        # Saved after every answer so an interrupted session loses nothing.
        save_json(scraper.HOBBYDIGI_MATCHES_FILENAME, matches)

    print(f"\n✅ reviewed {decided} — accepted {accepted_now}, rejected {rejected_now}")
    print(f"   {pending_total - decided} still pending; re-run to continue")
    print(f"   decisions → {os.path.join(directory, scraper.HOBBYDIGI_MATCHES_FILENAME)}")
    if accepted_now:
        print("   re-run the scraper to pick them up:  scripts/scrape-and-import.sh hd")
    return 0


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(130)
