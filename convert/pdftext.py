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

__all__ = ["fix_map", "apply_fixes", "line_items", "enabled"]


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
        for block in page.get_text("rawdict")["blocks"]:
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
    for block in page.get_text("rawdict")["blocks"]:
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


def fix_map(path):
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
    return out


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
    return text
