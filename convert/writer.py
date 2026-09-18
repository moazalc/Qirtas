"""The writer: turn the description into a Word file.

The only part that knows about Word. Everything right-to-left lives here -
paragraph direction, run direction, and the complex-script font - the three
things every other tool we tested forgets.
"""
import hashlib
import re
from collections import OrderedDict
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt
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


def _flag(parent, tag, val="1"):
    e = OxmlElement(tag)
    e.set(qn("w:val"), val)
    parent.append(e)


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


def _draw_furniture(doc, draw, model):
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
            try:
                p.add_run().add_picture(b.image, width=Emu(int(width * PT_PER_EMU)))
            except Exception:
                continue


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


def _emit_table(doc, block, body_pt, font):
    """A real Word table, mirrored so column one sits on the right."""
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
                try:
                    w = (block.col_widths[ci] if ci < len(block.col_widths) else 90) - 6
                    para.add_run().add_picture(pic, width=Emu(int(max(24.0, w) * PT_PER_EMU)))
                except Exception:
                    pass
                if not text.strip():
                    continue
                para = cell.add_paragraph()
            crtl = is_rtl(text) if text.strip() else rtl
            _rtl_paragraph(para, crtl)
            para.alignment = WD_ALIGN_PARAGRAPH.RIGHT if crtl else WD_ALIGN_PARAGRAPH.LEFT
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


def _emit_image(doc, block, column_pt, k=1.0):
    """Place a picture at the width it was drawn at, capped to the text column."""
    p = doc.add_paragraph()
    _rtl_paragraph(p)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    width = (block.x1 - block.x0) * k
    if width <= 0 or width > column_pt:
        width = column_pt
    try:
        p.add_run().add_picture(block.image, width=Emu(int(width * PT_PER_EMU)))
    except Exception:
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
        align = WD_ALIGN_PARAGRAPH.RIGHT
    elif block.kind == FOOTNOTE:
        size = max(7.0, round(body_pt * 0.78, 1))

    rtl = is_rtl(block.text)
    if not rtl:
        align = WD_ALIGN_PARAGRAPH.LEFT if block.kind != HEADING else WD_ALIGN_PARAGRAPH.LEFT
    p = doc.add_paragraph()
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
        pf.right_indent = Pt(18)          # indent from the right, this is RTL
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
    _page_setup(doc, model)

    scale = scale or {}
    # Page decoration goes to the header or footer, and a page whose pictures
    # would not fit gets them shrunk. Both exist to stop a page spilling: one
    # page taking two pushes every page after it out of step, permanently.
    lift, draw = _running_furniture(model)
    if draw:
        _draw_furniture(doc, draw, model)
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
                para = _emit_image(doc, b, column, k * img_fit.get(page, 1.0))
                if para is None:
                    continue
            elif b.kind == TABLE:
                if _emit_table(doc, b, model.body_size * k, model.font) is None:
                    continue
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
    return out_path
