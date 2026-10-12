#!/usr/bin/env python3
"""
Inherit a verified JAN from the catalogues we already trust.

hobbydigi.com publishes no JAN for ~89% of its listings, its detail pages and
GraphQL/REST endpoints are all unreachable, and an LLM asked to recall a
13-digit barcode fabricates one (measured: 0/3 against ground truth, with
sequential and zero-padded inventions). So instead of guessing a barcode, this
module matches a foreign title against titles already in the database — whose
`sku` was supplied by a shop API or read off the retailer's own page — and
inherits that verified JAN.

Matching is deliberately precision-first. A false match produces a wrong
cross-shop price comparison, which is worse than no comparison at all, so the
score requires a shared model code or a strong CJK overlap and abstains
otherwise. `evaluate()` reports precision and recall over the labeled pairs
already present in the database: every (grade, sku) carried by two shops is a
known match, and every other candidate with a different sku is a known non-match.
"""

import re
import sqlite3

# Shop-decoration that carries no product identity.
_NOISE_RE = re.compile(
    r"[\[【（(][^\]】）)]*(?:現貨|现货|保証有貨|保證有貨|預訂|預購|訂貨|限購|換購|優惠碼|"
    r"購物車|結帳|贈送|限量|现货|IN STOCK|PRE-?ORDER)[^\]】）)]*[\]】）)]"
    r"|\bBANDAI\b|\bBandai\b|組裝模型|拼装模型|模型|Y\d{3,4}|\(BAN\d{5,7}\)|BAN\d{5,7}"
    r"|4\d{12}|\bVER\.?\b|\bVer\b",
    re.IGNORECASE,
)

# Grade families. Matched loosely because the shops disagree on sub-line labels
# (HGUC / HGIBO / HGBF / HGGS / HG00 all mean "hg"). The lookarounds test letters
# only, so a grade glued to a malformed scale token — the real "1/1HG" that
# appears in animes-pro titles — still strips, while "HIGH" keeps its letters.
_GRADE_RE = re.compile(
    r"(?<![A-Za-z])(?:HGUC|HGIBO|HGBF|HGGS|HG00|HG|MGSD|MG|RG|PG|SD|EG|FM|RE)"
    r"(?![A-Za-z])",
    re.IGNORECASE)

_SCALE_RE = re.compile(r"\b1\s*/\s*(?:144|100|60|48|250|200)\b|#\s*\d+")

# Mech/model designations are the most reliable cross-shop signal:
# GN-001REII, GAT-X370, MBF-P02, MS-07B-3, ASW-G-66, XXXG-01W.
_CODE_RE = re.compile(r"\b[A-Za-z]{1,6}[-A-Za-z0-9]*\d[-A-Za-z0-9]*\b")

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

# Brackets left empty once their contents were stripped as noise.
_EMPTY_BRACKET_RE = re.compile(r"[\[【（(]\s*[\]】）)]")

# Scoring weights. A shared model code is near-conclusive on its own; CJK
# overlap alone must be very strong to carry a match, because transliteration
# differs between shops (維達爾 vs 維度爾 for the same kit).
CODE_WEIGHT = 0.62
CJK_WEIGHT = 0.55
DEFAULT_THRESHOLD = 0.72


def normalize_title(title):
    """Strip shop decoration, grade labels and scale from a title.

    Model codes are deliberately *kept* — they are the strongest cross-shop
    signal and are extracted separately by `model_codes`.
    """
    text = _NOISE_RE.sub(" ", title or "")
    text = _GRADE_RE.sub(" ", text)
    text = _SCALE_RE.sub(" ", text)
    text = _EMPTY_BRACKET_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def model_codes(title):
    """Uppercased mech/model designations found in a title."""
    return {m.group(0).upper() for m in _CODE_RE.finditer(title or "")}


def cjk_bigrams(title):
    """CJK character bigrams — the unit that survives word-order differences."""
    chars = _CJK_RE.findall(title or "")
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def _dice(left, right):
    if not left or not right:
        return 0.0
    return 2 * len(left & right) / (len(left) + len(right))


def score(query, candidate):
    """Similarity of two titles in [0, 1], weighted toward hard identifiers."""
    codes = model_codes(query) & model_codes(candidate)
    code_part = 1.0 if codes else 0.0
    cjk_part = _dice(cjk_bigrams(query), cjk_bigrams(candidate))
    return CODE_WEIGHT * code_part + CJK_WEIGHT * cjk_part


class JanCatalogue:
    """Trusted (grade, title) -> JAN index built from the application database."""

    def __init__(self, entries):
        self.entries = entries
        self._by_grade = {}
        for grade, sku, title in entries:
            self._by_grade.setdefault(grade, []).append((sku, title))

    @classmethod
    def from_database(cls, db_path, exclude_shops=()):
        """Load products whose shop supplied or embedded a real JAN.

        `exclude_shops` matters: a shop whose JANs are themselves *derived* by
        this matcher must never become a source for it, or matching turns
        circular and a wrong answer silently confirms itself on the next run.
        """
        connection = sqlite3.connect(db_path)
        try:
            rows = connection.execute(
                "SELECT p.grade, p.sku, p.title FROM products p "
                "JOIN shops s ON s.id = p.shop_id "
                "WHERE p.sku IS NOT NULL AND length(p.sku) = 13"
                + (" AND s.code NOT IN ({})".format(
                    ",".join("?" * len(exclude_shops))) if exclude_shops else ""),
                tuple(exclude_shops)).fetchall()
        finally:
            connection.close()
        return cls([tuple(row) for row in rows])

    def rows_for(self, grade):
        """The `(sku, title)` candidate pool for one grade."""
        return self._by_grade.get(grade) or []

    def lookup(self, title, grade, threshold=DEFAULT_THRESHOLD):
        """Best verified JAN for `title` within `grade`.

        Returns `(sku, score, matched_title)`, or `('', 0.0, None)` when nothing
        clears the threshold or the top two candidates tie on different SKUs —
        an ambiguous match is treated as no match rather than resolved by
        arbitrary ordering.
        """
        candidates = self._by_grade.get(grade) or []
        if not candidates:
            return "", 0.0, None

        scored = sorted(((score(title, candidate), sku, candidate)
                         for sku, candidate in candidates), reverse=True)
        best_score, best_sku, best_title = scored[0]
        if best_score < threshold:
            return "", 0.0, None
        if len(scored) > 1 and scored[1][0] >= best_score and scored[1][1] != best_sku:
            return "", 0.0, None
        return best_sku, best_score, best_title


def evaluate(catalogue, threshold=DEFAULT_THRESHOLD):
    """Measure the matcher on the labeled pairs already in the catalogue.

    Every (grade, sku) held by two shops is a known true match, so the title of
    one shop is a query whose correct answer is that sku. Reports recall (how
    many true matches are found), precision (how many returned JANs are right),
    and — the number that matters most — wrong-SKU matches.
    """
    by_key = {}
    for grade, sku, title in catalogue.entries:
        by_key.setdefault((grade, sku), []).append(title)

    matched = wrong = abstained = 0
    wrong_examples = []
    for (grade, sku), titles in by_key.items():
        if len(titles) < 2:
            continue
        query, _ = titles[0], titles[1:]
        found, found_score, found_title = catalogue.lookup(query, grade, threshold)
        if not found:
            abstained += 1
        elif found == sku:
            matched += 1
        else:
            wrong += 1
            if len(wrong_examples) < 8:
                wrong_examples.append((grade, sku, found, round(found_score, 3),
                                       query[:58], (found_title or "")[:58]))

    total = matched + wrong + abstained
    return {
        "pairs": total,
        "matched": matched,
        "wrong": wrong,
        "abstained": abstained,
        "recall": matched / total if total else 0.0,
        "precision": matched / (matched + wrong) if (matched + wrong) else 0.0,
        "wrong_examples": wrong_examples,
    }
