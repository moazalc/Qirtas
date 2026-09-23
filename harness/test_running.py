#!/usr/bin/env python3
"""Tests for running headers, footers and page numbers (N5b).

    python -m harness.test_running

N4 found journal headers, page-number graphics and header bands in the body
of 8 files, and wrong or missing page numbers in 4. Each case below is one of
them, reduced to a few blocks:

  - a header of two lines, English and Arabic: only one piece per edge was
    taken, the other stayed in the body (`z21095413`)
  - a page number inside the measured column and in the middle of the page's
    reading order - neither test could see it (`z21095413`)
  - a year on the title page with the shape of a page number, taken as the
    first page's number: the document was numbered from 5202 (`z20538636`)
  - the page number inside a line, "- 8 - 10 2016": the whole line was copied
    from page one, so every page said 6 (`z21763864`)
  - a header that alternates, the title on odd pages and the author on even
    ones: one was drawn on every page, the other left in the body
    (`z21761968`)
  - the same footer read in another order on even pages because it is
    mirrored: not an alternating header (`z21763864`)
  - a header band found as a table: an empty grid on every page (`z21762915`)
  - a logo inside the measured column, which starts at the page number above
    it (`z22051439`)
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert.model import Doc, Block, PARAGRAPH, IMAGE, TABLE
from convert.writer import write
from harness.compare import text_of_docx

FAILED = []
PAGES = 6


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<56} got {got!r}")
    if not ok:
        FAILED.append(name)
        print(f"        want {want!r}")


def _model(pages=PAGES):
    return Doc(pages=pages, page_width=515.0, page_height=729.0,
               margin_top=26.0, margin_bottom=40.0,
               margin_left=60.0, margin_right=60.0, body_size=12.0)


WORDS = ["الأولى", "الثانية", "الثالثة", "الرابعة", "الخامسة", "السادسة"]


def _body(m, p, text=None):
    # Different words on every page: the same sentence with only its number
    # changed IS a running header, and would be lifted as one.
    m.blocks.append(Block(kind=PARAGRAPH, page=p, y=200, y1=260, x0=60, x1=455,
                          text=text or f"نص الصفحة {WORDS[p]} في وسطها هنا."))


def _xml(docx, part):
    with zipfile.ZipFile(docx) as z:
        return z.read(part).decode("utf-8") if part in z.namelist() else ""


def _parts(docx):
    """{type: text} of each header and footer the section points to."""
    doc = _xml(docx, "word/document.xml")
    rels = _xml(docx, "word/_rels/document.xml.rels")
    target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    out = {}
    for kind, typ, rid in re.findall(
            r'<w:(header|footer)Reference w:type="(\w+)" r:id="([^"]+)"', doc):
        xml = _xml(docx, "word/" + target[rid])
        page = "PAGE" if "PAGE" in xml else ""
        out[f"{kind}-{typ}"] = " ".join(re.findall(r"<w:t[^>]*>([^<]*)<", xml)) \
            + (" [" + page + "]" if page else "")
    return out


def _body_text(docx):
    return " ".join(re.findall(r"<w:t[^>]*>([^<]*)<", _xml(docx, "word/document.xml")))


def main():
    tmp = Path("out/tests/running")
    tmp.mkdir(parents=True, exist_ok=True)

    print("a header of two lines, and a page number mid-page in reading order")
    m = _model()
    for p in range(PAGES):
        m.blocks.append(Block(kind=PARAGRAPH, page=p, y=35, y1=48, x0=206, x1=344,
                              text="Volume 3 - Issue 5, January - June 2026"))
        m.blocks.append(Block(kind=PARAGRAPH, page=p, y=53, y1=67, x0=207, x1=337,
                              text="مجلد3 - عدد5، يناير– يونيو 2026"))
        # inside the measured column, and not last on its page
        m.blocks.append(Block(kind=PARAGRAPH, page=p, y=664, y1=691, x0=88, x1=277,
                              text=str(273 + p)))
        _body(m, p)
        _body(m, p, f"خاتمة الصفحة {WORDS[p]} في آخرها.")
    docx = tmp / "two_lines.docx"
    write(m, str(docx))
    parts = _parts(docx)
    check("both header lines lifted", "Volume" in _body_text(docx)
          or "مجلد3" in _body_text(docx), False)
    check("both in the header", ("Volume 3" in parts.get("header-default", ""),
                                 "مجلد3" in parts.get("header-default", "")),
          (True, True))
    check("the number is a PAGE field", parts.get("footer-default", ""),
          "273 [PAGE]")
    check("numbering starts at 273", re.search(r'w:start="(\d+)"',
                                                _xml(docx, "word/document.xml"))
          and re.search(r'w:start="(\d+)"',
                        _xml(docx, "word/document.xml")).group(1), "273")
    check("nothing reads as lost", text_of_docx(docx).count("Volume 3"), PAGES)

    print("\na year on the title page is not the first page's number")
    m = _model()
    m.blocks.append(Block(kind=PARAGRAPH, page=0, y=660, y1=680, x0=200, x1=300,
                          text="٥٢٠٢"))
    for p in range(PAGES):
        _body(m, p)
        if p:
            m.blocks.append(Block(kind=PARAGRAPH, page=p, y=660, y1=680, x0=58,
                                  x1=77, text=str(156 + p)))
    docx = tmp / "year.docx"
    write(m, str(docx))
    check("numbered from the pages that agree",
          re.search(r'w:start="(\d+)"', _xml(docx, "word/document.xml")).group(1),
          "156")
    check("the year stays on the title page", "٥٢٠٢" in _body_text(docx), True)

    print("\na page number inside a line of text")
    m = _model()
    for p in range(PAGES):
        _body(m, p)
        m.blocks.append(Block(kind=PARAGRAPH, page=p, y=594, y1=606, x0=94, x1=358,
                              text=f"- {6 + p} - 10 2016"))
    docx = tmp / "inline_number.docx"
    write(m, str(docx))
    foot = _xml(docx, "word/footer1.xml")
    check("only the page number is a field", "PAGE" in foot and "10" in foot
          and "2016" in foot and ">6<" in foot, True)
    check("in the footer, though first in reading order",
          _parts(docx).get("footer-default", "").startswith("-"), True)

    print("\na header that alternates between odd and even pages")
    m = _model()
    for p in range(PAGES):
        m.blocks.append(Block(kind=PARAGRAPH, page=p, y=35, y1=47, x0=233, x1=364,
                              text="ثقافات النيوليتي القديم" if p % 2 == 0
                              else "لخضر بن بو زيد"))
        _body(m, p)
        m.blocks.append(Block(kind=PARAGRAPH, page=p, y=640, y1=652, x0=282, x1=317,
                              text=f"- {129 + p} -"))
    docx = tmp / "alternating.docx"
    write(m, str(docx))
    parts = _parts(docx)
    check("Word told to use two headers",
          "evenAndOddHeaders" in _xml(docx, "word/settings.xml"), True)
    # Page 0 is printed 129 - odd - so the title is the default (odd) header.
    check("the title on odd page numbers", parts.get("header-default"),
          "ثقافات النيوليتي القديم")
    check("the author on even page numbers", parts.get("header-even"),
          "لخضر بن بو زيد")
    check("the page number on both", ("PAGE" in parts.get("footer-default", ""),
                                      "PAGE" in parts.get("footer-even", "")),
          (True, True))
    got = text_of_docx(docx)
    check("the checker reads each on its own pages",
          (got.count("ثقافات النيوليتي"), got.count("لخضر")), (3, 3))

    print("\na mirrored footer read in another order is not an alternating one")
    m = _model()
    for p in range(PAGES):
        _body(m, p)
        text = f"- {6 + p} - 10 2016" if p % 2 == 0 else f"2016 10 - {6 + p} -"
        m.blocks.append(Block(kind=PARAGRAPH, page=p, y=594, y1=606, x0=94,
                              x1=358, text=text))
    docx = tmp / "mirrored.docx"
    write(m, str(docx))
    check("one footer, no even one", sorted(_parts(docx)), ["footer-default"])
    check("and none of it left in the body", "2016" in _body_text(docx), False)

    print("\na header band found as a table")
    m = _model()
    for p in range(PAGES):
        m.blocks.append(Block(kind=TABLE, page=p, y=29, y1=55, x0=0, x1=402, text="",
                              rows=[["", "", "د. لخضر بن بوزيد"], ["", "", ""]],
                              col_widths=[100.0, 100.0, 200.0]))
        _body(m, p)
    docx = tmp / "band.docx"
    write(m, str(docx))
    check("no table in the body", "<w:tbl>" in _xml(docx, "word/document.xml"),
          False)
    check("its text in the header", _parts(docx).get("header-default"),
          "د. لخضر بن بوزيد")

    print("\na logo inside the measured column, in the page's top strip")
    logo = tmp / "logo.png"
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 40))
    pix.clear_with(90)
    pix.save(str(logo))
    m = _model()
    for p in range(PAGES):
        # middle at y=43, below the 26pt top margin
        m.blocks.append(Block(kind=IMAGE, page=p, image=str(logo), text="",
                              x0=294, x1=344, y=29, y1=57))
        _body(m, p)
    docx = tmp / "logo.docx"
    write(m, str(docx))
    check("lifted into the header", ("<wp:" in _xml(docx, "word/document.xml"),
                                     "<wp:" in _xml(docx, "word/header1.xml")),
          (False, True))

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
