"""Punctuation put back where the page draws it.

Word draws a right-to-left line in runs, each laid out left to right, and the
extractor turns a run's Arabic letters round into reading order - but leaves
a full stop or comma at the run's left end where it was. Drawn on the left of
a word, in a right-to-left line, a mark comes AFTER the word; stored at the
run's start it is read BEFORE it: ،عشر for عشر،, ا،جلزائر, اهل.امل, and a
line-final full stop at the start of the line (z21762915, z22658522).

Only where it is drawn settles it. Every mark on an Arabic line goes right
after the word it is drawn beside - the nearest word on its right. Letters
and spaces never move, so the letter-pair repairs that read the extractor's
order of letters (`arabic.repair_ligatures`) see what they always saw.

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
# A line holding any of these is left alone: numbers and Latin run left to
# right inside the line, and where a mark beside them goes is not the
# nearest-word question (DVB-S, 2 . 11 - TASKS N5c).
LEFT_TO_RIGHT = re.compile(r"[%٪A-Za-z0-9\u0660-\u0669\u06F0-\u06F9]")
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


def order(line):
    """line: [(char, x0, x1)] as extracted. -> the order to read its units
    in, a list of unit indices; None where nothing moves."""
    if os.environ.get("QIRTAS_PUNCT_ORDER", "1") == "0":
        return None                # off, to measure against
    text = [c for c, _, _ in line]
    if not any(ARABIC.match(c) for c in text) \
            or any(LEFT_TO_RIGHT.match(c) for c in text) \
            or not any(c in MARKS for c in text):
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


def _fix_raw(line):
    """Reorder one rawdict line in place; -> (stored, read) or None."""
    chars = _chars(line)
    seq = order([(c["c"], c["bbox"][0], c["bbox"][2]) for c in chars])
    if seq is None:
        return None
    new = []
    for i in _indices(units([c["c"] for c in chars]), seq):
        if i is None:                # the gap a moved mark stood in
            a = new[-1]
            new.append(dict(a, c=" ", bbox=(a["bbox"][0] - 0.01,
                                            a["bbox"][1], a["bbox"][0],
                                            a["bbox"][3])))
        else:
            new.append(chars[i])
    stored = "".join(c["c"] for c in chars)
    # A moved mark joins the span of the character now before it.
    owner = {id(c): s for s in line["spans"] for c in s["chars"]}
    for s in line["spans"]:
        s["chars"] = []
    prev = None
    for c in new:
        mine = id(c) in owner and (prev is None or c["c"] not in MARKS)
        s = owner[id(c)] if mine else owner[id(prev)]
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
    return "".join(" " if i is None else text[i] for i in _indices(us, seq))


def _line_orders(page, flags, clip):
    """{stored line, vowel marks left out: [(unit order, units)]} for every
    line that changes, in page order."""
    kw = {"flags": flags}
    if clip is not None:
        kw["clip"] = clip
    out = {}

    def walk(node):
        for b in node.get("blocks", ()):
            for line in b.get("lines", ()):
                chars = _chars(line)
                text = [c["c"] for c in chars]
                seq = order([(c["c"], c["bbox"][0], c["bbox"][2])
                             for c in chars])
                if seq is not None:
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
    prev = None
    for i in _indices(us, seq):
        k, c = (prev, " ") if i is None else owned[i]
        if c in MARKS and prev is not None:
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
        for b in raw["blocks"]:
            for line in b.get("lines", ()):
                _fix_raw(line)
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
