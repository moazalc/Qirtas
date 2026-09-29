"""The reader: work out what is in the PDF.

Three ways of looking, because no single one works everywhere:

  tags      the labels' own /ActualText. The theses keep their words only
            there - their glyphs decode to nothing.
  labels    Word's labels for what each piece IS, over the page's glyph text
            for what it SAYS. Ordinary Word files.
  geometry  group lines by position on the page. Works when labels are missing.

We run all three and keep whichever recovered more Arabic, preferring the
labelled ones when they come close — measure, don't predict.
"""
import collections
import difflib
import functools
import os
import re
import statistics
from pathlib import Path
import pikepdf
import pymupdf

from convert.model import Doc, Block, PARAGRAPH, HEADING, LIST_ITEM, FOOTNOTE, IMAGE, TABLE
from convert.arabic import repair_lam_alef
from convert.pdftext import apply_fixes, fix_map
from convert.footnotes import MARK_OPEN, MARK_CLOSE, marker_numbers
from convert.glyphs import shown_digits
from convert.order import get_text

# Structure labels that mean "a block starts here".
BLOCK_TAGS = {
    "/P": PARAGRAPH, "/Textbox": PARAGRAPH, "/Caption": PARAGRAPH,
    "/Title": HEADING, "/H": HEADING,
    "/H1": HEADING, "/H2": HEADING, "/H3": HEADING,
    "/H4": HEADING, "/H5": HEADING, "/H6": HEADING,
    "/LI": LIST_ITEM,
    "/Footnote": FOOTNOTE, "/Note": FOOTNOTE,
}
ARABIC = re.compile(r"[؀-ۿ]")
WS = re.compile(r"[ \t ]+")


# A zero-width non-joiner (U+200C) where the space belongs: `z21850164`
# stores one between every pair of words, 2,636 in 14 pages, and Word draws
# it as nothing - the whole thesis came out glued (`البعدالقيميوالروحي`).
# The scoring already read it as a space (harness/loss.py), so no score saw.
ZWNJ_ON = os.environ.get("QIRTAS_ZWNJ", "1") != "0"


def _clean(s):
    # Every route's text passes through here, which makes it the one place the
    # lam-alef repair has to go - see convert/arabic.py.
    if ZWNJ_ON and s:
        s = s.replace("‌", " ")
    s = repair_lam_alef(s)
    s = WS.sub(" ", (s or "").replace("\r", " ").replace("\n", " ")).strip()
    # A sign read from its own label is set apart by spaces (_sign_reader);
    # the punctuation after it belongs against it, as in the original.
    return SIGN_GAP.sub(r"\1", s)


SIGN_GAP = re.compile("([" + chr(0xFDFA) + chr(0xFD47) + r"]) (?=[،؛,.:)])")


SENT_SPLIT = re.compile(r"[.؟!؛:\n]+|،")
MIN_SENT = 40

# Is a sentence already present? Not an exact test, deliberately.
#
# The two readers extract through different pymupdf modes which disagree about
# where spaces fall, and the lam-alef repair is space-sensitive, so one route
# yields "...ومنها الشاذ" and the other "...ومنهالا شاذ" - the same words,
# repaired on one side only. An exact substring test read that as missing and
# backfilled the whole paragraph a second time. Five such duplicates on one
# chapter added a page, and every page after it was one out of step.
#
# Folding both letter orders onto one symbol does not work: the two strings
# consume different pairs and the misalignment cascades. So sample instead.
# Text that is genuinely absent - which is what backfill exists to catch -
# matches no window at all, while text differing by a character or two still
# matches most of them.
WINDOW = 12
SAMPLES = 5
PRESENT_AT = 0.6


# The windows must also be found together, within about the sentence's own
# length. Anywhere in the text was enough before, and a reference list repeats
# itself: entry 30 of z21145041 has entry 16's title with another publisher,
# four of its five windows were found in entry 16, and it was never put back
# (FLAGS 29). QIRTAS_NEAR=0 for the old test.
NEAR_ON = os.environ.get("QIRTAS_NEAR", "1") != "0"
NEAR_AT = 0.9     # share of a sentence's letters that must line up
TURN_ON = os.environ.get("QIRTAS_BACKFILL_TURN", "1") != "0"
TURN_WORD = re.compile("[\u0621-\u064A]{4,}")
LATIN_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]+")
TURNED_AT = 0.8     # share of a block's words already there, either way round
LOOSE_ON = os.environ.get("QIRTAS_BACKFILL_LOOSE", "1") != "0"


def _present(sent, have):
    if len(sent) <= WINDOW:
        return sent in have
    last = len(sent) - WINDOW
    spots = sorted({round(i * last / (SAMPLES - 1)) for i in range(SAMPLES)})
    need = len(spots) * PRESENT_AT
    if not NEAR_ON:
        return sum(1 for i in spots if sent[i:i + WINDOW] in have) >= need
    # Where the samples say the sentence sits, it must also read the same,
    # letter by letter. Found anywhere was enough before, and a reference
    # list repeats itself: entry 30 of z21145041 is entry 16's title with
    # another publisher, its samples were all found in entry 16, and it was
    # never put back (FLAGS 29). Counting samples cannot separate that from
    # ومنها الشاذ / ومنهالا شاذ - two letters swapped in a short sentence
    # spoil as many samples as a new publisher in a long one. How many
    # letters line up can: 97% against 80%.
    starts = []
    for i in spots:
        w = sent[i:i + WINDOW]
        at = have.find(w)
        while at >= 0:
            starts.append(at - i)
            at = have.find(w, at + 1)
    slack = max(WINDOW, len(sent) // 4)
    for at in sorted(set(starts)):
        # Only where enough samples agree on the start, give or take.
        if sum(1 for x in starts if abs(x - at) <= slack) < need:
            continue
        near = have[max(0, at - slack): at + len(sent) + slack]
        same = sum(b.size for b in difflib.SequenceMatcher(
            None, sent, near, autojunk=False).get_matching_blocks())
        if same >= NEAR_AT * len(sent):
            return True
    return False


def _sentences(t):
    return [x for x in (_bare(s) for s in SENT_SPLIT.split(t or ""))
            if len(x) >= MIN_SENT]


# Vowel marks and the stretching stroke: two readings of one line place them
# differently (ًدورا against دوراً), and the backfill below compares readings.
MARKS = re.compile("[ً-ْٰـ]")


def _bare(t):
    return MARKS.sub("", WS.sub("", t or ""))


def _drawn_at(pieces, pdf):
    """page -> [(x0, x1, baseline from the top, letters)] of the labelled
    pieces with letters drawn, for the backfill to ask what is drawn where."""
    out = collections.defaultdict(list)
    tall = {}
    for p in pieces:
        letters = "".join(ARABIC_LETTER.findall(p))
        if not letters:
            continue
        pg = p.marks[0][0]
        if pg not in tall:
            try:
                box = pdf.pages[pg].mediabox
                tall[pg] = float(box[3])
            except Exception:
                tall[pg] = 0.0
        if not tall[pg]:
            continue
        for m in p.marks:
            # Each stretch of the piece's letters; the letters go with the
            # first, so a piece is counted once, where it starts.
            out[pg].append((m[1], m[2], tall[pg] - m[3], letters))
            letters = ""
    return dict(out)


# Letters a reading holds drawn where another reading's paragraph is. The
# labels of `z22058810` hold its opening verse right, and the glyphs hold it
# backwards, cut at every vowel mark: رَب ُهاَضْرَت اًحِلاَص. Asked by its words
# there is nothing four letters long to ask about, and by its sentences it
# reads backwards, so the backfill wrote it a second time under the verse
# (FLAGS 32). What is drawn in the same place on the page settles it:
# the labels' pieces there hold the same letters. Letters alone, asked of the
# whole page, cannot: a paragraph from another page shares 85% of them
# (QIRTAS_BACKFILL_PLACE).
PLACE_ON = os.environ.get("QIRTAS_BACKFILL_PLACE", "1") != "0"
PLACE_AT = 0.9


def _drawn_there(b, at):
    """Whether the letters of reading `b` are drawn where it is, in the
    chosen reading's pieces (`_drawn_at`)."""
    want = collections.Counter(ARABIC_LETTER.findall(b.text))
    n = sum(want.values())
    if not n or not (b.y1 > b.y) or b.page not in at:
        return False
    size = max(4.0, (b.y1 - b.y) * 0.1)
    have = collections.Counter()
    for x0, _, top, letters in at[b.page]:
        if letters and b.y - size <= top <= b.y1 + size \
                and b.x0 - size <= x0 <= b.x1 + size:
            have.update(letters)
    return sum(min(v, have[k]) for k, v in want.items()) >= PLACE_AT * n


def _backfill(chosen, results, path, fix=None):
    """Recover anything the chosen reader missed but another reader found.

    Preferring the labelled reader for its structure cost one Quranic verse on
    one file: 110 characters present in the geometry reading and absent from
    the labels. Losing text is the one thing that is not allowed, so rather
    than trade structure against completeness, take the structure and put back
    whatever went missing.

    Recovered text is placed on the page it actually appears on, so page
    alignment is not disturbed.

    `fix`: the spelling repair the chosen reading has had (read()). The other
    readings are compared, and taken, repaired the same way. Unrepaired, a
    sentence the chosen reading spells right - الهوية - did not match its
    other reading's اهلوية, looked missing, and was added again: 3,482 of
    `z21762915`'s 9,629 words were a second, misspelled copy (FLAGS 25).
    """
    fix = fix or (lambda t: t)
    # Table cells too: a header band read as a table holds its line there.
    have = "".join(_bare(b.text) + "".join(_bare(c) for row in (b.rows or [])
                                            for c in row)
                   for b in chosen.blocks)
    every = " ".join(b.text + " " + " ".join(c for row in (b.rows or []) for c in row)
                     for b in chosen.blocks)
    words = set(TURN_WORD.findall(every))
    latin = set(LATIN_WORD.findall(every))
    # A word stored backwards is not always ours turned round: the alef
    # carrying a tanween lands at the other end (مراصا for صارماً), and two
    # words run together (نامضلتانايبلا). Asked only by the exact word, turned
    # or not, `z21145041`'s paragraph at page 11 found 37 of its 47 words,
    # short of the 80%, and was written a second time backwards - seven
    # paragraphs there, four on `z22058810` (QIRTAS_BACKFILL_LOOSE).
    loose = LOOSE_ON
    same = {"".join(sorted(w)) for w in words}

    def exact(w):
        return w in words or w[::-1] in words or \
            (loose and "".join(sorted(w)) in same)

    def known(w):
        # A letter of the next word taken in, or its own left behind, at
        # either end (تراطإ: إطار and the ت of تستخدم; يدصر for رصدياً).
        return exact(w) or (loose and len(w) >= 5 and (
            exact(w[1:]) or exact(w[:-1]) or exact(w + "ا") or exact("ا" + w)))

    def there(w):
        return known(w) or (loose and any(
            known(w[:k]) and known(w[k:]) for k in range(4, len(w) - 3)))
    added = False
    at = getattr(chosen, "drawn_at", None)
    for _, other in results:
        if other is chosen:
            continue
        for b in other.blocks:
            # A picture's description is not text the page printed. Backfilled,
            # Word's "A green circle with white letters AI-generated content
            # may be incorrect" - an ORCID icon's /Alt - took a page of its own
            # in `z21095413` and put every later page one out of step.
            if b.from_alt:
                continue
            text = fix(b.text)
            sents = _sentences(text)
            if not sents:
                continue
            # A reading that stores lines backwards (يمازلإلا for الإلزامي)
            # has them the other way round from the chosen one, often only
            # some lines of a paragraph. Unchecked, z21145041 was written with
            # 1,431 of its 2,151 Arabic words a second time, backwards
            # (FLAGS 29). Asked word by word, either way round: turning a
            # whole sentence also turns its numbers and English, and lam-alef
            # and marks land differently. English is not asked - a reference
            # list entry missing from the chosen reading is all English.
            ws = TURN_WORD.findall(text) if TURN_ON else []
            # The loose match only for a paragraph that reads backwards - more
            # of its words ours only turned round than only as they stand. A
            # paragraph the right way round has its words in the rest of the
            # thesis too: `z21145041`'s title, missing from the chosen
            # reading, matched loosely and was not put back.
            turned = sum(1 for w in ws if w[::-1] in words and w not in words) \
                > sum(1 for w in ws if w in words and w[::-1] not in words)
            if len(ws) >= 3 and sum(1 for w in ws if (there(w) if turned else
                                                      w in words or w[::-1] in words)) \
                    >= TURNED_AT * len(ws) or \
                    PLACE_ON and at and _drawn_there(b, at):
                # Its English and numbers are put back on their own: the
                # chosen reading of z21145041 drops the English inside Arabic
                # lines - eGFR, T2DM, PRISMA - and this backwards copy was the
                # only place they were. Skipped whole, they were lost; taken
                # whole, the paragraph was doubled backwards.
                gone = [w for w in LATIN_WORD.findall(text) if w not in latin]
                if gone:
                    chosen.add(Block(kind=PARAGRAPH, text=" ".join(gone), page=b.page))
                    latin |= set(gone)
                    added = True
                continue
            missing = [x for x in sents if not _present(x, have)]
            # Only take a block that is genuinely absent. Adding one whose text
            # is mostly present already duplicated whole paragraphs and pushed
            # word counts above the original.
            if len(missing) < len(sents) * 0.6:
                continue
            chosen.add(Block(kind=PARAGRAPH, text=text, page=b.page))
            have += _bare(text)
            words |= set(TURN_WORD.findall(text))
            same |= {"".join(sorted(w)) for w in TURN_WORD.findall(text)}
            latin |= set(LATIN_WORD.findall(text))
            added = True
    if added:
        chosen.blocks.sort(key=lambda b: b.page)
    return chosen


# A printed page number: one to four digits, Western or Arabic-Indic, with at
# most some dashes or brackets around it.
PAGE_NO = re.compile(r"^[\s.\-–—()\[\]]*"
                     r"[0-9٠-٩۰-۹]{1,4}"
                     r"[\s.\-–—()\[\]]*$")
# How close to the top or bottom edge a number must sit to be the page's own.
PAGE_NO_EDGE = 0.12


def _page_numbers(doc, path):
    """Put back printed page numbers the chosen route never saw.

    Word tags a page number as an ARTIFACT - page furniture, not content - so
    it is absent from the structure tree, and every thesis chapter comes
    through the tag route. The number was never read, `writer._running_text`
    had nothing to turn into a PAGE field, and the theses came out with no page
    numbers at all (found 2026-09-21). The text layer has it: "2" at y=778 on
    page 2 of `الفصل الخامس المبحث الثالث`.

    Each number found near the top or bottom edge, on a page where the reader
    has no block with that text, is added as the LAST block of its page with
    its coordinates, which is where the running-text detection looks.

    Only an edge that carries a number on at least half the pages is used -
    the same bar `_running_text` sets - so a stray figure at the foot of one
    page, a table cell say, is never added to the body as a lone paragraph.
    """
    try:
        d = pymupdf.open(path)
    except Exception:
        return
    have = {}
    for b in doc.blocks:
        if b.text.strip():
            have.setdefault(b.page, set()).add(b.text.strip())
    found = {"top": [], "bottom": []}
    with d:
        pages = len(d)
        for i, page in enumerate(d):
            H = page.rect.height
            for x0, y0, x1, y1, text, *_ in get_text(page, "blocks"):
                t = text.strip()
                if not t or not PAGE_NO.match(t) or t in have.get(i, ()):
                    continue
                edge = "top" if y1 < PAGE_NO_EDGE * H else \
                    "bottom" if y0 > (1 - PAGE_NO_EDGE) * H else None
                if edge:
                    found[edge].append(Block(kind=PARAGRAPH, text=t, page=i,
                                             x0=x0, x1=x1, y=y0, y1=y1))
    need = max(3, pages // 2)
    added = False
    for blocks in found.values():
        if len({b.page for b in blocks}) >= need:
            for b in blocks:
                doc.add(b)
            added = True
    if added:
        doc.blocks.sort(key=lambda b: b.page)


def _recovered(doc):
    """How much did this reader actually get? Arabic if any, else total text.

    Scoring by Arabic alone made non-Arabic documents pick an empty reader.
    """
    ar = sum(len(ARABIC.findall(b.text)) for b in doc.blocks)
    return ar if ar else sum(len(b.text) for b in doc.blocks)


# ---------------------------------------------------------------- tags

def _page_index(pdf):
    """Map a page object's id -> its 0-based number, so blocks know their page."""
    return {pg.obj.objgen: i for i, pg in enumerate(pdf.pages)}


def _text_under(node, depth=0):
    """All text beneath this node, ignoring nested blocks (they emit separately)."""
    if depth > 80:
        return ""
    if isinstance(node, pikepdf.Array):
        return "".join(_text_under(k, depth + 1) for k in node)
    if not isinstance(node, pikepdf.Dictionary):
        return ""
    out = ""
    at = node.get("/ActualText") or node.get("/Alt")
    if at is not None:
        out += str(at)
    kids = node.get("/K")
    if kids is not None:
        out += _text_under(kids, depth + 1)
    return out


def _walk(node, doc, pages, pending, depth=0, ctx=None, state=None):
    """Emit a block per block-level label.

    Text that sits under no block label (inside /Figure, /Table cells, bare
    /Span under the root) used to be returned upward and silently dropped.
    It now collects in `pending` and is flushed as a paragraph in document
    order, so nothing is lost.
    """
    if depth > 80:
        return
    if state is None:
        state = {"page": 0}
    if isinstance(node, pikepdf.Array):
        for k in node:
            _walk(k, doc, pages, pending, depth + 1, ctx, state)
        return
    if isinstance(node, int) and not isinstance(node, bool):
        # A bare piece of the page. Under a label with text, that text
        # already speaks for it; otherwise it is read as drawn (TAGS_DRAWN_ON).
        if "drawn" in state and not state.get("cover"):
            pending.extend(state["drawn"](state["page"], [int(node)]))
        return
    if not isinstance(node, pikepdf.Dictionary):
        return
    if node.get("/Type") == "/MCR":
        ref = node.get("/Pg")
        pg = state["page"] = pages.get(ref.objgen, state["page"]) \
            if ref is not None else state["page"]
        if "drawn" in state and not state.get("cover") and node.get("/MCID") is not None:
            pending.extend(state["drawn"](pg, [int(node.get("/MCID"))]))
        return

    tag = str(node.get("/S", ""))
    if tag in BLOCK_TAGS:
        _flush(doc, pending, state["page"])
        ref = node.get("/Pg")
        pg = pages.get(ref.objgen, state["page"]) if ref is not None else state["page"]
        state["page"] = pg
        kind = BLOCK_TAGS[tag]
        # A /Footnote holds its text in nested /P children. Those emit their own
        # blocks, leaving the footnote itself empty and dropped. Push the kind
        # down so the nested paragraphs come out as footnotes - and nested list
        # items too: `الفصل الثالث`'s notes (34) and (35) are a list inside a
        # footnote, and pushing down only paragraphs is how they landed in the
        # middle of the body (Moaz's example, 2026-09-21).
        if ctx in (FOOTNOTE,) and kind in (PARAGRAPH, LIST_ITEM, HEADING):
            kind = ctx
        text = str(node.get("/ActualText") or "")
        inner = []
        state["cover"] = state.get("cover", 0) + bool(text)
        _walk(node.get("/K"), doc, pages, inner, depth + 1,
              kind if kind in (FOOTNOTE,) else ctx, state)
        state["cover"] -= bool(text)
        inner = _turn_lines(inner)
        blk = Block(kind=kind, text=_clean(text + _join_parts(inner)), page=pg,
                    from_alt=not text and _all_alt(inner))
        _rough_spans(blk, [text] + inner)
        _drawn_look(blk, [text] + inner)
        doc.add(blk)
        return

    ref = node.get("/Pg")
    if ref is not None:
        state["page"] = pages.get(ref.objgen, state["page"])
    actual = node.get("/ActualText")
    if actual is not None:
        look = state.get("fonts")
        fmt = look(state["page"], _mcids(node.get("/K"))) if look else None
        piece = _Run(str(actual), fmt)
        # Where it is drawn, for a line labelled left to right (_turn_lines).
        if "drawn" in state:
            piece.marks = [m for g in state["drawn"].got(
                state["page"], _mcids(node.get("/K"))) for m in g[1]]
            if piece.marks and "at" in state:
                state["at"].append(piece)
        pending.append(piece if fmt or piece.marks else str(actual))
    elif node.get("/Alt") is not None:
        pending.append(_Alt(str(node.get("/Alt"))))
    elif "signs" in state:
        pending.extend(state["signs"](state["page"], _mcids(node.get("/K"))))
    kids = node.get("/K")
    if kids is not None:
        said = actual is not None or node.get("/Alt") is not None
        state["cover"] = state.get("cover", 0) + said
        _walk(kids, doc, pages, pending, depth + 1, ctx, state)
        state["cover"] -= said


def _mcids(kids):
    """The marked-content numbers a label points at directly."""
    if isinstance(kids, pikepdf.Array):
        return [n for k in kids for n in _mcids(k)]
    if isinstance(kids, int):
        return [int(kids)]
    if isinstance(kids, pikepdf.Dictionary) and kids.get("/Type") == "/MCR":
        return [int(kids.get("/MCID"))] if kids.get("/MCID") is not None else []
    return []


def _sign_reader(pdf):
    """page, [mcid] -> the signs drawn there in a font of signs.

    Moaz's theses draw every word as a picture labelled with its text, and
    only ﷺ and رضي الله عنه as real text - AGA Arabesque, under a label of its
    own with no text. The tags route reads labels, so every sign was dropped
    (N4: "the honorific lost"). Only text in a font of signs is taken, so
    labels on any other file read exactly as before.
    """
    from convert.glyphs import SYMBOL_FONTS, _key, read_tounicode
    cache = {}

    def read_page(i):
        out, mcid, table = {}, None, None
        page = pdf.pages[i]
        fonts = page.obj.get("/Resources", {}).get("/Font", {})
        tables = {}
        for name, f in fonts.items():
            tu = f.get("/ToUnicode")
            if _key(str(f.get("/BaseFont", ""))) in SYMBOL_FONTS and tu is not None:
                tables[name] = read_tounicode(tu.read_bytes())
        if not tables:
            return out
        for operands, op in pikepdf.parse_content_stream(page):
            op = str(op)
            if op == "BDC" and len(operands) > 1                     and isinstance(operands[1], pikepdf.Dictionary):
                m = operands[1].get("/MCID")
                mcid = int(m) if m is not None else mcid
            elif op == "EMC":
                mcid = None
            elif op == "Tf":
                table = tables.get(str(operands[0]))
            elif op in ("Tj", "TJ") and table is not None and mcid is not None:
                parts = operands[0] if op == "TJ" else [operands[0]]
                for part in parts:
                    if isinstance(part, pikepdf.String):
                        b = bytes(part)
                        out[mcid] = out.get(mcid, "") + "".join(
                            table.get(int.from_bytes(b[k:k + 2], "big"), "")
                            for k in range(0, len(b) - 1, 2))
        return out

    def signs(page, mcids):
        if page not in cache:
            try:
                cache[page] = read_page(page)
            except Exception:
                cache[page] = {}
        return [" " + cache[page][m] + " " for m in mcids if m in cache[page]]
    return signs


# English and numbers inside the theses' Arabic lines (FLAGS 29). Word gives
# each Arabic word a label carrying its text, and leaves English words and
# numbers as bare pieces of the page under the paragraph, with no label text:
# `z22058810`'s "COVID19" sits between the paragraph's last word and its full
# stop with nothing to read it by. The tags route read labels only, so every
# one was dropped, and the backfill put them back on a line of their own. They
# are read from the letters drawn there, in their place. Arabic is never taken
# this way - these files draw it backwards; its labels are where it is right.
TAGS_DRAWN_ON = os.environ.get("QIRTAS_TAGS_DRAWN", "1") != "0"
LATIN_OR_DIGIT = re.compile(r"[A-Za-z0-9]")


class _Drawn(str):
    """Text read from the letters drawn in a piece no label spoke for, with
    how it is drawn: `marks` [(page, x0, x1, baseline, size, font)], one per
    stretch of letters shown."""
    marks = ()


def _cid_widths(desc):
    """code -> width in 1/1000 em from a CIDFont's /W array: `c [w ...]`
    gives codes from c on, `c1 c2 w` one width for a range."""
    out, w = {}, list(desc.get("/W", []))
    k = 0
    while k < len(w) - 1:
        if isinstance(w[k + 1], pikepdf.Array):
            for j, v in enumerate(w[k + 1]):
                out[int(w[k]) + j] = float(v)
            k += 2
        else:
            for c in range(int(w[k]), int(w[k + 1]) + 1):
                out[c] = float(w[k + 2])
            k += 3
    return out


def _page_marks(pdf, i):
    """mcid -> [text, marks] for page i: what each numbered piece draws, and
    where (page, x0, x1, baseline, size, font). Fonts of signs are left out."""
    from convert.glyphs import SYMBOL_FONTS, _key, read_tounicode
    page = pdf.pages[i]
    fonts = page.obj.get("/Resources", {}).get("/Font", {})
    tables = {}
    for name, f in fonts.items():
        key = _key(str(f.get("/BaseFont", "")))
        if key in SYMBOL_FONTS or "symbol" in key or "wingding" in key:
            continue
        widths = {}
        if f.get("/Widths") is not None:
            first = int(f.get("/FirstChar", 0))
            widths = {first + k: float(w) for k, w in enumerate(f["/Widths"])}
        elif f.get("/DescendantFonts") is not None:
            try:
                widths = _cid_widths(f["/DescendantFonts"][0])
            except Exception:
                widths = {}
        base = str(f.get("/BaseFont", ""))[1:]
        tu = f.get("/ToUnicode")
        if tu is not None:
            tables[name] = (read_tounicode(tu.read_bytes()),
                            2 if f.get("/Subtype") == "/Type0" else 1,
                            widths, base)
        elif f.get("/Subtype") in ("/TrueType", "/Type1"):
            tables[name] = (None, 1, widths, base)
    out, stack, table = {}, [], None
    size, scale, x, y = 0.0, 1.0, 0.0, 0.0
    for operands, op in pikepdf.parse_content_stream(page):
        op = str(op)
        if op == "BDC":
            m = operands[1].get("/MCID") if len(operands) > 1 and \
                isinstance(operands[1], pikepdf.Dictionary) else None
            stack.append(int(m) if m is not None else
                         (stack[-1] if stack else None))
        elif op == "BMC":
            stack.append(stack[-1] if stack else None)
        elif op == "EMC":
            if stack:
                stack.pop()
        elif op == "Tf":
            table = tables.get(str(operands[0]))
            size = float(operands[1])
        elif op == "Tm":
            a, _, _, _, x, y = (float(v) for v in operands)
            scale = abs(a) or 1.0
        elif op in ("Td", "TD"):
            x += float(operands[0]) * scale
            y += float(operands[1]) * scale
        elif op in ("Tj", "TJ", "'", '"') and table and stack \
                and stack[-1] is not None:
            codes, width, widths, base = table
            parts = operands[0] if op == "TJ" else [operands[-1]]
            s, x0, em = "", x, 0.0
            for part in parts:
                if not isinstance(part, pikepdf.String):
                    em -= float(part)
                    continue
                b = bytes(part)
                ks = [int.from_bytes(b[k:k + width], "big")
                      for k in range(0, len(b) - width + 1, width)]
                em += sum(widths.get(k, 0.0) for k in ks)
                if codes is None:
                    s += b.decode("cp1252", "replace")
                else:
                    s += "".join(codes.get(k, "") for k in ks)
            x += em / 1000 * size * scale
            got = out.setdefault(stack[-1], ["", []])
            got[0] += s
            if s.strip():
                got[1].append((i, x0, x, y, round(size * scale, 1), base))
    return out


def _drawn_reader(pdf):
    """page, [mcid] -> the text drawn there, except in fonts of signs (their
    own reader has them). Fonts with a ToUnicode table by it; simple fonts
    without one by their Windows encoding, which is how Word writes English.
    Where and how big each stretch is drawn goes with it (_drawn_look)."""
    cache = {}
    read_page = functools.partial(_page_marks, pdf)

    def got(page, mcids):
        if page not in cache:
            try:
                cache[page] = read_page(page)
            except Exception:
                cache[page] = {}
        return [cache[page][m] for m in mcids if m in cache[page]]

    def drawn(page, mcids):
        got = drawn.got(page, mcids)
        t = "".join(g[0] for g in got)
        # A space is a piece of its own between English words ("Biomarkers",
        # " ", "as" in `z21145041`'s title); left out, they ran together.
        if t and not t.strip():
            return [_Drawn(" ")]
        if not LATIN_OR_DIGIT.search(t) or ARABIC.search(t):
            return []
        piece = _Drawn(t)
        piece.marks = [m for g in got for m in g[1]]
        # Bold and italic by the font's name, as the labels' words are
        # (_font_reader): `z22058810`'s "Abstract" came out plain.
        if piece.marks:
            names = [m[5].lower() for m in piece.marks]
            piece.fmt = (sum("bold" in n for n in names) * 2 > len(names),
                         sum("italic" in n or "oblique" in n for n in names) * 2
                         > len(names))
        return [piece]
    drawn.got = got
    return drawn


# How the English read from the page is set. The tags route has no positions
# and no sizes, so `z21145041`'s English came out at the Arabic body's size,
# font and line height, justified: its reference list in Calibri 11pt,
# ragged at the right, took four pages for two, and the file 17 for 14. A
# paragraph mostly read as drawn takes those from how it is drawn.
DRAWN_LOOK_ON = os.environ.get("QIRTAS_DRAWN_LOOK", "1") != "0"
DRAWN_MOST = 0.6        # share of a paragraph's letters read as drawn
RAGGED = 6.0            # points short of the right edge: a line not justified


def _drawn_look(blk, parts):
    """Size, font, line height and alignment for a paragraph mostly read
    from the page (_Drawn), from how its letters are drawn."""
    if not DRAWN_LOOK_ON:
        return
    drawn = [p for p in parts if isinstance(p, _Drawn)]
    ours = sum(1 for p in drawn for c in p if c.isalnum())
    every = sum(1 for p in parts for c in p if c.isalnum())
    marks = [m for p in drawn for m in p.marks]
    if not marks or ours < DRAWN_MOST * every:
        return
    from convert.glyphs import family
    sizes, fonts = collections.Counter(), collections.Counter()
    for _, x0, x1, _, size, base in marks:
        sizes[size] += x1 - x0 or 1
        fonts[re.sub(r"[,-](Bold|Italic|BoldItalic|Regular)\w*$", "",
                     base.split("+", 1)[-1])] += x1 - x0 or 1
    size = sizes.most_common(1)[0][0]
    blk.text_size = size
    blk.latin_font = family(fonts.most_common(1)[0][0])
    # Lines: marks on one page sharing a baseline.
    lines = []
    for pg, x0, x1, y, *_ in sorted(marks, key=lambda m: (m[0], -m[3])):
        if lines and lines[-1][0] == pg and abs(lines[-1][3] - y) < 0.5 * size:
            ln = lines[-1]
            lines[-1] = (pg, min(ln[1], x0), max(ln[2], x1), ln[3])
        else:
            lines.append((pg, x0, x1, y))
    gaps = [a[3] - b[3] for a, b in zip(lines, lines[1:])
            if a[0] == b[0] and 0.8 * size < a[3] - b[3] < 2.5 * size]
    if gaps:
        blk.line_pitch = round(statistics.median(gaps), 1)
    blk.drawn_lines = lines


def _drawn_align(doc):
    """Justified or not, for the paragraphs _drawn_look measured: justified
    lines all reach the column's right edge, but the last. The edge is the
    document's, not the paragraph's: a reference entry is often two lines,
    and its own longest line says nothing. Left as it was where there are
    too few lines to tell."""
    measured = [b for b in doc.blocks if getattr(b, "drawn_lines", None)]
    ends = sorted(ln[2] for b in measured for ln in b.drawn_lines[:-1])
    right = ends[int(0.9 * (len(ends) - 1))] if len(ends) >= 5 else None
    for b in measured:
        inner = b.drawn_lines[:-1]
        if right is not None and inner and \
                sum(1 for ln in inner if right - ln[2] > RAGGED) > len(inner) / 3:
            b.align = "start"
        del b.drawn_lines


def _join_parts(parts):
    """The pieces of a label as one text. A drawn piece touching a word is
    set apart from it: the labels of `z21145041`'s contents have no line
    ends, and its page numbers, read as drawn, ran into the entries on either
    side ("المقدمة71.1 الخلفية")."""
    out, prev = "", ""
    for p in parts:
        if out and p and (isinstance(p, _Drawn) or isinstance(prev, _Drawn)) \
                and out[-1].isalnum() and p[0].isalnum():
            out += " "
        out += p
        if p:
            prev = p
    return out


# A line whose labels come left to right. Word labels most Arabic lines
# right to left, the order they are read in, but some lines in the order they
# are drawn: `z22058810`'s header on page 27 came out word for word backwards
# ("المالي الاستقرار لتحقيق ... نشأة تطور"), and the second line of its opening
# verse as "كَ فِي عِبَادِكَ الصَّالِحِينَ" then "وَأَدْخِلْنِي بِرَحْمَتِ" - the
# end of برحمتك cut off and set after the line (QIRTAS_TAGS_LINE_TURN).
LINE_TURN_ON = os.environ.get("QIRTAS_TAGS_LINE_TURN", "1") != "0"
STEP = 0.5      # of the letters' size: a move from one piece to the next


def _where(p):
    """(page, x0, x1, baseline, size) of a piece from where its letters are
    drawn, or None for one with no letters drawn (a space label)."""
    marks = getattr(p, "marks", ())
    if not marks:
        return None
    return (marks[0][0], min(m[1] for m in marks), max(m[2] for m in marks),
            statistics.median(m[3] for m in marks),
            max(m[4] for m in marks) or 1.0)


def _turn_lines(parts):
    """Pieces of one line labelled left to right, put right to left.

    A line is the pieces in a row drawn on one baseline. It is turned only
    where its Arabic pieces come left to right more often than right to left,
    so a line labelled in reading order is never touched. Spaces keep their
    places between pieces, and a run of pieces with no Arabic - English, a
    number with its brackets - keeps its own order: it reads left to right."""
    if not LINE_TURN_ON:
        return parts
    out, k = list(parts), 0
    while k < len(out):
        w = _where(out[k])
        if w is None:
            k += 1
            continue
        # This line: from k while the pieces drawn stay on its baseline.
        end, last = k + 1, k
        while end < len(out):
            v = _where(out[end])
            if v is not None:
                if v[0] != w[0] or abs(v[3] - w[3]) > 0.4 * w[4]:
                    break
                last = end
            end += 1
        k = _turn_line(out, k, last) if last > k else k + 1
    return out


def _turn_line(out, first, last):
    """Turn out[first:last + 1] if its Arabic pieces run left to right.
    Returns where the next line starts."""
    seq = out[first:last + 1]
    ar = [_where(p) for p in seq if _where(p) and ARABIC_LETTER.search(p)]
    # By where each piece starts: the width a run of marked letters is read
    # to take runs long - `z22058810`'s verse line ends at x=1115 on a page
    # 595 wide - but where it starts is set on the page.
    # A step counts at half the letters' size: the alef of a tanween is a
    # piece of its own that starts a few points right of its word (عشوائي,
    # اً on `z21145041` page 26), and counted, the line turned and split it.
    step = [b[1] - a[1] for a, b in zip(ar, ar[1:])]
    right = sum(d > STEP * ar[0][4] for d in step)
    left = sum(d < -STEP * ar[0][4] for d in step)
    if right <= left:
        return last + 1
    # Pieces drawn, and the spaces between them, alternate; the whole row
    # is turned, so the spaces stay between. A run of English or digits,
    # spaces inside it included, is one piece: it reads left to right. Digits
    # count with it, not with the Arabic - "٢٠٢٤." labelled ٢٠ then ٢٤ turned
    # into ".٠٢٤٢". A bracket on its own is not: it takes the line's
    # direction, and stuck to its number read "4()".
    items = []
    for p in seq:
        drawn = _where(p) is not None
        if items and items[-1][0] == drawn and not drawn:
            items[-1][1].append(p)
        else:
            items.append([drawn, [p]])

    def latin(item):
        text = "".join(item[1])
        return item[0] and not ARABIC_LETTER.search(text) and \
            any(c.isalnum() for c in text)

    def between(item):
        # A space, or a mark with no letters (Wilcoxon-Mann).
        return not any(c.isalnum() for c in "".join(item[1]))
    k = 0
    while k < len(items) - 1:
        nxt = items[k + 1]
        if latin(items[k]) and (latin(nxt) or (
                between(nxt) and k + 2 < len(items) and latin(items[k + 2]))):
            items[k][1] += nxt[1]
            del items[k + 1]
        else:
            k += 1
    out[first:last + 1] = [p for item in reversed(items) for p in item[1]]
    return last + 1


class _Alt(str):
    """Text that came from a picture's /Alt description, not from the page."""


def _all_alt(parts):
    parts = [p for p in parts if p.strip()]
    return bool(parts) and all(isinstance(p, _Alt) for p in parts)


def _flush(doc, pending, page=0):
    """Loose text kept defaulting to page 0, piling a whole document onto the
    first page and leaving later pages empty. Carry the current page."""
    if pending:
        pending[:] = _turn_lines(pending)
        blk = Block(kind=PARAGRAPH, text=_clean(_join_parts(pending)), page=page,
                    from_alt=_all_alt(pending))
        _rough_spans(blk, pending)
        _drawn_look(blk, pending)
        doc.add(blk)
        pending.clear()


# ------------------------------------------------ tags route: bold and italic
#
# The tags route reads /ActualText, which carries no formatting, so bold on
# the two theses read that way stayed at 7% and 15% (Part 3, bold). Each word
# there is a label of its own pointing at the letters drawn for it, and those
# letters are drawn in a font that says whether it is bold - the letters spell
# the word backwards, the font is still right. So each word's formatting is
# looked up from the fonts its letters are drawn in.
TAGS_FORMAT_ON = os.environ.get("QIRTAS_TAGS_FORMAT", "1") != "0"


class _Run(str):
    """Text from a label, with (bold, italic) read from its letters' fonts,
    and where they are drawn (`marks`, as _Drawn's)."""
    marks = ()
    def __new__(cls, text, fmt):
        s = super().__new__(cls, text)
        s.fmt = fmt
        return s


def _font_style(f):
    """(bold, italic) of a PDF font, by its name and its descriptor."""
    name = str(f.get("/BaseFont", "")).lower()
    desc = f.get("/FontDescriptor")
    if desc is None and f.get("/DescendantFonts") is not None:
        try:
            desc = f["/DescendantFonts"][0].get("/FontDescriptor")
        except Exception:
            desc = None
    flags = int(desc.get("/Flags", 0)) if desc is not None else 0
    weight = float(desc.get("/FontWeight", 0)) if desc is not None else 0
    bold = "bold" in name or "black" in name or "heavy" in name \
        or weight >= 600 or bool(flags & (1 << 18))
    italic = "italic" in name or "oblique" in name or bool(flags & (1 << 6))
    return bold, italic


def _font_reader(pdf):
    """page, [mcid] -> (bold, italic) of most of the letters drawn there, or
    None where nothing was drawn in a known font."""
    cache = {}

    def read_page(i):
        page = pdf.pages[i]
        fonts = page.obj.get("/Resources", {}).get("/Font", {})
        style = {}
        for name, f in fonts.items():
            try:
                style[name] = (_font_style(f),
                               2 if f.get("/Subtype") == "/Type0" else 1)
            except Exception:
                continue
        out, stack, font = {}, [], None
        for operands, op in pikepdf.parse_content_stream(page):
            op = str(op)
            if op == "BDC":
                m = operands[1].get("/MCID") if len(operands) > 1 and \
                    isinstance(operands[1], pikepdf.Dictionary) else None
                stack.append(int(m) if m is not None else
                             (stack[-1] if stack else None))
            elif op == "BMC":
                stack.append(stack[-1] if stack else None)
            elif op == "EMC":
                if stack:
                    stack.pop()
            elif op == "Tf":
                font = style.get(str(operands[0]))
            elif op in ("Tj", "TJ", "'", '"') and font and stack \
                    and stack[-1] is not None:
                parts = operands[0] if op == "TJ" else [operands[-1]]
                n = sum(len(bytes(p)) for p in parts
                        if isinstance(p, pikepdf.String)) // font[1]
                c = out.setdefault(stack[-1], [0, 0, 0])
                c[0] += n
                c[1] += n if font[0][0] else 0
                c[2] += n if font[0][1] else 0
        return out

    def look(page, mcids):
        if page not in cache:
            try:
                cache[page] = read_page(page)
            except Exception:
                cache[page] = {}
        got = [cache[page][m] for m in mcids if m in cache[page]]
        n = sum(c[0] for c in got)
        if not n:
            return None
        return (sum(c[1] for c in got) * 2 > n, sum(c[2] for c in got) * 2 > n)
    return look


def _rough_spans(blk, parts):
    """Formatting per piece as the labels gave it, before any repair of the
    text. `_fit_spans` lays it over the finished text at the end."""
    if not any(getattr(p, "fmt", None) and any(p.fmt) for p in parts):
        return
    spans = []
    for p in parts:
        if not p:
            continue
        fmt = getattr(p, "fmt", None)
        if fmt is None or not p.strip():
            # A space label has no letters; it takes the formatting before it.
            fmt = spans[-1][1:] if spans else (False, False)
        if spans and spans[-1][1:] == tuple(fmt):
            spans[-1] = (spans[-1][0] + p, *spans[-1][1:])
        else:
            spans.append((str(p), *fmt))
    blk.spans = spans
    n = sum(len(t.strip()) for t, *_ in spans) or 1
    blk.bold = sum(len(t.strip()) for t, b, _ in spans if b) * 2 > n


def _fit_spans(blk):
    """Lay the formatting read per label over the block's finished text.

    The text is repaired after it is read - lam-alef, the page's fix map,
    list markers taken off - and the writer writes the spans, not the text,
    so spans that had drifted would write words the checker never saw. The
    text is the authority: each of its words takes the formatting most of
    its letters had, and like words are joined into one span."""
    if not blk.spans or not blk.text:
        return
    blk.spans = _word_spans(blk.text, _char_fmts(blk.spans, blk.text))
    if not any(b or i for _, b, i in blk.spans):
        blk.spans = []


def _char_fmts(spans, text):
    """(bold, italic) for each non-space letter of `text`, from `spans`
    matched onto it letter by letter; None where no letter matched."""
    marks, fmts = [], []
    for t, b, i, *_ in spans:
        for ch in t:
            if not ch.isspace():
                marks.append(ch)
                fmts.append((b, i))
    want = [ch for ch in text if not ch.isspace()]
    if marks == want:
        return fmts
    got = [None] * len(want)
    sm = difflib.SequenceMatcher(None, want, marks, autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        got[a:a + n] = fmts[b:b + n]
    return got


def _word_spans(text, got):
    """Each word of `text` in the formatting most of its letters have in
    `got` (from _char_fmts), like words joined into one span."""
    spans, k = [], 0
    for w in text.split():
        mine = [f for f in got[k:k + len(w)] if f is not None]
        k += len(w)
        fmt = (sum(f[0] for f in mine) * 2 > len(mine),
               sum(f[1] for f in mine) * 2 > len(mine)) if mine else \
            (spans[-1][1:] if spans else (False, False))
        if spans and spans[-1][1:] == fmt:
            spans[-1] = (spans[-1][0] + " " + w, *fmt)
        else:
            spans.append((w, *fmt))
    return spans


def read_tags(path, drawn=TAGS_DRAWN_ON):
    doc = Doc(source_route="tags")
    with pikepdf.open(path) as pdf:
        if "/StructTreeRoot" not in pdf.Root:
            raise RuntimeError("not tagged")
        pages = _page_index(pdf)
        doc.pages = len(pdf.pages)
        pending, state = [], {"page": 0, "signs": _sign_reader(pdf)}
        if TAGS_FORMAT_ON:
            state["fonts"] = _font_reader(pdf)
        if drawn:
            state["drawn"] = _drawn_reader(pdf)
            state["at"] = []
        _walk(pdf.Root["/StructTreeRoot"].get("/K"), doc, pages, pending, state=state)
        _flush(doc, pending, state["page"])
        if drawn:
            doc.drawn_at = _drawn_at(state["at"], pdf)
    _drawn_align(doc)
    # Only where the labels carry the Arabic. A file with none has its words
    # in the glyphs, and the English read here would make this route look
    # as good as the others on it - it is chosen first on a tie.
    if drawn and not any(ARABIC.search(b.text) for b in doc.blocks):
        return read_tags(path, drawn=False)
    return doc


# ------------------------------------------------------------ geometry

BOLD_FLAG = 1 << 4
ITALIC_FLAG = 1 << 1


def read_geometry(path):
    """Group lines by position on the page.

    Prefers the detailed view, which carries font size and boldness. Where the
    glyphs cannot be decoded that view comes back nearly empty, so we fall back
    to the plain block view: text but no formatting.
    """
    doc = Doc(source_route="geometry")
    with pymupdf.open(path) as d:
        doc.pages = len(d)
        vocab = vocabulary(d)
        for i, page in enumerate(d):
            rich = _page_rich(page, i, (vocab, _letter_ends(
                page, pymupdf.TEXTFLAGS_DICT)))
            plain_len = len(ARABIC.findall(get_text(page, "text")))
            rich_len = sum(len(ARABIC.findall(b.text)) for b in rich)
            if plain_len and rich_len < plain_len * 0.5:
                rich = [Block(kind=PARAGRAPH, text=_clean(b[4]), page=i)
                        for b in sorted(get_text(page, "blocks"),
                                        key=lambda b: (round(b[1]), b[0]))
                        if b[6] == 0]
            for b in rich:
                doc.add(b)
    return doc


# Two pieces of one line "touch" within this share of the font size.
GLUE_GAP = 0.25
EDGE_PUNCT = ".,،:؛()[]«»\"'-–—"


def vocabulary(doc):
    """Every word the document prints whole, with how often - to tell a word
    split in two from two words that happen to touch.

    Only words wholly inside one piece of text, with a space or the piece's
    end on each side. The page's plain text glues touching pieces, so it
    would count the very joins in question as words (قامYazdanian)."""
    words = collections.Counter()
    for page in doc:
        for b in get_text(page, "dict")["blocks"]:
            for line in b.get("lines", []):
                for sp in line["spans"]:
                    t = sp["text"]
                    toks = t.split()
                    if not toks:
                        continue
                    inner = toks[1:-1]
                    if len(toks) > 1 and t[0].isspace():
                        inner.insert(0, toks[0])
                    if len(toks) > 1 and t[-1].isspace():
                        inner.append(toks[-1])
                    if len(toks) == 1 and t[0].isspace() and t[-1].isspace():
                        inner = toks
                    words.update(_bare(w).strip(EDGE_PUNCT) for w in inner)
    return words


ARABIC_LETTER = re.compile("[ء-يٱ-ۓﭐ-﷿ﹰ-ﻼ]")
# The letters either side of a cut touch, within this share of the font size;
# two words have a space's width between them, however their pieces touch.
TOUCH = 0.05
# A word ends at these: nothing is joined on after them.
WORD_END = "ةى"


def _letter_ends(page, flags):
    """{piece's box: (box of its first letter, box of its last, its
    characters)}, read with
    the same flags as the dict it is used with. A piece's own box runs on
    over the space after it, so only its letters tell whether it touches
    the next (PLAN "Words cut between two pieces")."""
    ends = {}

    def walk(node):
        for b in node.get("blocks", ()):
            for line in b.get("lines", ()):
                for s in line["spans"]:
                    cs = [c for c in s.get("chars", ())
                          if not c["c"].isspace() and not MARKS.match(c["c"])]
                    if cs:
                        # and every character with where it is drawn, for
                        # _edge_spaces and _tight
                        ends[_box(s["bbox"])] = (
                            cs[0]["bbox"], cs[-1]["bbox"],
                            [(c["c"], c["bbox"][0], c["bbox"][2])
                             for c in s["chars"]])
            walk(b)

    walk(get_text(page, "rawdict", flags=flags))
    return ends


def _box(bbox):
    return tuple(round(v, 1) for v in bbox)


def _glued(prev, sp, vocab, ends=None):
    """Is `sp` the rest of the word `prev` ends with?

    A PDF can write one line as several pieces, and cut a word between them:
    `z19773087` writes يحتفظ as "سورية، ي" and "حتفظ المؤلفون", touching at
    x=503. Joining every pair of touching pieces glued real words too - a
    justified line's words can touch (شملت دراستنا, FLAGS 24). So they are
    joined only when they touch on one line, an Arabic letter meets an Arabic
    letter at the seam with no space brought by either, and the joined word
    is one the document prints whole elsewhere - or, with `ends`
    (_letter_ends), the letters either side of the cut touch: `z21490618`'s
    التأ|هيلي and والخد|مي are printed nowhere else.
    """
    if not vocab or not prev or not prev["text"] or not sp["text"]:
        return False
    a, b = prev["text"], sp["text"]
    if a[-1].isspace() or b[0].isspace():
        return False
    # Only a letter against a letter: punctuation and a change of script are
    # where words end (مثل|PCI, قام|Yazdanian).
    tail_ch, head_ch = MARKS.sub("", a)[-1:], MARKS.sub("", b)[:1]
    if not (ARABIC_LETTER.match(tail_ch or " ") and ARABIC_LETTER.match(head_ch or " ")):
        return False
    size = max(prev["size"], sp["size"], 1.0)
    pa, pb = prev["bbox"], sp["bbox"]
    if abs(pa[3] - pb[3]) > 0.3 * size:
        return False                        # not on one line
    gap = min(abs(pa[0] - pb[2]), abs(pb[0] - pa[2]))
    if gap > GLUE_GAP * size:
        return False
    tail, head = a.split()[-1], b.split()[0]
    whole = _bare(tail + head).strip(EDGE_PUNCT)
    if len(whole) < 3:
        return False
    if vocab.get(whole, 0) > 0:
        return True
    if os.environ.get("QIRTAS_SEAM_TOUCH", "1") == "0":
        return False               # off, to measure against
    ea, eb = (ends or {}).get(_box(pa)), (ends or {}).get(_box(pb))
    if not ea or not eb or tail_ch in WORD_END:
        return False
    return -TOUCH <= (ea[1][0] - eb[0][2]) / size < TOUCH


# Where two pieces of a line meet at one of these, only the page says whether
# a space stands between them.
LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
TIGHT = "()[]%٪"
OPENING = "(["
# QIRTAS_TIGHT=0 turns _edge_spaces and _tight off, to measure against.
TIGHT_ON = os.environ.get("QIRTAS_TIGHT", "1") != "0"


def _right_to_left(chars):
    """Are a piece's Arabic letters stored right to left, as drawn? A piece
    with no two letters side by side (` .`) counts as so."""
    steps = [a[1] - b[1] for a, b in zip(chars, chars[1:])
             if ARABIC.match(a[0]) and ARABIC.match(b[0]) and a[1] != b[1]]
    return sum(1 for d in steps if d > 0) >= 0.5 * len(steps)


def _edge_spaces(sp, ends, arabic=False):
    """The piece's text, with the spaces stored at its start put where they
    are drawn.

    The extractor stores a right-to-left piece's spaces at its start
    wherever they are drawn. Drawn at its left end, they end it: ` . إنّ`
    is `. إنّ ` after `2005)`. Drawn just right of a bracket that ends it,
    they stand before the bracket too: ` المستوى العالمي(` is
    ` المستوى العالمي (`
    (`z20252507`). Only the spaces beside a bracket or % decide anything
    (_tight); elsewhere the join puts one space between pieces either way.
    A piece without Arabic letters (` .`) is read so only in Arabic text,
    `arabic`: in English a space stored first is drawn first.
    """
    t = sp["text"]
    e = (ends or {}).get(_box(sp["bbox"]))
    body = t.rstrip()
    n = len(body) - len(body.lstrip())
    if not TIGHT_ON or not e or not n or LATIN.search(body) or \
            not (arabic or ARABIC.search(body)):
        return t
    chars = e[2]
    lead, ink = chars[:n], [c for c in chars if not c[0].isspace()]
    if len(chars) != len(t) or any(c[0] != " " for c in lead) or not ink             or ink[-1][0] != body[-1]:
        return t
    # Only a piece read right to left: one stored backwards (ةليلقلا for
    # القليلة, `z20161304`) has its spaces where they are drawn already, and
    # moving them changed which words the spelling repairs saw (يف for في).
    if not _right_to_left(chars):
        return t
    size = max(sp["size"], 1.0)
    # A word keeps the space before it: the lam-alef repair reads a word's
    # start by it (لا يوجد read ال يوجد, `z20589058`).
    if not ARABIC_LETTER.match(body[n]) and             all(c[2] <= min(k[1] for k in ink) + TOUCH * size for c in lead):
        return body[n:] + " "
    bracket = ink[-1]
    if body[-1] in OPENING and len(ink) > 1 and             abs(min(c[1] for c in lead) - bracket[2]) <= TOUCH * size and             all(c[2] <= min(k[1] for k in ink[:-1]) + TOUCH * size
                for c in lead):
        return " " + body[n:-1] + " " + body[-1] + t[len(body):]
    return t


def _tight(prev, text, sp, run, ends):
    """Do `sp` and the piece before it meet at a bracket or % with nothing
    drawn between them?

    Each is its own piece where Arabic meets English or a number, and joined
    with a space `(Shegaze et al., 2020)` came out `( Shegaze et al., 2020 )`,
    and 15% as `15 %` (`z20252507`). Only a bracket or % is joined: two
    words drawn touching are still two words (قام|Yazdanian)."""
    if not TIGHT_ON or not prev or not ends or not text or not run:
        return False
    if text[-1].isspace() or run[0].isspace() or             not (text[-1] in TIGHT or run[0] in TIGHT):
        return False
    ea, eb = ends.get(_box(prev["bbox"])), ends.get(_box(sp["bbox"]))
    if not ea or not eb:
        return False
    size = max(prev["size"], sp["size"], 1.0)
    pa, pb = prev["bbox"], sp["bbox"]
    if abs(pa[3] - pb[3]) > 0.3 * size:
        return False                        # not on one line
    ia = [c for c in ea[2] if not c[0].isspace()]
    ib = [c for c in eb[2] if not c[0].isspace()]
    if pb[0] + pb[2] < pa[0] + pa[2]:       # drawn to the left: right to left
        gap = min(c[1] for c in ia) - max(c[2] for c in ib)
    else:
        gap = min(c[1] for c in ib) - max(c[2] for c in ia)
    return abs(gap) <= TOUCH * size


# A word drawn in two pieces of different formatting is put back together in
# the first piece's formatting; the rest of the second piece keeps its own.
GLUE_FORMAT_ON = os.environ.get("QIRTAS_GLUE_FORMAT", "1") != "0"


def _rich_block(text_blocks, i, kind=PARAGRAPH, vocab=None):
    """One Block from one or more PyMuPDF text blocks, with size, boldness and
    runs of like formatting. None if they hold no text.

    `vocab` (vocabulary()), or (vocab, _letter_ends()): a word cut between
    two pieces is put back together - see _glued. Without it every piece is
    joined with a space."""
    vocab, ends = vocab if isinstance(vocab, tuple) else (vocab, None)
    text, size, bold, spans = "", 0.0, False, []
    letters = {}             # size -> letters set at it
    prev = None
    for b in text_blocks:
        for line in b["lines"]:
            for sp in line["spans"]:
                run = sp["text"]
                if not run.strip():
                    continue
                run = _edge_spaces(sp, ends, bool(ARABIC.search(text)))
                glue = _glued(prev, sp, vocab, ends)
                # A bracket or % drawn against its neighbour is written
                # against it: joined like a word put back together.
                glue = glue or _tight(prev, text, sp, run, ends)
                prev = sp
                text += ("" if glue or not text else " ") + run
                size = max(size, sp["size"])
                letters[round(sp["size"], 1)] = letters.get(round(sp["size"], 1), 0) + len(run.strip())
                it = bool(sp["flags"] & ITALIC_FLAG)
                bo = bool(sp["flags"] & BOLD_FLAG)
                bold = bold or bo
                # Merge with the previous span when it reads the same. A line
                # often arrives as a dozen spans of identical formatting, and
                # one Word run each would bloat the file for no effect. A word
                # put back together stays in one run whatever its formatting:
                # the writer puts a space between runs.
                # Only the word, though: `z17804101` draws "الدرام" bold and
                # "ا، القاهرة، الهيئة ... ص44" plain, and the whole plain
                # rest came out bold with it.
                rest = ""
                if GLUE_FORMAT_ON and spans and glue and \
                        spans[-1][1:] != (bo, it) and " " in run.strip():
                    cut = run.find(" ", len(run) - len(run.lstrip()))
                    run, rest = run[:cut], run[cut:]
                if spans and (glue or (spans[-1][1] == bo and spans[-1][2] == it)):
                    spans[-1] = (spans[-1][0] + ("" if glue else " ") + run,
                                 spans[-1][1], spans[-1][2])
                else:
                    spans.append((run, bo, it))
                if rest.strip():
                    spans.append((rest.strip(), bo, it))
    if not spans:
        return None
    boxes = [b["bbox"] for b in text_blocks]
    return Block(kind=kind, text=_clean(text),
                 page=i, size=round(size, 1), bold=bold,
                 text_size=max(letters, key=letters.get) if letters else 0.0,
                 spans=[(_clean(t), b_, i_) for t, b_, i_ in spans],
                 y=round(min(r[1] for r in boxes), 1),
                 y1=round(max(r[3] for r in boxes), 1),
                 x0=round(min(r[0] for r in boxes), 1),
                 x1=round(max(r[2] for r in boxes), 1))


# ------------------------------------------------- italic drawn as a slant
#
# Word has no italic of most Arabic fonts, so it fakes one: the ordinary font
# drawn with a text matrix that leans 0.33 (`1 0 0.3333 1 x y Tm`). No font
# says italic, so the reading saw none - 9 theses use it, `z18634114` 299
# times. The slant is found in the content stream, and the pieces drawn with
# it are found again in MuPDF's trace of the page by where they start.
SKEW_ON = os.environ.get("QIRTAS_SKEW", "1") != "0"
SKEW_MIN, SKEW_MAX = 0.15, 0.6     # lean as a share of height; Word's is 0.33
_SCRATCH = []


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D,
            e * A + f * C + E, e * B + f * D + F)


def _leans(m):
    a, b, c, d = m[:4]
    wide, high = (a * a + b * b) ** 0.5, (c * c + d * d) ** 0.5
    if not wide or not high:
        return False
    return SKEW_MIN <= abs(a * c + b * d) / (wide * high) <= SKEW_MAX


def _slant_starts(page):
    """Where each piece of slanted text starts, in MuPDF's coordinates."""
    if not _SCRATCH:
        _SCRATCH.append(pikepdf.Pdf.new())
    data = page.read_contents()
    if b"Tm" not in data:
        return []
    ops = pikepdf.parse_content_stream(pikepdf.Stream(_SCRATCH[0], data))
    ctm, stack, tm, tlm, fresh = (1, 0, 0, 1, 0, 0), [], None, None, False
    out, to_page = [], page.transformation_matrix
    for operands, op in ops:
        op = str(op)
        try:
            nums = [float(x) for x in operands]
        except (TypeError, ValueError):
            nums = []
        if op == "q":
            stack.append(ctm)
        elif op == "Q":
            ctm = stack.pop() if stack else ctm
        elif op == "cm" and len(nums) == 6:
            ctm = _mul(tuple(nums), ctm)
        elif op == "BT":
            tm = tlm = (1, 0, 0, 1, 0, 0)
            fresh = True
        elif op == "Tm" and len(nums) == 6:
            tm = tlm = tuple(nums)
            fresh = True
        elif op in ("Td", "TD") and len(nums) == 2 and tlm:
            tm = tlm = _mul((1, 0, 0, 1, nums[0], nums[1]), tlm)
            fresh = True
        elif op in ("Tj", "TJ", "'", '"') and tm:
            m = _mul(tm, ctm)
            if fresh and _leans(m):
                out.append(pymupdf.Point(m[4], m[5]) * to_page)
            fresh = False
    return out


def _slanted_boxes(page):
    starts = _slant_starts(page)
    if not starts:
        return []
    boxes = []
    for s in page.get_texttrace():
        if s["chars"]:
            x, y = s["chars"][0][2]
            if any(abs(x - p.x) < 0.6 and abs(y - p.y) < 0.6 for p in starts):
                boxes.append(pymupdf.Rect(s["bbox"]))
    return boxes


# MuPDF calls a span italic when the font FILE says so. Some decorative
# Arabic fonts do and are drawn upright - `z20973693`'s AGA-Aladdin and
# Sultan Medium: the PDF gives them italic angle 0 and no italic flag, and
# Word shows them upright. Italic is kept only where the PDF's own
# description of the font agrees.
TRUE_ITALIC_ON = os.environ.get("QIRTAS_TRUE_ITALIC", "1") != "0"
CUT_NAME = 24            # MuPDF's spans cut font names to this many letters


def _pdf_italic_fonts(page):
    """Names of this page's fonts the PDF itself calls italic."""
    doc = page.parent
    out = set()
    for xref, _, _, base, *_ in page.get_fonts():
        name = base.split("+", 1)[-1]
        if re.search("italic|oblique", name, re.I):
            out.add(name)
            continue
        try:
            desc = doc.xref_get_key(xref, "FontDescriptor")
            if desc[0] != "xref":
                kids = doc.xref_get_key(xref, "DescendantFonts")
                ref = re.search(r"(\d+) 0 R", kids[1]) if kids[0] != "null" else None
                if ref:
                    desc = doc.xref_get_key(int(ref.group(1)), "FontDescriptor")
            if desc[0] != "xref":
                continue
            dx = int(desc[1].split()[0])
            angle = doc.xref_get_key(dx, "ItalicAngle")
            flags = doc.xref_get_key(dx, "Flags")
            if (angle[0] == "int" or angle[0] == "float") and float(angle[1]) != 0 \
                    or (flags[0] == "int" and int(flags[1]) & 64):
                out.add(name)
        except Exception:
            out.add(name)       # unreadable: leave MuPDF's word standing
    return out


def _mark_slant(page, got):
    """Set the italic flag on every span of this page's dict (or structure
    dict) that sits within text drawn slanted - and take it off a span whose
    font only its font file calls italic."""
    if TRUE_ITALIC_ON:
        try:
            italic = _pdf_italic_fonts(page)

            def clear(node):
                for b in node.get("blocks", []):
                    if b.get("type") == 2:
                        clear(b)
                    for line in b.get("lines", []):
                        for sp in line["spans"]:
                            # MuPDF cuts long names short in its spans:
                            # "TimesNewRomanPS-BoldItal" for ...BoldItalicMT.
                            f = sp["font"]
                            if sp["flags"] & ITALIC_FLAG and f and not any(
                                    n == f or (len(f) >= CUT_NAME and n.startswith(f))
                                    for n in italic):
                                sp["flags"] &= ~ITALIC_FLAG
            clear(got)
        except Exception:
            pass
    if not SKEW_ON:
        return
    try:
        boxes = _slanted_boxes(page)
    except Exception:
        return
    if not boxes:
        return

    def walk(node):
        for b in node.get("blocks", []):
            if b.get("type") == 2:
                walk(b)
            for line in b.get("lines", []):
                for sp in line["spans"]:
                    r = pymupdf.Rect(sp["bbox"])
                    area = r.get_area()
                    if area and sum((r & q).get_area() for q in boxes) * 2 > area:
                        sp["flags"] |= ITALIC_FLAG
    walk(got)


def _page_rich(page, i, vocab=None):
    out = []
    got = get_text(page, "dict")
    _mark_slant(page, got)
    for b in sorted(got["blocks"], key=lambda b: (round(b["bbox"][1]), b["bbox"][0])):
        if b.get("type") != 0:
            continue
        blk = _rich_block([b], i, vocab=vocab)
        if blk:
            out.append(blk)
    return _join_lines(out)


# ---------------------------------------------------------------- labels

# What Word's labels say a piece of text is. A unit starts at any of these,
# except inside a CONTAINER: a list item's number and its text are separate
# labels (Lbl, LBody) but one item, and a footnote may hold paragraphs or even
# a list - `الفصل الثالث`'s (34) and (35) are a list inside a footnote, and
# splitting them out is exactly how they landed in the body. A chart's axis
# numbers and legend sit inside a Figure; one paragraph each, they stacked
# down the page and `z20375390` ran from 24 pages to 29.
LABEL_UNIT = {"P", "H", "H1", "H2", "H3", "H4", "H5", "H6", "Title", "LI",
              "TD", "TH", "Caption", "TOCI", "Note", "Footnote", "Textbox",
              "Figure"}
LABEL_CONTAINER = {"LI", "Note", "Footnote", "TD", "TH", "Figure"}


def _label_kind(chain):
    """-> (kind, heading level). The whole chain decides: a list inside a
    footnote is a footnote. Table cells stay paragraphs here; `read_tables`
    builds the tables and drops the text found inside them, as it does for
    every other route."""
    s = set(chain)
    if s & {"Footnote", "Note"}:
        return FOOTNOTE, 0
    if s & {"TD", "TH", "Table"}:
        return PARAGRAPH, 0
    for t in reversed(chain):
        if t in ("H", "Title"):
            return HEADING, 1
        if len(t) == 2 and t[0] == "H" and t[1].isdigit():
            return HEADING, int(t[1])
    if s & {"LI", "LBody", "Lbl"}:
        return LIST_ITEM, 0
    return PARAGRAPH, 0


def read_labels(path):
    """Word's structure labels over the page's own glyph text.

    The tags route reads only /ActualText, which is where the theses keep
    their words. Ordinary Word files keep theirs in the glyphs, so on those
    the tags route recovered next to nothing and geometry won every time -
    on all 36 Word-made tuning files, which threw away what the author's own
    Word said each piece was and guessed it back from positions: no footnote
    found on any of them, and a third of prose made into list items
    (`PLAN.md`, "The answer key").

    Text outside every label is Word's page furniture - running headers,
    footers, page numbers. It is kept as ordinary blocks with their positions,
    so the writer's furniture detection sees it exactly as before.
    """
    doc = Doc(source_route="labels")
    with pymupdf.open(path) as d:
        if "/StructTreeRoot" not in d.xref_object(d.pdf_catalog(), compressed=True):
            raise RuntimeError("not tagged")
        doc.pages = len(d)
        vocab = vocabulary(d)
        for i, page in enumerate(d):
            flags = pymupdf.TEXTFLAGS_DICT | pymupdf.TEXT_COLLECT_STRUCTURE
            tree = get_text(page, "dict", flags=flags)
            _mark_slant(page, tree)
            ends = _letter_ends(page, flags)
            units = {}           # key -> [chain, [text blocks]], in order

            def walk(node, chain, owner):
                for b in node.get("blocks", []):
                    if b["type"] == 2:
                        tag = b.get("std") or b.get("raw") or ""
                        here = chain + [tag]
                        inside = owner is not None and \
                            LABEL_CONTAINER & set(owner[1])
                        # Word puts a note's label where it is referenced, so
                        # a note referenced inside a list item sits INSIDE
                        # that item. It is still its own note: absorbed, 1,011
                        # letters of `z21490618`'s notes became list text.
                        note = tag in ("Note", "Footnote") and not (
                            owner and {"Note", "Footnote"} & set(owner[1]))
                        own = (id(b), here) if tag in LABEL_UNIT and \
                            (note or not inside) else owner
                        walk(b, here, own)
                    elif b["type"] == 0:
                        key, ch = (id(b), []) if owner is None else owner
                        units.setdefault(key, [ch, []])[1].append(b)

            walk(tree, [], None)
            page_blocks = []
            for chain, blocks in units.values():
                kind, level = _label_kind(chain)
                # Not in headings: `z21764080` numbers one "1.1" with a small
                # "1", which was taken for a reference and vanished into it.
                if kind != HEADING:
                    _mark_note_numbers(blocks)
                blk = _rich_block(blocks, i, kind, (vocab, ends))
                if blk:
                    blk.level = level
                    page_blocks.extend(_split_notes(blk) if kind == FOOTNOTE
                                       else [_unmark(blk)])
            page_blocks = _split_typed_notes(page_blocks)
            for blk in _join_same_line(page_blocks):
                doc.add(blk)
    return doc


TYPED_NUMBER = re.compile(r"\((\d{1,3})\)")


def _split_typed_notes(blocks):
    """Split notes that arrived as one block but number themselves "(7) ...
    (8) ..." in type the same size as the text, so `_split_notes` cannot see
    them (`z21760325`). A "(k)" starts a new note only when k is the NEXT
    number and the page's body refers to k - an author's own "(2)" inside a
    note, a volume say, meets neither."""
    refs = {m for b in blocks if b.kind != FOOTNOTE
            for m in marker_numbers(b.text)}
    out = []
    for b in blocks:
        if b.kind != FOOTNOTE:
            out.append(b)
            continue
        m = TYPED_NUMBER.match(b.text)
        if not m:
            out.append(b)
            continue
        cuts, want = [], int(m.group(1)) + 1
        for n in TYPED_NUMBER.finditer(b.text, m.end()):
            if int(n.group(1)) == want and n.group(1) in refs:
                cuts.append(n.start())
                want += 1
        if not cuts and NOTE_LOOK_ON:
            out.append(b)
            continue
        # Cut with its formatting, as in _split_notes.
        got = _char_fmts(b.spans, b.text) if NOTE_LOOK_ON and b.spans else None
        for a, z in zip([0] + cuts, cuts + [len(b.text)]):
            piece = b.text[a:z].strip()
            if piece:
                nb = Block(kind=FOOTNOTE, text=piece, page=b.page, size=b.size,
                           y=b.y, y1=b.y1, x0=b.x0, x1=b.x1,
                           spans=[(piece, False, False)])
                if got is not None:
                    k = sum(1 for ch in b.text[:a] if not ch.isspace())
                    nb.spans = _word_spans(piece, got[k:])
                out.append(nb)
    return out


# A note number, as Word prints it: one to three digits set smaller than the
# text around them. Word draws the reference in the body and the number at
# the start of each note that way - "شاتليه¹³" - where the theses type
# "(13)". Found only by size: the superscript flag is set on some and not
# others in the same paragraph (`z21763864`), and the raised digits sit on a
# line of their own in PyMuPDF's view, so the comparison is with the whole
# labelled piece, not the line.
NOTE_NUMBER = re.compile(r"[0-9\u0660-\u0669]{1,3}")
NOTE_SMALL = 0.8
NOTE_PIECE = re.compile(r"[0-9\u0660-\u0669()\[\]]+")
NOTE_DIGITS = re.compile(r"[0-9\u0660-\u0669]")
# Wrapped in footnotes.MARK_OPEN/CLOSE - private-use characters that survive
# _clean - so a number found here can be told from a "(2)" the author typed.
MARKED =re.compile(MARK_OPEN + r"([0-9\u0660-\u0669]{1,3})" + MARK_CLOSE)
ADJACENT_MARKS = re.compile(MARK_CLOSE + r"\s*" + MARK_OPEN)


def _mark_note_numbers(text_blocks):
    """Wrap every small number in these PyMuPDF blocks in MARK_OPEN/CLOSE."""
    spans = [s for b in text_blocks for l in b["lines"] for s in l["spans"]
             if s["text"].strip()]
    weight = {}
    for s in spans:
        if not NOTE_NUMBER.fullmatch(s["text"].strip()):
            weight[s["size"]] = weight.get(s["size"], 0) + len(s["text"])
    if not weight:
        return
    body = max(weight, key=weight.get)
    # A number may also come in brackets and in pieces: `z21760325` refers to
    # note 11 as "(1" then "1", and numbers its notes "(11)". A run of
    # neighbouring small pieces made only of digits and brackets is one number.
    run = []
    for s in spans + [None]:
        t = s["text"].strip() if s else ""
        if s and s["size"] <= body * NOTE_SMALL and NOTE_PIECE.fullmatch(t):
            run.append(s)
            continue
        digits = "".join(NOTE_DIGITS.findall("".join(r["text"] for r in run)))
        if run and NOTE_NUMBER.fullmatch(digits):
            run[0]["text"] = MARK_OPEN + digits + MARK_CLOSE
            for r in run[1:]:
                r["text"] = ""
        run = []


def _joined(t):
    """A two-digit number can arrive as two small spans - `z21760325` refers
    to note 21 as "2" and "1" - so neighbouring marks are one number."""
    return ADJACENT_MARKS.sub("", t)


def _unmark(blk):
    """A body reference stays marked: the writer anchors a note to it, or
    writes it back as the raised digits it was."""
    fix = _joined
    blk.text = fix(blk.text)
    blk.spans = [(fix(t), b, i) for t, b, i in blk.spans]
    return blk


def _split_notes(blk):
    """One block per note. Word often labels a page's notes as ONE piece -
    "1 ... 2 ... 5 ..." - and the writer can pair a note with its reference
    only when the note starts with its own number."""
    full = _joined(blk.text)
    out = []                    # [(number or None, start, end)] in `full`
    at, num = 0, None
    for m in MARKED.finditer(full):
        out.append((num, at, m.start()))
        num, at = m.group(1), m.end()
    out.append((num, at, len(full)))
    # The piece's formatting, letter by letter, cut with it: the notes of one
    # piece lost which words were bold, and `z18037898` and `z18048055` bold
    # a book's or a sura's name in every note (Part 3, footnotes). Where the
    # piece's formatting is not known a note keeps what most of the piece
    # was - `z18441713`'s are bold throughout.
    n = sum(len(t) for t, *_ in blk.spans) or 1
    bold = sum(len(t) for t, b_, *_ in blk.spans if b_) * 2 > n
    italic = sum(len(t) for t, _, i_, *_ in blk.spans if i_) * 2 > n
    got = _char_fmts(blk.spans, full) if NOTE_LOOK_ON and blk.spans else None
    blocks = []
    for num, a, z in out:
        text = full[a:z].strip()
        if num is None and not text:
            continue                     # nothing before the first number
        t = text if num is None else f"({num}) {text}"
        b = Block(kind=FOOTNOTE, text=MARKED.sub(r"(\1)", t), page=blk.page,
                  size=blk.size, y=blk.y, y1=blk.y1, x0=blk.x0, x1=blk.x1,
                  bold=bold)
        b.spans = [(b.text, bold, italic)]
        if got is not None:
            k = sum(1 for ch in full[:a] if not ch.isspace())
            own = got[k:k + sum(1 for ch in full[a:z] if not ch.isspace())]
            spans = _word_spans(text, own)
            if num is not None:
                spans = [(f"({num})", False, False)] + spans
            b.spans = _word_spans(b.text, _char_fmts(spans, b.text))
        blocks.append(b)
    return blocks or [_unmark(blk)]


def _join_same_line(blocks):
    """Pieces of one kind that share a line are one paragraph.

    A form puts its fields side by side - `عن بعد` has اسم الطالبة, التوقيع
    and الرقم on one line, each labelled on its own. Written as three
    paragraphs they stacked, and the one-page form ran onto a second page.
    Joined in reading order: right to left when the text is Arabic.
    """
    out = []
    for b in blocks:
        prev = out[-1] if out else None
        if prev and prev.kind == b.kind and b.kind != FOOTNOTE and _same_line(prev, b):
            pieces = sorted([prev, b], key=lambda x: x.x1,
                            reverse=bool(ARABIC.search(prev.text + b.text)))
            prev.text = " ".join(x.text for x in pieces)
            prev.spans = [s for x in pieces for s in x.spans]
            prev.bold = prev.bold or b.bold
            prev.size = max(prev.size, b.size)
            prev.y, prev.y1 = min(prev.y, b.y), max(prev.y1, b.y1)
            prev.x0, prev.x1 = min(prev.x0, b.x0), max(prev.x1, b.x1)
            continue
        out.append(b)
    return out


def _same_line(a, b):
    """Do two blocks sit on one line: single-line each, heights overlapping
    by most of the shorter one, and side by side rather than stacked?"""
    ha, hb = a.y1 - a.y, b.y1 - b.y
    if ha <= 0 or hb <= 0 or max(ha, hb) > 2.2 * min(a.size, b.size or a.size or 1):
        return False
    overlap = min(a.y1, b.y1) - max(a.y, b.y)
    return overlap >= 0.6 * min(ha, hb) and (b.x1 <= a.x0 or b.x0 >= a.x1)


ENDS_PARA = (".", "؟", "!", ":", "؛")

# Bullet glyphs, a dash followed by a space, and "1." / "2-" / "(3)" openers.
# A bare "*" is deliberately excluded: "* Corresponding author" is a footnote
# marker on half the journal papers, and "*******" is a section divider. Both
# would have been read as list items.
BULLET_GLYPH = "•▪●○◦·⁃‣∙"
# What follows the marker must be the start of real text, not more
# punctuation: "[3] ." is a citation fragment, not a list item, and matched
# until this was tightened.
_ITEM_START = r"[^\s.,;:!?)\]}\u060C\u061B\u061F*\u2022-]"
LIST_MARK = re.compile(
    r"^\s*(?:[" + BULLET_GLYPH + r"]\s*"
    r"|[-\u2013\u2014]\s+"
    r"|[(\[]?\s*(?:\d{1,2}|[\u0660-\u0669]{1,2})\s*[-.)\]\u2013]\s+)"
    + _ITEM_START)


def _closes_paragraph(t):
    """Does this line finish a sentence?

    Checking only the END of the string was wrong for half the corpus. In
    right-to-left text the terminating punctuation is frequently STORED at the
    front: `تتمثل أساسا في:` extracts as `':وتتفرع عن هذه الإشكالية ... في'`,
    with the colon at index 0. `endswith` therefore never saw it, the line read
    as unfinished, and the bullet list that followed was merged into it -
    which is what turned five clean bullet points into one run-on paragraph.

    The punctuation is at whichever end the source put it, so look at both.
    """
    t = (t or "").strip()
    return bool(t) and (t.endswith(ENDS_PARA) or t.startswith(ENDS_PARA))


def _join_lines(blocks):
    """Merge consecutive lines back into paragraphs.

    The detailed page view hands back one entry per line as often as per
    paragraph - 290 entries for an 11-page document. Emitting each as its own
    Word paragraph forced a line break after every line, so pages held half the
    text they should and page counts doubled.

    Two entries join when they sit directly under one another at body spacing,
    share a font size, and the upper one does not end like a finished sentence.
    """
    if not blocks:
        return blocks
    gaps = sorted(b.y - a.y1 for a, b in zip(blocks, blocks[1:])
                  if b.page == a.page and b.y >= a.y1)
    lead = gaps[len(gaps) // 2] if gaps else 2.0
    out = [blocks[0]]
    for b in blocks[1:]:
        a = out[-1]
        same_page = b.page == a.page
        stacked = same_page and -2 <= (b.y - a.y1) <= max(4.0, lead * 2.2)
        same_size = abs(b.size - a.size) < 0.6 and b.bold == a.bold
        open_end = not a.text.rstrip().endswith(ENDS_PARA)
        wide = (a.x1 - a.x0) > 0 and (b.x1 - b.x0) > (a.x1 - a.x0) * 0.4
        # A line that opens with a bullet or a number starts a new item, however
        # the line above it ended. Without this the second and later items of a
        # list still ran into the first.
        starts_item = bool(LIST_MARK.match(b.text or ""))
        if stacked and same_size and open_end and wide and not starts_item:
            a.text = (a.text + " " + b.text).strip()
            a.spans = a.spans + b.spans
            a.y1 = b.y1
            a.x0 = min(a.x0, b.x0); a.x1 = max(a.x1, b.x1)
        else:
            out.append(b)
    return out


# ---------------------------------------------------------------- pick

HEAD_WORDS = ("المطلب", "المبحث", "الفصل", "تمهيد", "المقدمة", "الخاتمة",
              "الفهرس", "المراجع", "التوطئة", "أولا", "أولاً", "ثانيا", "ثانياً",
              "ثالثا", "ثالثاً", "رابعا", "رابعاً", "خامسا", "خامساً")
ENDS_SENTENCE = (".", "،", "؛", "؟", "!")
MAX_HEADING_CHARS = 90

# Particles that open a continuation, never a heading. The waw and the fa are
# written joined to the following word, so "وقد" and "فالقراءة" are caught by
# their first letter.
CONNECTIVES = ("و", "ف", "ثم", "بل", "أو", "على", "حتى", "كما", "إذ",
               "أما", "أمَّا", "لكن", "لأن", "قال")
COLONS = (":", "：")
MAX_LABEL_CHARS = 60


def _is_label_heading(t):
    """Is this short line ending in a colon a real sub-heading?

    These theses use no Word heading styles, so a line like "أهداف البحث:" is
    the only marker a section gets and the rule has to stay. But promoting
    EVERY colon-terminated line swept up sentence tails - "على قسمين:"
    ("...into two categories:") became a heading.

    Length cannot separate them: "على قسمين:" is the shortest such line in the
    corpus and it is wrong, while "مولده وصفاته وبركات بيت النبوَّة عليه:" is
    the longest and it is right. Grammar separates them. A heading is a noun
    phrase, so it carries no comma and no second colon, and it does not open
    with a connective particle - those always continue the sentence before.
    """
    t = (t or "").strip()
    if not t.endswith(COLONS) or len(t) > MAX_LABEL_CHARS:
        return False
    if "," in t or "،" in t:            # a comma means a clause, not a label
        return False
    if any(c in t[:-1] for c in COLONS):   # "أهمية البحث: البحث له أهميتان,"
        return False
    return not t.startswith(CONNECTIVES)


def detect_headings(doc):
    """Mark headings.

    Three sources, best first: the PDF's own heading labels; font size, where
    the glyphs were readable; and failing both, the shape of the line. The last
    is needed because none of the sample files use Word heading styles - their
    author just made text bigger by hand - while 44% of PDFs in the wild do
    carry real heading labels.
    """
    if any(b.kind == HEADING for b in doc.blocks):
        return doc

    body = _body_size(doc)
    if body:
        for b in doc.blocks:
            if b.kind == PARAGRAPH and b.size >= body * 1.15 and len(b.text) <= 160:
                b.kind = HEADING
                b.level = 1 if b.size >= body * 1.4 else 2
        if any(b.kind == HEADING for b in doc.blocks):
            return doc

    for b in doc.blocks:
        if b.kind != PARAGRAPH or not b.text:
            continue
        t = b.text.strip()
        if len(t) > MAX_HEADING_CHARS or t.endswith(ENDS_SENTENCE):
            continue
        if t.startswith(HEAD_WORDS) or _is_label_heading(t):
            b.kind = HEADING
            b.level = 1 if t.startswith(HEAD_WORDS[:6]) else 2
    return doc


def detect_lists(doc):
    """Mark the paragraphs that are really list items.

    Runs AFTER `detect_headings`, and that order is the whole trick. These
    documents number their sections - `1 . مقدمة`, `7 . متغيرات البحث` - so a
    numbered opener matches a list marker exactly as well as it matches a
    heading. Marking lists first turned every numbered heading in `z21011460`
    into a list item, and `detect_headings` only ever looks at paragraphs, so
    they could never be recovered.

    A heading has already claimed what it needs by the time this runs; what is
    left wearing a marker is a list.
    """
    for b in doc.blocks:
        if b.kind == PARAGRAPH and b.text and LIST_MARK.match(b.text):
            b.kind = LIST_ITEM
    return doc


def _body_size(doc):
    """Most common font size, weighted by how much text is set in it."""
    weight = {}
    for b in doc.blocks:
        if b.size:
            weight[b.size] = weight.get(b.size, 0) + len(b.text)
    if not weight:
        return 0.0
    return max(weight, key=weight.get)


SANE_PT = (6.0, 30.0)
MIN_SPAN_CHARS = 500    # enough decodable text to trust the stated font size
TIE_MARGIN = 0.97       # keep the labelled reader unless it loses >3% of the text
GLYPH_RATIO = 0.94      # inked band height as a fraction of font size, measured


def measure_layout(path, doc):
    """Read the original's margins and body font size off the page.

    Guessing 1-inch margins and 12pt put our pages visibly out of step with the
    originals. Both numbers are measurable, so measure them.

    Edges come from the middle of the distribution, not the extremes: page
    numbers and headers sit further out than the body and would drag the
    margins wrong. Font sizes are filtered to a believable range first, because
    undecodable decorative glyphs report sizes like 90pt.
    """
    import statistics
    lefts, rights, tops, bottoms = [], [], [], []
    heights, pitches, spans = [], [], []
    with pymupdf.open(path) as d:
        if not len(d):
            return doc
        w, h = d[0].rect.width, d[0].rect.height
        for page in d:
            for b in get_text(page, "blocks"):
                if b[6] != 0 or not str(b[4]).strip():
                    continue
                if (b[2] - b[0]) < w * 0.35:      # skip page numbers, stray marks
                    continue
                lefts.append(b[0]); rights.append(b[2])
                tops.append(b[1]); bottoms.append(b[3])
            hh, pit = _ink_rows(page)
            heights.extend(hh); pitches.extend(pit)
            for bl in get_text(page, "dict")["blocks"]:
                if bl.get("type") != 0:
                    continue
                for line in bl["lines"]:
                    for sp in line["spans"]:
                        t = sp["text"].strip()
                        if t and SANE_PT[0] <= sp["size"] <= SANE_PT[1]:
                            spans.extend([sp["size"]] * len(t))
    doc.font = _dominant_font(path)
    doc.digits = shown_digits(path)
    if lefts:
        doc.margin_left = max(18.0, statistics.median(lefts))
        doc.margin_right = max(18.0, w - statistics.median(rights))
        doc.margin_top = max(18.0, min(tops))
        doc.margin_bottom = max(18.0, h - max(bottoms))
    # Where the glyphs decode, the font size is stated outright - use it.
    # The ink estimate is for files whose Arabic cannot be decoded, and it
    # overestimated badly on ordinary files, doubling their page count.
    if len(spans) >= MIN_SPAN_CHARS:
        doc.body_size = round(statistics.median(spans), 1)
        if pitches:
            doc.line_pitch = round(statistics.median(pitches), 1)
            doc.line_spacing = round(min(3.0, max(0.9, doc.line_pitch / doc.body_size)), 2)
    elif heights:
        size = statistics.median(heights) / GLYPH_RATIO
        doc.body_size = round(min(SANE_PT[1], max(SANE_PT[0], size)), 1)
        if pitches:
            doc.line_pitch = round(statistics.median(pitches), 1)
            doc.line_spacing = round(min(3.0, max(0.9, doc.line_pitch / doc.body_size)), 2)
    return doc


SUBSET = re.compile(r"^[A-Z]{6}\+")
# Fonts of signs and bullets, never the body's.
SYMBOLIC = ("wingdings", "webdings", "symbol", "arabesque", "glyphless")
STYLE = re.compile(r"[-,]?(Bold|Italic|BoldItalic|Regular|Light|MT|PS)$")


def _dominant_font(path):
    """The document's own Arabic font: the one that draws the most Arabic.

    Setting everything in Arial made our text noticeably wider than the
    original - Arial's Arabic is wide, and fonts like Sakkal Majalla or
    Simplified Arabic are not - which stretched every page.

    It used to count the pages each font appeared on and skip Arial, Calibri
    and Times as generic. But Arial is the body font of Moaz's theses, and
    their Arabic is drawn as outlines with the words attached as labels, so
    no font draws it at all: what was left was a font seen once. Three
    chapters came out entirely in AGA Arabesque, a font of religious signs,
    and one in Sakkal Majalla, which drew nothing (N4, 2026-09-22).

    So count the letters each font draws: Arabic ones (and ones that do not
    decode, as broken Arabic fonts' do not - AL-Mohanad's decode to private
    codes), or when there are none, any letter or digit. A font of signs
    never counts, nor one whose name was lost (CIDFont+F4). The name is
    given the way Word knows the font: TimesNewRomanPSMT is Times New Roman.
    """
    from convert.glyphs import family
    import collections
    arabic, other = collections.Counter(), collections.Counter()
    with pymupdf.open(path) as d:
        for i, page in enumerate(d):
            if i > 9:
                break
            for span in page.get_texttrace():
                name = SUBSET.sub("", str(span["font"])).split(",")[0].strip()
                name = name.lstrip("+")
                for _ in range(2):
                    name = STYLE.sub("", name)
                if not name or name.startswith("CIDFont")                         or any(g in name.lower() for g in SYMBOLIC):
                    continue
                for ch in span["chars"]:
                    c = ch[0]
                    if (0x0600 <= c <= 0x06FF or 0xFB50 <= c <= 0xFEFF
                            or 0xE000 <= c <= 0xF8FF or c in (0, 0xFFFD)):
                        arabic[name] += 1
                    elif c < 0xE000 and chr(c).isalnum():
                        other[name] += 1
    weight = arabic or other
    return family(weight.most_common(1)[0][0]) if weight else ""


def _ink_rows(page):
    """Measure text lines off the page image: how tall, and how far apart.

    Font size could not be read from the text spans - on these files the Arabic
    glyphs do not decode, so the only spans reporting a size are Latin digits
    and decorative marks, which gave 18pt for 12pt body text. Ink does not care
    whether a glyph decodes.

    Line *pitch* alone was not enough either: it confuses a large font with a
    generously spaced small one. Measuring the height of the inked band gives
    the glyph size directly, and pitch divided by that gives the line spacing.
    """
    import numpy as np
    pm = page.get_pixmap(dpi=72, colorspace=pymupdf.csGRAY)
    a = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)
    rows = (a < 200).sum(axis=1)
    if not rows.max():
        return [], []
    inked = rows > max(2, rows.max() * 0.06)
    runs, start = [], None
    for j, v in enumerate(inked):
        if v and start is None:
            start = j
        elif not v and start is not None:
            runs.append(j - start); start = None
    starts = [j for j in range(1, len(inked)) if inked[j] and not inked[j - 1]]
    pitch = [starts[k + 1] - starts[k] for k in range(len(starts) - 1)]
    return ([r for r in runs if 3 < r < 40], [p for p in pitch if 4 < p < 60])


MIN_IMAGE_PT = 24.0      # drawn size below this is a spacer, not a picture
MIN_IMAGE_PX = 16        # Word scatters 2x2 pixel images across every page


def _word_can_read(blob):
    """Ask python-docx itself whether it can actually USE these bytes.

    Measured, not predicted. The file extension does not tell us: a PDF hands
    back valid JPEGs that python-docx rejects, and guessing which ones from the
    format name would mean reimplementing its parser.

    Identifying the bytes is not enough. A JPEG may declare a pixel density of
    zero, which python-docx parses happily and only trips over later, when it
    works out the native size as pixels / dpi. Asking for the dimensions here
    turns that into a re-render instead of a lost picture.
    """
    try:
        from docx.image.image import Image
        im = Image.from_blob(blob)
        im.width, im.height
        return True
    except Exception:
        return False


def _repaint(doc, xref):
    """Re-render one image through pymupdf as a PNG, or None if that fails."""
    try:
        pix = pymupdf.Pixmap(doc, xref)
        if pix.colorspace and pix.n - pix.alpha > 3:      # CMYK and friends
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        return pix.tobytes("png")
    except Exception:
        return None


def _is_flat(doc, xref, sample=4096):
    """Is the stored image one flat colour, with its real shape in a mask?

    `الفصل الثالث` carries its running header as two 676x132 RGB images that
    are **solid black**, with an 8-bit SMask holding the actual Arabic. We took
    the pixels and dropped the mask, so a black bar was stamped across the top
    of every page - of that file and of `z21358439` too. Every score rated it
    100% on images: a placed picture is counted, not looked at.

    Reconstructing the mask is not worth attempting. It is a `/Matte`
    pre-multiplied alpha whose values run 0..64 rather than 0..255, so the
    obvious composite comes out at a quarter opacity or fully transparent
    depending on how it is read, and `Pixmap(doc, xref)` does not apply it at
    all - it returns the same solid black with an alpha channel of 255.

    Flatness alone is NOT a sufficient signal, which cost one attempt. The
    second header image is a black box with a white border - 26 distinct
    colours, so not flat - whose text `الفصل الثالث` is entirely in the mask.
    It still rendered as a black box. Kept here because a flat image is a
    useful second trigger for pictures that have no mask at all.
    """
    try:
        pix = pymupdf.Pixmap(doc, xref)
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)
    except Exception:
        return False
    s, n = pix.samples, pix.n
    total = len(s) // max(1, n)
    if total < 4:
        return False
    first, step = s[:n], max(1, total // sample)
    for k in range(0, total, step):
        i = k * n
        if s[i:i + n] != first:
            return False
    return True


def _dpi_for(rect, px, lo=96, hi=300):
    """Enough dots to keep the picture's own detail, and no more.

    Rendering everything at a fixed high dpi turns a small logo into a large
    PNG and a large photo into a larger one, for no visible gain. Match the
    image's own pixel count across the width it is drawn at.
    """
    if rect.width <= 0 or not px:
        return lo
    return int(max(lo, min(hi, 72.0 * px / rect.width)))


def _turned(m):
    """Drawn turned or mirrored: the stored pixels are not the way round the
    page shows them, so a copy placed at the drawn size would come out
    squashed sideways (z20538636 page 17). Photograph those off the page."""
    if not TURNED_ON:
        return False
    return abs(m.b) > 1e-3 or abs(m.c) > 1e-3 or m.a < 0 or m.d < 0


TURNED_ON = os.environ.get("QIRTAS_IMG_SHAPE", "1") != "0"


def _render_region(page, rect, dpi=200):
    """Photograph the page where the picture sits, rather than decoding it.

    The same trick `render_vector_cells` uses for line art. It flattens
    transparency onto the page, which is exactly right for a decoration sitting
    on a white page and is what the reader sees anyway.
    """
    try:
        return page.get_pixmap(clip=rect, dpi=dpi).tobytes("png")
    except Exception:
        return None


# A title page built as a collage: a frame, a crest, and the title, the
# university and the author's name each as a separate picture laid over it.
# `مقدمة البحث` page 1 is 26 of them, overlapping. Pulled apart and stacked one
# under another they took two pages however they were shrunk, and that one
# extra page put all 15 pages after it one out of step - right page 33.7%
# where its siblings reach 56-73%.
COLLAGE_MIN = 3
COLLAGE_MAX_WORDS = 15
COLLAGE_DPI = 150
NUMBERS_AND_SPACE = re.compile(r"[\s0-9\u0660-\u0669\u06F0-\u06F9]+")


def _collage(path, blocks, outdir):
    """The first page as ONE photograph, when it is nothing but overlapping
    pictures. -> Block or None.

    Only the first page, and only when:
      - it has no words at all (a printed page number does not count), so
        nothing the reader or the loss gate cares about is inside the photo.
        BOTH the page's text layer and the words the reader chose for it are
        asked (the caller checks the second): Moaz's chapters keep their
        words in /ActualText with an almost empty text layer, so the layer
        alone called every chapter's first page empty and turned its real,
        editable headings into a photograph - which the loss gate could not
        see either, since it reads the same layer (2026-09-21);
      - it has at least COLLAGE_MIN pictures, and at least two of them overlap.
        Overlap is what stacking cannot reproduce; separate pictures side by
        side are left to the ordinary path.

    Photographed as the page shows it, page number included. The writer turns
    Word's header and footer off for this one page, so nothing is doubled.
    """
    blocks = [b for b in blocks if b.page == 0]
    if len(blocks) < COLLAGE_MIN:
        return None
    with pymupdf.open(path) as d:
        page = d[0]
        if NUMBERS_AND_SPACE.sub("", get_text(page, "text")):
            return None
        return _collage_shot(page, blocks, outdir)


def _collage_shot(page, blocks, outdir):
    rects = [pymupdf.Rect(b.x0, b.y, b.x1, b.y1) for b in blocks]
    if not any(not (a & b).is_empty
               for k, a in enumerate(rects) for b in rects[k + 1:]):
        return None
    union = pymupdf.Rect(rects[0])
    for r in rects[1:]:
        union |= r
    # Grow to take in line art the pictures overlap. The rounded frame on each
    # of Moaz's chapter title pages is drawn, not placed: its pictures stop at
    # y=699 while the frame's curve runs below, so the photo cut the frame
    # open. A drawing near the size of the page is a border, not part of this.
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    big = 0.9 * page.rect.width * page.rect.height
    for g in drawings:
        r = pymupdf.Rect(g["rect"])
        if r.width * r.height < big and not (r & union).is_empty:
            union |= r
    union &= page.rect
    shot = _render_region(page, union, COLLAGE_DPI)
    if not shot:
        return None
    dest = Path(outdir) / "p0_collage.png"
    dest.write_bytes(shot)
    return Block(kind=IMAGE, text="", page=0, image=str(dest),
                 x0=union.x0, x1=union.x1, y=union.y0, y1=union.y1,
                 origin="collage0", collage=True)


def _drop_collage_captions(doc, path):
    """Remove text on a photographed first page that the page never printed.

    The tag route reads each picture's description out of the structure tree.
    On `مقدمة البحث` that is Word's automatic alt text - "Logo Description
    automatically generated with medium confidence", ten times - and the
    title's own words, which exist only as pictures on the page. Written as
    paragraphs they filled two pages on top of the photo that already shows
    them.

    A block is kept if its words are in the page's own text layer, which is
    what the loss gate measures - so this cannot drop a word the gate counts.
    """
    try:
        with pymupdf.open(path) as d:
            printed = WS.sub("", get_text(d[0], "text")).replace("\n", "")
    except Exception:
        return
    keep = []
    for b in doc.blocks:
        if b.page == 0 and b.kind != IMAGE and b.text.strip():
            flat = WS.sub("", b.text).replace("\n", "")
            if flat not in printed:
                continue
        keep.append(b)
    doc.blocks = keep


def read_images(path, outdir):
    """Pull the real pictures out of the PDF, ignoring Word's pixel litter.

    One page carried 276 images of which 275 were 2x2 pixels stretched into
    thin bars. Filtering on both the stored size and the drawn size leaves the
    actual figures.

    Anything Word cannot identify is re-rendered as a PNG. PDFs routinely store
    bare DCT streams with no JFIF wrapper, because the PDF object already
    carries the colorspace and size, so the APP0 segment is redundant.
    python-docx identifies a JPEG only by the literal bytes "JFIF" or "Exif" at
    offset 6, so those images raise UnrecognizedImageError, and the writer
    caught that and dropped the picture without a word. Re-rendering costs
    nothing on the common path: images Word already accepts are written through
    untouched.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    blocks = []
    with pymupdf.open(path) as d:
        for i, page in enumerate(d):
            seen = set()
            mine = []
            for info in page.get_images(full=True):
                xref, w, h = info[0], info[2], info[3]
                if xref in seen or w < MIN_IMAGE_PX or h < MIN_IMAGE_PX:
                    continue
                placed = [(r, m) for r, m in
                          (page.get_image_rects(xref, transform=True) or [])
                          if r.width >= MIN_IMAGE_PT and r.height >= MIN_IMAGE_PT]
                if not placed:
                    continue
                rects = [r for r, _ in placed]
                turned = _turned(placed[0][1])
                seen.add(xref)
                try:
                    raw = d.extract_image(xref)
                except Exception:
                    continue
                blob, ext = raw["image"], raw.get("ext", "png")
                over = False
                # A picture whose appearance is partly in a transparency mask
                # cannot be rebuilt from the stored pixels - see _is_flat. Take
                # it off the page instead, where it is already correct.
                if raw.get("smask") or _is_flat(d, xref) or turned:
                    shot = _render_region(page, rects[0], _dpi_for(rects[0], w))
                    if shot:
                        blob, ext = shot, "png"
                        try:
                            over = bool(get_text(page, "text", clip=rects[0]).strip())
                        except Exception:
                            over = False
                if not _word_can_read(blob):
                    blob, ext = _repaint(d, xref), "png"
                    if blob is None:
                        continue
                dest = outdir / f"p{i}_x{xref}.{ext}"
                dest.write_bytes(blob)
                r = rects[0]
                mine.append(Block(kind=IMAGE, text="", page=i, image=str(dest),
                                  x0=r.x0, x1=r.x1, y=r.y0, y1=r.y1,
                                  origin=f"x{xref}", over_text=over))
            blocks.extend(mine)
    return blocks


EDGE_BAND = 0.08         # top and bottom share of a photo checked for leaks
EDGE_SLACK = 20          # dark pixels above the cleanest copy still counted clean


def _edge_ink(path):
    """Dark pixels along the top and bottom edges of a picture file."""
    try:
        pix = pymupdf.Pixmap(path)
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)
        if pix.n != 1:
            pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
        w, h, s = pix.width, pix.height, pix.samples
        band = max(1, int(h * EDGE_BAND))
        rows = list(range(band)) + list(range(h - band, h))
        return sum(1 for y in rows for v in s[y * w:(y + 1) * w] if v < 128)
    except Exception:
        return None


def _mark_edge_ink(blocks):
    """Mark copies of a repeated decoration whose photo caught the page.

    Each copy is photographed off its own page and takes in whatever reaches
    into its rectangle there. On `الفصل الثالث` page 2 the heading "تمهيد"
    starts at y=71 under a header picture ending at y=79, so that copy carried
    the tops of the heading's letters - and once it was the copy drawn, every
    page's header showed the sliver (2026-09-21). The heading is drawn as
    glyphs that do not decode, so neither removing text nor removing pictures
    before the photo gets rid of it; three attempts at that failed.

    Measured instead: whatever leaks in arrives at the photo's top or bottom
    edge, so count the ink there. On that header the bottom strip reads 108
    dark pixels with the sliver and 34 without. Copies more than EDGE_SLACK
    above the cleanest are marked `over_text`, and the writer draws a clean
    one.
    """
    groups = {}
    for b in blocks:
        if b.origin:
            groups.setdefault(b.origin, []).append(b)
    for copies in groups.values():
        if len(copies) < 3:
            continue
        inks = [_edge_ink(b.image) for b in copies]
        known = [v for v in inks if v is not None]
        if not known:
            continue
        floor = min(known)
        for b, v in zip(copies, inks):
            if v is not None and v > floor + EDGE_SLACK:
                b.over_text = True


def _unreverse(cell, page_flat):
    """Table extraction hands back Arabic in visual order.

    The table finder does not apply the logical ordering the text extractor
    does, so cells come out backwards ("مدختسملا" for "المستخدم"). Writing that
    into a Word file would be corruption, so check each cell against the page's
    correctly ordered text and flip the ones that only match reversed.
    """
    flat = WS.sub("", cell)
    if len(flat) < 6 or not ARABIC.search(flat):
        return cell
    # Probe with a slice from the middle rather than the whole cell: cell edges
    # pick up stray characters that break an exact match even when the body of
    # the text is present.
    n = min(14, max(6, len(flat) // 2))
    mid = (len(flat) - n) // 2
    probe = flat[mid:mid + n]
    if probe in page_flat:
        return cell
    if probe[::-1] in page_flat:
        return cell[::-1]
    return cell


def _cell_text(page, box, fallback, page_flat):
    """Read one cell off the PAGE rather than out of the table finder.

    The table finder returns Arabic in visual order, and `_unreverse` repaired
    that by flipping the string. Flipping is not the inverse of visual order:
    it also flips the two characters inside a lam-alef ligature, so `للأوراق`
    came back as `أللوارق` and then matched nothing, and the cell was written
    backwards into the document. Two of eight cells on one table, silently.

    Clipping to the cell's own rectangle goes through the SAME extractor that
    produces correctly ordered body text, so the order is right for the same
    reason it is right everywhere else - and it is consistent with the text the
    scorer reads, which a flipped string never was.

    Two guards, because a clip can go wrong in exactly two ways. It can catch a
    NEIGHBOURING cell, so the reading must be about as long as the table
    finder's. And it must actually be in logical order, so a probe from it has
    to be found forward in the page's own text. Either guard failing falls back
    to the old path rather than guessing.

    Character multisets are NOT used to decide this, though it was the obvious
    test: the lam-alef ligature expands to a different number of characters in
    the two extraction modes (`االتجاه` against `لا...`), so the multisets of
    identical content differ and one correct cell in four was rejected.
    """
    if box is None:
        return _cell_ends(_unreverse(_clean(fallback or ""), page_flat))
    try:
        clip = get_text(page, "text", clip=pymupdf.Rect(box))
        unseen = _unseen(page, box) if TABLE_MARK_ON else None
    except Exception:
        return _cell_ends(_unreverse(_clean(fallback or ""), page_flat))
    # Before the direction check: `الوسط ا` was found nowhere in the page's
    # text, and the table finder's backwards `طسولا` was written instead.
    # Once only: stripped twice, the second pass took the article's alef too.
    mine = _cell_ends(clip, unseen)
    read = _cell_read(mine, fallback, page_flat)
    return read if read == _clean(mine) else _cell_ends(read, unseen)


# `z17931421` draws at the start of a cell's word an invisible ۡ with one to
# three alefs or a م after it, all of no width: its header came out
# `الاختلافۡا`, `وحدة ۡالقياسۡم` - the "stray ا in header cells". Taken off a
# cell's end only where the page draws them with no width: inside a word a
# zero-width alef is half of a lam-alef, and a cell's own last word can be
# a real م (2022 م). And the probe that checks a clip's direction asks
# without ۡ: the page's text puts it at the other end of the word
# (`ۡضابطة` / `ضابطةۡ`), the probe failed, and the table finder's backwards
# `ةطباض` was written instead (QIRTAS_TABLE_MARK).
CELL_START = re.compile(r"^[ۡ\s]+")
CELL_END = re.compile(r"[ۡ\s]+([ۡام]{1,3})\s*$")
STRAY = set("ۡام")


# Cells stored backwards where the page's own text is backwards too
# (`z21145041`, read by its labels' /ActualText): `_cell_text` checks a cell's
# direction against the page's text, which agreed, and `ارشؤمل` went into the
# table - and its words, found nowhere in the table, were written again
# under it. Asked of the reading the file is written from instead: a cell
# whose Arabic words are there only turned round is turned, its English and
# numbers kept as they read (QIRTAS_CELLS_TURN).
CELLS_TURN_ON = os.environ.get("QIRTAS_CELLS_TURN", "1") != "0"


def _turn_cells(tables, doc):
    words = set(TURN_WORD.findall(" ".join(b.text for b in doc.blocks
                                           if b.kind != TABLE)))
    if not words:
        return

    def near(w):
        # a letter of the next word taken in, or the tanween's alef moved
        # (ارشؤمل for المؤشر; see _backfill)
        return w in words or (len(w) >= 5 and (w[1:] in words or w[:-1] in words))

    def known(w):
        return near(w) or near(w[-1] + w[:-1])

    def turn(cell):
        ws = TURN_WORD.findall(cell)
        back = sum(1 for w in ws if known(w[::-1]) and not known(w))
        ahead = sum(1 for w in ws if known(w) and not known(w[::-1]))
        if not ws or back <= ahead:
            return first_back(cell)
        # Turned whole, then brackets mirrored and English and numbers put
        # back as they read: (Cr) -> )rC( -> (rC) -> (Cr).
        flipped = cell[::-1].translate(BRACKET_MIRROR)
        return first_back(LATIN_RUN.sub(lambda m: m.group(0)[::-1], flipped))

    def first_back(c):
        # Stored backwards, a cell's first letter comes last: لمؤشرا for
        # المؤشر, لف التركيب الأنبوبيت for تلف التركيب الأنبوبي. Put back
        # where that makes its first word one the thesis has.
        letters = [i for i, ch in enumerate(c) if ARABIC_LETTER.match(ch)]
        first = FIRST_WORD.search(c)
        if not letters or not first or near(first.group(0)):
            return c
        i = letters[-1]
        if i <= first.start():
            return c
        moved = c[:i] + c[i + 1:]
        moved = moved[:first.start()] + c[i] + moved[first.start():]
        now = FIRST_WORD.search(moved)
        return moved if now and near(now.group(0)) else c
    for t in tables:
        t.rows = [[turn(c) for c in row] for row in t.rows]


LATIN_RUN = re.compile(r"[A-Za-z0-9.,%/\-]*[A-Za-z0-9][A-Za-z0-9.,%/\-]*")
BRACKET_MIRROR = str.maketrans("()[]", ")(][")
FIRST_WORD = re.compile("[ء-ي]+")


def _unseen(page, box):
    """(letters the page draws inside `box` with no width, letters the
    plain clip takes that are not the cell's), each by count.

    The plain clip takes any letter touching the box: the first letter of
    the entry beside a number, drawn over the rule, came into both cells -
    `251ح` and `حممد` for 251 and محمد (`z18037898`), and `ا ي جودة النموذج`
    on `z3387756`. The letter-by-letter reading takes only the cell's own;
    the text is still the plain clip's, whose order of English inside
    Arabic the other does not keep."""
    zero, own = collections.Counter(), collections.Counter()
    r = pymupdf.Rect(box)
    for b in page.get_text("rawdict", clip=r)["blocks"]:
        for ln in b.get("lines", ()):
            for sp in ln["spans"]:
                for ch in sp["chars"]:
                    own[ch["c"]] += 1
                    if ch["c"] in STRAY and ch["bbox"][2] - ch["bbox"][0] < 0.05:
                        zero[ch["c"]] += 1
    taken = collections.Counter(page.get_text("text", clip=r))
    extra = collections.Counter({c: n - own[c] for c, n in taken.items()
                                 if not c.isspace() and n > own[c]})
    return zero, extra


def _cell_ends(text, unseen=None):
    if not TABLE_MARK_ON or not text:
        return text
    text = CELL_START.sub("", text)
    if unseen is None:
        return text
    zero, extra = unseen
    m = CELL_END.search(text)
    if m and all(zero[c] >= m.group(1).count(c) for c in set(m.group(1))):
        text = text[:m.start()]
    # Letters not the cell's, off its two ends only, and never past the
    # first or last word: `ا المتغير` lost its stray alef and then the
    # article's, and `z21644412`'s table changed shape over seven pages.
    left = collections.Counter(extra)
    t = text.strip()
    while t and not t[-1].isspace() and left[t[-1]] > 0:
        left[t[-1]] -= 1
        t = t[:-1]
    t = t.rstrip()
    while t and not t[0].isspace() and left[t[0]] > 0:
        left[t[0]] -= 1
        t = t[1:]
    return t.lstrip()


def _cell_read(clip, fallback, page_flat):
    a, b = WS.sub("", (clip or "").replace("\n", "")), \
        WS.sub("", (fallback or "").replace("\n", ""))
    if not a:
        return _unreverse(_clean(fallback or ""), page_flat)
    if b and len(a) - len(b) > max(3, 0.25 * len(b)):
        return _unreverse(_clean(fallback or ""), page_flat)   # caught a neighbour
    if len(a) >= 6 and ARABIC.search(a):
        # Probed line by line: the page's text orders a cell's lines among
        # its other text, so a probe across a line break is found nowhere,
        # and 300 cells of correct text were written backwards from the
        # table finder instead (z22639353, z20375390's header band).
        lines = [x for x in (WS.sub("", ln) for ln in clip.split("\n"))
                 if len(x) >= 6 and ARABIC.search(x)] or [a]
        if TABLE_MARK_ON:
            bare = page_flat.replace("ۡ", "")
            ok = all(_probe(x.replace("ۡ", "")) in bare for x in lines)
        else:
            ok = all(_probe(x) in page_flat for x in lines)
        if not ok:
            return _unreverse(_clean(fallback or ""), page_flat)
    return _clean(clip)


def _probe(flat):
    n = min(14, max(6, len(flat) // 2))
    return flat[(len(flat) - n) // 2:][:n]


def read_tables(path):
    """Find tables and return them as blocks of rows."""
    blocks = []
    with pymupdf.open(path) as d:
        for i, page in enumerate(d):
            try:
                found = page.find_tables().tables
            except Exception:
                continue
            page_flat = WS.sub("", get_text(page, "text"))
            drawings = None
            for t in found:
                if RULES_ON:
                    if drawings is None:
                        drawings = page.get_drawings()
                    if not _ruled(drawings, pymupdf.Rect(t.bbox)):
                        continue
                try:
                    raw = t.extract()
                    cells = []
                    try:
                        cells = [[c for c in row.cells] for row in t.rows]
                    except Exception:
                        cells = []
                    rows = []
                    for ri, row in enumerate(raw):
                        out = []
                        for ci, c in enumerate(row):
                            box = None
                            if ri < len(cells) and ci < len(cells[ri]):
                                box = cells[ri][ci]
                            out.append(_cell_text(page, box, c, page_flat))
                        rows.append(out)
                except Exception:
                    continue
                if not rows or not any(any(c for c in r) for r in rows):
                    continue
                r = t.bbox
                widths = _col_widths(t)
                boxes = []
                try:
                    boxes = [[c for c in row.cells] for row in t.rows]
                except Exception:
                    boxes = []
                grid = SPAN_ON and _unnest(rows, boxes) and _is_grid(boxes)
                spans = _spans(boxes) if grid else {}
                if grid:
                    widths = _grid_widths(boxes, r[2]) or widths
                blocks.append(Block(kind=TABLE, text="", page=i, rows=rows,
                                    col_widths=widths, cell_boxes=boxes,
                                    cell_spans=spans,
                                    x0=r[0], y=r[1], x1=r[2], y1=r[3]))
    return _drop_pieces(blocks) if PIECES_ON else blocks


# A "table" with no rule inside it is not one: the finder builds grids from
# filled boxes too, and white or tinted fills behind lines of text - a
# thesis's footnotes (`z22058810` pages 11-12), its shaded opening verse
# (page 2, cells backwards and the verse written again garbled), reference
# lists (`z18896740`, `z5227331`), a cover's title (`z21644412`) - came out
# as tables. Word draws a table's borders as lines or as fills a hairline
# thin; with neither inside the box it is text, read as text
# (QIRTAS_TABLE_RULES). Checked on the 25 theses: every table so dropped
# was one of these.
RULES_ON = os.environ.get("QIRTAS_TABLE_RULES", "1") != "0"
RULE_THIN = 2.0       # points: a fill this thin is a rule


def _ruled(drawings, box):
    inner = box + (-1, -1, 1, 1)
    for g in drawings:
        r = g["rect"]
        if not inner.contains(r):
            continue
        if "s" in g["type"] or (g.get("fill") is not None
                                and min(r.width, r.height) <= RULE_THIN):
            return True
    return False


# A table found inside another's box on its page is a piece of it: the table
# finder finds `z3387756` page 12's 23-column table, and five rows of it again
# as small tables of their own, written as small tables and loose lines under
# it. Its text is the big table's cells already (QIRTAS_TABLE_PIECES).
PIECES_ON = os.environ.get("QIRTAS_TABLE_PIECES", "1") != "0"


def _drop_pieces(tables):
    def inside(a, b):
        return a is not b and a.page == b.page and \
            b.x0 - 2 <= a.x0 and a.x1 <= b.x1 + 2 and \
            b.y - 2 <= a.y and a.y1 <= b.y1 + 2 and \
            (a.x1 - a.x0) * (a.y1 - a.y) < (b.x1 - b.x0) * (b.y1 - b.y)
    return [t for t in tables if not any(inside(t, o) for o in tables)]


# A cell across several columns. The table finder gives the cell at its first
# column and None for the columns it covers, and the text was written into
# the first column alone - on a table drawn with double rules often a 5pt
# sliver, one letter a line (`z3387756` page 5). A None whose column the cell
# to its left does not reach is the row above reaching down; left empty.
SPAN_ON = os.environ.get("QIRTAS_TABLE_SPAN", "1") != "0"


def _unnest(rows, boxes):
    """A cell inside another of its row, holding nothing the outer one does
    not, is the table finder reading the same text twice: blanked, so the
    outer cell spans the columns. -> False if an inner cell has text of its
    own, and the table is left as found."""
    boxes[:] = [list(r) for r in boxes]
    for ri, row in enumerate(boxes):
        for i, a in enumerate(row):
            for j, b in enumerate(row):
                if i == j or a is None or b is None or ri >= len(rows):
                    continue
                if a[0] <= b[0] + 1 and b[2] <= a[2] + 1 and (a[0], a[2]) != (b[0], b[2]):
                    inner = "".join(rows[ri][j].split())
                    if inner and inner not in "".join(rows[ri][i].split()):
                        return False
                    row[j] = None
                    rows[ri][j] = ""
    return True


def _is_grid(boxes):
    """No two cells of a row overlap. A frame drawn round a whole page is
    found as a "table" whose cells lie inside each other (`z20782957` page
    11: 85-548 and 91-548 in one row); read as a grid, a 6pt column got the
    page's text and ran over six pages."""
    for row in boxes:
        cells = [c for c in row if c is not None]
        if any(b[0] < a[2] - 1 for a, b in zip(cells, cells[1:])):
            return False
    return True


def _edges(boxes):
    """Each column's left edge, from any row where it has a cell of its own."""
    n = max((len(r) for r in boxes), default=0)
    edges = [None] * n
    for row in boxes:
        for j, c in enumerate(row):
            if c is not None and edges[j] is None:
                edges[j] = c[0]
    return edges


def _spans(boxes):
    edges = _edges(boxes)
    spans = {}
    for ri, row in enumerate(boxes):
        for ci, c in enumerate(row):
            if c is None:
                continue
            k = 1
            while ci + k < len(row) and row[ci + k] is None                     and edges[ci + k] is not None and c[2] > edges[ci + k] + 1:
                k += 1
            if k > 1:
                spans[(ri, ci)] = k
    return spans


def _grid_widths(boxes, right):
    """Column widths off every row's edges; the first row alone misses a
    column when it holds a cell across two."""
    edges = _edges(boxes)
    if not edges or None in edges:
        return []
    w = [round(b - a, 1) for a, b in zip(edges, edges[1:] + [right])]
    return w if all(x > 1 for x in w) else []


def _col_widths(table):
    """Column widths in points, read off the cell boxes.

    Without them Word splits every column evenly and long cells wrap one word
    per line, turning a compact table into a tall ladder.
    """
    try:
        cells = [c for c in (table.rows[0].cells if table.rows else []) if c]
        w = [round(c[2] - c[0], 1) for c in cells]
        return w if all(x > 1 for x in w) else []
    except Exception:
        return []


VECTOR_MIN = 6           # drawings in a cell before we treat it as a figure
RENDER_DPI = 200


def render_vector_cells(path, tables, outdir):
    """Draw empty-looking table cells that actually contain line art.

    The molecular structures in one paper are not images - they are vector
    drawings, so nothing extracts them and the cells came out blank. Anything
    drawn rather than placed has to be rendered to be carried into Word.

    Only cells with no text of their own are rendered, so this never turns a
    text cell into a picture.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(path) as d:
        for t in tables:
            if not t.cell_boxes or t.page >= len(d):
                continue
            page = d[t.page]
            try:
                drawings = page.get_drawings()
            except Exception:
                continue
            for ri, row in enumerate(t.cell_boxes):
                for ci, box in enumerate(row):
                    if not box or (ri, ci) in t.cell_images:
                        continue
                    text = t.rows[ri][ci] if ri < len(t.rows) and ci < len(t.rows[ri]) else ""
                    if text.strip():
                        continue
                    rect = pymupdf.Rect(*box)
                    if rect.width < 20 or rect.height < 20:
                        continue
                    n = sum(1 for g in drawings if rect.contains(g["rect"]))
                    if n < VECTOR_MIN:
                        continue
                    try:
                        pm = page.get_pixmap(clip=rect, dpi=RENDER_DPI)
                        dest = outdir / f"vec_p{t.page}_{ri}_{ci}.png"
                        pm.save(str(dest))
                        t.cell_images[(ri, ci)] = str(dest)
                    except Exception:
                        continue


def _put_images_in_cells(tables, images):
    """Move a picture into the table cell it sits in.

    Pictures were appended to the foot of the page, so a table of molecular
    structures came out with empty cells and the diagrams stranded below it.

    Returns the pictures that belong to no cell, to be placed as before.
    """
    loose = []
    for img in images:
        placed = False
        cx = (img.x0 + img.x1) / 2.0
        cy = (img.y + img.y1) / 2.0
        for t in tables:
            if t.page != img.page or not t.cell_boxes:
                continue
            for ri, row in enumerate(t.cell_boxes):
                for ci, box in enumerate(row):
                    if not box:
                        continue
                    if box[0] <= cx <= box[2] and box[1] <= cy <= box[3]:
                        t.cell_images[(ri, ci)] = img.image
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break
        if not placed:
            loose.append(img)
    return loose


def _drop_text_inside_tables(doc, tables):
    """Remove paragraphs whose text the table already carries.

    The table's words are also picked up as ordinary text, so without this the
    document says everything twice.

    Where the paragraph has a position, it must also sit inside the table.
    `z21762915`'s header band repeats the article's title and author, and once
    its font was repaired the words matched: the title printed 40pt below the
    band was dropped as the band's copy, and page 1 lost its title.
    """
    if not tables:
        return
    if TABLE_JOINED_ON:
        _rejoin_articles(doc, tables)
    by_page = {}
    for t in tables:
        cells = " ".join(c for row in t.rows for c in row)
        by_page.setdefault(t.page, []).append((WS.sub("", cells), set(cells.split()), t))
    held = {}
    if TABLE_MARK_ON:
        for t in tables:
            cells = _unmarked(" ".join(c for row in t.rows for c in row))
            held.setdefault(t.page, []).append((WS.sub("", cells), set(cells.split()), t))
    keep = []
    for b in doc.blocks:
        if b.kind in (TABLE, IMAGE) or not b.text:
            keep.append(b)
            continue
        flat = WS.sub("", b.text)
        if len(flat) >= 6 and any(flat in joined and _inside(b, t)
                                  for joined, _, t in by_page.get(b.page, [])):
            continue
        if any(_held_by(b, t, words, joined) for joined, words, t in by_page.get(b.page, [])):
            continue
        if any(_held_by(b, t, words, joined, _unmarked(b.text))
               for joined, words, t in held.get(b.page, [])):
            continue
        for joined, words, t in by_page.get(b.page, []):
            _trim_held(b, t, words, joined)
            _trim_header(b, t)
        keep.append(b)
    doc.blocks = keep


LA_WORD = re.compile(r"(?<!\S)لا (\S+)")

# A table's words read again as paragraphs, stored with U+06E1 for spaces
# (`z17931421`: "ۡضابطة 17.600 ...", "تَحَمُّلۡالسرعة"), were not found in
# the table's cells word for word, and its widest table was written a second
# time under itself in small type. U+06E1 is also a Quranic sukun, so the
# text keeps it; only the comparison with the table reads it as a space,
# and without vowel marks, on both sides (QIRTAS_TABLE_MARK).
TABLE_MARK_ON = os.environ.get("QIRTAS_TABLE_MARK", "1") != "0"


def _unmarked(t):
    return MARKS.sub("", t.replace("ۡ", " "))


def _rejoin_articles(doc, tables):
    """A cell's word broken after its article (`ال` / `مطلوب`) comes back as
    `لا مطلوب`: alone at a line's end, `ال` reads as a lam-alef stored
    backwards. The page's paragraphs read the same words whole; where they
    have `المطلوب` and never `مطلوب`, so does the cell."""
    seen = {}
    for b in doc.blocks:
        if b.text and b.kind not in (TABLE, IMAGE):
            seen.setdefault(b.page, set()).update(b.text.split())
    for t in tables:
        words = seen.get(t.page, set())

        def fix(m):
            w = m.group(1)
            return "ال" + w if "ال" + w in words and w not in words else m.group(0)
        t.rows = [[LA_WORD.sub(fix, c) for c in row] for row in t.rows]


def _has(w, words, joined):
    # Whole words only. Matching inside the table's text with the spaces out
    # took `المجموعةۡالضابطة` as held by a cell reading `المجموعةۡالضابطةۡم`,
    # dropped the only copy as printed, and the gate lost 2.1% of
    # `z17931421` (full run, 2026-09-27). The broken word it was for
    # (`ال` / `مطلوب`) is joined back by `_rejoin_articles` instead.
    return w in words


def _trim_held(b, table, words, joined):
    """A paragraph that starts in the table's last row and runs on below it:
    the row's words lead the text below (`ممتازة ... المصدر :`). The leading
    words the table holds go; the rest stays."""
    if not TABLE_JOINED_ON or not b.y1 or not table.y1:
        return
    if not (table.y < b.y < table.y1 < b.y1) or not (table.x0 - 2 <= b.x0 and b.x1 <= table.x1 + 2):
        return
    mine = b.text.split()
    n = 0
    while n < len(mine) and _has(mine[n], words, joined):
        n += 1
    if not 2 <= n < len(mine):
        return
    # Cut by letters, not characters: the formatting runs need not carry the
    # same spaces as the text.
    need = sum(len(w) for w in mine[:n])
    b.text = _after_letters(b.text, need)
    if b.spans:
        spans = []
        for t, *rest in b.spans:
            have = len("".join(t.split()))
            if need >= have:
                need -= have
                continue
            spans.append((_after_letters(t, need) if need else t, *rest))
            need = 0
        b.spans = spans


def _trim_header(b, table):
    """A caption read together with the table's header row below it: the
    row's words end the caption (`... الانحدارية درجة خارجية المتغير علاقة
    السببية`). Trailing words the first row holds go."""
    if not TABLE_JOINED_ON or not b.y1 or not table.y1 or not table.rows:
        return
    if not (b.y < table.y < b.y1 < table.y1):
        return
    head = " ".join(table.rows[0])
    words, joined = set(head.split()), WS.sub("", head)
    mine = b.text.split()
    n = 0
    while n < len(mine) and _has(mine[-1 - n], words, joined):
        n += 1
    if not 2 <= n < len(mine):
        return
    keep = sum(len(w) for w in mine[:-n])
    b.text = _before_letters(b.text, keep)
    if b.spans:
        spans = []
        for t, *rest in b.spans:
            if keep <= 0:
                break
            have = len("".join(t.split()))
            spans.append((t if have <= keep else _before_letters(t, keep), *rest))
            keep -= have
        b.spans = spans


def _before_letters(text, n):
    """The text up to its first n non-space characters, trailing space gone."""
    for i, c in enumerate(text):
        if not c.isspace():
            if n <= 0:
                return text[:i].rstrip()
            n -= 1
    return text.rstrip()


def _after_letters(text, n):
    """The text after its first n non-space characters, leading space gone."""
    for i, c in enumerate(text):
        if n <= 0:
            return text[i:].lstrip()
        if not c.isspace():
            n -= 1
    return ""


# A table drawn with double rules is found with a column in the gap between
# each pair: 5pt wide, empty in every row. 29 of 79 tables on the dev theses
# had them - `z17804101`'s 7-column questionnaire came out with 19, a ladder
# one word wide (Part 3, 2026-09-27).
THIN_ON = os.environ.get("QIRTAS_TABLE_THIN", "1") != "0"
THIN_PT = 8.0


# A table cell's shading. 273 shaded cells on 10 of the 25 dev theses -
# banded rows, a coloured header row - all came out white. The colour is the
# fill drawn under most of the cell, the last one drawn where several are.
# A dark fill is left out: it carries white text, which we write black.
TABLE_FILL_ON = os.environ.get("QIRTAS_TABLE_FILL", "1") != "0"
FILL_COVER = 0.6        # share of the cell the fill must cover
FILL_DARK = 0.45        # lightness below which a fill is not copied


def _fill_hex(fill):
    if not fill or len(fill) < 3:
        return None
    r, g, b = fill[:3]
    if min(r, g, b) >= 0.97:
        return ""            # white: drawn over a shading, it clears it
    if 0.299 * r + 0.587 * g + 0.114 * b < FILL_DARK:
        return None
    return "%02X%02X%02X" % tuple(round(c * 255) for c in (r, g, b))


# A band behind ordinary text - a boxed dedication (`z14065750`), a table of
# one column the finder does not see, with coloured heading rows
# (`z20782957`), a running header white on black (`z7456037`). 48 such bands
# on 5 dev theses, all written as plain text. The paragraph takes the band's
# colour, and on a dark band its text keeps its own light colour - black on
# black would hide it.
BAND_ON = os.environ.get("QIRTAS_BAND", "1") != "0"
THIN_RULE = 1.5          # points: a strip this thin is a line, not a band


def _band_fills(path, doc, tables):
    by_page = {}
    for b in doc.blocks:
        if b.kind in (PARAGRAPH, HEADING, LIST_ITEM) and b.y1 > b.y and b.x1 > b.x0:
            by_page.setdefault(b.page, []).append(b)
    with pymupdf.open(path) as d:
        for i, blocks in by_page.items():
            if i >= len(d):
                continue
            page = d[i]
            whole = page.rect.get_area()
            fills = [g for g in page.get_drawings() if g.get("fill")
                     and g["rect"].get_area() < whole * 0.5
                     and min(g["fill"][:3]) < 0.97]
            if not fills:
                continue
            held = [pymupdf.Rect(t.x0, t.y, t.x1, t.y1) for t in tables if t.page == i]
            spans = None
            for b in blocks:
                box = pymupdf.Rect(b.x0, b.y, b.x1, b.y1)
                if any(box.intersects(t) for t in held):
                    continue
                area = box.get_area()
                # Word shades a paragraph a line at a time - one strip per
                # line - so strips of one colour are added up.
                cover, last = collections.Counter(), {}
                for n, g in enumerate(fills):
                    r = pymupdf.Rect(g["rect"])
                    if r.width <= THIN_RULE or r.height <= THIN_RULE:
                        continue
                    key = tuple(round(c, 2) for c in g["fill"][:3])
                    cover[key] += (r & box).get_area()
                    if (r & box).get_area():
                        last[key] = n
                full = [k for k, a in cover.items() if a >= area * FILL_COVER]
                if not full:
                    continue
                got = fills[max(last[k] for k in full)]
                r, gg, bb = got["fill"][:3]
                b.fill = "%02X%02X%02X" % tuple(round(c * 255) for c in (r, gg, bb))
                # An outline: drawn as a stroke, or - Word's way - as hairline
                # strips down both sides of the text.
                key = tuple(round(c, 2) for c in got["fill"][:3])
                band = pymupdf.Rect(box)
                for g in fills:
                    r = pymupdf.Rect(g["rect"])
                    if tuple(round(c, 2) for c in g["fill"][:3]) == key \
                            and r.intersects(box):
                        band |= r
                wide = band + (-3, -1, 3, 1)
                sides = [pymupdf.Rect(g["rect"]) for g in fills
                         if pymupdf.Rect(g["rect"]).width <= THIN_RULE
                         and pymupdf.Rect(g["rect"]).intersects(wide)]
                b.boxed = ("s" in got.get("type", "") and bool(got.get("color"))) \
                    or (any(s.x0 < band.x0 + 2 for s in sides)
                        and any(s.x1 > band.x1 - 2 for s in sides))
                if spans is None:
                    spans = [s for x in page.get_text("dict")["blocks"]
                             for l in x.get("lines", []) for s in l["spans"]
                             if s["text"].strip()]
                ink = collections.Counter()
                for s in spans:
                    if box.contains(pymupdf.Point((s["bbox"][0] + s["bbox"][2]) / 2,
                                                  (s["bbox"][1] + s["bbox"][3]) / 2)):
                        ink[s["color"]] += len(s["text"])
                if ink:
                    c = ink.most_common(1)[0][0]
                    if c != 0:
                        b.ink = "%06X" % c


# A line ruled under the running header - single, coloured, thin over thick,
# or double lines above and below a header band - on 7 of the 25 dev theses,
# dropped every time. Found as the same pattern of wide thin horizontal
# lines near the top of at least half the pages; a page framed all round is
# left alone (its top edge is the frame, `z3387756`).
HEADER_RULE_ON = os.environ.get("QIRTAS_HEADER_RULE", "1") != "0"
RULE_TOP = 0.15          # share of the page height the rules sit within
RULE_WIDE = 0.4          # share of the page width a rule spans
RULE_PAIR = 6.0          # points: two lines this close are one double rule
RULE_THICK = 4.5        # points: anything thicker is a band, not a line


def _page_rules(page):
    """[(y, thickness, colour)] of this page's header rules, top down."""
    H, W = page.rect.height, page.rect.width
    rules, tall = [], False
    for g in page.get_drawings():
        r = pymupdf.Rect(g["rect"])
        if r.height > H * 0.5 and r.width < 3:
            tall = True
        if r.width < W * RULE_WIDE or r.height >= RULE_THICK or not (0.02 * H < r.y0 < RULE_TOP * H):
            continue
        if g.get("fill") and "s" not in g["type"]:
            thick, colour = max(r.height, 0.25), g["fill"]
        elif g.get("color"):
            thick, colour = max(g.get("width") or 0.75, 0.25), g["color"]
        else:
            continue
        rules.append((round((r.y0 + r.y1) / 2, 1), round(thick, 2),
                      "%02X%02X%02X" % tuple(round(c * 255) for c in colour[:3])))
    if tall:
        return []
    # A hairline drawn twice, or a fill and its outline, is one line.
    out = []
    for r in sorted(rules):
        if out and abs(r[0] - out[-1][0]) < 0.6:
            continue
        out.append(r)
    return out


def _rule_style(group):
    """Word's border for one group of lines: (style, eighths of a point)."""
    if len(group) == 1:
        return "single", group[0][1]
    a, b = group[0][1], group[-1][1]
    if abs(a - b) < 0.3:
        return "double", a
    return ("thinThickSmallGap" if a < b else "thickThinSmallGap"), max(a, b)


def _header_rule(path, doc):
    with pymupdf.open(path) as d:
        pages = [_page_rules(p) for p in d]
    seen = collections.Counter()
    for rules in pages:
        if rules:
            seen[tuple((round(y), t, c) for y, t, c in rules)] += 1
    if not seen:
        return
    shape, n = seen.most_common(1)[0]
    # Lines at the same heights on half the pages: the header's own.
    if n < max(2, len(pages) // 2):
        near = sum(1 for rules in pages if rules and len(rules) == len(shape) and all(
            abs(r[0] - s[0]) <= 3 for r, s in zip(rules, shape)))
        if near < max(2, len(pages) // 2):
            return
    groups = []
    for y, t, c in shape:
        if groups and y - groups[-1][-1][0] <= RULE_PAIR:
            groups[-1].append((y, t, c))
        else:
            groups.append([(y, t, c)])
    sides = [("bottom", groups[-1])] if len(groups) == 1 else \
        [("top", groups[0]), ("bottom", groups[-1])]
    out = []
    for side, g in sides:
        style, thick = _rule_style(g)
        eighths = max(2, min(96, round(thick * 8)))
        out.append((side, style, eighths, g[0][2]))
    doc.header_rules = out


# The footnotes as the original sets them. Word's own line above them is 2
# inches long and starts where a left-to-right paragraph does, so ours sat at
# the left where most theses have it at the right (`z18037898`, `z21850164`);
# some draw it longer (288pt on `z18037898`), and one on the left
# (`z14065750`). And the notes took Word's ordinary line height, which in
# Traditional Arabic is far taller than the original's (`z18037898`: 15.6pt
# apart, ours near 21). Both measured: the line on each page with notes -
# the one just above its first note, the page's full-width one being Word's
# line for a note carried over - and the distance between the notes' lines.
NOTE_LOOK_ON = os.environ.get("QIRTAS_NOTE_LOOK", "1") != "0"
NOTE_RULE_NEAR = 4.0     # of the note size: how far above the notes the line sits


def _note_look(path, doc):
    import statistics
    width = doc.page_width - doc.margin_left - doc.margin_right
    rules, pitches = collections.Counter(), []
    with pymupdf.open(path) as d:
        for pno, page in enumerate(d):
            notes = [b for b in doc.blocks if b.kind == FOOTNOTE
                     and b.page == pno and b.y1 > b.y > 0]
            if not notes:
                continue
            top = min(b.y for b in notes)
            size = statistics.median(b.size or doc.body_size for b in notes)
            for g in page.get_drawings():
                r = pymupdf.Rect(g["rect"])
                if r.height >= 2.5 or r.width < 20 or r.width > 0.9 * width \
                        or not top - NOTE_RULE_NEAR * size < r.y0 < top + 2:
                    continue
                if g.get("fill") and "s" not in g["type"]:
                    thick, colour = max(r.height, 0.25), g["fill"]
                elif g.get("color"):
                    thick, colour = max(g.get("width") or 0.75, 0.25), g["color"]
                else:
                    continue
                mid = (doc.margin_left + doc.page_width - doc.margin_right) / 2
                side = "right" if (r.x0 + r.x1) / 2 > mid else "left"
                rules[(round(r.width), side, max(2, min(12, round(thick * 8))),
                       "%02X%02X%02X" % tuple(round(c * 255) for c in colour[:3]))] += 1
                break
            lines = set()
            for bl in page.get_text("dict")["blocks"]:
                for ln in bl.get("lines", []):
                    cy = (ln["bbox"][1] + ln["bbox"][3]) / 2
                    if ln["spans"] and any(b.y - 1 <= cy <= b.y1 + 1 for b in notes):
                        lines.add(round(ln["spans"][0]["origin"][1], 1))
            lines = sorted(lines)
            pitches += [b - a for a, b in zip(lines, lines[1:])
                        if 0.8 * size < b - a < 2.5 * size]
    if rules:
        doc.note_rule = rules.most_common(1)[0][0]
    if len(pitches) >= 5:
        doc.note_pitch = round(statistics.median(pitches), 1)


# A header in two parts at the page's two edges - the chapter at one, its
# title at the other (`z22643426`, `z7456037`, `z20585114`). The author put
# them apart with spaces or a tab, which cleaning makes one space, and the
# line came out as one centred sentence - on `z22643426` with its parts the
# wrong way round. The parts are found by position; each is matched to the
# block's own words by its letters, which survives the hidden text spelling
# them garbled (`ملتغريات` for لمتغيرات). Nothing is taken from the page:
# the parts are the block's words, cut and put in order.
PARTS_ON = os.environ.get("QIRTAS_HEADER_PARTS", "1") != "0"
PART_GAP = 30.0         # points of empty line between two parts
EDGE_ZONE = 0.15        # share of the page height at top and bottom


def _letters(s):
    return collections.Counter(ch for ch in s if not ch.isspace())


def _parts_of(words, clusters):
    """Cut `words` into len(clusters) runs matching the clusters' letters,
    in any order. -> the runs in cluster order, or None."""
    k = len(clusters)
    want = [_letters(c) for c in clusters]
    total = sum(sum(w.values()) for w in want) or 1
    best, cut = None, None
    import itertools
    for cuts in itertools.combinations(range(1, len(words)), k - 1):
        runs = [" ".join(words[a:b]) for a, b in
                zip((0,) + cuts, cuts + (len(words),))]
        have = [_letters(r) for r in runs]
        for order in itertools.permutations(range(k)):
            miss = sum(sum(((have[i] - want[j]) + (want[j] - have[i])).values())
                       for i, j in zip(range(k), order))
            if best is None or miss < best:
                best, cut = miss, (runs, order)
    if cut is None or best > 0.2 * total:
        return None
    runs, order = cut
    out = [None] * k
    for i, j in zip(range(k), order):
        out[j] = runs[i]
    return out


def _header_parts(path, doc):
    with pymupdf.open(path) as d:
        pages = {}
        for b in doc.blocks:
            if b.kind not in (PARAGRAPH, HEADING) or not (b.x1 > b.x0 and b.y1 > b.y):
                continue
            if b.page >= len(d) or b.y1 - b.y > 2.2 * (b.size or 12):
                continue
            H = d[b.page].rect.height
            if not (b.y1 < EDGE_ZONE * H or b.y > (1 - EDGE_ZONE) * H):
                continue
            if b.page not in pages:
                pages[b.page] = d[b.page].get_text("words")
            box = pymupdf.Rect(b.x0 - 1, b.y - 1, b.x1 + 1, b.y1 + 1)
            ws = sorted((w for w in pages[b.page]
                         if box.contains(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))),
                        key=lambda w: w[0])
            clusters = []
            for w in ws:
                if clusters and w[0] - clusters[-1][-1][2] < PART_GAP:
                    clusters[-1].append(w)
                else:
                    clusters.append([w])
            words = b.text.split()
            if not 2 <= len(clusters) <= 3 or len(words) < len(clusters):
                continue
            # right to left, as the page is read
            texts = ["".join(w[4] for w in c) for c in reversed(clusters)]
            got = _parts_of(words, texts) if len(words) <= 40 else None
            if got and all(got):
                b.parts = got


def _cell_fills(path, tables):
    by_page = {}
    for t in tables:
        by_page.setdefault(t.page, []).append(t)
    with pymupdf.open(path) as d:
        for i, ts in by_page.items():
            page = d[i]
            whole = page.rect.get_area()
            fills = [(pymupdf.Rect(g["rect"]), g["fill"]) for g in page.get_drawings()
                     if g.get("fill") and g["rect"].get_area() < whole * 0.5]
            if not fills:
                continue
            for t in ts:
                out = {}
                for ri, row in enumerate(t.cell_boxes or []):
                    for ci, box in enumerate(row):
                        if box is None:
                            continue
                        c = pymupdf.Rect(box)
                        area = c.get_area()
                        if not area:
                            continue
                        colour = None
                        for r, fill in fills:
                            if (r & c).get_area() >= area * FILL_COVER:
                                got = _fill_hex(fill)
                                if got is not None:
                                    colour = got
                        if colour:
                            out[(ri, ci)] = colour
                t.cell_fills = out


def _drop_thin_columns(t):
    """Take out columns narrower than THIN_PT that hold nothing in any row;
    their width goes to the column beside them."""
    if not THIN_ON or not t.col_widths:
        return
    n = len(t.col_widths)
    if any(len(r) != n for r in t.rows):
        return
    spans = t.cell_spans or {}

    def held(r, i):
        # Text a thin column holds only as the start of a cell across wider
        # ones moves along with that cell; it does not keep the column. Nor
        # does a copy of the cell beside it, which a 5pt clip can catch
        # (`z21145041` page 5, written a letter a line).
        row = t.rows[r]
        text = row[i].strip()
        twin = any(0 <= j < n and row[j].strip() == text for j in (i - 1, i + 1))
        return text and spans.get((r, i), 1) == 1 and not twin
    gone = [i for i, w in enumerate(t.col_widths)
            if w < THIN_PT and not any(held(r, i) for r in range(len(t.rows)))
            and not any(c == i for _, c in t.cell_images)]
    # A cell across only dropped columns would have nowhere to go.
    gone = [i for i in gone if not any(
        c <= i < c + k and all(j in gone for j in range(c, c + k))
        for (r, c), k in spans.items())]
    if not gone or len(gone) == n:
        return
    widths = list(t.col_widths)
    for i in gone:
        near = next((j for j in list(range(i + 1, n)) + list(range(i - 1, -1, -1))
                     if j not in gone), None)
        if near is not None:
            widths[near] += widths[i]
    keep = [i for i in range(n) if i not in gone]
    at = {old: new for new, old in enumerate(keep)}
    t.col_widths = [widths[i] for i in keep]
    old_rows = t.rows
    t.rows = [[r[i] for i in keep] for r in t.rows]
    t.cell_boxes = [[row[i] for i in keep] if len(row) == n else row
                    for row in (t.cell_boxes or [])]
    t.cell_images = {(r, at[c]): p for (r, c), p in t.cell_images.items()}
    moved, fills = {}, {}
    for (r, c), k in spans.items():
        kept = [at[j] for j in range(c, c + k) if j in at]
        if c not in at:        # its column went; the text goes to the next kept
            t.rows[r][kept[0]] = old_rows[r][c]
        if (r, c) in t.cell_fills:      # and its shading with it
            fills[(r, kept[0])] = t.cell_fills[(r, c)]
        if len(kept) > 1:
            moved[(r, kept[0])] = len(kept)
    t.cell_spans = moved
    for (r, c), v in t.cell_fills.items():
        if c in at:
            fills.setdefault((r, at[c]), v)
    t.cell_fills = fills


# A paragraph inside a table whose words the table holds, every one of them.
# The exact-text test misses a cell the table read in pieces - a heading cell
# of two lines split over two rows - and the table's text was written twice:
# about 3,100 words on the dev theses (Part 3, 2026-09-27). Every word must be
# there, so nothing the table lacks is dropped.
TABLE_WORDS_ON = os.environ.get("QIRTAS_TABLE_WORDS", "1") != "0"


TABLE_JOINED_ON = os.environ.get("QIRTAS_TABLE_JOINED", "1") != "0"


def _held_by(b, table, words, joined="", text=None):
    if not TABLE_WORDS_ON or not b.y1 or not table.y1:
        return False
    mx, my = (b.x0 + b.x1) / 2, (b.y + b.y1) / 2
    if not (table.x0 - 2 <= mx <= table.x1 + 2 and table.y - 2 <= my <= table.y1 + 2):
        return False
    mine = (b.text if text is None else text).split()
    if text is None:
        return bool(mine) and all(_has(w, words, joined) for w in mine)
    # Compared without the marks (`_unmarked`): a word of four letters or
    # more is also held where the table's letters have it with the spaces
    # out - the clip breaks words the page draws in pieces (`المع ا لم` for
    # المعالم, `z3387756` page 12), and every row came again as loose lines.
    # Whole words only was set after this matched `المجموعةۡالضابطة` inside a
    # cell's `المجموعةۡالضابطةۡم` and the gate lost the text: the ۡ was the
    # file's space, now read as one (glyphs.diagnose).
    return bool(mine) and all(w in words or (len(w) >= 4 and w in joined)
                              for w in mine)


def _inside(b, table):
    """Does this paragraph sit within the table's height? Unknown counts as yes:
    the tags route carries no positions, and there text is all there is."""
    if not (b.y or b.y1) or not (table.y or table.y1):
        return True
    mid = (b.y + b.y1) / 2
    return table.y - 2 <= mid <= table.y1 + 2


def read(path, image_dir=None):
    """Run both, keep whichever recovered more Arabic."""
    results = []
    for fn in (read_tags, read_labels, read_geometry):
        try:
            d = fn(path)
            results.append((_recovered(d), d))
        except Exception:
            continue
    if not results:
        raise RuntimeError("no reader succeeded")

    # Prefer the labels when they recover essentially as much text. One file
    # picked geometry by 0.6% and lost every footnote and list item with it -
    # a rounding-error win on quantity, a real loss on structure. The theses'
    # /ActualText first, then labels over glyphs, then geometry.
    top = max(r[0] for r in results)
    best = None
    for route in ("tags", "labels"):
        got = [r for r in results if r[1].source_route == route]
        if got and got[0][0] >= top * TIE_MARGIN:
            best = got[0][1]
            break
    if best is None:
        best = max(results, key=lambda r: r[0])[1]
    tables = []
    try:
        tables = read_tables(path)
    except Exception:
        tables = []
    # Before the thin columns go: a cell of a table drawn with double rules
    # can start in a 5pt sliver, and its box goes with the sliver.
    if tables and TABLE_FILL_ON:
        try:
            _cell_fills(path, tables)
        except Exception:
            pass
    for t in tables:
        _drop_thin_columns(t)
    pictures = []
    if image_dir:
        try:
            pictures = read_images(path, image_dir)
        except Exception:
            pictures = []
    if BAND_ON and best.source_route != "tags":
        try:
            _band_fills(path, best, tables)
        except Exception:
            pass
    if tables and CELLS_TURN_ON:
        _turn_cells(tables, best)
    if tables:
        _drop_text_inside_tables(best, tables)
        pictures = _put_images_in_cells(tables, pictures)
        if image_dir:
            try:
                render_vector_cells(path, tables, image_dir)
            except Exception:
                pass
        for t in tables:
            best.add(t)
    # The first page photographed whole only if the reader found almost no
    # real text on it: picture descriptions and a page number do not count,
    # and a few title lines are allowed. `مقدمة البحث` has two - "بـحث مقدم
    # لنيل درجة العالمية" and "بعنوان" - as real text among 26 pictures, and
    # those two lines become part of the photo, no longer editable. Traded for
    # the other 15 pages landing on the right page; FLAGS.md 21.
    real = sum(len(b.text.split()) for b in best.blocks
               if b.page == 0 and b.kind != IMAGE and not b.from_alt
               and NUMBERS_AND_SPACE.sub("", b.text))
    if image_dir and real <= COLLAGE_MAX_WORDS:
        whole = _collage(path, pictures, image_dir)
        if whole:
            rest = [b for b in pictures if b.page != 0]
            # Keep the title page's copies of a decoration that repeats on
            # most pages. They are lifted into Word's header, never placed on
            # the page, and they are often the only clean photo of it: every
            # other copy of `الفصل الثاني`'s header catches a sliver of the
            # body text beneath it. Dropped with the rest of page 1, they left
            # nothing clean to draw.
            on = {}
            for b in rest:
                on.setdefault(b.origin, set()).add(b.page)
            need = max(2, best.pages // 2)
            keep = [b for b in pictures if b.page == 0 and b.origin
                    and len(on.get(b.origin, ())) >= need]
            pictures = rest + keep + [whole]
    # After the title page has become one photo, so the copies compared are
    # the copies that will actually be drawn from.
    _mark_edge_ink(pictures)
    for b in pictures:
        best.add(b)
    if any(b.collage for b in pictures):
        _drop_collage_captions(best, path)
    # One pass over the finished model, like writer._clean does for characters
    # XML cannot hold. Every route's text goes through here, whether it came
    # from glyphs or from /ActualText, so the tag route gets the same repairs
    # the geometry route does - and so does the checker, from the same map.
    # Applying it to one route only is what broke the gate the first time; see
    # convert/pdftext.py.
    fixes = {}
    try:
        fixes = fix_map(path)
    except Exception:
        fixes = {}
    # The spelling repair is NOT run again here. It is not safe twice: on
    # z20276145, which stretches words with alefs, each pass moves an alef
    # one place further, and a second pass cost that file 21% of the gate.
    # The checker (`compare.text_of`) runs the same two steps in this order:
    # spelling as read, then the map.
    if fixes:
        def fix(t):
            return apply_fixes(t, fixes)
        for b in best.blocks:
            b.text = fix(b.text)
            if b.spans:
                b.spans = [(fix(t), *rest) for t, *rest in b.spans]
            if b.rows:
                b.rows = [[fix(c) for c in row] for row in b.rows]

    best = _backfill(best, results, path,
                     (lambda t: apply_fixes(t, fixes)) if fixes else None)
    _page_numbers(best, path)
    best = detect_headings(best)
    # Word's labels already say which paragraphs are list items. Guessing on
    # top of them is how geometry turned a third of prose into lists.
    if best.source_route != "labels":
        best = detect_lists(best)
    if best.source_route == "tags":
        for b in best.blocks:
            if b.kind != TABLE:
                _fit_spans(b)
    measure_layout(path, best)
    if HEADER_RULE_ON:
        try:
            _header_rule(path, best)
        except Exception:
            pass
    if PARTS_ON:
        try:
            _header_parts(path, best)
        except Exception:
            pass
    with pymupdf.open(path) as d:
        r = d[0].rect
        best.page_width, best.page_height = r.width, r.height
    if NOTE_LOOK_ON:
        try:
            _note_look(path, best)
        except Exception:
            pass
    return best
