"""The writer: turn the description into a Word file.

The only part that knows about Word. Everything right-to-left lives here -
paragraph direction, run direction, and the complex-script font - the three
things every other tool we tested forgets.
"""
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


def _emit(doc, block, body_pt=BODY_PT, pitch=0.0, font=None, first_on_page=False):
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

    run = p.add_run(block.text)
    run.font.size = Pt(size)
    run.bold = bold
    _rtl_run(run, size, font, rtl)
    return p


def write(model: Doc, out_path, scale=None):
    doc = Document()
    _page_setup(doc, model)

    scale = scale or {}
    by_page = {}
    for b in model.blocks:
        by_page.setdefault(b.page, []).append(b)

    # Walk every page of the original, including ones with no text (title pages
    # are often a single image). Skipping them shifted everything that followed
    # onto the wrong page.
    last = max(by_page) if by_page else -1
    pages = OrderedDict((i, by_page.get(i, []))
                        for i in range(max(model.pages, last + 1)))

    for n, (page, blocks) in enumerate(pages.items()):
        body = [b for b in blocks if b.kind not in (FOOTNOTE, IMAGE, TABLE)]
        pics = [b for b in blocks if b.kind in (IMAGE, TABLE)]
        notes = [b for b in blocks if b.kind == FOOTNOTE]
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
                para = _emit_image(doc, b, column, k)
                if para is None:
                    continue
            elif b.kind == TABLE:
                if _emit_table(doc, b, model.body_size * k, model.font) is None:
                    continue
                para = doc.add_paragraph()
                _rtl_paragraph(para)
            else:
                para = _emit(doc, b, model.body_size * k, model.line_pitch * k, model.font,
                             first_on_page=(b.kind == FOOTNOTE and b is notes[0] if notes else False))
            if first and n:
                # break BEFORE this paragraph rather than inserting an empty one:
                # the empty paragraph ate a line on every page and the overflow
                # pushed pagination steadily out of step.
                para.paragraph_format.page_break_before = True
            first = False

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path
