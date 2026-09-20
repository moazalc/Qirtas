#!/usr/bin/env python3
"""Tests for the things that pushed pages out of step.

    python -m harness.test_pagination

A page break is written before each original page's content, so a page that
needs two pages shifts every page after it - permanently, and the shifts add
up. On one chapter the document ended four pages out of step and only 12% of
words landed on the matching page.

None of them is text overflow.

  1. Two decorations sat at y=31 with a top margin of 71.6 - above the text
     column, a running header. Emitted as ordinary paragraphs they stole 96pt
     from every page's 735pt of usable height.
  2. A title page of 14 pictures was emitted one under another, stacking to
     1158pt against 735pt, so it took two pages before a word had been read.
  3. A page whose first block is a TABLE got its page break after the table
     instead of before it, so the table stayed on the previous page and
     everything on that page was one out of step. 60 of the 72 pages of
     z10442411.pdf begin with a table.
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert.model import Doc, Block, PARAGRAPH, IMAGE, TABLE
from convert.writer import write

FAILED = []
EMU_PER_PT = 12700


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}")
    if not ok:
        FAILED.append(name)


def _png(path, w, h, shade=128):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h))
    pix.clear_with(shade)
    pix.save(path)
    return str(path)


def _model(pages=4):
    m = Doc(pages=pages, page_width=595.0, page_height=842.0,
            margin_top=71.6, margin_bottom=35.6,
            margin_left=70.0, margin_right=70.0, body_size=12.0)
    return m


def _heights(docx, part="word/document.xml"):
    """Drawn height in points of every picture in a part."""
    with zipfile.ZipFile(docx) as z:
        if part not in z.namelist():
            return []
        xml = z.read(part).decode("utf-8")
    return [int(v) / EMU_PER_PT for v in re.findall(r'<wp:extent [^>]*cy="(\d+)"', xml)]


def _parts(docx, pattern):
    with zipfile.ZipFile(docx) as z:
        return [n for n in z.namelist() if re.match(pattern, n)]


def _break_after_table(docx):
    """Does a page break sit on something that FOLLOWS the table?

    That is the fault itself: the break was written onto the paragraph after
    the table, so a page beginning with a table kept the table on the page
    before. Where the break belongs instead is a question for the renderer,
    not for this test - see the rendered check.
    """
    with zipfile.ZipFile(docx) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    body = xml.split("<w:body>")[1]
    return "<w:pageBreakBefore/>" in body[body.index("</w:tbl>"):]


def _rendered_page_of(pdf, needle):
    """Which rendered page does this text land on? -> 0-based, or None."""
    with pymupdf.open(pdf) as d:
        for i, page in enumerate(d):
            if needle in page.get_text("text"):
                return i
    return None


def main():
    tmp = Path("out/tests/pagination")
    tmp.mkdir(parents=True, exist_ok=True)

    print("a decoration above the text column is a running header, not content")
    banner = _png(tmp / "banner.png", 240, 47)
    m = _model(pages=4)
    for p in range(4):
        # centre y = 54.6, above the 71.6pt top margin
        m.blocks.append(Block(kind=IMAGE, text="", page=p, image=banner,
                              x0=70, x1=313, y=31, y1=78))
        m.blocks.append(Block(kind=PARAGRAPH, text="نص الصفحة رقم %d هنا." % p,
                              page=p, y=200, y1=220))
    docx = tmp / "header.docx"
    write(m, str(docx))
    check("lifted out of the body flow", len(_heights(docx)), 0)
    check("a header part was written", bool(_parts(docx, r"word/header\d*\.xml$")), True)
    hdr = _parts(docx, r"word/header\d*\.xml$")
    check("drawn once in the header", len(_heights(docx, hdr[0])), 1)

    print("\na decoration appearing only once is not a running header")
    m = _model(pages=4)
    m.blocks.append(Block(kind=IMAGE, text="", page=0, image=banner,
                          x0=70, x1=313, y=31, y1=78))
    for p in range(4):
        m.blocks.append(Block(kind=PARAGRAPH, text="نص", page=p, y=200, y1=220))
    docx = tmp / "once.docx"
    write(m, str(docx))
    check("stays in the body", len(_heights(docx)), 1)

    print("\na page of stacked pictures must still fit on one page")
    tall = _png(tmp / "tall.png", 380, 570, shade=90)
    m = _model(pages=1)
    for n in range(6):
        m.blocks.append(Block(kind=IMAGE, text="", page=0, image=tall,
                              x0=70, x1=450, y=100 + n, y1=670 + n))
    docx = tmp / "stack.docx"
    write(m, str(docx))
    usable = 842.0 - 71.6 - 35.6
    total = sum(_heights(docx))
    check("six tall pictures were emitted", len(_heights(docx)), 6)
    check("stacked height now fits the page", round(total) <= round(usable), True)

    print("\npages that already fit are left alone")
    small = _png(tmp / "small.png", 100, 60)
    m = _model(pages=1)
    m.blocks.append(Block(kind=IMAGE, text="", page=0, image=small,
                          x0=70, x1=170, y=200, y1=260))
    docx = tmp / "small.docx"
    write(m, str(docx))
    check("drawn at its own size", [round(h) for h in _heights(docx)], [60])

    print("\na page that begins with a table starts on its own page")
    m = _model(pages=2)
    m.line_pitch = 14.0
    m.blocks.append(Block(kind=PARAGRAPH, text="نص الصفحة الأولى قبل الجدول.",
                          page=0, y=100, y1=120))
    m.blocks.append(Block(kind=TABLE, text="", page=1,
                          rows=[["العمود الأول", "العمود الثاني"],
                                ["خليةجدولمميزة", "قيمة"]],
                          col_widths=[120.0, 120.0], x0=70, x1=310, y=80, y1=200))
    m.blocks.append(Block(kind=PARAGRAPH, text="نص يلي الجدول في الصفحة الثانية.",
                          page=1, y=220, y1=240))
    docx = tmp / "table_first.docx"
    write(m, str(docx))
    check("no break is left on what follows the table",
          _break_after_table(docx), False)

    # Rendering, because the XML can only confirm we wrote what we meant to.
    # A w:tbl cannot carry w:pageBreakBefore itself, so where the break has to
    # go is a question about what the renderer honours - see test_alignment.
    from harness.roundtrip import docx_to_pdf
    pdf = docx_to_pdf(docx, tmp)
    check("the table lands on the second page",
          _rendered_page_of(pdf, "خليةجدولمميزة"), 1)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
