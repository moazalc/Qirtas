"""Repairs for Arabic text the source PDF hands over incorrectly.

Nothing here knows about PDFs or about Word. It takes text and returns text.

Both the converter and the checker import this, and they must: if only the
converter repaired its text, our output would no longer match the (still
mangled) original it is scored against, and fixing a real defect would show up
as the score getting worse. Correcting both sides compares what each document
MEANT to say, which is the only comparison worth making.
"""
import re

# لا is a ligature - one glyph in the PDF, mapped back to two letters by the
# font's ToUnicode table. Across much of this corpus that table lists them in
# the wrong order, so لا arrives as a standalone alef-lam.
#
# Safe to repair because a standalone ال is not Arabic: the definite article is
# a prefix and must attach to the word it defines. Bounded by non-word on both
# sides, an ال can only be a broken لا. Measured over 25 corpus files: 773
# occurrences, no legitimate ones.
LAM, ALEF = "ل", "ا"

# A real character is required on BOTH sides, rather than the simpler
# (?<!\w)...(?!\w), because that form treats the START or END of the string as
# a boundary - and the reader repairs text one block at a time while the
# checker repairs the whole document at once. An ال sitting at a block edge
# therefore looked standalone to one and mid-word to the other, and the two
# fired different rules on the same words: z21763864.pdf came out with لاآلف
# where the checker expected الآلف, and the hard gate dropped to 98.89%.
#
# The cost is that an ال truly beginning or ending a block is left alone. That
# is the right side to err on: a missed repair leaves text as the PDF gave it,
# while a divergent repair makes our output disagree with what it is scored
# against, which is worse than the defect.
_BOUND = r"\s،؛:.!؟\"'()\[\]«»\-"
HAMZA_ALEFS = "أإآا"

# The trailing lookahead is what stops the two repairs below from competing.
# The reader and the checker extract the same page by different pymupdf modes,
# and those disagree about where spaces go: one yields اآل contiguously, the
# other ال آل. The trigram rule fires on the first, the standalone rule on the
# second, and the same words come out الآ in one and لا آ in the other - which
# is how z21763864.pdf lost its hard gate at 98.89%.
#
# An ال followed by an alef form is a split ligature, not a standalone word, so
# it is left for the trigram rule (or left alone, which after whitespace
# normalisation reads the same as the trigram result).
_STANDALONE_AL = re.compile(
    rf"(?<=[{_BOUND}]){ALEF}{LAM}(?=[{_BOUND}])(?![{_BOUND}]*[{HAMZA_ALEFS}])")

# لا is not the only lam-alef ligature: لأ لإ لآ are ligatures too, and the same
# reversed ToUnicode turns them into أل إل آل. After the definite article that
# leaves األ اإل اآل - two alef forms side by side, which Arabic orthography
# does not allow - so those trigrams can only be the reversal.
#
# Deliberately anchored to the preceding ALEF. A bare أل is ordinary: ألف is a
# thousand, ألم is pain, ألوان is colours. Only alef + hamza-alef + lam is
# repaired, never أل on its own.
# Plain ALEF belongs in this class too: الاستثمار arrives as االستثمار, the
# same reversal with the plain-alef ligature. Two alefs in a row are no more
# possible than an alef beside a hamza-alef, so it is the same safe trigram.
# (HAMZA_ALEFS is defined above, where the standalone rule needs it.)
_AL_HAMZA = re.compile(rf"{ALEF}([{HAMZA_ALEFS}]){LAM}")

# في stored يف, 2026-09-22: its two letters are one glyph and the font lists
# them backwards, like لا. The glyph repair cannot take it: a two-letter word
# is too short to substitute safely in general - رب, a real word, would go
# too - and ya-fa is a real ligature as well (كيف), so the glyph alone does
# not say which way round it was. But يف standing ALONE is not Arabic, and
# في is the commonest word in the language. Word's readings of 13 files never
# had it, apart from one file it read partly backwards, against 2,777 في;
# our output had 231, all on z20763272. Same boundaries as the standalone ال.
YA, FA = "ي", "ف"
_STANDALONE_YF = re.compile(rf"(?<=[{_BOUND}]){YA}{FA}(?=[{_BOUND}])")


import unicodedata

# Arabic presentation forms (TASKS N3c, 2026-09-22): one codepoint per SHAPE of
# a letter - initial, medial, final, isolated - instead of the letter itself.
# Some PDF makers store text that way. It displays right and is useless: Word
# cannot search it, spell-check it or reshape it, and z21508463 was 93% such
# glyphs. Unicode's compatibility folding (NFKC) maps each shape back to its
# letter, and the lam-alef ligature shapes (ﻻ ﻷ) to لا لأ in reading order.
#
# Letter shapes only. The same blocks hold symbols an author types on
# purpose - ﷺ, ﷻ, ﷽ and the ornate Quran brackets ﴾ ﴿ - which NFKC would
# expand into whole phrases or plain brackets, changing the document.
_KEEP = {chr(c) for c in range(0xFDF0, 0xFE00)} | {"﴾", "﴿"}


def _is_display_form(c):
    o = ord(c)
    return (0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFC) and c not in _KEEP


def fold_display_forms(text):
    """Arabic presentation-form letters -> the letters they are shapes of."""
    if not text or not any(_is_display_form(c) for c in text):
        return text
    return "".join(unicodedata.normalize("NFKC", c) if _is_display_form(c) else c
                   for c in text)


def repair_lam_alef(text):
    """Put reversed lam-alef ligatures back in their written order.

    Three cases, all unambiguous:
      ال standing alone     -> لا    (the definite article cannot stand alone)
      يف standing alone     -> في    (not a word; the commonest word, reversed)
      ا + أإآ + ل           -> ا ل + أإآ  (two alef forms cannot sit together)

    Prefixed forms (وال, بال, فال) are deliberately left alone: some are real
    words - بال is mind or condition, فأل is an omen - and they are an order of
    magnitude rarer, so repairing them would risk corrupting valid text to fix
    far fewer cases. See harness/test_arabic.py.
    """
    if not text:
        return text
    text = fold_display_forms(text)
    text = _STANDALONE_AL.sub(LAM + ALEF, text)
    text = _STANDALONE_YF.sub(FA + YA, text)
    return _AL_HAMZA.sub(rf"{ALEF}{LAM}\1", text)


# ---------------------------------------------------------------------------
# The same two faults again, settled by geometry instead of by orthography.
#
# The rules above are orthographic: they repair only what Arabic spelling makes
# impossible, and that leaves a whole class untouched. حاملا arrives as حامال -
# a lam-alef ligature reversed at the end of a word - and no spelling rule can
# reach it, because مال, حال, شمال and جمال are all real words ending in the
# same two letters. Guessing there would corrupt valid text to fix invalid.
#
# Measured on z21358439.pdf, every ALEF followed by LAM on a page, grouped by
# the boxes the two characters carry:
#
#     two boxes   26   العامة العدد الحكاية اللحظة التأسيسية   the article
#     zero width  11   حامال تحوال واالجت اءاالست ال           reversed ligature
#
# لا is ONE glyph. When the font's ToUnicode lists its letters backwards,
# pymupdf hands back two characters from that single glyph - so the first has
# NO WIDTH and the second carries the whole advance. A real alef followed by a
# real lam is two glyphs with two boxes. The ambiguity is only in the text; the
# glyphs were never ambiguous.
#
# These take characters and return characters, so this file still knows nothing
# about PDFs. The caller supplies (char, x0, x1); pymupdf stays in the reader.
# ---------------------------------------------------------------------------

import unicodedata

# A box this narrow is a ligature's second letter carrying no advance of its
# own, not a glyph. Measured at exactly 0.0 on every case seen; the tolerance
# is for fonts that round.
_ZERO_W = 0.15
# Two boxes ending within this of each other end at the same edge: halves of
# one glyph. Measured at exactly equal on every case seen.
_SAME_EDGE = 0.3


def repair_ligatures(chars):
    """[(c, x0, x1)] -> the same list with reversed ligatures put back.

    Measured 2026-09-22 against Word's own reading of ten files (TASKS N3):
    reversing a group gave the word Word read 2,597 times, keeping it as
    stored once (مال / ملا). Lam-alef is the commonest case, not the only one.

    A zero-width alef form immediately before a LAM is the two halves of one
    ligature glyph, handed back in the wrong order. All four of لا لأ لإ لآ
    reverse the same way and carry the same signature, so all four are covered
    here - where the orthographic rules above need two separate patterns and
    still cannot reach the word-final case at all.

    Nothing else is touched: the test is the glyph's own box, so a genuine
    alef beside a genuine lam, which is two glyphs with two boxes, is left
    exactly as stored - and so is a vowel mark, zero width by nature.

    Items are swapped intact, never rebuilt, so anything a caller carries after
    (char, x0, x1) rides along with its character.

    Each swap consumes both characters. Without that, the alef lands at i+1,
    the next step sees it beside the FOLLOWING lam and swaps again: زيلالي
    stored as زياللي came back زيللاي, moving the alef one place too far. The
    two halves of a ligature are one glyph and can only be swapped once.

    A second signature, 2026-09-22: in some fonts the first half is NOT zero
    width. The z22110258 bibliography, in Traditional Arabic, gives the alef
    of اإلعالم a box 6.45 wide - but the alef and the lam END AT THE SAME
    EDGE, because they are one glyph's two halves, and the lam runs on past
    it. Two real glyphs never share an edge like that. On ten files every
    zero-width case also had the shared edge; the edge alone found ~130 more
    broken words (األجل, االختالف) and fired on no correctly spelled one. A
    looser "the alef sits inside its neighbour's box" test did: غزال, تزال.
    """
    out = list(chars)
    i = 0
    while i < len(out) - 1:
        a, ax0, ax1 = out[i][:3]
        b, bx0, bx1 = out[i + 1][:3]
        one_glyph = ((ax1 - ax0) < _ZERO_W
                     or (abs(ax1 - bx1) < _SAME_EDGE and bx0 < ax0 - _SAME_EDGE))
        if a in HAMZA_ALEFS and b == LAM and one_glyph:
            out[i], out[i + 1] = out[i + 1], out[i]
            i += 2
            continue
        # Any other glyph that stands for several letters fails the same way
        # (2026-09-22): في stored يف, the lam-meem-jeem of المجتمع stored
        # اجملتمع, التي stored اليت. Every letter but the last comes back with
        # no width, at the glyph's right edge; the last carries the glyph and
        # ends at the same edge. The whole group is reversed.
        j = i
        while (j < len(out) and _is_letter(out[j][0])
               and (out[j][2] - out[j][1]) < _ZERO_W):
            j += 1
        if (j > i and j < len(out) and _is_letter(out[j][0])
                and abs(out[j][2] - out[i][2]) < _SAME_EDGE):
            out[i:j + 1] = out[i:j + 1][::-1]
            i = j + 1
        else:
            i = max(j, i + 1)
    return out


# Letters only. A vowel mark is zero width by nature and belongs to the
# letter BEFORE it, so a mark followed by a letter is not a glyph group. And a
# digit glued to a letter ("١ت", 279 times on z20763272) fits the geometry but
# neither order is a word Word read - something else, left alone.
def _is_letter(c):
    o = ord(c)
    # 0621-064A base letters (the marks at 064B+ are outside), 0671-06D3 the
    # extended ones - Persian yeh and keheh turn up in this corpus.
    return 0x0621 <= o <= 0x064A or 0x0671 <= o <= 0x06D3


# Unicode's own bidi classes, rather than a hand-written punctuation list.
# Letters and digits keep the order the PDF stored them in; only neutrals are
# moved, and only to where their own position says they belong.
#
# NSM - the combining marks - is in this set and must stay in it. A haraka has
# NO WIDTH and sits on top of the letter it belongs to, so its x is its base
# letter's x and the slot arithmetic cannot place it: treated as a neutral, the
# marks of a fully-vowelled text drift onto their neighbours. It was caught on
# a Quranic verse in `الفصل الخامس المبحث الثالث.pdf`, whose every letter is
# vowelled - {َوَالَّذِين came back {ََواَّلِذين - and it cost the hard gate
# 1.000 -> 0.944. A mark is not a neutral; it is part of the character before
# it, and it moves only when that character moves.
_STRONG = {"L", "R", "AL", "EN", "AN", "NSM"}


def _is_strong(c):
    return unicodedata.bidirectional(c) in _STRONG


def reorder_neutrals(chars, min_arabic=0.8):
    """[(c, x0, x1)] for ONE line -> the same characters in logical order.

    Some PDFs store a line's spaces and punctuation out of sequence. The
    heading `مقدمة:` is stored `:مقدمة`, colon first; and the first line of a
    paragraph stores its TRAILING space second, so `تبدأ الحكاية` arrives as
    `ت بدأ الحكاية` - a word split by a space that belongs at the far end of
    the line. Both are visible on the page as soon as you look, and no pymupdf
    mode orders them correctly (text, sort=True, blocks and words were all
    tried).

    Where a character truly belongs is not a guess: it is written on the page.
    In a right-to-left line the reading order is descending x, so a neutral
    goes after however many strong characters sit to its right.

    Only neutrals move. Letters and digits stay exactly as stored, so an
    embedded English phrase or a year cannot be reversed by this. Lines that
    are not overwhelmingly Arabic are left alone entirely - an English abstract
    has its own direction and nothing here would improve it.

    On text that is already stored correctly this is a no-op, because the
    neutrals are already in x order.
    """
    chars = list(chars)
    strong = [t for t in chars if _is_strong(t[0])]
    if len(strong) < 2:
        return chars

    arabic = sum(1 for t in strong
                 if unicodedata.bidirectional(t[0]) in ("AL", "AN"))
    if arabic / len(strong) < min_arabic:
        return chars

    # Where does each strong character sit? In stored order, for an RTL line,
    # x should be descending. Bail out if it is not - this line is laid out in
    # some way we have not seen, and leaving it is safer than rearranging it.
    xs = [t[1] for t in strong]
    if sum(1 for a, b in zip(xs, xs[1:]) if a >= b) < 0.8 * max(1, len(xs) - 1):
        return chars

    slots = [[] for _ in range(len(strong) + 1)]
    for item in chars:
        if _is_strong(item[0]):
            continue
        # How many strong characters lie to the right of this one?
        k = sum(1 for t in strong if t[1] > item[1])
        slots[min(k, len(strong))].append(item)

    out = []
    for i, s in enumerate(strong):
        out.extend(slots[i])
        out.append(s)
    out.extend(slots[len(strong)])
    return out


def repair_line(chars):
    """[(c, x0, x1, ...)] for ONE line -> the same items, repaired and ordered."""
    if not chars:
        return []
    return reorder_neutrals(repair_ligatures(chars))


def logical_text(chars):
    """[(c, x0, x1, ...)] for one line -> its text, repaired, as a string."""
    return "".join(t[0] for t in repair_line(chars))
