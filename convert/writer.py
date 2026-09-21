"""The writer: turn the description into a Word file.

The only part that knows about Word. Everything right-to-left lives here -
paragraph direction, run direction, and the complex-script font - the three
things every other tool we tested forgets.
"""
import hashlib
import re
import sys
from collections import OrderedDict
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH as _AL

from convert.model import Doc, HEADING, FOOTNOTE, LIST_ITEM, IMAGE, TABLE
from convert.footnotes import (MARKER as FN_MARKER, FIRST_ID, split_number,
                               build_xml, install)

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
# How much of a page a stack of pictures may claim. Measured, not chosen: at
# 0.95 a picture-only title page still needed two pages, at 0.88 it fitted, and
# below that nothing more was gained. 0.85 leaves room for the paragraph each
# picture sits in and for a header taller than the top margin.
#
# This has to be right first time. fit.py cannot rescue it: _spilled() matches
# rendered pages to original ones by shared words and skips any original page
# that has none, so a page of nothing but pictures is invisible to it.
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
    """
    for b in model.blocks:
        b.text = _xml_safe(b.text)
        if b.spans:
            b.spans = [(_xml_safe(t), *rest) for t, *rest in b.spans]
        if b.rows:
            b.rows = [[_xml_safe(c) for c in row] for row in b.rows]


def _flag(parent, tag, val="1"):
    e = OxmlElement(tag)
    e.set(qn("w:val"), val)
    parent.append(e)


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
    outside = [b for b in model.blocks if b.kind == IMAGE and b.image
               and not (top <= (b.y + b.y1) / 2 <= bottom)]
    if not outside:
        return {}, {}
    pages = max(1, model.pages)
    groups = {}
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
        groups.setdefault(key, []).append(b)
    lift, draw = {}, {}
    for key, blocks in groups.items():
        if len({b.page for b in blocks}) < max(2, pages // 2):
            continue                       # a one-off, leave it in the flow
        where = "header" if (blocks[0].y + blocks[0].y1) / 2 < top else "footer"
        draw.setdefault(where, []).append(blocks[0])
        for b in blocks:
            lift[id(b)] = where
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
DIGITS = re.compile(r"[0-9\u0660-\u0669\u06F0-\u06F9]+")
ONLY_PAGE_NO = re.compile(r"^[\s.\-\u2013\u2014()\[\]]*"
                          r"[0-9\u0660-\u0669\u06F0-\u06F9]{1,4}"
                          r"[\s.\-\u2013\u2014()\[\]]*$")


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

    Two things make this harder than the picture case:

    - **The page number is different on every page**, so grouping by exact text
      finds nothing. Digits are replaced by a placeholder before grouping, so
      "82" and "83" are recognised as the same piece of furniture.
    - **The tags route carries no coordinates for text** (the geometry route
      does). Where there is no y, position on the page cannot be used at all,
      so the first or last block of its page is what counts as an edge.

    Repetition is the real signal and is route-independent: a Word header is
    drawn on every page, so lifting something that appears once would stamp it
    across the whole document.

    -> ({id(block): "header"|"footer"}, {"header"|"footer": Block})
    """
    pages = max(1, model.pages)
    if pages < 4:
        # Too few pages for "repeats on most of them" to mean anything.
        return {}, {}
    top, bottom = _text_column(model)

    by_page = {}
    for b in model.blocks:
        if b.kind in (IMAGE, TABLE) or not b.text.strip():
            continue
        by_page.setdefault(b.page, []).append(b)

    def edge(b):
        # Coordinates decide it when they put the block clearly outside the
        # column. They often do not, and the reason is circular: the margins
        # are MEASURED from the content, and the running header is part of that
        # content, so the column is drawn to include it and it never looks
        # outside. That is why the journal line was missed on the first attempt
        # here while the page numbers were found.
        if b.y or b.y1:
            mid = (b.y + b.y1) / 2
            if mid < top:
                return "header"
            if mid > bottom:
                return "footer"
        # Fall back to where it sits in the page's reading order. This is the
        # only test available on the tags route, which carries no coordinates
        # for text at all. Repetition is what makes it safe: being first on the
        # page is ordinary, being first on the page with the same words every
        # time is furniture.
        sibs = by_page.get(b.page) or []
        if sibs and b is sibs[0]:
            return "header"
        if sibs and b is sibs[-1]:
            return "footer"
        return None

    groups = {}
    for sibs in by_page.values():
        for b in sibs:
            flat = WS_RUN.sub(" ", b.text.strip())
            if len(flat) > RUNNING_MAX_CHARS:
                continue
            where = edge(b)
            if not where:
                continue
            groups.setdefault((where, DIGITS.sub("#", flat)), []).append(b)

    need = max(3, pages // 2)
    lift, draw = {}, {}
    for (where, _), blocks in sorted(groups.items(),
                                     key=lambda kv: -len({b.page for b in kv[1]})):
        if len({b.page for b in blocks}) < need or where in draw:
            continue
        draw[where] = blocks[0]
        for b in blocks:
            lift[id(b)] = where
    return lift, draw


def _page_number_start(model, block):
    """What number the original printed on its FIRST page. -> int or None.

    A PAGE field numbers from 1, but these are chapters and offprints: page 9
    of `z21011460` is printed 82. Without an offset the footer would contradict
    every cross-reference in the text.
    """
    flat = WS_RUN.sub(" ", block.text.strip())
    if not ONLY_PAGE_NO.match(flat):
        return None
    m = DIGITS.search(flat)
    if not m:
        return None
    try:
        shown = int("".join(str(ord(c) & 0xF) if ord(c) > 0x600 else c
                            for c in m.group(0)))
    except ValueError:
        return None
    start = shown - block.page
    return start if start > 0 else None


def _draw_text_furniture(doc, draw, model):
    """Put the running header and footer text into Word's header and footer.

    A page number becomes a real PAGE field rather than the literal digits, or
    every page of the Word file would read 82.
    """
    section = doc.sections[0]
    # The block's OWN measured size, not a fraction of the body size. The
    # journal line on z21011460 is 8pt and drawn 332pt wide in a 378pt column;
    # writing it at 0.8 x 12pt body made it 9.6pt, about 398pt wide, and it
    # wrapped onto a second line the original never had.
    fallback = max(7.0, round(model.body_size * 0.8, 1))
    for where, block in draw.items():
        size = block.size if block.size and block.size >= 5 else fallback
        part = section.header if where == "header" else section.footer
        part.is_linked_to_previous = False
        p = part.paragraphs[0] if part.paragraphs else part.add_paragraph()
        if p.text.strip() or p.runs:
            p = part.add_paragraph()
        rtl = is_rtl(block.text)
        _rtl_paragraph(p, rtl)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        start = _page_number_start(model, block)
        if start is not None:
            fld = OxmlElement("w:fldSimple")
            fld.set(qn("w:instr"), " PAGE ")
            r = OxmlElement("w:r")
            t = OxmlElement("w:t")
            t.text = str(start + block.page)
            r.append(t)
            fld.append(r)
            p._p.append(fld)
            _set_page_number_start(section, start)
        else:
            run = p.add_run(WS_RUN.sub(" ", block.text.strip()))
            run.font.size = Pt(size)
            _rtl_run(run, size, model.font, rtl)


def _set_page_number_start(section, start):
    """Make Word's own numbering begin where the original's did."""
    pr = section._sectPr
    for old in pr.findall(qn("w:pgNumType")):
        pr.remove(old)
    el = OxmlElement("w:pgNumType")
    el.set(qn("w:start"), str(max(1, start)))
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
            _place(p, b.image, width, dropped)


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
    out = list(body)
    for pic in sorted(pics, key=lambda b: b.y, reverse=True):
        if pic.y <= 0:
            out.append(pic)
            continue
        frac = min(1.0, max(0.0, (pic.y - top) / span))
        out.insert(int(round(frac * len(body))), pic)
    return out


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
    if block.col_widths and len(block.col_widths) == width:
        order = [max(18.0, w) for w in block.col_widths]
        if rtl:
            order = list(reversed(order))
        _fix_columns(t, order, rows)
    # Mirror the columns only for a table that is actually right-to-left. An
    # English table was being mirrored too, which reversed a table that was
    # never right-to-left.
    if rtl:
        _flag(t._tbl.tblPr, "w:bidiVisual")
    for ri, row in enumerate(rows):
        for ci in range(width):
            cell = t.cell(ri, ci)
            text = (row[ci] if ci < len(row) else "") or ""
            para = cell.paragraphs[0]
            pic = block.cell_images.get((ri, ci))
            if pic:
                w = (block.col_widths[ci] if ci < len(block.col_widths) else 90) - 6
                _place(para, pic, max(24.0, w), dropped)
                if not text.strip():
                    continue
                para = cell.add_paragraph()
            crtl = is_rtl(text) if text.strip() else rtl
            _rtl_paragraph(para, crtl)
            para.alignment = ALIGN_START   # see ALIGN_START: correct both ways
            run = para.add_run(text)
            run.font.size = Pt(body_pt)
            run.bold = (ri == 0)
            _rtl_run(run, body_pt, font, crtl)
    return t


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


def _place(para, path, width_pt, dropped):
    """Draw a picture into a paragraph. -> True if it went in.

    python-docx identifies an image by its literal signature bytes and raises on
    anything it does not recognise - a bare DCT JPEG with no APP0/JFIF segment,
    for instance. The reader re-renders those to PNG before we ever get here, so
    reaching this `except` means something got past that. Record it: a silent
    drop is how one missing picture survived weeks of runs unnoticed.
    """
    try:
        para.add_run().add_picture(path, width=Emu(int(width_pt * PT_PER_EMU)))
        return True
    except Exception as e:
        dropped.append((str(path), f"{type(e).__name__}: {e}"))
        return False


def _emit_image(doc, block, column_pt, k=1.0, dropped=None):
    """Place a picture at the width it was drawn at, capped to the text column."""
    width = (block.x1 - block.x0) * k
    if width <= 0 or width > column_pt:
        width = column_pt
    p = doc.add_paragraph()
    _rtl_paragraph(p)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if not _place(p, block.image, width, dropped if dropped is not None else []):
        # Take the paragraph back out. Left in, it is an empty paragraph eating
        # a line on the page - the same defect the page-break comment in write()
        # warns about, and it would push pagination out of step for free.
        p._element.getparent().remove(p._element)
        return None
    return p


def _emit(doc, block, body_pt=BODY_PT, pitch=0.0, font=None, first_on_page=False,
          notes=None):
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

    rtl = is_rtl(block.text)
    if not rtl and block.kind != HEADING:
        align = WD_ALIGN_PARAGRAPH.JUSTIFY
    p = doc.add_paragraph()
    if block.kind == HEADING:
        _heading_style(p, block.level or 2)
    _rtl_paragraph(p, rtl)
    p.alignment = align

    pf = p.paragraph_format
    # Exact pitch, not a multiplier: the measured gap between lines is what the
    # original actually used, and a multiplier plus paragraph gaps overflowed
    # every page, doubling the page count.
    if pitch:
        pf.line_spacing = Pt(pitch * FIT * (1.0 if block.kind != FOOTNOTE else 0.62))
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
    # paragraph stays a bold phrase. A heading is bold as a whole, so its own
    # spans do not get to override that.
    parts = block.spans if (block.spans and block.kind != HEADING) else \
        [(block.text, bold, False)]

    def add(text, sbold, sital, lead=False):
        run = p.add_run((" " if lead else "") + text)
        run.font.size = Pt(size)
        run.bold = sbold
        run.italic = sital
        if block.kind == HEADING:
            # Stated outright, not left to inherit. Word's Heading styles are
            # blue (#2F5496), and the original document's headings are not.
            run.font.color.rgb = RGBColor(0, 0, 0)
        _rtl_run(run, size, font, rtl)
        return run

    for n, (text, sbold, sital) in enumerate(parts):
        lead = bool(n)
        # "ابن مجاهد(2)" - the marker becomes a real reference and the digits
        # go away, because Word draws the number itself and would otherwise
        # print it twice.
        for piece, num in _split_markers(text, notes or {}):
            if num is None:
                if piece:
                    add(piece, sbold, sital, lead)
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
        if m.group(1) not in notes:
            continue
        out.append((text[at:m.start()], None))
        out.append(("", m.group(1)))
        at = m.end()
    out.append((text[at:], None))
    return out


def _take(notes, num):
    """A note is referenced once. "(1)" occurring twice on a page is a citation
    the second time, not a second marker for the same note."""
    return notes.pop(num)


def _footnote_ref(run, wid):
    """Turn an empty run into a superscript reference to footnote `wid`."""
    rPr = run._r.get_or_add_rPr()
    va = OxmlElement("w:vertAlign")
    va.set(qn("w:val"), "superscript")
    rPr.append(va)
    ref = OxmlElement("w:footnoteReference")
    ref.set(qn("w:id"), str(wid))
    run._r.append(ref)


def write(model: Doc, out_path, scale=None):
    doc = Document()
    _scrub(model)
    _page_setup(doc, model)
    # write() is called repeatedly on the same model by the fit loop, so start
    # from empty rather than accumulating the same drops once per round.
    model.dropped_images = []

    scale = scale or {}
    # Page decoration goes to the header or footer, and a page whose pictures
    # would not fit gets them shrunk. Both exist to stop a page spilling: one
    # page taking two pushes every page after it out of step, permanently.
    lift, draw = _running_furniture(model)
    if draw:
        _draw_furniture(doc, draw, model, model.dropped_images)
    tlift, tdraw = _running_text(model)
    if tdraw:
        _draw_text_furniture(doc, tdraw, model)
        lift = {**lift, **tlift}
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

    real_notes = []          # [(w:id, text)] for footnotes.xml
    next_id = FIRST_ID

    for n, (page, blocks) in enumerate(pages.items()):
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
                    or num not in FN_MARKER.findall(page_text):
                loose.append(b)
                continue
            anchors[num] = next_id
            real_notes.append((next_id, rest))
            next_id += 1
        notes = loose
        body = _interleave(body, pics, model)
        k = scale.get(page, 1.0)
        first = True
        if not blocks:
            para = doc.add_paragraph()
            _rtl_paragraph(para)
            if n:
                para.paragraph_format.page_break_before = True
            continue
        column = model.page_width - model.margin_left - model.margin_right
        for b in body + notes:
            if b.kind == IMAGE:
                para = _emit_image(doc, b, column, k * img_fit.get(page, 1.0),
                                   model.dropped_images)
                if para is None:
                    continue
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
            else:
                para = _emit(doc, b, model.body_size * k, model.line_pitch * k, model.font,
                             first_on_page=(b.kind == FOOTNOTE and b is notes[0] if notes else False),
                             notes=anchors if b.kind != FOOTNOTE else None)
            if first and n:
                # break BEFORE this paragraph rather than inserting an empty one:
                # the empty paragraph ate a line on every page and the overflow
                # pushed pagination steadily out of step.
                para.paragraph_format.page_break_before = True
            first = False

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    if real_notes:
        install(str(out_path), build_xml(real_notes,
                                         font=model.font or ARABIC_FONT,
                                         size_pt=max(7.0, model.body_size * 0.78)))
    if model.dropped_images:
        n = len(model.dropped_images)
        print(f"warning: {n} picture{'s' if n > 1 else ''} could not be placed "
              f"in {Path(out_path).name}", file=sys.stderr)
        for path, why in model.dropped_images[:5]:
            print(f"  {Path(path).name}: {why}", file=sys.stderr)
        if n > 5:
            print(f"  ... and {n - 5} more", file=sys.stderr)
    return out_path
