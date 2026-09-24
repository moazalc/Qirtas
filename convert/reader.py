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
import os
import re
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


def _clean(s):
    # Every route's text passes through here, which makes it the one place the
    # lam-alef repair has to go - see convert/arabic.py.
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
    added = False
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
            if len(ws) >= 3 and sum(1 for w in ws if w in words or w[::-1] in words) \
                    >= TURNED_AT * len(ws):
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
    if not isinstance(node, pikepdf.Dictionary):
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
        _walk(node.get("/K"), doc, pages, inner, depth + 1,
              kind if kind in (FOOTNOTE,) else ctx, state)
        doc.add(Block(kind=kind, text=_clean(text + "".join(inner)), page=pg,
                      from_alt=not text and _all_alt(inner)))
        return

    ref = node.get("/Pg")
    if ref is not None:
        state["page"] = pages.get(ref.objgen, state["page"])
    actual = node.get("/ActualText")
    if actual is not None:
        pending.append(str(actual))
    elif node.get("/Alt") is not None:
        pending.append(_Alt(str(node.get("/Alt"))))
    elif "signs" in state:
        pending.extend(state["signs"](state["page"], _mcids(node.get("/K"))))
    kids = node.get("/K")
    if kids is not None:
        _walk(kids, doc, pages, pending, depth + 1, ctx, state)


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


class _Alt(str):
    """Text that came from a picture's /Alt description, not from the page."""


def _all_alt(parts):
    parts = [p for p in parts if p.strip()]
    return bool(parts) and all(isinstance(p, _Alt) for p in parts)


def _flush(doc, pending, page=0):
    """Loose text kept defaulting to page 0, piling a whole document onto the
    first page and leaving later pages empty. Carry the current page."""
    if pending:
        doc.add(Block(kind=PARAGRAPH, text=_clean("".join(pending)), page=page,
                      from_alt=_all_alt(pending)))
        pending.clear()


def read_tags(path):
    doc = Doc(source_route="tags")
    with pikepdf.open(path) as pdf:
        if "/StructTreeRoot" not in pdf.Root:
            raise RuntimeError("not tagged")
        pages = _page_index(pdf)
        doc.pages = len(pdf.pages)
        pending, state = [], {"page": 0, "signs": _sign_reader(pdf)}
        _walk(pdf.Root["/StructTreeRoot"].get("/K"), doc, pages, pending, state=state)
        _flush(doc, pending, state["page"])
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


def _rich_block(text_blocks, i, kind=PARAGRAPH, vocab=None):
    """One Block from one or more PyMuPDF text blocks, with size, boldness and
    runs of like formatting. None if they hold no text.

    `vocab` (vocabulary()), or (vocab, _letter_ends()): a word cut between
    two pieces is put back together - see _glued. Without it every piece is
    joined with a space."""
    vocab, ends = vocab if isinstance(vocab, tuple) else (vocab, None)
    text, size, bold, spans = "", 0.0, False, []
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
                it = bool(sp["flags"] & ITALIC_FLAG)
                bo = bool(sp["flags"] & BOLD_FLAG)
                bold = bold or bo
                # Merge with the previous span when it reads the same. A line
                # often arrives as a dozen spans of identical formatting, and
                # one Word run each would bloat the file for no effect. A word
                # put back together stays in one run whatever its formatting:
                # the writer puts a space between runs.
                if spans and (glue or (spans[-1][1] == bo and spans[-1][2] == it)):
                    spans[-1] = (spans[-1][0] + ("" if glue else " ") + run,
                                 spans[-1][1], spans[-1][2])
                else:
                    spans.append((run, bo, it))
    if not spans:
        return None
    boxes = [b["bbox"] for b in text_blocks]
    return Block(kind=kind, text=_clean(text),
                 page=i, size=round(size, 1), bold=bold,
                 spans=[(_clean(t), b_, i_) for t, b_, i_ in spans],
                 y=round(min(r[1] for r in boxes), 1),
                 y1=round(max(r[3] for r in boxes), 1),
                 x0=round(min(r[0] for r in boxes), 1),
                 x1=round(max(r[2] for r in boxes), 1))


def _page_rich(page, i, vocab=None):
    out = []
    for b in sorted(get_text(page, "dict")["blocks"], key=lambda b: (round(b["bbox"][1]), b["bbox"][0])):
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
        for a, z in zip([0] + cuts, cuts + [len(b.text)]):
            piece = b.text[a:z].strip()
            if piece:
                nb = Block(kind=FOOTNOTE, text=piece, page=b.page, size=b.size,
                           y=b.y, y1=b.y1, x0=b.x0, x1=b.x1,
                           spans=[(piece, False, False)])
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
    parts = MARKED.split(_joined(blk.text))
    out = []
    head = parts[0].strip()
    if head:                                  # the tail of an earlier note
        out.append(head)
    for num, text in zip(parts[1::2], parts[2::2]):
        out.append(f"({num}) {text.strip()}")
    blocks = []
    for t in out:
        b = Block(kind=FOOTNOTE, text=MARKED.sub(r"(\1)", t), page=blk.page,
                  size=blk.size, y=blk.y, y1=blk.y1, x0=blk.x0, x1=blk.x1)
        b.spans = [(b.text, False, False)]
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
        return _unreverse(_clean(fallback or ""), page_flat)
    try:
        clip = get_text(page, "text", clip=pymupdf.Rect(box))
    except Exception:
        return _unreverse(_clean(fallback or ""), page_flat)
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
        if not all(_probe(x) in page_flat for x in lines):
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
            for t in found:
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
                blocks.append(Block(kind=TABLE, text="", page=i, rows=rows,
                                    col_widths=widths, cell_boxes=boxes,
                                    x0=r[0], y=r[1], x1=r[2], y1=r[3]))
    return blocks


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
    by_page = {}
    for t in tables:
        joined = WS.sub("", " ".join(c for row in t.rows for c in row))
        by_page.setdefault(t.page, []).append((joined, t))
    keep = []
    for b in doc.blocks:
        if b.kind in (TABLE, IMAGE) or not b.text:
            keep.append(b)
            continue
        flat = WS.sub("", b.text)
        if len(flat) >= 6 and any(flat in joined and _inside(b, t)
                                  for joined, t in by_page.get(b.page, [])):
            continue
        keep.append(b)
    doc.blocks = keep


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
    pictures = []
    if image_dir:
        try:
            pictures = read_images(path, image_dir)
        except Exception:
            pictures = []
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
    measure_layout(path, best)
    with pymupdf.open(path) as d:
        r = d[0].rect
        best.page_width, best.page_height = r.width, r.height
    return best
