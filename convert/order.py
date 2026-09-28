"""Punctuation put back where the page draws it.

Word draws a right-to-left line in runs, each laid out left to right, and the
extractor turns a run's Arabic letters round into reading order - but leaves
a full stop or comma at the run's left end where it was. Drawn on the left of
a word, in a right-to-left line, a mark comes AFTER the word; stored at the
run's start it is read BEFORE it: ،عشر for عشر،, ا،جلزائر, اهل.امل, and a
line-final full stop at the start of the line (z21762915, z22658522).

Only where it is drawn settles it. Every mark on an Arabic line goes right
after the word it is drawn beside - the nearest word on its right. Letters
never move, so the letter-pair repairs that read the extractor's order of
letters (`arabic.repair_ligatures`) see what they always saw; spaces move
only on a line with numbers or Latin, and only one stranded at the line's
end (`_order_mixed`).

Every reading of a page's text goes through `get_text` here - the reader's
and the checker's alike - so both see the same order. Two attempts that
moved marks in the text AFTER extraction, as a find-and-replace, failed: a
mark crosses words, and a key several words long matched only where the two
sides happened to split the text alike (PLAN "Punctuation where it is
drawn"). Moving the mark inside the extracted line has no key to match.
"""
import os
import re
import unicodedata

import pymupdf

# Arabic letters, the stretching stroke, vowel marks, display shapes.
ARABIC = re.compile(r"[\u0621-\u064A\u066E-\u06D3\u06FA-\u06FF\u0640"
                    r"\u064B-\u065F\u0670\uFB50-\uFDFF\uFE70-\uFEFC]")
# Numbers and Latin run left to right inside a line; a line holding any is
# read by _order_mixed (DVB-S, 2 . 11 - TASKS N5c).
LEFT_TO_RIGHT = re.compile(r"[%٪A-Za-z0-9\u0660-\u0669\u06F0-\u06F9]")
LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
MARKS = set(".،,:؛;!؟?")
# What may stand between a word and its mark: it is already after the word.
BETWEEN = set(" ()[]«»\"'") | MARKS
TOL = 1.0          # points: a mark touching a word's left edge is beside it
# Share of a line's letters that must stand at a place of their own. Letters
# joined into one shape share a place, so not all of them.
PLACED = 0.5
# points: two letters this far apart are two words, whatever the stored text
# says - a mark stored between them was all that parted them.
GAP = 1.5
SPACE = None       # in an order: a space the stored text did not hold


def _combining(c):
    return unicodedata.combining(c) or 0x064B <= ord(c) <= 0x065F \
        or c == "\u0670"


def units(chars):
    """[[i, ...]]: each character with the vowel marks after it, so a line
    read with its marks and one read without them line up."""
    out = []
    for i, c in enumerate(chars):
        if out and _combining(c):
            out[-1].append(i)
        else:
            out.append([i])
    return out


def order(line, arabic_page=None):
    """line: [(char, x0, x1)] as extracted. -> the order to read its units
    in, a list of unit indices; None where nothing moves. `arabic_page`:
    called to ask whether the page is mostly Arabic."""
    if os.environ.get("QIRTAS_PUNCT_ORDER", "1") == "0":
        return None                # off, to measure against
    text = [c for c, _, _ in line]
    if not any(ARABIC.match(c) for c in text):
        # `( 40 .)`: the ` .)` a line of its own, stored as drawn left to
        # right; on an Arabic page it reads right to left. Not a line with a
        # number or word in it: `(2018)` after Riley is read as stored.
        if DRAWN_ON and arabic_page is not None \
                and any(c in BRACKETS for c in text) \
                and not any(c.isalnum() for c in text) and arabic_page():
            return _order_drawn(line)
        return None
    if DRAWN_ON and any(c in BRACKETS for c in text):
        if sum(1 for c in text if LATIN.match(c)) \
                > sum(1 for c in text if ARABIC.match(c)):
            return None            # an English line: see below
        return _order_drawn(line)
    if any(LEFT_TO_RIGHT.match(c) for c in text):
        if os.environ.get("QIRTAS_PUNCT_MIXED", "1") == "0":
            return None            # off, to measure against
        # An English line with Arabic words in it runs left to right: the
        # rule below took it for Arabic and lost text of `z22179435`'s and
        # `z21760107`'s English abstracts (the gate, 2026-09-23).
        if sum(1 for c in text if LATIN.match(c)) \
                > sum(1 for c in text if ARABIC.match(c)):
            return None
        return _order_mixed(line)
    if not any(c in MARKS for c in text):
        return None
    us = units(text)
    base = [line[u[0]] for u in us]          # a unit's letter and box
    # Only where the characters are really laid out: a line whose text is a
    # label over a drawing puts every character at one point (the theses:
    # all at x 310, no width), and there no position says anything.
    xs = {round(x0, 1) for c, x0, _ in base if ARABIC.match(c)}
    if len(xs) < PLACED * sum(1 for c, _, _ in base if ARABIC.match(c)):
        return None
    words, cur = [], []
    for k, (c, _, _) in enumerate(base):
        if ARABIC.match(c):
            cur.append(k)
        elif cur:
            words.append(cur)
            cur = []
    if cur:
        words.append(cur)
    # And only where they are read right to left already: a line stored in
    # drawing order (فدهلا for الهدف) is backwards as a whole, marks too.
    steps = [base[w[i]][1] - base[w[i + 1]][1] for w in words
             for i in range(len(w) - 1)]
    if sum(1 for d in steps if d > 0) < PLACED * sum(1 for d in steps if d):
        return None
    lefts = [min(base[k][1] for k in w) for w in words]
    after = {}
    moved = set()
    for k, (c, _, x1) in enumerate(base):
        if c not in MARKS:
            continue
        near = [(left, w) for w, left in enumerate(lefts) if left >= x1 - TOL]
        if not near:
            continue
        w = min(near)[1]
        last = words[w][-1]
        if k > last and all(base[j][0] in BETWEEN for j in range(last + 1, k)):
            continue                          # already after its word
        after.setdefault(last, []).append(k)
        moved.add(k)
    if not moved:
        return None
    out = []
    for k in range(len(base)):
        if k not in moved:
            out.append(k)
        elif 0 < k < len(base) - 1 and ARABIC.match(base[k - 1][0])                 and ARABIC.match(base[k + 1][0])                 and base[k - 1][1] - base[k + 1][2] > GAP:
            # بإدارة،الرصف: the comma goes, the gap it stood in stays
            out.append(SPACE)
        # several marks after one word: as drawn, right to left
        out.extend(sorted(after.get(k, ()), key=lambda j: -base[j][1]))
    # A vowel mark stored after a moved mark is the word's (مبكراً،, not
    # مبكرا،ً): the unit is read vowel marks first. Negative = so read.
    return [~k if k is not SPACE and k in moved else k for k in out]


# Besides the marks, what may stand misplaced between Arabic and a number or
# English word: the extractor stores it at the Arabic run's far end, like a
# mark (` وبأطوال30` for وبأطوال 30, `( ،فارس2002)` for فارس، (2002)).
SHIFTED = set(" ()[]")


def _order_mixed(line):
    """order() for a line holding numbers or Latin as well as Arabic.

    Each run of numbers or Latin is kept whole, with what lies inside it
    (2.11, DVB-S, Omega loop), and counts as a word. A mark goes after the
    word drawn on its right, as on an Arabic line; a space or bracket only
    where it is drawn beside a number or Latin run - between two Arabic
    words the stored spaces are left alone (PLAN "Spaces inside words")."""
    text = [c for c, _, _ in line]
    us = units(text)
    base = [line[u[0]] for u in us]
    arabic = [bool(ARABIC.match(c)) for c, _, _ in base]
    xs = {round(x0, 1) for (c, x0, _), a in zip(base, arabic) if a}
    if len(xs) < PLACED * sum(arabic):
        return None
    pct = _percent_first(base, arabic)
    if pct is not None:
        return pct
    ltr = [bool(LEFT_TO_RIGHT.match(c)) for c, _, _ in base]
    # Words: runs of Arabic letters; runs of numbers or Latin, taking in
    # anything stored and drawn between two of their characters.
    words, kinds, k = [], [], 0
    while k < len(base):
        if arabic[k]:
            w = [k]
            while k + 1 < len(base) and arabic[k + 1]:
                k += 1
                w.append(k)
            words.append(w)
            kinds.append("R")
        elif ltr[k]:
            w = [k]
            j = k + 1
            while j < len(base) and not arabic[j]:
                if ltr[j]:
                    lo = min(base[i][1] for i in w + [j])
                    hi = max(base[i][2] for i in w + [j])
                    if all(lo - TOL <= base[i][1] and base[i][2] <= hi + TOL
                           for i in range(w[-1] + 1, j)):
                        w.extend(range(w[-1] + 1, j + 1))
                        k = j
                    else:
                        break
                j += 1
            words.append(w)
            kinds.append("L")
        k += 1
    inside = {k for w in words for k in w}
    rtl = [w for w, t in zip(words, kinds) if t == "R"]
    steps = [base[w[i]][1] - base[w[i + 1]][1] for w in rtl
             for i in range(len(w) - 1)]
    if sum(1 for d in steps if d > 0) < PLACED * sum(1 for d in steps if d):
        return None
    lefts = [min(base[k][1] for k in w) for w in words]
    rights = [max(base[k][2] for k in w) for w in words]
    owner = {k: v for v, w in enumerate(words) for k in w}
    after = {}
    moved = set()
    for k, (c, x0, x1) in enumerate(base):
        if k in inside or not (c in MARKS or c in SHIFTED):
            continue
        # A mark stored right after a number or Latin run and drawn at its
        # right end is that run's, laid out left to right: `(Evershed,` at
        # a line's end, its comma drawn between Evershed and the Arabic
        # word before it (z21760107 - moved there, the gate lost it).
        p = next((j for j in range(k - 1, -1, -1)
                  if base[j][0] not in BETWEEN), None)
        if c in MARKS and p in owner and kinds[owner[p]] == "L" \
                and abs(x0 - rights[owner[p]]) <= 2 * TOL:
            continue
        near = [(left, w) for w, left in enumerate(lefts) if left >= x1 - TOL]
        if not near:
            continue
        w = min(near)[1]
        if c in SHIFTED:
            # Only one left stranded at the line's end or beside a mark: one
            # stored between two words is where it belongs (سبق  قدّم, and
            # the brackets of (TGV), drawn mirrored).
            p = next((j for j in range(k - 1, -1, -1) if base[j][0] != " "),
                     None)
            n = next((j for j in range(k + 1, len(base))
                      if base[j][0] != " "), None)
            if p is not None and n is not None and (arabic[p] or ltr[p]) \
                    and (arabic[n] or ltr[n]):
                continue
            if c != " " and ((p is not None and ltr[p])
                             or (n is not None and ltr[n])):
                continue
            far = [(-right, v) for v, right in enumerate(rights)
                   if right <= x0 + TOL]
            if kinds[w] != "L" and not (far and kinds[min(far)[1]] == "L"):
                continue
        last = words[w][-1]
        if k > last and all(base[j][0] in BETWEEN or j in moved
                            for j in range(last + 1, k)):
            continue                          # already after its word
        after.setdefault(last, []).append(k)
        moved.add(k)
    if not moved:
        return None
    out = []
    for k in range(len(base)):
        if k not in moved:
            out.append(k)
        out.extend(sorted(after.get(k, ()), key=lambda j: -base[j][1]))
    return [~k if k in moved else k for k in out]


DRAWN_ON = os.environ.get("QIRTAS_DRAWN_BRACKETS", "1") != "0"
BRACKETS = set("()[]")


def _order_drawn(line):
    """order() for an Arabic line holding a bracket: everything read as the
    page draws it.

    Word stores the brackets, full stops and spaces between an Arabic run and
    a number or English word at the run's far end, as drawn: a reference
    "ابن كثير، إسماعيل. (1999). تفسير" is stored `( .ابن كثير، إسماعيل1999`
    then ` .)تفسير`, and came out "( ابن كثير، إسماعيل. 1999 .) تفسير" - a
    third of the theses' brackets were out of place (PLAN "Brackets where
    the page draws them"). Here each Arabic word, and each number or English run, stays as
    stored, and the line's pieces are read right to left by where they are
    drawn; a number or English run with what lies between its parts (et al.,
    2020) is read left to right. What is drawn decides, so a reading that
    splits the line into pieces (the structure labels, `_Whole`) puts every
    bracket in the same place as one that reads it whole."""
    text = [c for c, _, _ in line]
    us = units(text)
    base = [line[u[0]] for u in us]
    arabic = [bool(ARABIC.match(c)) for c, _, _ in base]
    # Any other letter or digit runs left to right: Greek (λ1) and the math
    # letters of a formula (𝚫𝒚∕𝚫𝒙, `z3387756`) as much as Latin.
    ltr = [not a and (bool(LEFT_TO_RIGHT.match(c)) or c.isalnum())
           for (c, _, _), a in zip(base, arabic)]
    xs = {round(x0, 1) for (c, x0, _), a in zip(base, arabic) if a}
    if len(xs) < PLACED * sum(arabic):
        return None
    # A hamza or other small mark on a bracket is a font's broken digits
    # (`z15446639` stores ١ as ٔ): it would move with the bracket.
    if any(text[u[0]] in BRACKETS and any("ٓ" <= text[i] <= "ٟ"
                                          for i in u[1:]) for u in us):
        return None
    # Pieces, in stored order: a run of Arabic letters, a run of other
    # letters or digits, or one other character.
    pieces, k = [], 0
    while k < len(base):
        j = k + 1
        if arabic[k] or ltr[k]:
            same = arabic if arabic[k] else ltr
            while j < len(base) and same[j]:
                j += 1
        pieces.append([k, j, "R" if arabic[k] else "L" if ltr[k] else "N"])
        k = j
    steps = [base[i][1] - base[i + 1][1] for a, b, t in pieces if t == "R"
             for i in range(a, b - 1)]
    if sum(1 for d in steps if d > 0) < PLACED * sum(1 for d in steps if d):
        return None                    # stored in drawing order as a whole

    def span(p):
        return (min(base[i][1] for i in range(p[0], p[1])),
                max(base[i][2] for i in range(p[0], p[1])))
    boxes = [span(p) for p in pieces]
    for n, p in enumerate(pieces):
        if p[2] != "N" or base[p[0]][0] != " ":
            continue
        # A space between two Arabic words stays between them, wherever the
        # extractor put its box (PLAN "Spaces inside words").
        if 0 < n < len(pieces) - 1 and pieces[n - 1][2] == "R" \
                and pieces[n + 1][2] == "R":
            boxes[n] = (boxes[n + 1][1], boxes[n - 1][0])
    # A mark stored right after a number or Latin run and drawn at its right
    # end is that run's: `(Evershed,` at a line's end (z21760107).
    for n in range(1, len(pieces)):
        p, q = pieces[n - 1], pieces[n]
        if q[2] == "N" and p[2] == "L" and base[q[0]][0] in MARKS \
                and abs(boxes[n][0] - boxes[n - 1][1]) <= 2 * TOL:
            q[2] = "L+"
            boxes[n] = (boxes[n - 1][1] - 0.001, boxes[n - 1][1])
    order_ = sorted(range(len(pieces)),
                    key=lambda n: (-(boxes[n][0] + boxes[n][1]) / 2, n))
    out, i, inl = [], 0, set()
    while i < len(order_):
        if pieces[order_[i]][2] != "L":
            out.append(order_[i])
            i += 1
            continue
        last = i
        for j in range(i + 1, len(order_)):
            if pieces[order_[j]][2] == "R":
                break
            if pieces[order_[j]][2] == "L":
                last = j
        run = order_[i:last + 1]
        # A bracket closing one opened inside the run is the run's: I(2)
        # (`z3387756`), drawn left to right with it - at its right end, so
        # read just before it.
        while out and pieces[out[-1]][2] == "N":
            n = out[-1]
            c = base[pieces[n][0]][0]
            left = sum(base[pieces[m][0]][0] == MIRROR.get(c) for m in run) \
                - sum(base[pieces[m][0]][0] == c for m in run)
            if c not in ")]" or left <= 0 or \
                    boxes[n][0] > max(boxes[m][1] for m in run) + 2 * TOL:
                break
            run.append(out.pop())
        inl.update(run)
        out.extend(sorted(run, key=lambda n: ((boxes[n][0] + boxes[n][1]) / 2,
                                              n)))
        i = last + 1
    # Arabic words never change places: only what lies between them moves.
    # Where reading by position would move one, the positions are not to be
    # trusted - `z21145041` stores لوبلا يف for في البول, words drawn left to
    # right, and has a stray letter drawn far from its word; read as drawn,
    # both turned round, and the gate lost 3% of that file.
    words = [n for n in out if pieces[n][2] == "R"]
    if words != sorted(words):
        return None
    inside = frozenset(k for n in inl for k in range(*pieces[n][:2]))
    seq, prev = Seq(), None
    for n in out:
        a, b, t = pieces[n]
        # A vowel mark stored after a bracket is the letter's before it
        # (أنموذجاً), read first either way: see order().
        moved = t in ("N", "L+") and (prev != (n - 1 if n else None)
                                      or len(us[a]) > 1)
        seq.extend(~k if moved else k for k in range(a, b))
        prev = n
    # Kept even where nothing moves: `_turn` may still turn a bracket.
    seq.flip = _drawn_shapes([k for n in out for k in range(*pieces[n][:2])],
                             base, arabic, ltr, inside)
    seq.inside = inside
    return seq


class Seq(list):
    """A unit order read as drawn (_order_drawn), with the units whose
    bracket is to be turned round, and those inside a number or Latin run."""
    flip = frozenset()
    inside = frozenset()


MIRROR = {"(": ")", ")": "(", "[": "]", "]": "["}
# Two of the extractor's lines are one printed line when they share this
# much of the shorter one's height.
ROW = 0.6


def _drawn_shapes(read, base, arabic, ltr, inside):
    """Brackets stored as the shape drawn, not the bracket meant.

    Word draws a bracket in a right-to-left line turned round, and some fonts
    (Times New Roman in an Arabic line, most often) store the shape: "(62)"
    is stored `)62(`, and written so Word draws it `)62(` (`z7456037`,
    `z3387756`). Read in order, such a bracket gives itself away: a `)` with
    a space before it and a word right after opens, a `(` after a word with
    a space after it closes. Where a line's brackets say so and none says
    otherwise, its brackets at the line's ends are turned round too. Asked
    of a whole printed line (`_Whole.turns`), not only of the piece the
    extractor cut it into: ` جدول رقم )`, `29` and `( :` are three pieces
    (`z7456037`), and none of them alone says which way its bracket is.
    `read`: the units in reading order; `inside`: units inside a number or
    Latin run, drawn left to right and so as meant. -> {unit}"""
    def word(i):
        return 0 <= i < len(read) and (arabic[read[i]] or ltr[read[i]])

    def gap(i):
        return 0 <= i < len(read) and not word(i)
    turned, sure, loose = set(), 0, set()
    for i, k in enumerate(read):
        c = base[k][0]
        if c not in MIRROR or k in inside:
            continue
        opens = c in "(["
        before, after = (word(i - 1), gap(i + 1)) if opens else (gap(i - 1), word(i + 1))
        if before and after:
            turned.add(k)              # `word( ` or ` )word`: turned round
        elif (gap(i - 1) or i == 0) and word(i + 1) if opens else \
                word(i - 1) and (gap(i + 1) or i == len(read) - 1):
            sure += 1                  # `(word` or `word)`: as meant
        else:
            loose.add(k)
    if not turned or sure:
        return frozenset()
    return frozenset(turned | loose)


PERCENT = "%٪"


def _percent_first(base, arabic):
    """A % that ends the stored line but is drawn at its right end starts
    it: `  من حالات%` is `% من حالات`, the % of the 15 drawn just right of
    it in the piece before (`z20252507`, 15% من حالات). None otherwise.
    QIRTAS_TIGHT=0 turns it off, with the reader's joins beside it."""
    if os.environ.get("QIRTAS_TIGHT", "1") == "0":
        return None
    k = next((j for j in range(len(base) - 1, -1, -1)
              if base[j][0] != " "), None)
    if k is None or base[k][0] not in PERCENT or not any(arabic):
        return None
    # and only on a line read right to left, not one stored backwards
    steps = [base[j][1] - base[j + 1][1] for j in range(len(base) - 1)
             if arabic[j] and arabic[j + 1] and base[j][1] != base[j + 1][1]]
    if sum(1 for d in steps if d > 0) < PLACED * len(steps):
        return None
    others = [base[j] for j in range(len(base)) if j != k and base[j][0] != " "]
    if any(LEFT_TO_RIGHT.match(c) for c, _, _ in others) or \
            any(x1 > base[k][1] + TOL for _, _, x1 in others):
        return None
    return [~k] + [j for j in range(len(base)) if j != k]


def _moved(us, seq):
    """Character indices of the units `seq` moves."""
    return {i for k in seq if k is not SPACE and k < 0 for i in us[~k]}


def _turned(us, seq):
    """Character indices of the brackets `seq` turns round."""
    return {us[k][0] for k in getattr(seq, "flip", ())}


def _indices(us, seq):
    """Character indices in the order `seq` reads the units."""
    out = []
    for k in seq:
        if k is SPACE:
            out.append(None)
            continue
        u = us[~k] if k < 0 else us[k]
        out.extend(u[1:] + u[:1] if k < 0 else u)
    return out


def _chars(line):
    return [c for s in line["spans"] for c in s["chars"]]


def _alike(a, b):
    """May a mark moved out of span `b` join span `a`? Not across a change
    of size: the span before it may be a raised note number, `(1)`, and a
    comma taken into it left a `)` in the text (`z18048055`)."""
    return abs(a.get("size", 0) - b.get("size", 0)) <= 0.1 * max(
        a.get("size", 0), b.get("size", 0), 1)


def _key(c):
    """A character by where it is drawn: the same in every reading."""
    return c["c"], round(c["bbox"][0], 1), round(c["bbox"][1], 1)


def _turn(seq, chars, whole):
    """`seq` with its brackets turned round as the whole printed line says
    (`_Whole.turns`); `chars`: the rawdict line's characters. Only a line
    read as drawn, right to left, and only a bracket outside a number or
    Latin run: one read left to right is read as meant (`(Gobira, 2023;19)`,
    an English piece of its own on an Arabic line, `z17366480`). And in a
    reading by structure labels, not a bracket that is a line on its own:
    there it is already in the order Word wrote it, `(` `Maina,` ... `249`
    `)` (`z20306213`) - turned, it read `)Maina, ... 249(`. One with a mark
    beside it, `(  :` after `58` (`z7456037`), is stored as drawn."""
    if not isinstance(seq, Seq):
        return seq
    alone = sum(1 for c in chars if not c["c"].isspace()) <= 1
    if whole is not None and not (whole.off and alone):
        turns = whole.turns()
        flip = set(seq.flip)
        for k, u in enumerate(units([c["c"] for c in chars])):
            said = turns.get(_key(chars[u[0]])) if k not in seq.inside else None
            if said is True:
                flip.add(k)
            elif said is False:
                flip.discard(k)
        seq.flip = frozenset(flip)
    # Nothing moved and nothing turned: the line is left exactly as it was.
    # Rebuilt, a mark joins the piece before it, and the full stop after a
    # raised note number `(1)` became part of it - a `)` was left in the
    # text (`z18048055`).
    if not seq.flip and list(seq) == list(range(len(seq))):
        return None
    return seq


def _fix_raw(line, whole=None):
    """Reorder one rawdict line in place; -> (stored, read) or None.
    `whole`: see _Whole."""
    chars = _chars(line)
    seq = _turn(order([(c["c"], c["bbox"][0], c["bbox"][2]) for c in chars],
                      whole.letterless(line) if whole else None), chars, whole)
    if seq is None or (whole and not whole.keeps(
            "".join(c["c"] for c in chars))):
        return None
    new = []
    shifted = {id(chars[i]) for i in _moved(units([c["c"] for c in chars]),
                                             seq)}
    turned = _turned(units([c["c"] for c in chars]), seq)
    copied = {}
    for i in _indices(units([c["c"] for c in chars]), seq):
        if i is None:                # the gap a moved mark stood in
            a = new[-1]
            new.append(dict(a, c=" ", bbox=(a["bbox"][0] - 0.01,
                                            a["bbox"][1], a["bbox"][0],
                                            a["bbox"][3])))
        elif i in turned:
            new.append(dict(chars[i], c=MIRROR[chars[i]["c"]]))
            copied[id(new[-1])] = chars[i]
        else:
            new.append(chars[i])
    stored = "".join(c["c"] for c in chars)
    # A moved mark, space or bracket joins the span of the character now
    # before it.
    owner = {id(c): s for s in line["spans"] for c in s["chars"]}
    for s in line["spans"]:
        s["chars"] = []
    prev = None
    for c in new:
        was = copied.get(id(c), c)   # a bracket turned round is a copy
        before = None if prev is None else owner.get(id(copied.get(id(prev), prev)))
        mine = id(was) in owner and (before is None or (
            c["c"] not in MARKS and id(was) not in shifted)
            or not _alike(before, owner[id(was)]))
        s = owner[id(was)] if mine else before
        s["chars"].append(c)
        prev = c
    line["spans"] = [s for s in line["spans"] if s["chars"]]
    return stored, "".join(c["c"] for c in new)


def _reorder(text, seq, n):
    """Apply a unit order to a line read another way (with or without its
    vowel marks); None if its units do not line up."""
    us = units(text)
    if len(us) != n:
        return None
    turned = _turned(us, seq)
    return "".join(" " if i is None else MIRROR[text[i]] if i in turned
                   else text[i] for i in _indices(us, seq))


class _Whole:
    """Is a line holding numbers or Latin one line in the structure-tree
    reading too?

    A tagged PDF's reader (`read_tags`) reads the page by its structure
    labels, and Word labels an English word or a number apart: there
    `معين (Benchmark` is two lines, `معين` and `Benchmark`, and no line
    holds both. Read plainly - as the checker and the geometry reader do -
    it is one, and _order_mixed moved its bracket; the two readings
    disagreed and the gate lost the sentence on seven files (2026-09-23).
    Such a line is reordered only where both readings see it whole.
    Computed once per page, only when a mixed line asks."""

    def __init__(self, page, flags, clip):
        self.page, self.clip, self.lines = page, clip, None
        self.off = bool(flags & pymupdf.TEXT_COLLECT_STRUCTURE)
        self._arabic = None
        self._turns = None

    def turns(self):
        """{character by place (_key): is this bracket turned round?} for
        every bracket on an Arabic printed line: the extractor's pieces on
        one baseline put back together and read as drawn (_drawn_shapes).
        From the plain reading, so a reading by structure labels, which cuts
        lines apart, turns the same brackets."""
        if self._turns is None:
            self._turns = {}
            kw = {} if self.clip is None else {"clip": self.clip}
            rows = []
            for b in self.page.get_text("rawdict", **kw)["blocks"]:
                for line in b.get("lines", ()):
                    if abs(line["dir"][1]) > 0.1:
                        continue
                    y0, y1 = line["bbox"][1], line["bbox"][3]
                    for r in rows:
                        if min(r[1], y1) - max(r[0], y0) > \
                                ROW * min(r[1] - r[0], y1 - y0):
                            r[0], r[1] = min(r[0], y0), max(r[1], y1)
                            r[2].extend(_chars(line))
                            break
                    else:
                        rows.append([y0, y1, _chars(line)])
            for _, _, chars in rows:
                if not any(c["c"] in MIRROR for c in chars):
                    continue
                seq = order([(c["c"], c["bbox"][0], c["bbox"][2])
                             for c in chars], self.arabic)
                if not isinstance(seq, Seq):
                    continue
                us = units([c["c"] for c in chars])
                for k, u in enumerate(us):
                    if chars[u[0]]["c"] in MIRROR and k not in seq.inside:
                        self._turns[_key(chars[u[0]])] = k in seq.flip
        return self._turns

    def letterless(self, line):
        """`arabic_page` for order(): a line with no letters is read right to
        left on an Arabic page - but in a reading by structure labels only
        when it is one piece (` .)` of `( 40 .)`). Pieces formatted apart
        are already in the order Word wrote them: `)` + ` ،` after a raised
        note number was read `)،`, the comma was taken into the number, and
        a `)` was left in the text (`z18048055`)."""
        return None if self.off and len(line["spans"]) > 1 else self.arabic

    def arabic(self):
        """Is the page mostly Arabic? Asked by a line with no letters."""
        if self._arabic is None:
            t = self.page.get_text("text")
            self._arabic = sum(1 for c in t if ARABIC.match(c)) \
                > sum(1 for c in t if LATIN.match(c))
        return self._arabic

    def keeps(self, text):
        if DRAWN_ON and any(c in BRACKETS for c in text):
            return True                # read as drawn: see _order_drawn
        if self.off or not (any(ARABIC.match(c) for c in text)
                            and any(LEFT_TO_RIGHT.match(c) for c in text)):
            return True
        if self.lines is None:
            kw = {"flags": pymupdf.TEXTFLAGS_DICT
                  | pymupdf.TEXT_COLLECT_STRUCTURE}
            if self.clip is not None:
                kw["clip"] = self.clip
            self.lines = set()

            def walk(node):
                for b in node.get("blocks", ()):
                    for line in b.get("lines", ()):
                        self.lines.add(_bare(
                            "".join(c["c"] for c in _chars(line))))
                    walk(b)
            walk(self.page.get_text("rawdict", **kw))
        return _bare(text) in self.lines


def _line_orders(page, flags, clip):
    """{stored line, vowel marks left out: [(unit order, units)]} for every
    line that changes, in page order."""
    kw = {"flags": flags}
    if clip is not None:
        kw["clip"] = clip
    out = {}
    whole = _Whole(page, flags, clip)

    def walk(node):
        for b in node.get("blocks", ()):
            for line in b.get("lines", ()):
                chars = _chars(line)
                text = [c["c"] for c in chars]
                seq = _turn(order([(c["c"], c["bbox"][0], c["bbox"][2])
                                   for c in chars], whole.letterless(line)),
                            chars, whole)
                if seq is not None and whole.keeps("".join(text)):
                    out.setdefault(_bare("".join(text)), []).append(
                        (seq, len(units(text))))
            walk(b)             # a structure tree nests blocks in nodes

    walk(page.get_text("rawdict", **kw))
    return out


def _bare(t):
    return "".join(c for c in t if not _combining(c))


def _fix_text(text, orders):
    """Apply the line orders to plain text: each line looked up by its own
    text, so a line one reading splits differently costs only itself - and
    where the plain text runs a line on into the next (منه, و against
    منه, وقال), looked for inside the longer one. Takes the orders it uses
    out of `orders`."""
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        todo = orders.get(_bare(ln))
        if todo:
            seq, n = todo.pop(0)
            fixed = _reorder(ln, seq, n)
            if fixed is not None:
                lines[i] = fixed
    for stored, todo in orders.items():
        while todo and len(stored) >= 6:
            for i, ln in enumerate(lines):
                keep = [j for j, c in enumerate(ln) if not _combining(c)]
                at = "".join(ln[j] for j in keep).find(stored)
                if at < 0:
                    continue
                start = keep[at]
                end = keep[at + len(stored) - 1] + 1
                while end < len(ln) and _combining(ln[end]):
                    end += 1
                seq, n = todo[0]
                fixed = _reorder(ln[start:end], seq, n)
                if fixed is not None:
                    lines[i] = ln[:start] + fixed + ln[end:]
                break
            todo.pop(0)
    return "\n".join(lines)


def _fix_dict_line(line, orders):
    """Apply a line order found by the line's text to a dict line: the
    spans keep their characters, a moved mark joining the span of the
    character now before it."""
    owned = [(k, c) for k, sp in enumerate(line["spans"]) for c in sp["text"]]
    text = "".join(c for _, c in owned)
    todo = orders.get(_bare(text))
    if not todo:
        return
    seq, n = todo[0]
    us = units([c for _, c in owned])
    if len(us) != n:
        return
    todo.pop(0)
    spans = [[] for _ in line["spans"]]
    shifted = _moved(us, seq)
    turned = _turned(us, seq)
    prev = None
    for i in _indices(us, seq):
        k, c = (prev, " ") if i is None else owned[i]
        if i in turned:
            c = MIRROR[c]
        if (c in MARKS or i in shifted) and prev is not None \
                and _alike(line["spans"][prev], line["spans"][k]):
            k = prev
        spans[k].append(c)
        prev = k
    for sp, cs in zip(line["spans"], spans):
        sp["text"] = "".join(cs)


def _walk(node, orders):
    """Every line, however deep: a structure tree nests blocks in nodes."""
    for b in node.get("blocks", ()):
        for line in b.get("lines", ()):
            _fix_dict_line(line, orders)
        _walk(b, orders)


def get_text(page, kind="text", **kw):
    """page.get_text, with each Arabic line's punctuation where it is drawn."""
    if kind == "rawdict":
        raw = page.get_text("rawdict", **kw)
        whole = _Whole(page, kw.get("flags", pymupdf.TEXTFLAGS_RAWDICT),
                       kw.get("clip"))
        def walk(node):          # a structure tree nests blocks in nodes
            for b in node.get("blocks", ()):
                for line in b.get("lines", ()):
                    _fix_raw(line, whole)
                walk(b)
        walk(raw)
        return raw
    if kind == "dict":
        # The dict is MuPDF's own - a structure tree nests its blocks
        # differently in a rawdict - and each line's order is found by its
        # text in a rawdict read with the same flags.
        got = page.get_text("dict", **kw)
        # read the same way, so its lines are split alike
        flags = kw.get("flags", pymupdf.TEXTFLAGS_DICT)
        orders = _line_orders(page, flags, kw.get("clip"))
        if orders:
            _walk(got, orders)
        return got
    if kind in ("text", "blocks"):
        flags = kw.get("flags", pymupdf.TEXTFLAGS_TEXT if kind == "text"
                       else pymupdf.TEXTFLAGS_BLOCKS)
        orders = _line_orders(page, flags, kw.get("clip"))
        got = page.get_text(kind, **kw)
        if not orders:
            return got
        if kind == "text":
            return _fix_text(got, orders)
        return [b[:4] + (_fix_text(b[4], orders),) + tuple(b[5:])
                for b in got]
    return page.get_text(kind, **kw)
