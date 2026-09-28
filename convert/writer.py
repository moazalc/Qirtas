"""The writer: turn the description into a Word file.

The only part that knows about Word. Everything right-to-left lives here -
paragraph direction, run direction, and the complex-script font - the three
things every other tool we tested forgets.
"""
import copy
import hashlib
import itertools
import os
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH as _AL

from convert.glyphs import spell_out
from convert.model import Doc, HEADING, FOOTNOTE, LIST_ITEM, IMAGE, TABLE, PARAGRAPH
from convert.footnotes import (MARKER as FN_MARKER, NUMBER as FN_NUMBER, FIRST_ID, split_number,
                               marker_numbers, RAISED, WESTERN,
                               build_xml, install, directional)

PT_PER_EMU = 12700
RTL_CHARS = re.compile(r"[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]")
LTR_CHARS = re.compile(r"[A-Za-z\u00C0-\u024F\u0370-\u04FF]")


def is_rtl(text):
    """Does this text actually read right-to-left?

    Everything used to be forced right-to-left, which mirrored English tables
    and flipped Latin paragraphs that were never right-to-left to begin with.
    Direction is a property of the content, not of the document.
    """
    t = text or ""
    r, l = len(RTL_CHARS.findall(t)), len(LTR_CHARS.findall(t))
    return r > 0 and r >= l
ARABIC_FONT = "Arial"
BODY_PT = 12
FIT = 0.95              # small safety margin: a slight overflow turns every page into two
FOOTNOTE_PT = 9
# Fewer notes than this at the end of a document are not treated as endnotes.
ENDNOTES_MIN = 3
# What may be left on a page emptied of its endnotes for it still to go.
ENDNOTE_PAGE_SCRAP = 60
# How much of a page a stack of pictures may claim. Measured, not chosen: at
# 0.95 a picture-only title page still needed two pages, at 0.88 it fitted, and
# below that nothing more was gained. 0.85 leaves room for the paragraph each
# picture sits in and for a header taller than the top margin.
#
# This has to be right first time. fit.py cannot rescue it: _spilled() matches
# rendered pages to original ones by shared words, and a page of nothing but
# pictures has none - when it spills, the extra wordless page is blamed on the
# page before it.
IMAGE_PAGE_FILL = 0.85
HEADING_PT = {1: 16, 2: 14}


def _xml_safe(text):
    """Drop characters XML 1.0 has no way to represent.

    lxml enforces the Char production, which allows only tab, newline and
    carriage return out of the C0 controls. A PDF text layer can carry the
    others - stray NULs and backspaces both turn up in the wild corpus - and
    python-docx passes run text through untouched, so a single one of them
    anywhere in a document raises ValueError and costs the entire conversion.

    Dropping is right rather than substituting: these characters are extraction
    debris with no glyph, so there is nothing to stand in for. Surrogates go too
    (lone ones cannot be encoded at all), and so do U+FFFE/U+FFFF.
    """
    if not text:
        return text
    return "".join(c for c in text if
                   c in "\t\n\r"
                   or 0x20 <= ord(c) <= 0xD7FF
                   or 0xE000 <= ord(c) <= 0xFFFD
                   or ord(c) >= 0x10000)


def _scrub(model: Doc):
    """Make every string in the model legal XML, in place.

    Done once here rather than at each add_run: text reaches the document by
    three separate routes (body runs, table cells, and footnotes.py, which
    builds its XML by hand and whose escape() does not touch controls either).
    Cleaning the model instead means all three are covered by one pass, and the
    invariant - nothing unrepresentable gets past this line - is in one place.
    A sign no font draws is written out here for the same reason
    (glyphs.SPELLED).
    """
    for b in model.blocks:
        b.text = spell_out(_xml_safe(b.text))
        if b.spans:
            b.spans = [(spell_out(_xml_safe(t)), *rest) for t, *rest in b.spans]
        if b.rows:
            b.rows = [[spell_out(_xml_safe(c)) for c in row] for row in b.rows]


SHOWN = {"arabic": str.maketrans("0123456789", "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"),
         "persian": str.maketrans("0123456789", "\u06F0\u06F1\u06F2\u06F3\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9")}
STRONG = re.compile(r"[A-Za-z\u00C0-\u024F\u0370-\u04FF]|"
                    r"[\u0621-\u064A\u066E-\u06D3\u06FA-\u06FF\uFB50-\uFDFF\uFE70-\uFEFC]")


def _in_context(text, table, rtl):
    """Typed digits as the original showed them: after an Arabic letter in
    the shown form, after a Latin one as typed - Word's own "Context" rule.
    Digits before any letter follow the paragraph's direction."""
    out, arabic, last = [], rtl, 0
    for m in STRONG.finditer(text):
        piece = text[last:m.start()]
        out.append(piece.translate(table) if arabic else piece)
        arabic = not LTR_CHARS.match(m.group(0))
        out.append(m.group(0))
        last = m.end()
    tail = text[last:]
    out.append(tail.translate(table) if arabic else tail)
    return "".join(out)


def _show_digits(model: Doc):
    """Write digits the way the original's pages show them (N5a).

    Word stores a typed 121 and, set to Hindi or Context numbers, DRAWS
    ١٢١: the text says one thing and the page another. Moaz's theses show
    ١٢١ everywhere; ours showed 121, because the reader's Word is set
    otherwise and the file cannot say which it wants. So the digits are
    written as shown. Only where the embedded font proves it
    (glyphs.shown_digits) - a typed 121 displayed as 121 stays 121.

    Page numbers cannot follow: they are Word's PAGE field, whose digits come
    from the reader's settings (hindiNumbers is Devanagari, tried 2026-09-22).
    Idempotent, since write() runs on the same model every fit round.
    """
    table = SHOWN.get(model.digits)
    if table is None:
        return
    for b in model.blocks:
        rtl = is_rtl(b.text)
        b.text = _in_context(b.text, table, rtl)
        if b.spans:
            # Spans are pieces of one line of text: take the context across
            # them, then cut back at the same places (a digit stays one char).
            joined = _in_context("".join(t for t, *_ in b.spans), table, rtl)
            spans, at = [], 0
            for t, *rest in b.spans:
                spans.append((joined[at:at + len(t)], *rest))
                at += len(t)
            b.spans = spans
        if b.rows:
            b.rows = [[_in_context(c, table, is_rtl(c)) for c in row]
                      for row in b.rows]


def _flag(parent, tag, val="1"):
    e = OxmlElement(tag)
    e.set(qn("w:val"), val)
    parent.append(e)


# Word keeps bold and italic twice: w:b and w:i for Latin text, w:bCs and w:iCs
# for right-to-left scripts, and Arabic in a right-to-left run follows only the
# second. python-docx's run.bold writes w:b alone, so every bold Arabic word
# came out regular: as Word drew the 8 quick-set theses, 18% of the words
# bold in the original were bold in ours, 78% with this (Part 3, 2026-09-24).
# Size was already written both ways (w:szCs, _rtl_run). QIRTAS_CS_STYLE=0
# for the old behaviour.
CS_STYLE_ON = os.environ.get("QIRTAS_CS_STYLE", "1") != "0"
# A heading's own formatting where the reading kept it (_emit).
HEADING_OWN_ON = os.environ.get("QIRTAS_HEADING_OWN", "1") != "0"
# Each paragraph at the size the original set it (_emit).
OWN_SIZE_ON = os.environ.get("QIRTAS_OWN_SIZE", "1") != "0"


def _style(run, bold, italic):
    run.bold = bold
    run.italic = italic
    if CS_STYLE_ON:
        # Each straight after its Latin twin: the schema orders them
        # b, bCs, i, iCs, and python-docx has put b and i in their places.
        rPr = run._r.get_or_add_rPr()
        for latin, cs, on in (("w:b", "w:bCs", bold), ("w:i", "w:iCs", italic)):
            e = OxmlElement(cs)
            e.set(qn("w:val"), "1" if on else "0")
            rPr.find(qn(latin)).addnext(e)


# w:jc is LOGICAL, not physical, and this cost every heading in the corpus.
#
# In OOXML "left" means START and "right" means END, and a right-to-left
# paragraph flips which side those are. So `w:jc="right"` on an Arabic heading
# puts it against the LEFT margin - the opposite of what the name says and of
# what was intended. Measured, not reasoned about: an RTL paragraph rendered at
# each setting put jc=right at x0=93 and jc=left at x0=515 on a 612pt page.
#
# Every Arabic heading in the corpus was therefore aligned to the wrong side,
# 420pt out of place on the file this was found on. The same line in table
# cells had the same fault.
#
# Correct for BOTH directions: start is the right margin in Arabic and the left
# margin in English, which is exactly what a heading wants.
#
# ECMA-376 behaviour rather than a renderer quirk. Confirmed in real Word on
# 2026-09-21: harness/test_alignment.py renders through Word and measures it.
ALIGN_START = WD_ALIGN_PARAGRAPH.LEFT


def _rtl_paragraph(p, rtl=True):
    if rtl:
        _flag(p._p.get_or_add_pPr(), "w:bidi")


def _rtl_run(run, size, font=None, rtl=True):
    rPr = run._r.get_or_add_rPr()
    if rtl:
        _flag(rPr, "w:rtl")
    font = font or ARABIC_FONT
    f = OxmlElement("w:rFonts")
    for a in ("w:cs", "w:ascii", "w:hAnsi"):
        f.set(qn(a), font)
    rPr.append(f)
    sz = OxmlElement("w:szCs")          # complex-script size is separate from w:sz
    sz.set(qn("w:val"), str(int(size * 2)))
    rPr.append(sz)


MAX_HEADING = 6


def _heading_style(p, level):
    """Make this paragraph a real Word heading, without letting Word restyle it.

    Applying the style is what gives the document structure: a table of
    contents, the navigation pane, and an outline level that other tools can
    read. Bold text at a larger size looks like a heading and is not one.

    The catch is that Word's built-in Heading styles carry their own font,
    size, colour and paragraph spacing, and all four would override what this
    converter measured from the original. Spacing especially - the page-fitting
    loop assumes the gaps it set are the gaps in the file, and a style quietly
    adding 12pt before every heading would push pages out of step.

    So the style goes on first and every property we care about is re-asserted
    over it afterwards, by the caller. The only thing settled here is the
    colour, which the style would otherwise make blue.
    """
    level = max(1, min(MAX_HEADING, int(level or 2)))
    try:
        p.style = f"Heading {level}"
    except KeyError:
        # A style absent from the template is not worth losing the heading
        # over; the outline level below still carries the structure.
        pass
    pr = p._element.get_or_add_pPr()
    for tag in ("w:outlineLvl", "w:numPr"):
        for old in pr.findall(qn(tag)):
            pr.remove(old)
    lvl = OxmlElement("w:outlineLvl")
    lvl.set(qn("w:val"), str(level - 1))       # 0-based in OOXML
    pr.append(lvl)


def _top_border(p):
    """A rule above the footnotes, the way Word draws one."""
    pPr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    top = OxmlElement("w:top")
    top.set(qn("w:val"), "single")
    top.set(qn("w:sz"), "6")
    top.set(qn("w:space"), "4")
    top.set(qn("w:color"), "auto")
    borders.append(top)
    pPr.append(borders)


def _page_setup(doc, model: Doc):  # noqa: C901
    s = doc.sections[0]
    s.page_width = Emu(int(model.page_width * PT_PER_EMU))
    s.page_height = Emu(int(model.page_height * PT_PER_EMU))
    s.left_margin = Emu(int(model.margin_left * PT_PER_EMU))
    s.right_margin = Emu(int(model.margin_right * PT_PER_EMU))
    s.top_margin = Emu(int(model.margin_top * PT_PER_EMU))
    s.bottom_margin = Emu(int(model.margin_bottom * PT_PER_EMU))
    if is_rtl(" ".join(b.text for b in model.blocks[:400])):
        _flag(s._sectPr, "w:bidi")       # only when the document really is RTL
    # These theses restart footnote numbering on every page - page 1 runs 1..4
    # and page 3 starts again at 1. Word and LibreOffice both number
    # continuously unless told otherwise, which would renumber that first note
    # on page 3 as 5.
    pr = OxmlElement("w:footnotePr")
    restart = OxmlElement("w:numRestart")
    restart.set(qn("w:val"), "eachPage")
    pr.append(restart)
    s._sectPr.append(pr)


def _text_column(model):
    return model.margin_top, model.page_height - model.margin_bottom


def _running_furniture(model):
    """Pictures that are page decoration rather than content.

    A picture whose middle sits outside the text column is not part of the
    flow - it is a running header or footer. One thesis carries two of them at
    y=31 with a top margin of 71.6, and emitting them as ordinary paragraphs
    stole 96pt from every page's 735pt of usable height. That 13% is what drove
    content steadily onto later pages until the whole document was four pages
    out of step.

    Only pictures that RECUR are treated this way, because a Word header is
    drawn on every page: something appearing once is a one-off, and putting it
    in the header would stamp it across the document. -> {id(block): "header"
    or "footer"} for the blocks to lift out, plus the file to draw in each.
    """
    top, bottom = _text_column(model)
    H = model.page_height or 0.0
    # Or wholly inside the page's outer strip: the margins are measured from
    # the content, so a page number at the very top pulls the column up over
    # the logo and the corner graphic beside it (`z22051439`).
    outside = [b for b in model.blocks if b.kind == IMAGE and b.image
               and (not (top <= (b.y + b.y1) / 2 <= bottom)
                    or (H and (b.y1 <= EDGE_ZONE * H
                               or b.y >= (1 - EDGE_ZONE) * H)))]
    if not outside:
        return {}, {}
    pages = max(1, model.pages)
    by_origin, by_place = {}, {}
    for b in outside:
        # Identity comes from the SOURCE object, not from the bytes we wrote.
        # Hashing the file used to work because the same decoration extracted
        # to identical bytes on every page. It stopped working the moment
        # masked images began being rendered off the page: anti-aliasing makes
        # each copy unique, 48 header pictures became 39 distinct hashes, and
        # nothing grouped. The running header went back into the body and one
        # file fell 56.3% -> 28.4% on right page.
        key = b.origin
        if not key:
            try:
                key = hashlib.md5(Path(b.image).read_bytes()).hexdigest()
            except OSError:
                continue
        by_origin.setdefault(key, []).append(b)
        # ...and, second, by where it sits and how big it is. Some files store
        # a separate copy of the same decoration on every page - `z21358439`
        # boxes its page number with a fresh picture object each time - so no
        # two copies share an origin and the check above never groups them.
        # Same place, same size, on most pages, is the same furniture. Rounded
        # to 2pt so a fraction of a point of drift does not split a group.
        place = tuple(round(v / 2) for v in (b.x0, b.y, b.x1, b.y1))
        by_place.setdefault(place, []).append(b)

    lift, draw = {}, {}
    groups = [(g, False) for g in by_origin.values()] +              [(g, True) for g in by_place.values()]
    for blocks, by_position in groups:
        blocks = [b for b in blocks if id(b) not in lift]
        if len({b.page for b in blocks}) < max(2, pages // 2):
            continue                       # a one-off, leave it in the flow
        mid = (blocks[0].y + blocks[0].y1) / 2
        where = "header" if mid < (H / 2 if H else top) else "footer"
        for b in blocks:
            lift[id(b)] = where
        # A photographed picture with page text inside it carries THAT page's
        # words - the box around a page number, photographed with the number
        # in it. Drawn once in the footer it would print page 1's number on
        # every page, next to the real PAGE field. Lift it out of the body and
        # draw nothing: the number itself is already in the footer as a field.
        #
        # Only for groups found by POSITION. A group sharing one source object
        # is the same decoration drawn again, and was always drawn: applying
        # this to it too stopped one of the two running-header pictures of
        # `الفصل الخامس المبحث الثالث` being drawn at all, because one of its
        # photos happens to overlap a word of the page (2026-09-21).
        #
        # And only when most copies caught text: the page-number box has its
        # number in every copy. `z21760107`'s journal logo caught a word on 1
        # of 16 pages, and "any" dropped the logo from the whole file once the
        # page's outer strip counted as furniture (N5b).
        if by_position and 2 * sum(b.over_text for b in blocks) > len(blocks):
            continue
        # Draw a copy with no page text caught inside it, where there is one.
        # Each copy is photographed off its own page, and a header photo can
        # take in the tops of the first body line beneath it. The first
        # page's copy used to be the one drawn and happened to be clean; once
        # a title page is photographed whole it is no longer in the group, and
        # page 2's copy printed a sliver of page 2's text under every header.
        #
        # With no clean copy at all, draw none. `z22051439` photographs its
        # corner graphic with the page number printed on it, every copy; drawn
        # once, it printed page one's 80 on every page next to the real
        # number (N5b).
        clean = [b for b in blocks if not b.over_text]
        if clean:
            draw.setdefault(where, []).append(clean[0])
    return lift, draw


# How much text may be furniture. A running header is a line, not a paragraph;
# without a cap a whole body paragraph that happened to repeat could be lifted
# out of the document and drawn on every page.
# A list item is indented from the side the text starts on, with the marker
# hanging outside it.
LIST_INDENT = 30.0
LIST_HANG = 14.0

RUNNING_MAX_CHARS = 200
WS_RUN = re.compile(r"\s+")
DIGITS = re.compile(r"[0-9٠-٩۰-۹]+")
# The strip along the top and bottom of the page, as a share of its height,
# where text that repeats is furniture whatever the measured margins say. The
# margins are measured FROM the content, header included, so on `z21095413`
# the page number at y=664 of 729 sat inside the "column" and in the middle of
# the page's reading order - neither test below could see it.
EDGE_ZONE = 0.12
# A header that alternates - the author on even pages, the title on odd ones
# (`z21761968`) - has to be on this share of the pages of its side.
PARITY_SHARE = 0.6
# The share of a group's copies whose number must follow the page for that
# number to be taken as the page number.
NUMBER_SHARE = 0.6


class Furniture:
    """One piece of running text: its copies, and how to draw it.

    parity  None, or the page parity (0-based index % 2) it is printed on
    run     None, or (which number in the text is the page number, the number
            printed on page 0)
    silent  lifted out of the body, not drawn: a table whose text is already
            drawn by another piece, or a band with no text at all
    shown   None, or the text to draw when it is less than the block's: the
            words a band at the same edge already prints are left out
    """

    def __init__(self, blocks, parity=None, run=None):
        self.blocks, self.parity, self.run = blocks, parity, run
        self.silent = False
        self.shown = None

    @property
    def text(self):
        if self.shown is not None:
            return self.shown
        return WS_RUN.sub(" ", _furniture_text(self.block).strip())

    @property
    def block(self):
        return self.blocks[0]

    @property
    def y(self):
        ys = sorted(b.y for b in self.blocks)
        return ys[len(ys) // 2]


def _furniture_text(b):
    if b.kind == TABLE:
        return " ".join(c.strip() for row in (b.rows or []) for c in row
                        if c and c.strip())
    return b.text or ""


def _page_run(blocks):
    """Which number in these copies is the page number. -> (index, number on
    page 0) or None.

    The number whose value less the page is the same on most copies. Taking
    the first copy's instead is what `z20538636` did: a year on its title page
    read backwards, ٥٢٠٢, has the shape of a page number, and the whole
    document was numbered from 5202. A number that never changes - a volume,
    a year - is not the page number however it lines up.
    """
    runs = [[int(d.translate(WESTERN)) for d in DIGITS.findall(_furniture_text(b))]
            for b in blocks]
    if not any(runs):
        return None
    width = Counter(len(r) for r in runs if r).most_common(1)[0][0]
    best = None
    for i in range(width):
        pairs = [(r[i], b.page) for r, b in zip(runs, blocks) if len(r) == width]
        if len({v for v, _ in pairs}) < 2:
            continue
        start, n = Counter(v - p for v, p in pairs).most_common(1)[0]
        if n >= max(2, NUMBER_SHARE * len(blocks)) and start >= 0 \
                and (best is None or n > best[2]):
            best = (i, start, n)
    return best and best[:2]


def _agrees(b, run):
    i, start = run
    runs = DIGITS.findall(_furniture_text(b))
    return len(runs) > i and int(runs[i].translate(WESTERN)) - b.page == start


def _letters(text):
    return Counter(c for c in text if c.isalpha())


def _running_text(model):
    """Text that repeats at the same edge of most pages is furniture, not content.

    `_running_furniture` above does this for PICTURES, which is why Moaz's
    files stopped inflating. Repeating TEXT was never detected, so the journal
    line and the page number were emitted as ordinary paragraphs in the body:

        z20256558   "A. Abboud, Journal of Al-Wataniya..."  TWO body lines
        z21358439   "مجلة مداولة سلسلة الأعداد..." first line; page no. 53 last
        z21011460   journal line over two body lines; page no. 82 last

    Two or three lines off every page's column is the same mechanism that drove
    the original pagination blow-up, and those three files inflate 17->23,
    37->48 and 33->43.

    What makes this harder than the picture case:

    - **The page number is different on every page**, so grouping by exact text
      finds nothing. Digits are replaced by a placeholder before grouping, so
      "82" and "83" are recognised as the same piece of furniture.
    - **The tags route carries no coordinates for text** (the geometry route
      does). Where there is no y, position on the page cannot be used at all,
      so the first or last block of its page is what counts as an edge.
    - **A header is often more than one piece** (N5b, 2026-09-22): a journal
      line in two languages, a header that alternates between even and odd
      pages, a page number printed twice on top of itself. Only one piece per
      edge used to be taken; the rest stayed in the body.
    - **Some headers are tables**: the band between two rules is found as a
      table and was written as an empty grid on every page (`z21762915`).

    Repetition is the real signal and is route-independent: a Word header is
    drawn on every page, so lifting something that appears once would stamp it
    across the whole document.

    -> ({id(block): "header"|"footer"}, {"header"|"footer": [[Furniture]]}),
    each inner list one line of the header, top to bottom.
    """
    pages = max(1, model.pages)
    if pages < 4:
        # Too few pages for "repeats on most of them" to mean anything.
        return {}, {}
    top, bottom = _text_column(model)
    H = model.page_height or 0.0

    def placed(b):
        return bool(b.y or b.y1)

    def zone(b):
        if not (H and placed(b)):
            return None
        if b.y1 <= EDGE_ZONE * H:
            return "header"
        if b.y >= (1 - EDGE_ZONE) * H:
            return "footer"
        return None

    by_page, tables = {}, []
    for b in model.blocks:
        if b.kind == TABLE:
            if zone(b):
                tables.append(b)
        elif b.kind != IMAGE and b.text.strip():
            by_page.setdefault(b.page, []).append(b)

    def edge(b):
        if b.kind == TABLE:
            return zone(b)
        # Coordinates decide it when they put the block clearly outside the
        # column. They often do not, and the reason is circular: the margins
        # are MEASURED from the content, and the running header is part of that
        # content, so the column is drawn to include it and it never looks
        # outside. That is why the journal line was missed on the first attempt
        # here while the page numbers were found - and why the outer strip of
        # the page counts too.
        if placed(b):
            mid = (b.y + b.y1) / 2
            if mid < top:
                return "header"
            if mid > bottom:
                return "footer"
            if zone(b):
                return zone(b)
        # Fall back to where it sits in the page's reading order. This is the
        # only test available on the tags route, which carries no coordinates
        # for text at all. Repetition is what makes it safe: being first on the
        # page is ordinary, being first on the page with the same words every
        # time is furniture.
        sibs = by_page.get(b.page) or []
        if not sibs or (b is not sibs[0] and b is not sibs[-1]):
            return None
        # Which edge is settled by which half of the page it sits in, when that
        # is known, not by whether it came first. A photographed title page
        # leaves its page number alone on the page, and asking "first?" filed
        # it as a header; `z21763864` reads its footer first on every page.
        if placed(b) and H:
            return "footer" if (b.y + b.y1) / 2 > H / 2 else "header"
        return "header" if b is sibs[0] else "footer"

    groups = {}
    for b in [b for sibs in by_page.values() for b in sibs] + tables:
        flat = WS_RUN.sub(" ", _furniture_text(b).strip())
        if len(flat) > RUNNING_MAX_CHARS:
            continue
        where = edge(b)
        if not where:
            continue
        key = (where, b.kind == TABLE, DIGITS.sub("#", flat))
        groups.setdefault(key, []).append(b)

    need = max(3, pages // 2)
    lift, found = {}, {}
    for (where, _, _), blocks in groups.items():
        on = {b.page for b in blocks}
        sides = {p % 2 for p in on}
        parity = None
        if len(sides) == 1:
            side = next(iter(sides))
            if len(on) < max(3, PARITY_SHARE * len(range(side, pages, 2))):
                continue
            parity = side
        elif len(on) < need:
            continue
        run = _page_run(blocks)
        if run:
            # Only the copies whose number IS the page number. The rest - the
            # year on the title page - stay where they were.
            blocks = [b for b in blocks if _agrees(b, run)]
        found.setdefault(where, []).append(Furniture(blocks, parity, run))
        for b in blocks:
            lift[id(b)] = where

    # A table band whose words another piece already draws is lifted and not
    # drawn: `z20276275` has its header both as text and, read backwards, as
    # a table around it. Letters are compared as a bag, so the backwards
    # reading still matches.
    for pieces in found.values():
        for f in pieces:
            if f.block.kind != TABLE:
                continue
            own = _letters(_furniture_text(f.block))
            other = sum((_letters(b.text) for b in by_page.get(f.block.page, ())
                         if lift.get(id(b))), Counter())
            left = sum((own - other).values())
            f.silent = left <= 0.1 * sum(own.values())

    # A piece found only on pages of one side, carrying nothing the other
    # pieces at its edge do not, is the same furniture read in another order -
    # not a header that alternates. `z21763864` mirrors its footer on even
    # pages, and there "- 8 - 10 2016" reads "2016 10 - 8 -": taken as an even
    # page footer, it printed next to the real one. `z21761968`'s title and
    # author alternate and share nothing, so they stay apart.
    # When both sides are read differently, whatever covered the silenced
    # piece is printed on every page.
    def bag(g):
        return Counter(DIGITS.sub("#", WS_RUN.sub("", _furniture_text(g.block))))

    for pieces in found.values():
        for f in pieces:
            if f.parity is None or f.silent:
                continue
            cover = [g for g in pieces if g is not f and not g.silent
                     and g.parity != f.parity]
            own = bag(f)
            if own and cover and not own - sum(map(bag, cover), Counter()):
                f.silent, f.parity = True, None
                for g in cover:
                    g.parity = None

    # A line a band at the same edge already prints, printed again beside it.
    # `z21762915`'s footer band ends ":العدد05 - أفريل2017", and so does the
    # line holding its page number: the footer said the issue twice. The
    # band's words are left out of the line, and the page number stays.
    for pieces in found.values():
        bands = [g for g in pieces if g.block.kind == TABLE and not g.silent]
        if not bands:
            continue
        cover = "".join(WS_RUN.sub("", _furniture_text(g.block)) for g in bands)
        for f in pieces:
            if f.block.kind == TABLE or f.silent:
                continue
            text = f.text
            words = text.split(" ")
            number = inside = None
            if f.run:
                at = list(DIGITS.finditer(text))[f.run[0]].start()
                number = text[:at].count(" ")
                # which number within its word the page number is
                inside = len(DIGITS.findall(text[text.rfind(" ", 0, at) + 1:at]))
            keep = [k for k, w in enumerate(words) if k == number or w not in cover]
            if len(keep) == len(words):
                continue
            if not keep:
                f.silent = True
                continue
            f.shown = " ".join(words[k] for k in keep)
            if f.run:
                before = " ".join(words[k] for k in keep if k < number)
                f.run = (len(DIGITS.findall(before)) + inside, f.run[1])

    # Pieces sharing a line are drawn as one paragraph, as the original shows
    # them: "- 8 -" and "2016" at the foot of `z21763864`, two blocks on one
    # line, would otherwise take two lines of the footer.
    draw = {}
    for where, pieces in found.items():
        lines = []
        for f in sorted(pieces, key=lambda f: f.y):
            last = lines[-1][-1] if lines else None
            if last and placed(f.block) and placed(last.block) \
                    and f.y < last.y + max(1.0, (last.block.y1 - last.block.y) / 2):
                lines[-1].append(f)
            else:
                lines.append([f])
        draw[where] = lines
    return lift, draw


def _page_base(draw):
    """The number the original printed on its first page, or None."""
    return next((f.run[1] for lines in draw.values() for line in lines
                 for f in line if f.run), None)


def _add_page_field(p, cached, run=None):
    """A PAGE field; `run`, a formatted run, carries its look. Without one the
    number takes Word's default size, larger than the footer around it
    ("- 8 - 10 2016" on `z21763864`)."""
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), " PAGE ")
    if run is None:
        r = OxmlElement("w:r")
        t = OxmlElement("w:t")
        t.text = str(cached)
        r.append(t)
    else:
        r = run._r
        r.getparent().remove(r)
    fld.append(r)
    p._p.append(fld)


# A paragraph drawn in the middle of the text column is centred. Headings went
# to the start of the line and body text was justified whatever the original
# did: of 37 centred lines in the 8 quick-set theses, 11 were centred in ours
# (Part 3, 2026-09-24) - titles, chapter headings, a verse on a page of its own.
CENTRE_ON = os.environ.get("QIRTAS_CENTRE", "1") != "0"
CENTRE_WIDTH = 0.7       # narrower than this share of the column
CENTRE_SLACK = 0.04      # its middle this close to the column's


def _centred(block, model, within=None):
    """Centred on the text column - or, given `within` (left, right), on
    that stretch of the page: a cell of blocks side by side."""
    if not CENTRE_ON or not (block.x0 or block.x1):
        return False
    lo, hi = within or (model.margin_left, model.page_width - model.margin_right)
    column = hi - lo
    if column <= 0:
        return False
    width = block.x1 - block.x0
    mid = lo + column / 2
    return 0 < width < CENTRE_WIDTH * column and \
        abs((block.x0 + block.x1) / 2 - mid) < CENTRE_SLACK * column


# Blocks the original set side by side - a title page's two supervisors, two
# pictures in a row - were written one under the other, so the page held
# more than the original's and ran long (`z20782957`, Part 3). They go into a
# borderless table of two cells instead, the one read first in cell one.
BESIDE_ON = os.environ.get("QIRTAS_BESIDE", "1") != "0"
BESIDE_SLACK = 2.0       # points two edges may overlap and still count apart


class Beside:
    """Runs of blocks drawn next to each other, in reading order."""
    kind = "beside"

    def __init__(self, runs):
        self.runs = runs
        self.blocks = [b for r in runs for b in r]
        self.y = min(b.y for b in self.blocks)
        self.y1 = max(b.y1 for b in self.blocks)
        self.text = " ".join(b.text for b in self.blocks)


def _placed(b):
    return isinstance(b, Beside) or (b.y1 > b.y and b.x1 > b.x0)


def _span(blocks):
    return min(b.x0 for b in blocks), max(b.x1 for b in blocks)


def _apart(a, b):
    """The two runs share no stretch across the page."""
    (a0, a1), (b0, b1) = _span(a), _span(b)
    return a1 <= b0 + BESIDE_SLACK or b1 <= a0 + BESIDE_SLACK


def _level(a, b):
    """The two runs share at least half the height of the shorter one. A
    page number at the foot, read before the text at the top, is not beside
    it (`z18048055`)."""
    a0, a1 = min(x.y for x in a), max(x.y1 for x in a)
    b0, b1 = min(x.y for x in b), max(x.y1 for x in b)
    return min(a1, b1) - max(a0, b0) >= 0.5 * min(a1 - a0, b1 - b0)


# A number or dash alone - an entry's number set out in the margin, level
# with its first line: "47 -" beside "( روسو، جان جاك. 2011 .)".
MARKER_ONLY = re.compile(r"[\s0-9٠-٩۰-۹.\-–)(•▪❖*]{1,8}")


def _joined(first, second):
    """The margin number put back on the front of its entry, as one
    paragraph. A copy: the fit loop writes the same model again."""
    lead, rest = first[0], second[0]
    b = copy.copy(rest)
    b.text = lead.text.strip() + " " + rest.text
    if rest.spans:
        b.spans = [(lead.text.strip(), False, False)] + list(rest.spans)
    b.y, b.y1 = min(lead.y, rest.y), max(lead.y1, rest.y1)
    b.x0, b.x1 = min(lead.x0, rest.x0), max(lead.x1, rest.x1)
    return [b] + second[1:]


def _beside(body):
    """-> body with each side-by-side stretch folded into one `Beside`.

    The sign is the reading going back UP the page: a block that starts above
    where the one before it ended, and sits clear of it across the page. The
    first run is what came before it and still reaches down past its top; the
    second is it and what follows while it stays level with the first run and
    clear of it. Blocks with no position (the tags route) never match.
    """
    if not BESIDE_ON:
        return body
    out, i = [], 0
    while i < len(body):
        b = body[i]
        prev = out[-1] if out else None
        # A table read just before (`z3387756`) is never one side.
        if prev is None or isinstance(prev, Beside) or b.kind not in (
                PARAGRAPH, HEADING, LIST_ITEM, IMAGE) \
                or prev.kind not in (PARAGRAPH, HEADING, LIST_ITEM, IMAGE) \
                or not _placed(b) or not _placed(prev) \
                or b.y >= prev.y1 - BESIDE_SLACK or not _apart([prev], [b]):
            out.append(b)
            i += 1
            continue
        # Walking back must go up the page: a page number at the foot, read
        # first, is not part of the column above it (`z18441713`).
        first = []
        while out and not isinstance(out[-1], Beside) and _placed(out[-1]) \
                and out[-1].kind in (PARAGRAPH, HEADING, LIST_ITEM, IMAGE) \
                and out[-1].y1 > b.y + BESIDE_SLACK and _apart([out[-1]], [b]) \
                and (not first or out[-1].y <= first[0].y + BESIDE_SLACK):
            first.insert(0, out.pop())
        # Then the runs after it. A block clear of every run so far, starting
        # back up above the last run's foot and further along the same way,
        # starts another run - a table drawn without borders, read cell by
        # cell ("م", "العبارة", "موافق بشدة" ...: `z17804101`); else it
        # carries on the last run while it stays clear of the others.
        rtl = _span(first)[0] >= _span([b])[1] - BESIDE_SLACK
        runs, starts, j = [first, [b]], [None, i], i + 1
        bottom = max(x.y1 for x in first)
        while j < len(body) and body[j].kind in (PARAGRAPH, HEADING, LIST_ITEM, IMAGE) \
                and _placed(body[j]) and body[j].y < bottom - BESIDE_SLACK:
            x, last = body[j], runs[-1]
            if not all(_apart(r, [x]) for r in runs[:-1]):
                break
            onward = x.x1 <= _span(last)[0] + BESIDE_SLACK if rtl \
                else x.x0 >= _span(last)[1] - BESIDE_SLACK
            if onward and x.y < max(y.y1 for y in last) - BESIDE_SLACK:
                runs.append([x])
                starts.append(j)
            else:
                last.append(x)
            j += 1
        # Every run clear of the others and level with the first; a run that
        # is not goes back to the page, and what follows it with it.
        while len(runs) > 2 and (
                not all(_apart(r, q) for r, q in itertools.combinations(runs, 2))
                or not _level(first, runs[-1])):
            j = starts.pop()
            runs.pop()
        second = runs[1]
        if not _apart(first, second) or not _level(first, second):
            out.extend(first)
            out.append(b)
            i += 1
            continue
        if len(runs) == 2 and len(first) == 1 and first[0].kind != IMAGE \
                and second[0].kind != IMAGE \
                and MARKER_ONLY.fullmatch(first[0].text.strip() or "x"):
            out.extend(_joined(first, second))
        else:
            out.append(Beside(runs))
        i = j
    return out


# The space the original left above a paragraph, beyond the ordinary space
# between lines. Every paragraph is written with none: a title page spread
# down the page comes out bunched at the top (`z20782957`, Part 3).
#
# OFF by default (QIRTAS_GAP=1 to try it). Measured 2026-09-25 on the quick
# set, even kept to pages under 150 words: three theses gained 1-3 pages and
# right page fell 53.4 -> 48.6%; the page fitting then shrank the text to
# make room, so titles came out small again. Our pages hold more than the
# original's - blocks side by side are stacked - and the original's gaps no
# longer fit. Tried again with side by side fixed (2026-09-25): still
# worse, right page 53.4 -> 49.5%, `z20973693` 22 pages -> 24. Pages run
# long for some other reason, and that has to be found first.
GAP_ON = os.environ.get("QIRTAS_GAP", "0") == "1"
GAP_MIN = 0.5            # of the body size: less is ordinary line spacing
GAP_MAX = 6              # lines: more is a page laid out some other way
GAP_PAGE_WORDS = 150     # pages with fewer words than this get their gaps


def _gap_above(block, above, model):
    """Points of space above `block`: from the one written before it on the
    page, or from the top margin for the first. 0 when not clearly more than
    the ordinary gap between two lines of a paragraph."""
    if not GAP_ON or not block.y or not model.line_pitch:
        return 0.0
    size = block.text_size or block.size or model.body_size
    # between two lines of one paragraph, bottom of one to top of the next
    ordinary = max(0.0, model.line_pitch - 1.15 * size)
    if above is None:
        raw = block.y - model.margin_top
        ordinary = 0.0
    elif above.y1 and block.y > above.y1:
        raw = block.y - above.y1
    else:
        return 0.0
    extra = raw - ordinary
    if extra < GAP_MIN * model.body_size:
        return 0.0
    return min(extra, GAP_MAX * model.line_pitch)


def _furniture_align(model, line, rtl):
    """Where the line sits across the page: the middle, or one side."""
    b = line[0].block
    W = model.page_width
    if not (W and (b.x0 or b.x1)):
        return WD_ALIGN_PARAGRAPH.CENTER
    x0 = min(f.block.x0 for f in line)
    x1 = max(f.block.x1 for f in line)
    mid = (x0 + x1) / 2
    if abs(mid - W / 2) < 0.1 * W:
        return WD_ALIGN_PARAGRAPH.CENTER
    left = mid < W / 2
    # w:jc is logical: in a right-to-left paragraph "left" is its start, the
    # right side of the page. See ALIGN_START.
    return WD_ALIGN_PARAGRAPH.LEFT if left != rtl else WD_ALIGN_PARAGRAPH.RIGHT


def _draw_text_furniture(doc, draw, model):
    """Put the running header and footer text into Word's header and footer.

    A page number becomes a real PAGE field rather than the literal digits, or
    every page of the Word file would read 82 - also when the number sits
    inside a line of text, "- 8 - 10 2016" (`z21763864`), where the whole line
    used to be copied from the first page.

    A header that differs between even and odd pages goes into Word's two
    headers. Word picks between them by the page NUMBER, so the printed
    numbering decides which of our page indexes is even.
    """
    section = doc.sections[0]
    # The block's OWN measured size, not a fraction of the body size. The
    # journal line on z21011460 is 8pt and drawn 332pt wide in a 378pt column;
    # writing it at 0.8 x 12pt body made it 9.6pt, about 398pt wide, and it
    # wrapped onto a second line the original never had.
    fallback = max(7.0, round(model.body_size * 0.8, 1))
    base = _page_base(draw)
    if base is not None:
        _set_page_number_start(section, base)
    split = any(f.parity is not None and not f.silent
                for lines in draw.values() for line in lines for f in line)
    if split:
        doc.settings.odd_and_even_pages_header_footer = True
    first = 1 if base is None else base
    for where, lines in draw.items():
        parts = [(getattr(section, where), 1)]
        if split:
            parts.append((getattr(section, f"even_page_{where}"), 0))
        for part, odd in parts:
            part.is_linked_to_previous = False
            for line in lines:
                shown = [f for f in line if not f.silent and
                         (f.parity is None or (first + f.parity) % 2 == odd)]
                if not shown:
                    continue
                p = part.paragraphs[0] if part.paragraphs else part.add_paragraph()
                if p.text.strip() or p.runs:
                    p = part.add_paragraph()
                text = " ".join(f.text for f in shown)
                rtl = is_rtl(text)
                _rtl_paragraph(p, rtl)
                p.alignment = _furniture_align(model, shown, rtl)
                band = next((f.block for f in shown if f.block.fill), None)
                if band is not None:
                    _band(p, band)
                one = shown[0]
                if PARTS_OUT_ON and len(shown) == 1 and 2 <= len(one.block.parts) <= 3 \
                        and not one.run and one.shown is None:
                    _draw_parts(p, one, fallback, model, rtl, section)
                    continue
                for k, f in enumerate(shown):
                    if k:
                        _furniture_run(p, " ", f, fallback, model, rtl)
                    _draw_piece(p, f, fallback, model, rtl)
            # A header band's pictures go with it: `z20276275` keeps its
            # journal logo in a cell of the header box, and lifting the box
            # without them dropped the logo from all 18 pages.
            for line in lines:
                for f in line:
                    cells = f.block.cell_images if f.block.kind == TABLE else {}
                    if not cells:
                        continue
                    p = part.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for (ri, ci), path in sorted(cells.items()):
                        box = (f.block.cell_boxes or [])[ri][ci] \
                            if ri < len(f.block.cell_boxes or []) else None
                        width = (box[2] - box[0]) if box else 60.0
                        _place(p, path, width, model.dropped_images)


# A running header or footer as bold or italic as most of its letters were.
# It was always written plain: `z22643426`'s italic chapter line lost its
# slant on all nine pages that carry it.
FURNITURE_STYLE_ON = os.environ.get("QIRTAS_FURNITURE_STYLE", "1") != "0"


# A header in parts at the page's edges (reader._header_parts): the first
# part at the line's start, the last against its end, a middle one centred -
# by tab stops at the middle and the far end of the text width. An end tab is
# the far side in either direction; Word's positional tab, tried first,
# wrapped the second part onto a line of its own in a right-to-left header.
PARTS_OUT_ON = os.environ.get("QIRTAS_HEADER_PARTS", "1") != "0"


def _draw_parts(p, f, fallback, model, rtl, section):
    width = int((section.page_width - section.left_margin - section.right_margin) / 635)
    tabs = OxmlElement("w:tabs")
    # Word's Header and Footer styles bring stops of their own, centre 4680
    # and right 9360; the first tab went to the centre one, leaving the
    # title in the middle of the line. Cleared here.
    stops = [("clear", 4680), ("clear", 9360)]
    stops += ([("center", width // 2)] if len(f.block.parts) == 3 else []) + [("end", width)]
    for val, pos in sorted(stops, key=lambda s: s[1]):
        t = OxmlElement("w:tab")
        t.set(qn("w:val"), val)
        t.set(qn("w:pos"), str(pos))
        tabs.append(t)
    p._p.get_or_add_pPr().insert_element_before(tabs, *PPR_AFTER_SHD[1:])
    p.alignment = ALIGN_START
    for k, part in enumerate(f.block.parts):
        _furniture_run(p, ("\t" if k else "") + part, f, fallback, model, rtl)


def _furniture_run(p, text, f, fallback, model, rtl):
    size = f.block.size if f.block.size and f.block.size >= 5 else fallback
    run = p.add_run(text)
    run.font.size = Pt(size)
    _ink(run, f.block)
    if FURNITURE_STYLE_ON:
        bold, italic = _note_style(f.block)
        if bold or italic:
            _style(run, bold, italic)
    _rtl_run(run, size, model.font, rtl)


def _draw_piece(p, f, fallback, model, rtl):
    text = f.text
    if not f.run:
        _furniture_run(p, text, f, fallback, model, rtl)
        return
    i, start = f.run
    runs = list(DIGITS.finditer(text))
    m = runs[i]
    if text[:m.start()]:
        _furniture_run(p, text[:m.start()], f, fallback, model, rtl)
    _furniture_run(p, str(start + f.block.page), f, fallback, model, rtl)
    _add_page_field(p, start + f.block.page, p.runs[-1])
    if text[m.end():]:
        _furniture_run(p, text[m.end():], f, fallback, model, rtl)


def _first_page_number(doc, model, draw, lift):
    """Keep the page number on a photographed title page, when the photo does
    not already show it.

    A title page photographed whole turns Word's header and footer off for
    that page (`reader._collage`), so nothing the photo shows is printed
    twice. But on Moaz's chapters the photo stops at y~725 and the number sits
    at y=778, below it - so turning the footer off simply lost the chapter's
    first page number. Copy the footer onto the first page in that case only.
    """
    photo = next((b for b in model.blocks if b.collage and b.page == 0), None)
    numbered = any(f.run for line in draw.get("footer", ()) for f in line)
    if photo is None or not numbered:
        return
    first = [b for b in model.blocks
             if lift.get(id(b)) == "footer" and b.page == 0]
    if not first or not first[0].y or first[0].y < photo.y1:
        return                               # the photo shows the number
    section = doc.sections[0]
    target = section.first_page_footer
    target.is_linked_to_previous = False
    for p in list(target.paragraphs):
        p._p.getparent().remove(p._p)
    for p in section.footer.paragraphs:
        target._element.append(copy.deepcopy(p._p))


BARE_FRONT_ON = os.environ.get("QIRTAS_BARE_FRONT", "1") != "0"


def _bare_front(model, lift):
    """-> how many pages at the front the original left with no header and no
    page number, 0 for none.

    Word draws the running header and footer on every page, so a thesis's
    title page got the chapter's header and a page number - "70" under
    `z20782957`'s supervisors - and so did the unnumbered pages after it.
    Those pages go into a section of their own with no header or footer
    (`_end_front`). Counted up to the first page anything was lifted from.
    """
    if not BARE_FRONT_ON or not lift:
        return 0
    if any(b.collage and b.page == 0 for b in model.blocks):
        return 0                        # the photo's own rule, _first_page_number
    return min((b.page for b in model.blocks if id(b) in lift), default=0)


def _end_front(doc, first_el):
    """End a section with no header or footer just before `first_el`, the
    first thing on the first numbered page.

    A CONTINUOUS break, so every page still starts with its own page break -
    the scoring splits pages there - and Word takes each page's header from
    the section in force at its top: the front pages get none, and numbering
    starts again where the page-number start on the main section says.
    """
    main = doc.sections[-1]._sectPr
    brk = copy.deepcopy(main)
    for tag in ("w:headerReference", "w:footerReference", "w:pgNumType", "w:titlePg"):
        for el in brk.findall(qn(tag)):
            brk.remove(el)
    for el in brk.findall(qn("w:type")):
        brk.remove(el)
    kind = OxmlElement("w:type")
    kind.set(qn("w:val"), "continuous")
    brk.insert(0, kind)
    prev = first_el.getprevious()
    if prev is None or prev.tag != qn("w:p"):
        # a table ends the page: the break needs a paragraph of its own
        prev = OxmlElement("w:p")
        first_el.addprevious(prev)
    ppr = prev.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        prev.insert(0, ppr)
    ppr.append(brk)


def _set_page_number_start(section, start):
    """Make Word's own numbering begin where the original's did."""
    pr = section._sectPr
    for old in pr.findall(qn("w:pgNumType")):
        pr.remove(old)
    el = OxmlElement("w:pgNumType")
    el.set(qn("w:start"), str(max(0, start)))
    pr.append(el)


def _draw_furniture(doc, draw, model, dropped):
    """Put each running picture into the Word header or footer, once."""
    section = doc.sections[0]
    column = model.page_width - model.margin_left - model.margin_right
    for where, blocks in draw.items():
        part = section.header if where == "header" else section.footer
        part.is_linked_to_previous = False
        p = part.paragraphs[0] if part.paragraphs else part.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for b in blocks:
            width = min(b.x1 - b.x0, column)
            if width <= 0:
                continue
            height = (b.y1 - b.y) * width / (b.x1 - b.x0) if SHAPE_ON else 0
            _place(p, b.image, width, dropped, height if height > 0 else None)


def _image_fit(model, lift):
    """How much to shrink each page's pictures so they still fit on one page.

    Pictures are emitted one under another, but in the original they overlap and
    sit side by side. A title page of 14 pictures stacked to 1158pt against
    735pt of usable height, so it took two pages - and every page after it was
    one out of step for the rest of the document.

    -> {page: factor}. 1.0 for pages that already fit, which is nearly all.
    """
    top, bottom = _text_column(model)
    usable = max(1.0, bottom - top)
    column = model.page_width - model.margin_left - model.margin_right
    tall = {}
    for b in model.blocks:
        if b.kind != IMAGE or id(b) in lift:
            continue
        w0 = b.x1 - b.x0
        if w0 <= 0:
            continue
        # Height follows from the width Word will actually use, not from the
        # rectangle in the PDF: a picture wider than the column gets capped.
        w = min(w0, column)
        tall[b.page] = tall.get(b.page, 0.0) + (b.y1 - b.y) * (w / w0)
    out = {}
    for page, h in tall.items():
        room = usable * IMAGE_PAGE_FILL
        if h > room:
            out[page] = room / h
    return out


def _interleave(body, pics, model):
    """Put each picture where it sat on the page, not at the bottom.

    Stacking every picture at the foot of the page added height the original
    never had: on one chapter that pushed 25 pages out to 32. Text read from
    the tag tree carries no coordinates, but the pictures do, so each one is
    dropped in at the same fraction down the page it occupied in the original.
    """
    if not pics:
        return body
    if not body:
        return list(pics)
    top = model.margin_top
    bottom = model.page_height - model.margin_bottom
    span = max(1.0, bottom - top)
    placed = [i for i, b in enumerate(body) if b.y1 > 0]
    if BY_Y_ON and len(placed) * 5 >= len(body) * 4:
        return _by_y(body, pics, placed)
    out = list(body)
    for pic in sorted(pics, key=lambda b: b.y, reverse=True):
        if pic.y <= 0:
            out.append(pic)
            continue
        frac = min(1.0, max(0.0, (pic.y - top) / span))
        out.insert(int(round(frac * len(body))), pic)
    return out


# Where the text carries its place on the page, a picture or table goes after
# the last paragraph that starts above it - starts, since a caption read
# together with the table's header row runs down into the table. The share of the way down the list put a table
# into the middle of a paragraph when the page's text is not spread evenly -
# a table whose rows are also read as paragraphs below it (`z3387756` page 5).
BY_Y_ON = os.environ.get("QIRTAS_PLACE_BY_Y", "1") != "0"
Y_SLACK = 4.0


def _by_y(body, pics, placed):
    at = {}
    for pic in pics:
        if pic.y <= 0:
            at.setdefault(len(body), []).append(pic)
            continue
        above = [i for i in placed if body[i].y < pic.y - Y_SLACK]
        at.setdefault(max(above) + 1 if above else 0, []).append(pic)
    out = []
    for i in range(len(body) + 1):
        out.extend(sorted(at.get(i, []), key=lambda b: b.y))
        if i < len(body):
            out.append(body[i])
    return out


def _run_centred(run):
    """Are the blocks of one side centred on each other? Measured against the
    run's own width, not the cell's: the cell stretches to the gutter and
    the page edge, which the original's column need not reach."""
    if len(run) < 2:
        return False
    lo, hi = _span(run)
    mid, width = (lo + hi) / 2, hi - lo
    close = sum(abs((b.x0 + b.x1) / 2 - mid) < CENTRE_SLACK * 2 * width for b in run)
    return CENTRE_ON and close * 2 >= len(run)


def _emit_beside(doc, g, model, k, img_k, notes, first_break):
    """Two runs of blocks side by side, as a borderless table of two cells -
    the run read first in cell one, which sits on the right when the
    original has it on the right."""
    left, right = model.margin_left, model.page_width - model.margin_right
    spans = [_span(r) for r in g.runs]
    rtl = spans[0][0] >= spans[1][1] - BESIDE_SLACK
    # Cell edges halfway across each gap, the outer ones at the column's
    # edges; in reading order, which runs right to left when `rtl`.
    edges = [(a[0] + b[1]) / 2 if rtl else (a[1] + b[0]) / 2
             for a, b in zip(spans, spans[1:])]
    edges = [right if rtl else left] + edges + [left if rtl else right]
    least = min(36.0, (right - left) / (2 * len(g.runs)))
    widths = [max(least, abs(b - a)) for a, b in zip(edges, edges[1:])]
    scale = (right - left) / sum(widths)
    widths = [w * scale for w in widths]
    t = doc.add_table(rows=1, cols=len(g.runs))
    _fix_columns(t, widths, [0])
    if rtl:
        _flag(t._tbl.tblPr, "w:bidiVisual")
    for cell, run, width in zip(t.rows[0].cells, g.runs, widths):
        centre = _run_centred(run)
        for b in run:
            if b.kind == IMAGE:
                _emit_image(cell, b, max(24.0, width - 12), k * img_k,
                            model.dropped_images)
                continue
            p = _emit(cell, b, model.body_size * k, model.line_pitch * k, model.font,
                      notes=notes, base_pt=model.body_size)
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.space_before = Pt(0)
            # Never justified: in a narrow cell it spread a five-line French
            # heading word by word across the column (`z21850164`).
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if centre else ALIGN_START
        paras = cell.paragraphs
        if len(paras) > 1:            # the empty one every new cell starts with
            paras[0]._element.getparent().remove(paras[0]._element)
    if first_break:
        t.cell(0, 0).paragraphs[0].paragraph_format.page_break_before = True
    return t


FLIP_ON = os.environ.get("QIRTAS_TABLE_FLIP", "1") != "0"


def _emit_table(doc, block, body_pt, font, dropped=None):
    """A real Word table, mirrored so column one sits on the right."""
    if dropped is None:
        dropped = []
    rows = [r for r in block.rows if r]
    if not rows:
        return None
    width = max(len(r) for r in rows)
    flat = " ".join(c for r in rows for c in r)
    rtl = is_rtl(flat)
    t = doc.add_table(rows=len(rows), cols=width)
    t.style = "Table Grid"
    widths = [max(18.0, w) for w in block.col_widths]         if block.col_widths and len(block.col_widths) == width else []
    rows = [list(r) + [""] * (width - len(r)) for r in rows]
    pics, spans = dict(block.cell_images), dict(block.cell_spans or {})
    fills = dict(block.cell_fills or {})
    # The table finder lists a row's cells left to right, as drawn. A mirrored
    # table puts cell one on the RIGHT, so a right-to-left table is handed to
    # Word in reverse; handed over as read, every column came out on the
    # wrong side (seen on every table page looked at, 2026-09-27).
    if rtl and FLIP_ON:
        rows = [r[::-1] for r in rows]
        widths = widths[::-1]
        pics = {(r, width - 1 - c): v for (r, c), v in pics.items()}
        fills = {(r, width - c - spans.get((r, c), 1)): v
                 for (r, c), v in fills.items()}
        spans = {(r, width - c - k): k for (r, c), k in spans.items()}
    elif rtl:
        widths = widths[::-1]
    if widths:
        _fix_columns(t, widths, rows)
    # Mirror the columns only for a table that is actually right-to-left. An
    # English table was being mirrored too, which reversed a table that was
    # never right-to-left.
    if rtl:
        _flag(t._tbl.tblPr, "w:bidiVisual")
    covered = set()
    for (ri, ci), k in spans.items():
        if ri < len(rows) and 0 <= ci and ci + k <= width:
            text = " ".join(x for x in rows[ri][ci:ci + k] if x.strip())
            rows[ri][ci:ci + k] = [text] + [""] * (k - 1)
            t.cell(ri, ci).merge(t.cell(ri, ci + k - 1))
            covered.update((ri, j) for j in range(ci + 1, ci + k))
    for ri, row in enumerate(rows):
        for ci in range(width):
            if (ri, ci) in covered:
                continue
            cell = t.cell(ri, ci)
            if fills.get((ri, ci)):
                _shade(cell, fills[(ri, ci)])
            text = (row[ci] if ci < len(row) else "") or ""
            para = cell.paragraphs[0]
            pic = pics.get((ri, ci))
            if pic:
                w = (widths[ci] if ci < len(widths) else 90) - 6
                _place(para, pic, max(24.0, w), dropped)
                if not text.strip():
                    continue
                para = cell.add_paragraph()
            crtl = is_rtl(text) if text.strip() else rtl
            _rtl_paragraph(para, crtl)
            para.alignment = ALIGN_START   # see ALIGN_START: correct both ways
            for piece, prtl in directional(text, crtl):
                run = para.add_run(piece)
                run.font.size = Pt(body_pt)
                _style(run, ri == 0, False)
                _rtl_run(run, body_pt, font, prtl)
    return t


# What follows w:pBdr and w:shd in a paragraph's properties, in schema order.
PPR_AFTER_SHD = ("w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
                 "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE",
                 "w:autoSpaceDN", "w:bidi", "w:adjustRightInd", "w:snapToGrid",
                 "w:spacing", "w:ind", "w:contextualSpacing", "w:mirrorIndents",
                 "w:suppressOverlap", "w:jc", "w:textDirection",
                 "w:textAlignment", "w:textboxTightWrap", "w:outlineLvl",
                 "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange")


def _band(p, block):
    """The band drawn behind this text in the original (reader._band_fills):
    the paragraph shaded, and outlined where the band was. Word joins
    neighbouring paragraphs shaded and outlined alike into one box."""
    if not block.fill:
        return
    pPr = p._p.get_or_add_pPr()
    if block.boxed:
        bdr = OxmlElement("w:pBdr")
        for side in ("top", "left", "bottom", "right"):
            e = OxmlElement(f"w:{side}")
            e.set(qn("w:val"), "single")
            e.set(qn("w:sz"), "4")
            e.set(qn("w:space"), "1")
            e.set(qn("w:color"), "auto")
            bdr.append(e)
        pPr.insert_element_before(bdr, "w:shd", *PPR_AFTER_SHD)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), block.fill)
    pPr.insert_element_before(shd, *PPR_AFTER_SHD)


def _border(p, side, style, eighths, colour):
    """One side of a paragraph's border, added to any it already has."""
    pPr = p._p.get_or_add_pPr()
    bdr = pPr.find(qn("w:pBdr"))
    if bdr is None:
        bdr = OxmlElement("w:pBdr")
        pPr.insert_element_before(bdr, "w:shd", *PPR_AFTER_SHD)
    for old in bdr.findall(qn(f"w:{side}")):
        bdr.remove(old)
    e = OxmlElement(f"w:{side}")
    e.set(qn("w:val"), style)
    e.set(qn("w:sz"), str(eighths))
    e.set(qn("w:space"), "1")
    e.set(qn("w:color"), colour)
    # Schema order inside w:pBdr: top, left, bottom, right, between, bar.
    order = ["top", "left", "bottom", "right", "between", "bar"]
    later = [x for x in bdr if x.tag.split("}")[1] in order[order.index(side) + 1:]]
    if later:
        later[0].addprevious(e)
    else:
        bdr.append(e)


# The line ruled under the running header (reader._header_rule), as a border
# on Word's header paragraph - on an empty one where the header has no text.
HEADER_RULE_OUT_ON = os.environ.get("QIRTAS_HEADER_RULE", "1") != "0"


def _header_rules(doc, model):
    if not HEADER_RULE_OUT_ON or not model.header_rules:
        return
    section = doc.sections[0]
    parts = [section.header]
    if doc.settings.odd_and_even_pages_header_footer:
        parts.append(section.even_page_header)
    for part in parts:
        part.is_linked_to_previous = False
        paras = part.paragraphs or [part.add_paragraph()]
        for side, style, eighths, colour in model.header_rules:
            p = paras[0] if side == "top" else paras[-1]
            _border(p, side, style, eighths, colour)


def _ink(run, block):
    """Text on a band in its own colour - white on a black band."""
    if block.fill and block.ink:
        run.font.color.rgb = RGBColor.from_string(block.ink)


def _shade(cell, colour):
    """Fill a table cell with the original's shading (reader._cell_fills)."""
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), colour)
    # Schema order: w:shd comes after the width, borders and merge, before
    # the margins and alignment. Placed after whatever of those is there.
    before = [qn(x) for x in ("w:noWrap", "w:tcMar", "w:textDirection",
                              "w:tcFitText", "w:vAlign", "w:hideMark")]
    nxt = next((e for e in tcPr if e.tag in before), None)
    if nxt is not None:
        nxt.addprevious(shd)
    else:
        tcPr.append(shd)


TWIPS_PER_PT = 20


def _fix_columns(table, widths_pt, rows):
    """Pin the column widths.

    Setting cell widths alone did nothing - twice. Word ignores them unless the
    table also declares a fixed layout AND carries a w:tblGrid saying how wide
    each column is. Without both, columns are shared out evenly and long cells
    wrap one word per line, turning a table into a tall ladder.
    """
    table.autofit = False
    tblPr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)

    grid = table._tbl.find(qn("w:tblGrid"))
    if grid is not None:
        table._tbl.remove(grid)
    grid = OxmlElement("w:tblGrid")
    for w in widths_pt:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(int(w * TWIPS_PER_PT)))
        grid.append(col)
    tblPr.addnext(grid)

    for ci, w in enumerate(widths_pt):
        for ri in range(len(rows)):
            try:
                table.cell(ri, ci).width = Emu(int(w * PT_PER_EMU))
            except Exception:
                pass


# Give Word the height the picture was drawn at, not only its width. Word
# otherwise keeps the file's own shape, and authors often squash a picture to
# fit: drawn at its own shape it came out up to 41pt taller (z21418248).
SHAPE_ON = os.environ.get("QIRTAS_IMG_SHAPE", "1") != "0"


def _place(para, path, width_pt, dropped, height_pt=None):
    """Draw a picture into a paragraph. -> True if it went in.

    python-docx identifies an image by its literal signature bytes and raises on
    anything it does not recognise - a bare DCT JPEG with no APP0/JFIF segment,
    for instance. The reader re-renders those to PNG before we ever get here, so
    reaching this `except` means something got past that. Record it: a silent
    drop is how one missing picture survived weeks of runs unnoticed.
    """
    try:
        height = Emu(int(height_pt * PT_PER_EMU)) if height_pt else None
        para.add_run().add_picture(path, width=Emu(int(width_pt * PT_PER_EMU)),
                                   height=height)
        return True
    except Exception as e:
        dropped.append((str(path), f"{type(e).__name__}: {e}"))
        return False


def _emit_image(doc, block, column_pt, k=1.0, dropped=None):
    """Place a picture at the size it was drawn at, capped to the text column."""
    width = (block.x1 - block.x0) * k
    height = (block.y1 - block.y) * k if SHAPE_ON else 0
    if width <= 0 or width > column_pt:
        # Capped: keep the drawn shape, not the file's.
        if width > 0 and height > 0:
            height *= column_pt / width
        width = column_pt
    p = doc.add_paragraph()
    _rtl_paragraph(p)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if not _place(p, block.image, width, dropped if dropped is not None else [],
                  height if height > 0 else None):
        # Take the paragraph back out. Left in, it is an empty paragraph eating
        # a line on the page - the same defect the page-break comment in write()
        # warns about, and it would push pagination out of step for free.
        p._element.getparent().remove(p._element)
        return None
    return p


def _emit(doc, block, body_pt=BODY_PT, pitch=0.0, font=None, first_on_page=False,
          notes=None, base_pt=None):
    size = body_pt
    bold = block.bold
    align = WD_ALIGN_PARAGRAPH.JUSTIFY

    if block.kind == HEADING:
        size = round(body_pt * (1.35 if (block.level or 2) == 1 else 1.15), 1)
        bold = True
        # START, not RIGHT - and in OOXML that is spelled "left". See ALIGN_START.
        align = ALIGN_START
    elif block.kind == FOOTNOTE:
        size = max(7.0, round(body_pt * 0.78, 1))
    # The size the original set it at, shrunk as the page is (body_pt is the
    # body size times the page's fitting scale). Every paragraph was the body
    # size and every heading 1.15 or 1.35 of it: a title page's 22pt title
    # came out near 14pt, its 18pt names at 12 (`z20782957`, Part 3).
    if OWN_SIZE_ON and base_pt and block.text_size:
        size = max(6.0, round(block.text_size * body_pt / base_pt, 1))

    rtl = is_rtl(block.text)
    if not rtl and block.kind != HEADING:
        align = WD_ALIGN_PARAGRAPH.JUSTIFY
    p = doc.add_paragraph()
    if block.kind == HEADING:
        _heading_style(p, block.level or 2)
    _rtl_paragraph(p, rtl)
    p.alignment = align
    _band(p, block)

    pf = p.paragraph_format
    # Exact pitch, not a multiplier: the measured gap between lines is what the
    # original actually used, and a multiplier plus paragraph gaps overflowed
    # every page, doubling the page count.
    if pitch:
        # The body's line height, grown or shrunk with the text: set at its
        # own size (OWN_SIZE_ON), a 22pt title under a 12pt body's exact
        # line height had its two lines drawn over each other (`z20782957`).
        own = OWN_SIZE_ON and base_pt and block.text_size
        share = size / body_pt if own else (1.0 if block.kind != FOOTNOTE else 0.62)
        pf.line_spacing = Pt(pitch * FIT * share)
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if block.kind == HEADING:
        pf.space_before = Pt(4)
    elif block.kind == FOOTNOTE:
        if first_on_page:
            _top_border(p)
    elif block.kind == LIST_ITEM:
        # "left" means START here, exactly as it does for w:jc - see
        # ALIGN_START. Measured on a rendered page: in a right-to-left
        # paragraph left_indent moves the text 72pt off the RIGHT margin,
        # while right_indent moves it nowhere visible. The old line set
        # right_indent "because this is RTL", which indented the far edge and
        # left the marker where it was.
        pf.left_indent = Pt(LIST_INDENT)
        # Negative first line = hanging indent, so the bullet or number sits
        # outside the text column and the wrapped lines line up under the text
        # rather than under the marker.
        pf.first_line_indent = Pt(-LIST_HANG)
    else:
        pf.first_line_indent = Pt(24)

    # One Word run per run of like-formatted text, so a bold phrase inside a
    # paragraph stays a bold phrase. A heading was bold as a whole whatever the
    # original did; where the reading kept its formatting, it now keeps the
    # original's - an author can style a plain sentence as a heading
    # (`z3387756`'s thanks page), and a third of the bold in ours was headings
    # the original did not bold (Part 3, 2026-09-24). Bold as a whole only
    # where the reading has no formatting to go by.
    own = HEADING_OWN_ON and block.kind == HEADING and block.spans
    parts = block.spans if (block.spans and block.kind != HEADING) or own else \
        [(block.text, bold, False)]

    def add(text, sbold, sital, lead=False):
        # English in an Arabic paragraph is a run of its own (`directional`).
        for piece, prtl in directional((" " if lead else "") + text, rtl):
            run = p.add_run(piece)
            run.font.size = Pt(size)
            _style(run, sbold, sital)
            if block.kind == HEADING:
                # Stated outright, not left to inherit. Word's Heading styles
                # are blue (#2F5496), and the original document's are not.
                run.font.color.rgb = RGBColor(0, 0, 0)
            _ink(run, block)
            _rtl_run(run, size, font, prtl)
        return run

    for n, (text, sbold, sital) in enumerate(parts):
        lead = bool(n)
        # "ابن مجاهد(2)" - the marker becomes a real reference and the digits
        # go away, because Word draws the number itself and would otherwise
        # print it twice.
        for piece, num in _split_markers(text, notes or {}):
            if num is None:
                for bit, raised in _raised(piece):
                    run = add(bit, sbold, sital, lead)
                    if raised:
                        _superscript(run)
                    lead = False
                continue
            if num not in notes:          # already used earlier in this page
                continue
            _footnote_ref(add("", sbold, sital, lead), _take(notes, num))
            lead = False
    return p


def _split_markers(text, notes):
    """-> [(text, None) | ("", number)] splitting on markers we have a note for."""
    out, at = [], 0
    for m in FN_MARKER.finditer(text):
        num = (m.group(1) or m.group(2)).translate(WESTERN)
        if num not in notes:
            continue
        out.append((text[at:m.start()], None))
        out.append(("", num))
        at = m.end()
    out.append((text[at:], None))
    return out


def _raised(text):
    """-> [(text, raised)]. A raised reference the reader found but no note
    claimed is written back as the small raised digits it was. As "(13)" it
    would be text the original never printed."""
    out, at = [], 0
    for m in RAISED.finditer(text or ""):
        if m.start() > at:
            out.append((text[at:m.start()], False))
        out.append((m.group(1), True))
        at = m.end()
    if at < len(text or ""):
        out.append((text[at:], False))
    return out


def _superscript(run):
    va = OxmlElement("w:vertAlign")
    va.set(qn("w:val"), "superscript")
    run._r.get_or_add_rPr().append(va)


def _take(notes, num):
    """A note is referenced once. "(1)" occurring twice on a page is a citation
    the second time, not a second marker for the same note."""
    return notes.pop(num)


def _footnote_ref(run, wid):
    """Turn an empty run into a superscript reference to footnote `wid`, or
    to an endnote when `wid` is ("endnote", id)."""
    note = "footnote"
    if isinstance(wid, tuple):
        note, wid = wid
    rPr = run._r.get_or_add_rPr()
    va = OxmlElement("w:vertAlign")
    va.set(qn("w:val"), "superscript")
    rPr.append(va)
    ref = OxmlElement(f"w:{note}Reference")
    ref.set(qn("w:id"), str(wid))
    run._r.append(ref)


def _note_style(block):
    """(bold, italic) for a whole note: what most of its letters are. A note
    goes to Word as one run of text (footnotes.build_xml), and a bold note -
    `z18441713`'s are bold throughout - came out regular."""
    spans = [s for s in (block.spans or []) if s[0].strip()]
    n = sum(len(t) for t, *_ in spans)
    if not n or not CS_STYLE_ON:
        return False, False
    return (sum(len(t) for t, b, *_ in spans if b) * 2 > n,
            sum(len(t) for t, _, i, *_ in spans if i) * 2 > n)


def _note_pieces(block, num, rest):
    """The note's text after its number, as [(text, bold, italic)] pieces in
    the original's own formatting - `z18037898` bolds the book's title in
    each note, `z18048055` the sura's name, and a note went to Word all
    regular. Taken from the reading's pieces only where they spell exactly
    the same note; otherwise the plain text, for the whole-note style."""
    plain = RAISED.sub(r"\1", rest)
    spans = [s for s in (block.spans or []) if s[0]]
    if not NOTE_LOOK_ON or not CS_STYLE_ON or not spans:
        return plain
    joined = " ".join(t for t, *_ in spans)
    m = FN_NUMBER.match(joined)
    if not m or m.group(1).translate(WESTERN) != num \
            or RAISED.sub(r"\1", joined[m.end():].strip()) != plain:
        return plain
    skip = m.end()
    out, at = [], 0
    for n, (t, b, i, *_) in enumerate(spans):
        t = (" " if n else "") + t
        cut = max(0, min(len(t), skip - at))
        at += len(t)
        piece = t[cut:]
        if not piece:
            continue
        if out and out[-1][1:] == (bool(b), bool(i)):
            out[-1] = (out[-1][0] + piece, bool(b), bool(i))
        else:
            out.append((piece, bool(b), bool(i)))
    out = [(RAISED.sub(r"\1", t), b, i) for t, b, i in out]
    if "".join(t for t, *_ in out).strip() != plain or \
            not any(b or i for _, b, i in out):
        return plain
    out[0] = (out[0][0].lstrip(),) + out[0][1:]
    out[-1] = (out[-1][0].rstrip(),) + out[-1][1:]
    return out


NOTE_LOOK_ON = os.environ.get("QIRTAS_NOTE_LOOK", "1") != "0"


def _note_size(model):
    """The size the original's notes were set at - the commonest, by letters -
    else 0.78 of the body. The fixed share made notes far too small where a
    thesis sets them at 12pt under a 14pt body (Moaz's page 13)."""
    sizes = Counter()
    for b in model.blocks:
        if b.kind == FOOTNOTE and b.size:
            sizes[round(b.size * 2) / 2] += len(b.text)
    fallback = max(7.0, model.body_size * 0.78)
    if not NOTE_SIZE_ON or not sizes:
        return fallback
    return max(7.0, min(sizes.most_common(1)[0][0], model.body_size))


NOTE_SIZE_ON = os.environ.get("QIRTAS_NOTE_SIZE", "1") != "0"


def _endnotes(pages):
    """Notes printed together at the END of the document, each referred to
    from an earlier page.

    Word labels endnotes and footnotes alike, so the reader cannot tell them
    apart; where they are printed can. A note becomes an endnote when its own
    page does not refer to its number but an earlier page does - the earliest
    such page is where the reference goes. `z21763864` prints all its notes
    on its last six pages, referred to from pages 2 to 18; paired page by page
    as footnotes, not one of them was found.

    Only when the document really ends with its notes: at least ENDNOTES_MIN
    of them pair up this way, and none sits before a page that refers to one.
    Without that, `z21764080` - footnotes, and a heading "1.1" - had a page-13
    note paired with the heading's "1" on page 1 as an "endnote".

    Endnote blocks are taken out of `pages`: Word prints endnotes itself, and
    pages left with nothing are dropped, or Word would print them blank.
    -> ({page: {number: ("endnote", w:id)}}, [(w:id, text)])
    """
    refs = {}                 # number -> earliest page whose body cites it
    for page, blocks in pages.items():
        body = " ".join(b.text for b in blocks
                        if b.kind not in (FOOTNOTE, IMAGE, TABLE))
        for num in marker_numbers(body):
            refs.setdefault(num, page)
    found = []                # (note page, block, number, rest, cited on)
    for page, blocks in pages.items():
        own = " ".join(b.text for b in blocks
                       if b.kind not in (FOOTNOTE, IMAGE, TABLE))
        own_refs = set(marker_numbers(own))
        for b in blocks:
            if b.kind != FOOTNOTE:
                continue
            num, rest = split_number(b.text)
            if num is None or not rest or num in own_refs:
                continue
            at = refs.get(num)
            if at is not None and at < page:
                found.append((page, b, num, rest, at))
    if len(found) < ENDNOTES_MIN or \
            min(f[0] for f in found) <= max(f[4] for f in found):
        return {}, []
    anchors, notes, wid = {}, [], FIRST_ID
    for page, b, num, rest, at in found:
        if num in anchors.get(at, {}):
            continue
        anchors.setdefault(at, {})[num] = ("endnote", wid)
        notes.append((wid, RAISED.sub(r"\1", rest)))
        wid += 1
        pages[page].remove(b)
    # A page that held little but endnotes goes: kept, it printed nearly
    # blank - five of them in `z21763864`, each left with only its running
    # line "2016 10 - 26 -". That scrap is not dropped (nothing may be lost);
    # it joins the page before.
    order = list(pages)
    for page in sorted({f[0] for f in found}):
        left = pages[page]
        if sum(len(b.text) for b in left) > ENDNOTE_PAGE_SCRAP or \
                any(b.kind in (IMAGE, TABLE) for b in left):
            continue
        before = [p for p in order if p < page and p in pages]
        if before:
            pages[before[-1]].extend(left)
        elif left:
            continue
        del pages[page]
    return anchors, notes


def write(model: Doc, out_path, scale=None):
    doc = Document()
    _scrub(model)
    _show_digits(model)
    _page_setup(doc, model)
    # write() is called repeatedly on the same model by the fit loop, so start
    # from empty rather than accumulating the same drops once per round.
    model.dropped_images = []

    scale = scale or {}
    # Page decoration goes to the header or footer, and a page whose pictures
    # would not fit gets them shrunk. Both exist to stop a page spilling: one
    # page taking two pushes every page after it out of step, permanently.
    # A first page photographed whole already shows its own header and footer;
    # Word's must not be drawn over it. See reader._collage.
    if any(b.collage and b.page == 0 for b in model.blocks):
        doc.sections[0].different_first_page_header_footer = True
    lift, draw = _running_furniture(model)
    if draw:
        _draw_furniture(doc, draw, model, model.dropped_images)
    tlift, tdraw = _running_text(model)
    if tdraw:
        _draw_text_furniture(doc, tdraw, model)
        _first_page_number(doc, model, tdraw, tlift)
        lift = {**lift, **tlift}
    _header_rules(doc, model)
    front = _bare_front(model, lift)
    if front:
        # The main section now starts at page `front`: its first number is
        # the one printed there, not on page 0.
        for el in doc.sections[0]._sectPr.findall(qn("w:pgNumType")):
            el.set(qn("w:start"), str(int(el.get(qn("w:start"), "1")) + front))
    img_fit = _image_fit(model, lift)

    by_page = {}
    for b in model.blocks:
        if id(b) in lift:
            continue
        by_page.setdefault(b.page, []).append(b)

    # Walk every page of the original, including ones with no text (title pages
    # are often a single image). Skipping them shifted everything that followed
    # onto the wrong page.
    last = max(by_page) if by_page else -1
    pages = OrderedDict((i, by_page.get(i, []))
                        for i in range(max(model.pages, last + 1)))

    real_notes = []          # [(w:id, text, bold, italic)] for footnotes.xml
    next_id = FIRST_ID
    end_anchors, end_notes = _endnotes(pages)

    body_el = doc.element.body
    front_el = None          # the first thing written on page `front`
    for n, (page, blocks) in enumerate(pages.items()):
        if front and n == front:
            # Content goes in just before the body's own w:sectPr, so the
            # last child now is the one the page's first element will follow.
            front_at = len(body_el) - 1
        body = [b for b in blocks if b.kind not in (FOOTNOTE, IMAGE, TABLE)]
        pics = [b for b in blocks if b.kind in (IMAGE, TABLE)]
        notes = [b for b in blocks if b.kind == FOOTNOTE]

        # Pair each note with its marker in this page's body. Numbering restarts
        # on every page, so this has to be done a page at a time. A note whose
        # marker is nowhere to be found stays an ordinary paragraph at the foot
        # of the page - the old behaviour - rather than being anchored wrongly.
        anchors, loose = {}, []
        page_text = " ".join(b.text for b in body)
        for b in notes:
            num, rest = split_number(b.text)
            if num is None or num in anchors or not rest \
                    or not FN_MARKER.search(page_text) \
                    or num not in marker_numbers(page_text):
                loose.append(b)
                continue
            anchors[num] = next_id
            real_notes.append((next_id, _note_pieces(b, num, rest),
                               *_note_style(b)))
            next_id += 1
        notes = loose
        # This page's references to endnotes, where a footnote on the page
        # has not already claimed the number.
        anchors = {**end_anchors.get(page, {}), **anchors}
        body = _beside(_interleave(body, pics, model))
        k = scale.get(page, 1.0)
        first = True
        if not blocks:
            para = doc.add_paragraph()
            _rtl_paragraph(para)
            if n:
                para.paragraph_format.page_break_before = True
            continue
        column = model.page_width - model.margin_left - model.margin_right
        above = None             # the text block written last on this page
        # Only on a page with little text - a title page, a chapter's cover.
        # On body pages the original's gaps pushed pages over: ours are
        # fuller than the original's (side-by-side blocks stacked), and
        # right page on the quick set fell 53.4 -> 40.2% (`z20782957` 13
        # pages -> 14).
        spaced = sum(len(b.text.split()) for b in body if b.kind not in (IMAGE, TABLE)) \
            < GAP_PAGE_WORDS
        for b in body + notes:
            if isinstance(b, Beside):
                _emit_beside(doc, b, model, k, img_fit.get(page, 1.0), anchors,
                             first and n)
                first = False
                above = b
                continue
            if b.kind == IMAGE:
                para = _emit_image(doc, b, column, k * img_fit.get(page, 1.0),
                                   model.dropped_images)
                if para is None:
                    continue
                # What comes next is measured from the picture's foot, not
                # from the top of the page: a title page's first line under
                # its logo got the logo's height again as space, and ran over.
                above = b
            elif b.kind == TABLE:
                tbl = _emit_table(doc, b, model.body_size * k, model.font,
                                  model.dropped_images)
                if tbl is None:
                    continue
                # A w:tbl cannot carry w:pageBreakBefore itself, and the
                # paragraph added below sits AFTER the table - so breaking
                # there left a page that BEGINS with a table on the previous
                # page, and everything on it one out of step. 60 of the 72
                # pages of z10442411.pdf begin with a table. The break goes on
                # the first paragraph of the first cell, which is where a
                # renderer looks to start a table on a new page.
                if first and n:
                    tbl.cell(0, 0).paragraphs[0].paragraph_format \
                        .page_break_before = True
                    first = False
                para = doc.add_paragraph()
                _rtl_paragraph(para)
                above = b
            else:
                para = _emit(doc, b, model.body_size * k, model.line_pitch * k, model.font,
                             first_on_page=(b.kind == FOOTNOTE and b is notes[0] if notes else False),
                             notes=anchors if b.kind != FOOTNOTE else None,
                             base_pt=model.body_size)
                if b.kind in (HEADING, PARAGRAPH) and _centred(b, model):
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if b.kind != FOOTNOTE and spaced:
                    gap = _gap_above(b, above, model)
                    if gap:
                        para.paragraph_format.space_before = Pt(gap * k * FIT)
                    above = b
            if first and n:
                # break BEFORE this paragraph rather than inserting an empty one:
                # the empty paragraph ate a line on every page and the overflow
                # pushed pagination steadily out of step.
                para.paragraph_format.page_break_before = True
            first = False

    if front and front < len(pages):
        front_el = body_el[front_at]
        if front_el.tag != qn("w:sectPr"):
            _end_front(doc, front_el)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    note_pt = _note_size(model)
    # The notes' line and line height as the original has them (NOTE_LOOK_ON).
    look = dict(pitch=model.note_pitch, rule=model.note_rule,
                width=model.page_width - model.margin_left - model.margin_right) \
        if NOTE_LOOK_ON else {}
    if real_notes:
        install(str(out_path), build_xml(real_notes,
                                         font=model.font or ARABIC_FONT,
                                         size_pt=note_pt, **look))
    if end_notes:
        install(str(out_path), build_xml(end_notes,
                                         font=model.font or ARABIC_FONT,
                                         size_pt=note_pt,
                                         note="endnote"), note="endnote")
    if model.dropped_images:
        n = len(model.dropped_images)
        print(f"warning: {n} picture{'s' if n > 1 else ''} could not be placed "
              f"in {Path(out_path).name}", file=sys.stderr)
        for path, why in model.dropped_images[:5]:
            print(f"  {Path(path).name}: {why}", file=sys.stderr)
        if n > 5:
            print(f"  ... and {n - 5} more", file=sys.stderr)
    return out_path
