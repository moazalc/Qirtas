#!/usr/bin/env python3
"""Tests for the numbers warning (convert/digits.py, FLAGS 13).

    python -m harness.test_number_warning

A PDF can show 1951 and store 1901; the Word file is made from what is
stored, and every score agrees with it. After converting, the person is told
which pages, what they show and what is stored. The PDFs here are made on the
spot: a line in Arial, whose stored-text table is then edited to claim the
glyph for 5 is a 0 - the lie `z21358439` tells.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert.digits import Judge, Wrong, _merge, _read, message, scan

FAILED = []
ARIAL = Path("C:/Windows/Fonts/arial.ttf")


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}")
    if not ok:
        print(f"        want {want!r}")
        FAILED.append(name)


def _pdf(tmp, name, text, lie=True, embed=True):
    """One line of `text`. With `lie`, the stored-text table says Arial's 5
    (glyph 0x18) is a 0."""
    doc = pymupdf.open()
    page = doc.new_page()
    if embed:
        page.insert_font(fontname="F0", fontfile=str(ARIAL))
        page.insert_text((72, 100), text, fontname="F0", fontsize=14)
    else:
        page.insert_text((72, 100), text, fontname="helv", fontsize=14)
    path = Path(tmp) / f"{name}.pdf"
    doc.save(path)
    doc.close()
    if lie:
        doc = pymupdf.open(path)
        xref = doc[0].get_fonts(full=True)[0][0]
        tu = int(doc.xref_get_key(xref, "ToUnicode")[1].split()[0])
        cmap = doc.xref_stream(tu).decode("latin-1")
        old = "<0011> <001d> <002e>"
        assert old in cmap, "Arial's digits are not where this test expects"
        cmap = cmap.replace(old, "<0011> <0017> <002e>\n<0018> <0018> <0030>\n"
                                 "<0019> <001d> <0036>")
        cmap = cmap.replace("100 beginbfrange", "102 beginbfrange")
        doc.update_stream(tu, cmap.encode("latin-1"))
        doc.save(path.with_name(f"{name}-lie.pdf"))
        doc.close()
        path = path.with_name(f"{name}-lie.pdf")
    return str(path)


def main():
    print("one font from several of the same name")
    check("subsets that agree are one table",
          _merge([{"1": 20, "2": 21}, {"1": 20, "5": 24}]),
          {"1": 20, "2": 21, "5": 24})
    check("two that disagree about a digit: none",
          _merge([{"1": 20}, {"1": 22}]), {})
    check("two digits on one glyph: none", _merge([{"1": 20}, {"7": 20}]), {})
    check("one with no table (not embedded): none",
          _merge([{"1": 20}, {}]), {})
    times = {"0": 19, "1": 20, "4": 23, "6": 25}
    shared = Judge({}, [({}, {}), (times, {23: "6", 20: "1", 25: "4"})])
    check("a system Times beside an embedded one: the embedded one's span",
          shared.table_for([(23, "6"), (20, "1")]), times)
    check("a glyph its table does not give that character: neither",
          shared.table_for([(23, "2")]), None)
    spare = Judge({}, [({}, {}), ({"0": 19, "1": 20, ".": 17},
                                  {17: "0", 19: "0", 20: "1", 28: "1"})])
    check("a lone 0 through a spare entry: neither",
          spare.table_for([(17, "0")]), None)
    check("a spare beside a digit that is the font's own: the font",
          bool(spare.table_for([(20, "1"), (28, "1")])), True)
    check("a glyph the font names", _read(24, {"0": 19, "5": 24}), "5")
    check("a glyph it does not: nothing", _read(30, {"0": 19}), None)

    if not ARIAL.exists():
        print("\n  (no Arial here - the PDF checks are skipped)")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            print("a PDF that shows 1951 and stores 1901")
            lie = _pdf(tmp, "geneva", "Geneva 1951, protocol 1967, article 3")
            check("the text says 1901",
                  "1901" in pymupdf.open(lie)[0].get_text(), True)
            got = [(w.page, w.stored, w.drawn) for w in scan(lie)]
            check("found, with what the page shows", got,
                  [(1, "1901", "1951")])
            print("PDFs that tell the truth")
            check("the same line, table untouched",
                  scan(_pdf(tmp, "honest", "Geneva 1951, protocol 1967",
                            lie=False)), [])
            check("a font that is not embedded",
                  scan(_pdf(tmp, "plain", "Geneva 1951", lie=False,
                            embed=False)), [])
            check("no digits at all", scan(_pdf(tmp, "words", "Geneva")), [])

    print("the message")
    one = message([Wrong(8, "1901", "1951"), Wrong(8, "1922", "1967"),
                   Wrong(8, "1901", "1951")])
    check("names the page", "page 8: 1951 (stored as 1901), "
          "1967 (stored as 1922)" in one, True)
    check("says it once per number", one.count("1951"), 1)
    check("1 page", "on 1 page" in one, True)
    many = message([Wrong(p, "1", "5") for p in range(1, 15)])
    check("ten pages quoted, the rest listed",
          "and 4 more pages: 11, 12, 13, 14" in many, True)
    check("nothing to say", message([]), "")

    known = Path("corpus/wild/z21358439.pdf")
    if known.exists():
        print("the file this was found in")
        pages = {(w.stored, w.drawn) for w in scan(known) if w.page == 8}
        check("page 8: the Geneva Convention's 1951",
              ("1901", "1951") in pages, True)
        check("and its 1967 protocol", ("1922", "1967") in pages, True)
    thesis = Path("corpus") / "مقدمة البحث.pdf"
    if thesis.exists():
        check("Moaz's own chapter: nothing", scan(thesis), [])

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
