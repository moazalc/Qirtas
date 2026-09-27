#!/usr/bin/env python3
"""Tests for reading table cells in the right order.

    python -m harness.test_tables

The table finder hands back Arabic in VISUAL order - `مدختسملا` for
`المستخدم` - while the text extractor hands back logical order. The repair
used to flip the string, and flipping is not the inverse of visual order: it
also flips the two characters inside a lam-alef ligature, so `للأوراق` came
back as `أللوارق`, matched nothing, and the cell was written into the document
backwards. Two of eight cells on one table, with nothing reported.

Nothing measured it either. `right page` counts words and the words were all
present; the structure score counts that a table EXISTS, not what is in it. A
table of unreadable Arabic scored the same as a correct one.

Cells are now read by clipping to the cell's own rectangle, which goes through
the same extractor that gets body text right. Two guards decide whether to
trust that, and both are tested here, because a clip can go wrong in exactly
two ways: it can swallow a neighbouring cell, or it can come back in an order
nobody checked.

**This file does not test Arabic ORDER, and cannot.** A PDF built here with
`insert_textbox` stores presentation-form glyphs, not the logical characters a
real Word-exported PDF stores, so a synthetic page is not a model of the bug -
the first version of this test asserted against it and failed on correct code.
What is tested is the decision: does a valid clip win over a corrupted reading
from the table finder, and do both guards refuse a clip that should not be
trusted. Order itself is verified on real files, in `PLAN.md`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert.reader import _cell_text, WS
from convert.arabic import fold_display_forms

FAILED = []
FONT = Path.home() / ".local/share/fonts/arabic/Amiri-Regular.ttf"

CELL = "مؤشر سوق دمشق للأوراق المالية"
NEIGHBOUR = "سببية أحادية الاتجاه وهذا نص إضافي طويل من الخلية المجاورة"


def flat_of(t):
    """Whitespace and newlines out - the same normalisation the reader uses."""
    return WS.sub("", (t or "").replace("\n", ""))


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}")
    if not ok:
        print(f"        want {want!r}")
        FAILED.append(name)


def _page(tmp):
    """One page holding the cell text and a longer neighbour below it."""
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=200)
    page.insert_textbox(pymupdf.Rect(20, 20, 380, 60), CELL,
                        fontfile=str(FONT), fontname="ar", fontsize=13)
    page.insert_textbox(pymupdf.Rect(20, 80, 380, 140), NEIGHBOUR,
                        fontfile=str(FONT), fontname="ar", fontsize=13)
    out = Path(tmp) / "cells.pdf"
    doc.save(out)
    doc.close()
    return pymupdf.open(out)


def main():
    tmp = Path("out/tests/tables")
    tmp.mkdir(parents=True, exist_ok=True)
    if not FONT.exists():
        print(f"no Arabic font at {FONT} - see docs/fonts.md")
        return 1

    d = _page(tmp)
    page = d[0]
    flat = flat_of(page.get_text("text"))
    tight = pymupdf.Rect(18, 18, 382, 62)
    greedy = pymupdf.Rect(18, 18, 382, 150)      # swallows the neighbour

    # What the page itself holds in the cell's rectangle. This, not our own
    # idea of the text, is what a correct read must return.
    on_page = flat_of(page.get_text("text", clip=tight))
    # As the reader hands it on: this font writes display shapes, and the
    # reader folds them to letters since 2026-09-22 (TASKS N3c).
    want = fold_display_forms(on_page)

    print("the bug: flipping the string is not the inverse of visual order")
    # Exactly the failure seen on z21011460: reversing the stored form
    # scrambles the lam-alef pair, so the result matches nothing on the page.
    corrupt = on_page[::-1]
    check("the flipped reading is not on the page", corrupt in flat, False)

    print("\nthe page's own reading wins over a corrupted one")
    got = flat_of(_cell_text(page, tight, corrupt, flat))
    check("clip is used, not the fallback", got, want)
    check("the corrupted reading was discarded", got == corrupt, False)

    print("\nguard 1: a clip that swallows a neighbour is refused")
    # The greedy box covers both lines, so the clip comes back far longer than
    # the table finder's reading. Trusting it would put a neighbouring cell's
    # words inside this one.
    got = flat_of(_cell_text(page, greedy, on_page, flat))
    check("a clip much longer than the cell is not trusted", got, want)

    print("\nguard 2: no box at all falls back rather than guessing")
    got = flat_of(_cell_text(page, None, on_page, flat))
    check("the fallback is used when there is no rectangle", got, want)

    print("\na cell the table finder read as empty still gets its text")
    check("an empty fallback does not blank the cell",
          bool(_cell_text(page, tight, "", flat).strip()), True)

    print("\na cell of several lines the page orders among other text")
    # The page's text puts a cell's lines among its neighbours' (z22639353):
    # a probe across the cell's line break is found nowhere, and the cell
    # was written backwards from the table finder.
    # Order can only be checked on a real file (see the top of this file).
    real = Path("corpus/wild/z22639353.pdf")
    if real.exists():
        from convert.glyphs import repaired
        from convert.reader import read_tables
        cells = " ".join(" ".join(c for row in t.rows for c in row)
                         for t in read_tables(repaired(str(real)))
                         if getattr(t, "rows", None)).replace("ـ", "")
        check("a cell of several lines reads forward (يستوعب)",
              "يستوعب" in cells, True)
        check("and not backwards from the table finder (بعوتسي)",
              "بعوتسي" in cells, False)

    d.close()

    print("\na table drawn with double rules (z17804101: 7 columns found as 19)")
    from convert.model import Block, Doc, PARAGRAPH, TABLE
    from convert.reader import _drop_thin_columns, _drop_text_inside_tables
    t = Block(kind=TABLE, text="", page=0, x0=50, x1=550, y=100, y1=250,
              rows=[["", "غير موافق", "", "موافق", "", "العبارة", "", "م"],
                    ["", "", "", "", "", "التعرف على حياة الشعوب", "", "1."]],
              col_widths=[5, 60, 5, 60, 6, 300, 5, 30])
    _drop_thin_columns(t)
    check("the empty 5pt columns go, width to the next", t.col_widths, [65, 65, 306, 35])
    check("the cells keep their text, in order", t.rows[0],
          ["غير موافق", "موافق", "العبارة", "م"])
    twin = Block(kind=TABLE, text="", page=0, rows=[["نص", "كلمة", "كلمة"], ["أ", "", "ب"]],
                 col_widths=[60, 5, 60])
    _drop_thin_columns(twin)
    check("a thin column copying its neighbour goes (z21145041)", twin.rows,
          [["نص", "كلمة"], ["أ", "ب"]])
    thin_text = Block(kind=TABLE, text="", page=0, rows=[["x", "نص"]], col_widths=[5, 60])
    _drop_thin_columns(thin_text)
    check("a thin column holding text stays", thin_text.col_widths, [5, 60])

    print("\na paragraph the table holds, read in pieces")
    doc = Doc(pages=1)
    split = Block(kind=PARAGRAPH, text="الإشباعات والحاجات المدبلجة هي", page=0,
                  x0=300, x1=520, y=100, y1=130)
    more = Block(kind=PARAGRAPH, text="الإشباعات والحاجات كلمة جديدة", page=0,
                 x0=300, x1=520, y=140, y1=160)
    below = Block(kind=PARAGRAPH, text="الإشباعات والحاجات", page=0,
                  x0=300, x1=520, y=400, y1=420)
    t = Block(kind=TABLE, text="", page=0, x0=50, x1=550, y=90, y1=250,
              rows=[["الإشباعات والحاجات"], ["المدبلجة هي"]])
    doc.blocks = [split, more, below, t]
    _drop_text_inside_tables(doc, [t])
    check("every word in the table: dropped", split in doc.blocks, False)
    check("one word the table lacks: kept", more in doc.blocks, True)
    check("outside the table: kept", below in doc.blocks, True)

    print("\na cell across several columns (z3387756 page 5)")
    from convert.reader import _spans, _grid_widths
    edges = [[(50, 55), (55, 200), (200, 206), (206, 420), (420, 425), (425, 530)],
             [(50, 200), None, (200, 420), None, (420, 530), None],
             [None, None, (200, 420), None, (420, 530), None]]
    boxes = [[None if c is None else (c[0], 100 + 20 * r, c[1], 120 + 20 * r) for c in row]
             for r, row in enumerate(edges)]
    check("each row-2 cell covers two columns", _spans(boxes),
          {(1, 0): 2, (1, 2): 2, (1, 4): 2, (2, 2): 2, (2, 4): 2})
    check("the row above reaching down is not a span", (2, 0) in _spans(boxes), False)
    check("widths from every row", _grid_widths(boxes, 530), [5, 145, 6, 214, 5, 105])
    from convert.reader import _is_grid
    check("a real grid is one", _is_grid(boxes), True)
    frame = [[(85, 72, 91, 80), (91, 72, 554, 80), None],
             [(85, 80, 548, 700), (91, 80, 548, 700), None]]
    check("a page frame, cells inside each other, is not (z20782957)", _is_grid(frame), False)
    from convert.reader import _unnest
    rows = [["", "الفصل", ""], ["الفصل الخامس", "الفصل الخامس", ""]]
    check("the same text read twice, nested: unnested", _unnest(rows, frame), True)
    check("the inner cell blanked, so the outer spans", (frame[1][1], rows[1][1]), (None, ""))
    check("and the outer spans it", _spans(frame), {(1, 0): 2})
    own = [[(85, 72, 548, 80), (91, 72, 300, 80)]]
    check("a nested cell with text of its own: not a grid",
          _unnest([["أ", "ب"]], own), False)
    t = Block(kind=TABLE, text="", page=0, x0=50, x1=530, y=100, y1=200,
              rows=[["", "جودة", "", "علاقة", "", "درجة"],
                    ["تقدير", "", "اختبار", "", "ضعيفة", ""]],
              col_widths=[5, 145, 6, 214, 5, 105],
              cell_spans={(1, 0): 2, (1, 2): 2, (1, 4): 2})
    _drop_thin_columns(t)
    check("thin columns go, the spanned text moves along", t.rows,
          [["جودة", "علاقة", "درجة"], ["تقدير", "اختبار", "ضعيفة"]])
    check("no spans left once the columns are one each", t.cell_spans, {})
    t = Block(kind=TABLE, text="", page=0,
              rows=[["", "جودة", "", "علاقة"], ["تقدير", "", "اختبار", ""]],
              col_widths=[5, 145, 6, 214],
              cell_spans={(1, 0): 2, (1, 2): 2},
              cell_fills={(0, 1): "DEEAF6", (1, 0): "E2EFD9"})
    _drop_thin_columns(t)
    check("shading moves with a cell that started in a sliver (z17931421)",
          t.cell_fills, {(0, 0): "DEEAF6", (1, 0): "E2EFD9"})

    print("\na right-to-left table written with column one on the right")
    import re, tempfile, zipfile
    from convert.writer import write
    t = Block(kind=TABLE, text="", page=0, x0=50, x1=530, y=100, y1=200,
              rows=[["جودة النموذج", "علاقة السببية", "درجة المتغير"],
                    ["تقدير النموذج", "", "ضعيفة"]],
              col_widths=[150, 220, 110], cell_spans={(1, 0): 2})
    with tempfile.TemporaryDirectory() as dd:
        write(Doc(blocks=[t], pages=1), Path(dd) / "t.docx")
        with zipfile.ZipFile(Path(dd) / "t.docx") as z:
            xml = z.read("word/document.xml").decode("utf-8")
    cells = re.findall(r"<w:tc>.*?</w:tc>", xml, re.S)
    text = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", c)) for c in cells]
    check("cell one is the rightmost as drawn", text[0], "درجة المتغير")
    check("widths flipped with it", re.findall(r'<w:gridCol w:w="(\d+)"', xml),
          ["2200", "4400", "3000"])
    check("row two: one cell across two columns", text[3:], ["ضعيفة", "تقدير النموذج"])
    check("merged in Word", '<w:gridSpan w:val="2"/>' in xml, True)

    print("\na cell's shading kept, on the cell it was drawn under")
    from convert.reader import _fill_hex
    check("a light blue band", _fill_hex((0.87, 0.92, 0.96)), "DEEBF5")
    check("white clears", _fill_hex((1.0, 1.0, 1.0)), "")
    check("a dark fill is not copied (its text is white)", _fill_hex((0.1, 0.1, 0.3)), None)
    t = Block(kind=TABLE, text="", page=0, x0=50, x1=530, y=100, y1=200,
              rows=[["جودة النموذج", "علاقة السببية", "درجة المتغير"],
                    ["تقدير النموذج", "", "ضعيفة"]],
              col_widths=[150, 220, 110], cell_spans={(1, 0): 2},
              cell_fills={(0, 2): "DEEAF6", (1, 0): "FADECB"})
    with tempfile.TemporaryDirectory() as dd:
        write(Doc(blocks=[t], pages=1), Path(dd) / "t.docx")
        with zipfile.ZipFile(Path(dd) / "t.docx") as z:
            xml = z.read("word/document.xml").decode("utf-8")
    cells = re.findall(r"<w:tc>.*?</w:tc>", xml, re.S)
    shade = [(re.search(r'w:fill="(\w+)"', c) or [None, None])[1] for c in cells]
    check("flipped with the table: the drawn-right cell is Word's first",
          shade, ["DEEAF6", None, None, None, "FADECB"])

    print("\na table's row read again below it, and its header on the caption")
    from convert.reader import _rejoin_articles
    t = Block(kind=TABLE, text="", page=0, x0=50, x1=530, y=212, y1=298,
              rows=[["جودة النموذج", "علاقة السببية"],
                    ["في الاتجاه لا مطلوب", "قوية"], ["عدم وجود", "ممتازة"]])
    cap = Block(kind=PARAGRAPH, text="الجدول رقم (11) يوضح أنواع علاقة السببية جودة النموذج",
                page=0, x0=69, x1=492, y=190, y1=214)
    row = Block(kind=PARAGRAPH, text="قوية في الاتجاه المطلوب", page=0,
                x0=80, x1=487, y=256, y1=280)
    tail = Block(kind=PARAGRAPH, text="ممتازة عدم وجود المصدر : إعداد الطالب", page=0,
                 x0=60, x1=490, y=277, y1=321)
    no = Block(kind=PARAGRAPH, text="لا يوجد", page=0, x0=60, x1=490, y=400, y1=420)
    doc = Doc(pages=1, blocks=[cap, row, tail, no, t])
    _drop_text_inside_tables(doc, [t])
    check("the cell's broken article joined back", t.rows[1][0], "في الاتجاه المطلوب")
    check("the row read again: dropped", row in doc.blocks, False)
    check("the row leading the source line: cut off", tail.text, "المصدر : إعداد الطالب")
    check("the header row off the caption", cap.text, "الجدول رقم (11) يوضح أنواع")
    t2 = Block(kind=TABLE, text="", page=0, rows=[["لا يوجد"]])
    _rejoin_articles(Doc(pages=1, blocks=[no]), [t2])
    check("a real لا is left alone", t2.rows[0][0], "لا يوجد")

    print("\na table placed after the paragraph above it, not by share of the list")
    from convert.writer import _interleave
    m = Doc(pages=1, blocks=[])
    body = [Block(kind=PARAGRAPH, text=str(i), page=0, x0=50, x1=500, y=y, y1=y + 20)
            for i, y in enumerate([70, 90, 110, 190, 256, 277, 300])]
    tb = Block(kind=TABLE, text="", page=0, x0=50, x1=530, y=212, y1=298, rows=[["x"]])
    got = _interleave(body, [tb], m)
    check("right after the caption", got.index(tb), 4)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
