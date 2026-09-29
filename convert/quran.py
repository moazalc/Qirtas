"""Verses set in a Quran font, written as the Quran has them (FLAGS 33).

Theses set their verses in the King Fahd Complex's fonts (KFGQPC Uthmanic),
Al Qalam Quran and the like. These draw some letters joined into one shape
and the PDF stores the shape as its first letter only: `z18037898` holds
ٱلۡيَوۡمَ without its ي, ٱلَّذِينَ without its ذ, ٱللَّهِ without its ه. Shapes
that do carry two letters come out of the text reader turned round: ٱنلَّاس
for ٱلنَّاس. Nothing in the file holds the missing letters, so the only
source for them is the Quran's own text: Tanzil's Uthmani text, shipped
unchanged in `convert/data/quran-uthmani.txt` (its terms: verbatim copies,
credit to tanzil.net).

How:
  - every run of text in a Quran font is lined up, letter by letter, with the
    stretch of the Quran it best matches. Letters only: the vowel marks are
    where these fonts go most wrong, and the two texts spell them differently
  - the run's words are grouped with the Quran words their letters landed on,
    and each group becomes a repair: {its letters -> the Quran's words}
  - the repair is keyed on letters alone, no spaces or marks, because the
    converter and the checker do not hold a broken verse identically - one
    has ٱلنَّاس ُ where the other has ٱنلَّاس ُ, one عَدُوِي where the other has
    عَدُو ِي. It fires on whole words, and never across a digit, a bracket
    or a line of the thesis's own prose

Both sides apply it through `pdftext.apply_fixes`, like every other repair of
the stored text, so a repaired verse is not read as lost. A key whose letters
also occur in the thesis's own writing is not used: مِن spelled م ِن in a
verse must not rewrite every من of the prose.

QCF fonts (a whole word per shape, stored as private codes) have no letters
to line up and are left as they are.
"""
import collections
import functools
import os
import re
from pathlib import Path

import pymupdf

from convert.order import get_text

ON = os.environ.get("QIRTAS_QURAN", "1") != "0"

TEXT = Path(__file__).resolve().parent / "data" / "quran-uthmani.txt"
QURAN_FONT = re.compile(r"KFGQPC|Quran|QCF|Uthmani|Hafs|Warsh", re.I)

# Share of a run's letters that must line up with the Quran, and the fewest
# letters a run needs before its match is believed at all.
AGREE = 0.8
MIN_LETTERS = 8
# The most words one repair may cover, and the longest stretch of Quran
# letters a run is lined up against beyond its own length.
MAX_WORDS = 8
SLACK = 0.35
# A three-letter piece found more often than this in the Quran says nothing
# about where a run is.
COMMON = 400

_LETTER = "\u0621-\u063F\u0641-\u064A\u0671-\u06D3"
_MARK = "\u0640\u064B-\u065F\u0670\u06D6-\u06ED"
# A word: letters and marks, and marks alone (a mark set apart by a space
# belongs to the word beside it).
WORD = re.compile(f"[{_LETTER}{_MARK}]+")
_FOLD = str.maketrans({"\u0671": "\u0627", "\u0623": "\u0627", "\u0625": "\u0627",
                       "\u0622": "\u0627", "\u0649": "\u064A", "\u0626": "\u064A",
                       "\u0629": "\u0647", "\u0624": "\u0648"})
_LETTERS_ONLY = re.compile(f"[^{_LETTER}]")


def letters(s):
    """The bare letters, folded so both texts' spellings of a hamza, a final
    ya or ta marbuta read the same."""
    return _LETTERS_ONLY.sub("", s).translate(_FOLD)


@functools.lru_cache(maxsize=1)
def _quran():
    """-> (words, letters of all of it, word index of each letter, index of
    every three letters)."""
    words, flat, owner = [], [], []
    with open(TEXT, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            if len(parts) != 3:
                continue
            for w in parts[2].split():
                k = letters(w)
                if not k:
                    continue
                words.append(w)
                flat.append(k)
                owner.extend([len(words) - 1] * len(k))
    q = "".join(flat)
    grams = collections.defaultdict(list)
    for i in range(len(q) - 2):
        grams[q[i:i + 3]].append(i)
    return words, q, owner, grams


def _align(s, q):
    """Line s up inside q: -> (cost, {position in s: position in q}).
    All of s, any stretch of q; a letter missing, added or changed costs 1,
    and so does a pair turned round - a shape of two letters comes out of
    the text reader backwards (ٱنلَّاس for ٱلنَّاس) - whose letters still
    count as found."""
    m, n = len(s), len(q)
    rows = [list(range(0, 1)) + [0] * n]
    back = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        prev = rows[-1]
        cur = [i] + [0] * n
        back[i][0] = 1
        for j in range(1, n + 1):
            best, step = prev[j - 1] + (s[i - 1] != q[j - 1]), 0
            if prev[j] + 1 < best:
                best, step = prev[j] + 1, 1      # a letter of s not in q
            if cur[j - 1] + 1 < best:
                best, step = cur[j - 1] + 1, 2   # a letter of q missing from s
            if i > 1 and j > 1 and s[i - 1] == q[j - 2] \
                    and s[i - 2] == q[j - 1] and s[i - 1] != s[i - 2] \
                    and rows[-2][j - 2] + 1 < best:
                best, step = rows[-2][j - 2] + 1, 3
            cur[j] = best
            back[i][j] = step
        rows.append(cur)
        if len(rows) > 2:
            rows.pop(0)
    last = rows[-1]
    j = min(range(n + 1), key=lambda k: last[k])
    cost, pairs, i = last[j], {}, m
    while i > 0:
        step = back[i][j] if j > 0 else 1
        if step == 0:
            if s[i - 1] == q[j - 1]:
                pairs[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif step == 3:
            pairs[i - 1], pairs[i - 2] = j - 2, j - 1
            i, j = i - 2, j - 2
        elif step == 1:
            i -= 1
        else:
            j -= 1
    return cost, pairs


def locate(s):
    """Where in the Quran the letters s are: -> {position in s: position in
    the Quran's letters}, or None when no stretch agrees well enough."""
    if len(s) < MIN_LETTERS:
        return None
    _, q, _, grams = _quran()
    votes = collections.Counter()
    for i in range(len(s) - 2):
        at = grams.get(s[i:i + 3], ())
        if len(at) > COMMON:
            continue
        for p in at:
            votes[(p - i) // 4] += 1
    best = None
    for bin_, n in votes.most_common(3):
        if n < 2:
            break
        lo = max(0, bin_ * 4 - 8)
        hi = bin_ * 4 + int(len(s) * (1 + SLACK)) + 8
        cost, pairs = _align(s, q[lo:hi])
        if best is None or cost < best[0]:
            best = (cost, {a: b + lo for a, b in pairs.items()})
    if best is None or len(best[1]) < AGREE * len(s):
        return None
    return best[1]


def _groups(words, spots, owner, qwords):
    """The run's words, grouped with the Quran words their letters landed on:
    -> [(first word, last word, first Quran word, last Quran word)].

    A group is kept only where its own letters agree with its Quran words:
    a run can line up well as a whole with one stretch of it lined up
    anywhere - وَقَدْ كَفَرُوا۟ بِمَا came out as وَقَدْ سَرِيعُ ٱلْحِسَابِ."""
    reach, sizes, k = [], [], 0
    for w in words:
        n = len(letters(w))
        hit = [owner[spots[k + i]] for i in range(n) if k + i in spots]
        reach.append((min(hit), max(hit)) if hit else None)
        # one letter lined up with nothing: a mark stored as a letter, as
        # حِلٌّ is stored حِل ر - junk, not a word the verse lacks
        sizes.append((0 if n == 1 and not hit else n, len(hit)))
        k += n
    out = []
    for i, r in enumerate(reach):
        if r is None:
            if out:                 # a mark on its own, or an unmatched word
                a, _, lo, hi = out[-1]
                out[-1] = (a, i, lo, hi)
            continue
        if out and r[0] <= out[-1][3]:
            a, _, lo, hi = out[-1]
            out[-1] = (a, i, lo, max(hi, r[1]))
        else:
            if out:                 # Quran words no stored letter landed on
                a, b, lo, _ = out[-1]
                out[-1] = (a, b, lo, r[0] - 1)
            out.append((i, i, r[0], r[1]))

    def agrees(g):
        a, b, lo, hi = g
        stored = sum(n for n, _ in sizes[a:b + 1])
        hit = sum(h for _, h in sizes[a:b + 1])
        quran = sum(len(letters(w)) for w in qwords[lo:hi + 1])
        # a letter missing is the fault itself: وََكَنَ is وَكَانَ
        return hit >= AGREE * stored and quran - hit <= max(1, (1 - AGREE) * quran)
    return [g for g in out if g[3] - g[2] < MAX_WORDS and agrees(g)]


def _runs(page):
    """The text of each line's stretch set in a Quran font, as stored."""
    for b in get_text(page, "dict")["blocks"]:
        for line in b.get("lines", []):
            cur = []
            for s in line["spans"] + [None]:
                if s is not None and QURAN_FONT.search(s["font"]):
                    cur.append(s["text"])
                    continue
                if cur and "".join(cur).strip():
                    yield "".join(cur).strip()
                cur = []


def _word_keys(text, most):
    """Letters of every stretch of up to `most` whole words, as `apply` sees
    them."""
    ws = [m for m in WORD.finditer(text)]
    for i in range(len(ws)):
        for n in range(1, most + 1):
            if i + n > len(ws):
                break
            if n > 1 and text[ws[i + n - 2].end():ws[i + n - 1].start()].strip():
                break
            k = letters(text[ws[i].start():ws[i + n - 1].end()])
            if k:
                yield k


def _found(runs, i):
    """Run i's words and where they are in the Quran: read alone, and with
    the runs either side of it - a line of three letters is not found alone,
    and a word ending one line and one starting the next are only told apart
    by what is around them. But the line before may end another verse, and
    read with it the first words of this one land wrong (وََّلَ, 6:164 after
    19:95), so every reading that is found counts.
    -> [(words, [(first word, last word, first Quran word, last Quran word)])]"""
    _, _, owner, _ = _quran()
    out = []
    for lo, hi in ((i, i + 1), (i - 1, i + 2), (i, i + 2), (i - 1, i + 1)):
        if lo < 0 or hi > len(runs):
            continue
        words = [m.group() for r in runs[lo:hi] for m in WORD.finditer(r)]
        spots = locate(letters("".join(words)))
        if spots is not None:
            out.append((words, _groups(words, spots, owner, _quran()[0])))
    return out


def table(path, variants=()):
    """-> {letters: the Quran's words} for the verses in this PDF's Quran
    fonts. `variants`: functions giving the forms the two sides turn stored
    text into before the table is applied (the lam-alef repair), so a key is
    made from each."""
    if not ON or not TEXT.exists():
        return {}
    forms = (lambda t: t,) + tuple(variants)
    with pymupdf.open(path) as d:
        if not any(QURAN_FONT.search(f[3]) for p in d for f in p.get_fonts()):
            return {}
        pages, prose = [], []
        for p in d:
            runs = list(_runs(p))
            pages.append(runs)
            text = get_text(p, "text")
            for r in sorted(runs, key=len, reverse=True):
                text = text.replace(r, "\n")
            prose.append(text)
    return build(pages, prose, forms)


def _pairs(words, found, qwords):
    """(stored, the Quran's words) for each group, and each two and three
    groups side by side, in the run and in the Quran."""
    for n in (1, 2, 3):
        for g in range(len(found) - n + 1):
            if any(found[h + 1][0] != found[h][1] + 1
                   or found[h + 1][2] != found[h][3] + 1
                   for h in range(g, g + n - 1)):
                continue
            a, b = found[g][0], found[g + n - 1][1]
            yield (" ".join(words[a:b + 1]),
                   " ".join(qwords[found[g][2]:found[g + n - 1][3] + 1]))


def build(pages, prose, forms=(lambda t: t,)):
    """The table, from each page's Quran-font runs and the text outside them."""
    qwords = _quran()[0]
    seen, bad = {}, set()
    for runs in pages:
        for i in range(len(runs)):
            for words, found in _found(runs, i):
                for stored, right in _pairs(words, found, qwords):
                    if stored == right:
                        continue
                    for form in forms:
                        k = letters(form(stored))
                        if len(k) < 2:
                            continue
                        if seen.get(k, right) != right:
                            bad.add(k)
                        seen[k] = right
    # Letters that also stand for something in the thesis's own writing, as
    # either side will hold it: هلم is لهم once the lam-alef map has run.
    used = set()
    for text in prose:
        for form in forms:
            used.update(_word_keys(form(text), 4))
    return {k: v for k, v in seen.items() if k not in bad and k not in used}


def _starts(verses):
    """Every beginning of a key, to stop lengthening a stretch early."""
    hit = _STARTS.get(id(verses))
    if hit is not None and hit[0] is verses:
        return hit[1]
    # "": a stretch may begin with a mark set apart by a space
    out = {k[:n] for k in verses for n in range(len(k) + 1)}
    if len(_STARTS) > 8:
        _STARTS.clear()
    _STARTS[id(verses)] = (verses, out)
    return out


_STARTS = {}


def apply(text, verses):
    """Write each stretch of whole words whose letters are a key as the
    Quran's words. Longest stretch first; words joined by spaces only."""
    if not text or not verses:
        return text
    starts = _starts(verses)
    ws = list(WORD.finditer(text))
    lw = [letters(m.group()) for m in ws]
    out, at, i = [], 0, 0
    while i < len(ws):
        hit, k = None, ""
        for j in range(i, len(ws)):
            if j > i and text[ws[j - 1].end():ws[j].start()].strip():
                break
            k += lw[j]
            if k not in starts:
                break
            if k in verses:         # a stray mark after it goes with it
                hit = j
        # The word was cut in two and the letter the repair adds is the
        # piece after it: ٱَّلل ه ِ is ٱللَّهِ already, and was written
        # ٱللَّهِ ه (`z17366480`'s Basmala). A lone letter that is the start of
        # the next word (خَلَقَكُم م ِن) is no reason to stop.
        if hit is not None:
            after = hit + 1
            while after < len(ws) and not lw[after] \
                    and not text[ws[after - 1].end():ws[after].start()].strip():
                after += 1
            if after < len(ws) and len(lw[after]) == 1 \
                    and not text[ws[after - 1].end():ws[after].start()].strip():
                key = "".join(lw[i:hit + 1])
                if letters(verses[key]) == key + lw[after]:
                    hit = None
        if hit is None:
            i += 1
            continue
        out.append(text[at:ws[i].start()])
        out.append(verses["".join(lw[i:hit + 1])])
        at = ws[hit].end()
        i = hit + 1
    out.append(text[at:])
    return "".join(out)
