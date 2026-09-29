"""What the glyphs on a page say, as a set of text repairs.

`convert/arabic.py` holds the repairs and knows nothing about PDFs, by design.
This is the one place that turns a pymupdf page into the character stream those
repairs need - and then, crucially, turns the result back into plain
text-to-text substitutions.

That last step is the whole point, and it was learned the hard way. The first
version of this applied the geometric repairs directly, in the reader's
geometry path and in the checker. It broke the hard gate: 100.0% -> 96.2% on
the regression set, one file's text score falling 0.998 -> 0.000, while
`page_score` did not move on a single file. The converter's output had not
changed at all. What changed was that the CHECKER now repaired the original and
the READER did not, because six of those eight files come through the tag route
- `/ActualText` strings, which carry no glyph boxes for the repair to read.

That is `PLAN.md` caveat 1 and the invariant at the top of `convert/arabic.py`:
a repair applied to one side and not the other is worse than no repair, because
our output stops matching the thing it is scored against and a genuine fix
reads as a regression.

So the repairs are derived from the glyphs ONCE, expressed as
{broken word -> repaired word}, and then applied as text by
whoever has text. Both sides derive the same map from the same file and apply
it to whatever they extracted, so neither can be repaired without the other.
"""
import os
import re
import unicodedata

import pymupdf

from convert.arabic import _ZERO_W, repair_lam_alef, repair_ligatures
from convert.order import get_text

__all__ = ["fix_map", "join_map", "apply_fixes", "line_items", "enabled"]


def enabled():
    """Is the geometric repair switched on? QIRTAS_ARABIC_FIX=off turns it off.

    It exists to measure the repair against its own absence on the same code,
    the same machine and the same renderer. Off is exactly the behaviour
    before the repair: `fix_map` returns nothing, and since the reader and the
    checker both get their repairs only from `fix_map`, they switch together -
    one side repaired and not the other is the failure this file was written
    around.

    Off from 2026-09-21 to 2026-09-22: on 29 unseen files it broke the hard
    gate, 100.0% -> 98.3%, worst file 79.9%. ON again since 2026-09-22 (TASKS
    N3a): the loss was the reader and the checker applying the two repairs in
    different orders, not lost text. Fixed, the gate holds at 100% on the 24
    unseen files and the theses, and lam-alef misspellings fall from 1.2% to
    0.1% of words by `harness.spelling`, which does not share our extractor.
    See FLAGS.md 20 and PLAN.md "N3a".
    """
    flag = os.environ.get("QIRTAS_ARABIC_FIX", "on").strip().lower()
    return flag not in ("off", "0", "false", "no")

# A fragment shorter than this is too common to replace safely: mapping ال onto
# لا everywhere would corrupt every definite article in the document. The
# geometric evidence is per-occurrence, but a text substitution is not, so the
# unit has to be big enough to be specific.
MIN_FRAGMENT = 3



def line_items(line):
    """One rawdict line -> [(char, x0, x1)], lam-alef repaired.

    Lam-alef only. This used to be `arabic.repair_line`, which also moves
    spaces and punctuation to where the page draws them. That half is out,
    2026-09-21 (TASKS N3a): a moved neutral crosses words, so its fragment is
    several words long and fires only where both sides split the words alike.
    On z22110258 it gave the checker "دراسةم لأمون فندي( 2008)" and "D-VBS"
    for DVB-S while our text kept the page's spacing - reported as lost.
    A lam-alef swap stays inside one word, and the gate's pass or fail no
    longer depends on where each side put its spaces."""
    items = []
    for span in line.get("spans", []):
        for ch in span["chars"]:
            x0, _, x1, _ = ch["bbox"]
            items.append((ch["c"], x0, x1))
    return repair_ligatures(items)


# A glyph layer has to be worth reading before its geometry can be trusted.
#
# The repair's whole premise is that a zero-width character is half of a
# ligature. On the six hard thesis files the glyphs barely decode at all -
# RESEARCH.md measured 0-8% recovered, the text really living in /ActualText -
# and their widths are therefore meaningless. Run on them, the repair "fixed"
# every definite article: الله came back لاله, القرشي came back لاقرشي, and a
# whole line's spaces collapsed. The hard gate fell to 0.944.
#
# Measured over the first pages of each file, non-space non-combining
# characters only:
#
#     z21358439        10,961 chars    2.14% zero width    healthy
#     z21011460        14,060 chars    1.56%               healthy
#     ödev              1,120 chars    0.00%               healthy
#     الفصل الخامس الثالث   11 chars   27.27%              degenerate
#     الفصل الخامس الأول    37 chars   67.57%              degenerate
#     مقدمة البحث          202 chars   96.04%              degenerate
#
# Two orders of magnitude between the two groups on both counts, so the
# thresholds sit in open space rather than being tuned to a boundary.
MAX_ZERO_WIDTH = 0.10
MIN_CHARS = 200


def trustworthy(doc):
    """Can this PDF's glyph widths be believed? -> (bool, share, chars)

    Computed from the file alone, so the reader and the checker reach the same
    verdict without either knowing what the other did.
    """
    total = zero = 0
    for page in list(doc)[:8]:
        for block in get_text(page, "rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    for ch in span["chars"]:
                        c = ch["c"]
                        if c.isspace() or unicodedata.combining(c):
                            continue
                        total += 1
                        x0, _, x1, _ = ch["bbox"]
                        if (x1 - x0) < _ZERO_W:
                            zero += 1
    if total < MIN_CHARS:
        return False, 0.0, total
    share = zero / total
    return share <= MAX_ZERO_WIDTH, share, total


def _line_pairs(page, all_lines=None):
    """-> [(stored line, repaired line)] for every line that CHANGED.

    Lines that did not change are appended to `all_lines` when one is given:
    they are the evidence that a fragment is not universally broken, which is
    what `fix_map` needs to decide whether a substitution is safe.
    """
    out = []
    for block in get_text(page, "rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            stored = "".join(c["c"] for s in line.get("spans", [])
                             for c in s["chars"])
            repaired = "".join(t[0] for t in line_items(line))
            if stored != repaired:
                out.append((stored, repaired))
            elif all_lines is not None:
                all_lines.append(stored)
    return out


# A word, for the map: a run of Arabic letters and their marks. Not a
# whitespace-separated token - a note number or a bracket glued to the word
# ("واإلسالميني1") is part of a token, and the reader moves such numbers into
# real notes (N2b), so a token-keyed repair then fired on the checker's side
# only.
LETTERS = "ء-غف-يً-ٰٟٱ-ۓ"
_WORD = re.compile(f"[{LETTERS}]+")
# Three alefs in a row are not Arabic spelling. z20276145 stretches its words
# with them - المصلحة set as المصاااالحة - and there the alefs next to a lam
# are filler, not ligature halves: the checker and the reader each moved a
# different one, and the gate lost 14% of the file. Such words are left to
# the spelling rules, which both sides apply alike.
_STRETCHED = re.compile("[اأإآ]{3,}")


def _fragments(stored, repaired):
    """(before, after) for each WORD the ligature repair changed.

    The repair swaps two adjacent letters and nothing else, so the repaired
    line is the stored one with some pairs exchanged: same length, and every
    word in the same place. Compared position by position, a changed word is
    one whose letters changed - no diff, and no fragment that can span words.
    """
    if len(stored) != len(repaired):
        return
    for m in _WORD.finditer(stored):
        before, after = m.group(), repaired[m.start():m.end()]
        # Never a word the swap reached into from outside: then it is not a
        # permutation of itself, and applying it alone would change letters.
        if (before != after and sorted(before) == sorted(after)
                and len(before) >= MIN_FRAGMENT
                and not _STRETCHED.search(before)):
            yield before, after


def _with_neighbours(stored, repaired):
    """(word, (the word and the word after or before it, repaired)) for each
    word the repair changed. Same positions on both sides, as in
    `_fragments`, so a stretch is cut from each at the same place."""
    if len(stored) != len(repaired):
        return
    words = list(_WORD.finditer(stored))
    for i, m in enumerate(words):
        before, after = m.group(), repaired[m.start():m.end()]
        if not (before != after and sorted(before) == sorted(after)
                and len(before) >= MIN_FRAGMENT
                and not _STRETCHED.search(before)):
            continue
        for a, b in ((m, words[i + 1] if i + 1 < len(words) else None),
                     (words[i - 1] if i else None, m)):
            if a is None or b is None:
                continue
            gap = stored[a.end():b.start()]
            # One line, one space or a mark and a space: a stretch over
            # anything longer depends on how each side spaced it.
            if not gap or len(gap) > 2 or set(gap) - set(" .،,:؛"):
                continue
            yield before, (stored[a.start():b.end()], repaired[a.start():b.end()])


class Fixes(dict):
    """The map, and the verses written as the Quran has them
    (`convert/quran.py`), which are found by their letters rather than as
    fixed text. Applied after the map, by `apply_fixes`."""
    verses = {}

    def __bool__(self):
        return bool(len(self)) or bool(self.verses)


def fix_map(path):
    """-> {broken fragment: repaired fragment} for this PDF: the lam-alef
    repairs (`_lam_alef_map`) and the words a space cuts in two
    (`join_map`); and the verses in Quran fonts (FLAGS 33)."""
    out = Fixes(_lam_alef_map(path))
    try:
        joins = join_map(path)
    except Exception:
        joins = {}
    for k, v in joins.items():
        out.setdefault(k, v)
    try:
        from convert import quran
        # A key for each form the two sides may hold a verse in by the
        # time the map is applied: as stored, lam-alef repaired, and both.
        plain = dict(out)
        out.verses = quran.table(path, (
            lambda t: repair_lam_alef(" " + t + " ").strip(),
            lambda t: apply_fixes(t, plain),
            lambda t: apply_fixes(repair_lam_alef(" " + t + " ").strip(), plain)))
    except Exception:
        out.verses = {}
    return out


def _lam_alef_map(path):
    """-> {broken fragment: repaired fragment} for this PDF.

    Derived from glyph geometry, so it says only what the page itself shows:
    which alef-lam pairs came out of a single ligature glyph. One entry per
    word (a run of letters).

    Two words are dropped rather than trusted:

      - one that maps to two different repairs. The same broken text is then
        genuinely ambiguous, and guessing is how a repair starts corrupting
        text instead of fixing it;
      - one whose `before` still appears somewhere the page did NOT repair -
        a real alef beside a real lam somewhere else. A substitution is global
        even when the evidence for it is local, so it is only kept when every
        occurrence agrees.
    """
    if not enabled():
        return {}
    seen, bad = {}, set()
    near = {}                   # word -> [(stretch with a neighbour, repaired)]
    stored_all, repaired_all = [], []
    with pymupdf.open(path) as d:
        ok, _, _ = trustworthy(d)
        if not ok:
            return {}
        for page in d:
            for stored, repaired in _line_pairs(page, all_lines=stored_all):
                repaired_all.append(repaired)
                for before, after in _fragments(stored, repaired):
                    if before in seen and seen[before] != after:
                        bad.add(before)
                    seen[before] = after
                for before, pair in _with_neighbours(stored, repaired):
                    near.setdefault(before, []).append(pair)

    # Everything the document holds, after the geometric pass. If a fragment
    # survives in there, some occurrence of it was left alone and the
    # substitution would not be safe to apply everywhere.
    settled = "\n".join(repaired_all) + "\n" + "\n".join(
        s for s in stored_all if s not in ("",))
    out = {}
    for k, v in seen.items():
        if k in bad:
            continue
        if _pattern(k).search(settled):
            # Left alone somewhere, so not safe alone - but with the word
            # beside it, it may be. بني is a word, and z21762915 prints it
            # unrepaired seven times; ".بني الجزائريين" it holds once, and
            # that is بين.
            for stretch, fixed in near.get(k, ()):
                if stretch not in out and not _pattern(stretch).search(settled):
                    out[stretch] = fixed
            continue
        out[k] = v
    # The same word as both sides will hold it when the map is applied: the
    # reader and the checker both repair lam-alef by spelling first
    # (`reader._clean`, `compare.text_of`), then apply this map. A word with
    # two ligatures - االسالمية, stored for الاسلامية - is half-repaired by
    # spelling to الاسالمية, and a map keyed only on the stored form no
    # longer matched it. When the checker applied the map first, it got the
    # word right and we did not, and the gate read 20% of z22110258 as lost
    # (FLAGS 20). Spaces around it, because the spelling rule needs a
    # boundary on both sides.
    for k, v in list(out.items()):
        k2 = repair_lam_alef(" " + k + " ").strip()
        if k2 != k and k2 not in out and k2 not in seen \
                and not _pattern(k2).search(settled):
            out[k2] = v
    # And the word it becomes spelled the same way: a spelling rule that
    # adds a letter - the ه of الله (convert/arabic.py) - was otherwise taken
    # back out by the map, اللَُّه -> اللَُّ (z21644412, FLAGS 29). The rules
    # fire only on broken text, so a word in its right order passes through.
    return {k: repair_lam_alef(" " + v + " ").strip() for k, v in out.items()}


def _pattern(fragment):
    """A word as a regex: whole, bounded by anything that is not a letter.

    So `حامال` never fires inside a longer word, and does fire beside a digit,
    a bracket or a line break."""
    return re.compile(f"(?<![{LETTERS}])" + re.escape(fragment) + f"(?![{LETTERS}])")


_COMPILED = {}


def _compile(fixes):
    """-> [(first word, pattern, repair)], longest fragment first. Built once
    per map.

    It used to be rebuilt on every call. A wild file yields ~1,650 fragments,
    more than `re`'s own cache holds, so every paragraph recompiled every
    pattern - and the reader calls this per paragraph, per span and per table
    cell, on every round of `fit.py`. That made a 30-file run take 3-4x as
    long with the repair on as with it off (2026-09-21).
    """
    hit = _COMPILED.get(id(fixes))
    if hit is not None and hit[0] is fixes:
        return hit[1]
    out = [(k, _pattern(k), v) for k, v in
           sorted(fixes.items(), key=lambda kv: len(kv[0]), reverse=True)]
    if len(_COMPILED) > 8:
        _COMPILED.clear()
    _COMPILED[id(fixes)] = (fixes, out)
    return out


def apply_fixes(text, fixes):
    """Apply a fix map to text, longest fragment first.

    Bounded by whitespace or the ends of the string, so a fragment can only
    replace whole words - `حامال` must not fire inside a longer word that
    happens to contain it.

    Applied one fragment at a time, in order, each to the result of the last -
    exactly as before. The substring test only skips a pattern that cannot
    match: its first word is not in the text as it stands at that step.
    """
    if not text or not fixes:
        return text
    for first, pat, after in _compile(fixes):
        if first in text:
            text = pat.sub(lambda _, a=after: a, text)
    verses = getattr(fixes, "verses", None)
    if verses:
        from convert.quran import apply
        text = apply(text, verses)
    return text


# -- spaces inside words -------------------------------------------------------

_ARABIC_LETTER = re.compile("[ء-ي]")
_JOINS_NEXT = {"init", "medi"}
_JOINS_PREVIOUS = {"medi", "fina"}
_JOINS = {}


# How far apart, as a share of the letter's height, two joined letters may be
# measured: the joining stroke belongs to one of them, and the boxes a font
# gives do not always meet exactly.
TOUCH = 0.15


def _touch(before, after):
    """Does `before` end where `after` begins, right to left, on one line?"""
    a, b = before["bbox"], after["bbox"]
    h = max(1.0, a[3] - a[1])
    if abs(before["origin"][1] - after["origin"][1]) > TOUCH * h:
        return False
    return abs(a[0] - b[2]) <= TOUCH * h


# The share of a page's spaces between Arabic letters that must be drawn
# between them before one drawn elsewhere counts as evidence. Pages below it
# draw their spaces away from the words (z21761968, z22179435).
PLACED_SHARE = 0.8
# Closer than `_touch` asks: two words a space apart are 0.15 of the type size
# apart at the least (5% of 9183 real spaces), a split word under 0.1 (93% of
# 238). "مباشر أو" sits 0.15 apart with its space drawn elsewhere.
CLOSE = 0.1
# QIRTAS_SPACE_PLACE=0 turns this evidence off, to measure against.
PLACE_ON = os.environ.get("QIRTAS_SPACE_PLACE", "1") != "0"


def _drawn_between(space, before, after, size):
    """Is the space drawn in the gap between its two letters, right to left?"""
    size = size or 10.0
    mid = (space["bbox"][0] + space["bbox"][2]) / 2
    return after["bbox"][2] - 0.2 * size <= mid <= before["bbox"][0] + 0.2 * size


def _split_at(chars, drop):
    """The words of a line that hold a dropped space: [(as stored, joined)].
    A word here is a run of letters and marks and the dropped spaces inside
    it."""
    out, word, cut = [], [], False
    for i, c in enumerate(chars + [" "]):
        if i in drop:
            word.append(c)
            cut = True
        elif _WORD.fullmatch(c):
            word.append(c)
        else:
            if cut:
                out.append(("".join(word), "".join(w for w in word
                                                    if w != " ")))
            word, cut = [], False
    return out


def join_map(path):
    """-> {word as stored with a space in it: the word} for this PDF.

    Word stores a real space character inside some words - الواحد as
    "الواح د", على as "ع ل ى" - and draws it where no gap is (FLAGS 24,
    PLAN "The gate asks the page"). Moving each space to where it is drawn
    was tried and reverted: two letters that touch round a space also happen
    at real word boundaries.

    The letters' own shapes settle it. A letter drawn in its joining form -
    `init` or `medi` before the space, `medi` or `fina` after it - is joined
    across the space on the page, so the space is not a word boundary. The
    form comes from the installed font's shaping rules (`glyphs.forms`); a
    font that is not installed gives no evidence and nothing is joined.
    Letters that never join forward (ا د ذ ر ز و) give none either.

    For those, and for words the page draws broken (الم ستخرجة), the space's
    own place settles it: letters closer than a word gap, with the space
    drawn away from them, where the page's other spaces sit between their
    letters (2026-09-23, PLAN "The space's own place"). "إ يجاد" is joined
    this way.

    The same safety as the lam-alef map: a stored word that also appears
    somewhere without that evidence is left alone everywhere.
    """
    key = (str(path), os.path.getmtime(path), os.path.getsize(path))
    if key in _JOINS:
        return _JOINS[key]
    from convert.glyphs import forms, reference
    found, joined, plain = {}, {}, []
    with pymupdf.open(path) as d:
        for page in d:
            drawn = {}
            for span in page.get_texttrace():
                shape, ref = forms(span["font"]), reference(span["font"])
                if not shape or not ref:
                    continue
                for _, gid, origin, _ in span["chars"]:
                    drawn[(round(origin[0], 1), round(origin[1], 1))] = \
                        (shape.get(gid), ref[0].get(gid) or "")

            def form(c):
                # Only where the installed font names this shape as the letter
                # the page says it is: a font of another version numbers its
                # shapes differently, and there the numbers say nothing.
                got = drawn.get((round(c["origin"][0], 1),
                                 round(c["origin"][1], 1)))
                return got[0] if got and c["c"] in got[1] else None

            def letter(text, i, step):
                """The nearest letter from i in this direction, past vowel
                marks; -1 if there is none."""
                while 0 <= i < len(text) and not _ARABIC_LETTER.match(text[i]):
                    if not _WORD.fullmatch(text[i]):
                        return -1
                    i += step
                return i if 0 <= i < len(text) else -1

            lines = []
            for b in get_text(page, "rawdict")["blocks"]:
                for line in b.get("lines", ()):
                    chars, size = [], []
                    for s in line["spans"]:
                        chars += s["chars"]
                        size += [s["size"]] * len(s["chars"])
                    lines.append((chars, size))
            # Where the page draws its spaces between the letters round them,
            # a space drawn somewhere else is not the gap between them.
            placed = [_drawn_between(chars[i], chars[i - 1], chars[i + 1],
                                     size[i])
                      for chars, size in lines
                      for i in range(1, len(chars) - 1)
                      if chars[i]["c"] == " "
                      and _ARABIC_LETTER.match(chars[i - 1]["c"])
                      and _ARABIC_LETTER.match(chars[i + 1]["c"])]
            trust_place = PLACE_ON and bool(placed) and \
                sum(placed) / len(placed) >= PLACED_SHARE
            for chars, size in lines:
                text = [c["c"] for c in chars]
                plain.append("".join(text))
                drop = set()
                for i, c in enumerate(text):
                    if c != " ":
                        continue
                    j, k = letter(text, i - 1, -1), letter(text, i + 1, 1)
                    if j < 0 or k < 0:
                        continue
                    # A joined pair touches: the letter before ends where
                    # the one after begins, right to left. Where the text
                    # holds letters out of drawing order, two letters side
                    # by side in it may be far apart on the page, and
                    # their shapes are joined to other letters -
                    # "م في كان" came out as ميفكان.
                    if not _touch(chars[j], chars[k]):
                        continue
                    before, after = form(chars[j]), form(chars[k])
                    if (before and before <= _JOINS_NEXT) \
                            or (after and after <= _JOINS_PREVIOUS):
                        drop.add(i)
                    # Letters that never join forward (إ يجاد) and words
                    # the page draws broken show nothing in their shapes:
                    # the space's own place does. Touching letters with
                    # the space drawn away from them (2026-09-23: 209 of
                    # 238 such spaces on the dev pages, 10 of 9183 real
                    # ones, on pages whose spaces sit where drawn).
                    elif trust_place and not _drawn_between(
                            chars[i], chars[j], chars[k], size[i]) \
                            and chars[j]["bbox"][0] - chars[k]["bbox"][2] \
                            < CLOSE * (size[i] or 10.0):
                        drop.add(i)
                # The word joined as the letter-pair repair reads it:
                # "امل حددات" is المحددات, not املحددات. The repair only
                # swaps letters, so its spaces are where the stored ones are.
                fixed = [c[0] for c in repair_ligatures(
                    [(c["c"], c["bbox"][0], c["bbox"][2]) for c in chars])]
                for (stored, _), (_, whole) in zip(_split_at(text, drop),
                                                   _split_at(fixed, drop)):
                    found[stored] = found.get(stored, 0) + 1
                    joined[stored] = whole
    everything = "\n".join(plain)
    out = {}
    for stored, n in found.items():
        # Every occurrence must carry the evidence.
        if len(_pattern(stored).findall(everything)) > n:
            continue
        whole = repair_lam_alef(" " + joined[stored] + " ").strip()
        # Both sides spell lam-alef first and apply this map after
        # (`reader.read`, `compare.text_of`): key on the spelled form too.
        for k in {stored, repair_lam_alef(" " + stored + " ").strip()}:
            out.setdefault(k, whole)
    _JOINS[key] = out
    return out
