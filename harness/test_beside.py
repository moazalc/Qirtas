#!/usr/bin/env python3
"""Tests for blocks the original set side by side.

    python -m harness.test_beside

A title page's two supervisors were written one under the other, so the page
held more than the original's and ran long (`z20782957`). They now go into a
borderless table of two cells. Two things that look side by side and are
not: a page number at the foot, read before the text at the top; and an
entry's number set out in the margin level with it, which belongs on the
front of the entry, not in a cell of its own.
"""
import re
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.model import Block, Doc, HEADING, PARAGRAPH, TABLE
from convert.writer import write

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}")
    if not ok:
        FAILED.append(name)


def _b(text, y, y1, x0, x1, kind=HEADING, page=0):
    return Block(kind, text, page=page, y=y, y1=y1, x0=x0, x1=x1, size=14,
                 text_size=14)


def _xml(model):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "t.docx"
        write(model, out)
        with zipfile.ZipFile(out) as z:
            return z.read("word/document.xml").decode("utf-8")


def _text(xml):
    return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


def main():
    print("two supervisors, the right one read first")
    right = [_b("الأستاذ الدكتور", 573, 596, 330, 476),
             _b("إلهام مصطفى عبيد", 596, 626, 343, 461),
             _b("جامعة الإسكندرية", 668, 697, 358, 445)]
    left = [_b("الأستاذ الدكتور", 573, 596, 149, 221),
            _b("دعاء محمد أحمد", 596, 626, 132, 236),
            _b("جامعة الإسكندرية", 649, 672, 143, 226)]
    top = _b("إشراف", 543, 573, 270, 316)
    foot = _b("2025م", 700, 725, 265, 321)
    m = Doc(blocks=[top] + right + left + [foot], pages=1)
    xml = _xml(m)
    check("one table", xml.count("<w:tbl>"), 1)
    check("two cells", xml.count("<w:tc>"), 2)
    check("mirrored, so cell one is on the right", "<w:bidiVisual" in xml, True)
    table = re.search(r"<w:tbl>.*</w:tbl>", xml, re.S).group(0)
    check("the line above and the year stay outside", ("إشراف" in table, "2025" in table),
          (False, False))
    cells = re.findall(r"<w:tc>.*?</w:tc>", table, re.S)
    check("right supervisor in cell one", "إلهام" in _text(cells[0]), True)
    check("left supervisor in cell two", "دعاء" in _text(cells[1]), True)
    check("no empty paragraph left in a cell",
          [c.count("<w:p>") + c.count("<w:p ") for c in cells], [3, 3])
    check("centred in the cell", cells[0].count('<w:jc w:val="center"/>'), 3)
    check("every word kept, in reading order",
          _text(xml).replace(" ", ""), "".join(b.text for b in m.blocks).replace(" ", ""))
    m = Doc(blocks=[_b("République du Niger Ministère de l'Enseignement", 111, 195, 20, 230,
                       PARAGRAPH),
                    _b("جمهورية النيجر", 100, 190, 300, 510, PARAGRAPH)], pages=1)
    check("a lone paragraph in a cell is not justified", '"both"' in _xml(m), False)

    print("a row of three read cell by cell, a table drawn without borders")
    row = [_b("م", 100, 120, 470, 510, PARAGRAPH),
           _b("العبارة الأولى في الجدول", 100, 140, 250, 450, PARAGRAPH),
           _b("موافق بشدة", 100, 120, 90, 200, PARAGRAPH)]
    m = Doc(blocks=row + [_b("نص تحت الجدول بعرض الصفحة كلها", 160, 180, 72, 510,
                               PARAGRAPH)], pages=1)
    xml = _xml(m)
    table = re.search(r"<w:tbl>.*</w:tbl>", xml, re.S).group(0)
    check("three cells", table.count("<w:tc>"), 3)
    check("in reading order", [_text(c) for c in re.findall(r"<w:tc>.*?</w:tc>", table, re.S)],
          ["م", "العبارة الأولى في الجدول", "موافق بشدة"])
    widths = [int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"', table)]
    check("the middle cell is the widest", max(widths) == widths[1], True)
    check("the text below stays outside", "تحت" in table, False)

    print("a page number at the foot, read before the text at the top")
    m = Doc(blocks=[_b("54", 757, 789, 258, 493, PARAGRAPH),
                    _b("46 -", 72, 94, 511, 530, PARAGRAPH),
                    _b("المراجع العربية", 100, 120, 300, 510)], pages=1)
    check("no table", "<w:tbl>" in _xml(m), False)

    print("an entry's number in the margin, level with its first line")
    entry = _b("( روسو، جان جاك. 2011 .) في العقد الاجتماعي", 119, 168, 72, 510, PARAGRAPH)
    m = Doc(blocks=[_b("47 -", 121, 142, 511, 530, PARAGRAPH), entry], pages=1)
    xml = _xml(m)
    check("no table", "<w:tbl>" in xml, False)
    check("one paragraph", len(re.findall(r"<w:p[ >]", xml)), 1)
    check("the number leads the entry", _text(xml).startswith("47 -"), True)
    xml = _xml(m)                 # the fit loop writes the same model again
    check("written again, the number is not doubled", _text(xml).count("47"), 1)
    check("the model is left as it was", entry.text.startswith("47"), False)

    print("a table read just before a block beside it (z3387756 crashed)")
    tbl = Block(TABLE, "", page=0, y=100, y1=200, x0=300, x1=510, rows=[["أ", "ب"]])
    m = Doc(blocks=[tbl, _b("نص إلى جانبه", 120, 140, 72, 280, PARAGRAPH)], pages=1)
    check("written, no side-by-side table", _xml(m).count("<w:tbl>"), 1)

    print("blocks with no position (the tags route)")
    m = Doc(blocks=[Block(HEADING, "إلهام مصطفى عبيد"), Block(HEADING, "دعاء محمد أحمد")],
            pages=1)
    check("no table", "<w:tbl>" in _xml(m), False)

    print()
    if FAILED:
        print(f"FAILED: {', '.join(FAILED)}")
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
