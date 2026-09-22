#!/usr/bin/env python3
"""Tests for writing digits the way the original showed them (N5a).

    python -m harness.test_digits

Word stores a typed 121 and, with its numbers set to Hindi or Context, draws
١٢١. Moaz's theses show ١٢١ on every page; our Word files showed 121,
because what a typed digit looks like is a setting of the reader's Word, not
of the file. So where the embedded font proves the pages showed ١٢١
(`glyphs.shown_digits`), the writer writes ١٢١ - after Arabic, not after
English, which is Word's own Context rule.

Two things had to follow, or the change would have broken what it touched:

  - footnotes pair a reference with its note by number, as text: the body's
    (١) and the note's (1) must still be one note
  - the checker compares against the original's STORED 121: both sides read
    digits as plain numbers, or every corrected number counts as lost
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.footnotes import marker_numbers, split_number
from convert.glyphs import shown_digits
from convert.model import Doc, Block, PARAGRAPH, TABLE
from convert.writer import SHOWN, _in_context, write
from harness.compare import text_of_docx

FAILED = []
ARABIC = SHOWN["arabic"]
PAGE = "صفحة"


def check(name, got, want):
    ok = got == want
    if not ok:
        FAILED.append(name)
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<55} got {got!r}")


def _xml(model, tmp, name):
    import zipfile
    out = Path(tmp) / f"{name}.docx"
    write(model, out)
    with zipfile.ZipFile(out) as z:
        return z.read("word/document.xml").decode("utf-8")


def main():
    print("the context rule")
    check("after Arabic", _in_context(f"{PAGE} 121", ARABIC, True),
          f"{PAGE} ١٢١")
    check("after English", _in_context("ISBN 978", ARABIC, True), "ISBN 978")
    check("both in one line",
          _in_context(f"{PAGE} 12 and page 13", ARABIC, True),
          f"{PAGE} ١٢ and page 13")
    check("alone in an Arabic paragraph", _in_context("(3)", ARABIC, True),
          "(٣)")
    check("alone in an English one", _in_context("(3)", ARABIC, False), "(3)")
    check("twice is the same as once",
          _in_context(_in_context(f"{PAGE} 7", ARABIC, True), ARABIC, True),
          f"{PAGE} ٧")

    print("the Word file")
    with tempfile.TemporaryDirectory() as tmp:
        def doc(digits):
            return Doc(digits=digits, blocks=[
                Block(kind=PARAGRAPH, text=f"{PAGE} 45 English 45"),
                Block(kind=TABLE, text="", rows=[[f"{PAGE} 6", "Table 6"]])])
        xml = _xml(doc("arabic"), tmp, "shown")
        check("a paragraph after Arabic", f"{PAGE} ٤٥" in xml, True)
        check("a paragraph after English", "English 45" in xml, True)
        check("a table cell", f"{PAGE} ٦" in xml, True)
        check("an English table cell", "Table 6" in xml, True)
        xml = _xml(doc(""), tmp, "typed")
        check("pages that showed 45 keep 45", f"{PAGE} 45" in xml, True)
        check("persian digits", "۴۵" in _xml(doc("persian"), tmp, "fa"), True)
        m = Doc(digits="arabic",
                blocks=[Block(kind=PARAGRAPH, text=f"{PAGE} 12",
                              spans=[(f"{PAGE} ", False, False),
                                     ("12", True, False)])])
        xml = _xml(m, tmp, "spans")
        check("a number in its own bold span", "١٢" in xml, True)

        print("the checker")
        check("reads the shown digits as the number",
              "45" in text_of_docx(Path(tmp) / "shown.docx"), True)

    print("footnotes")
    check("a reference shown as (١)", marker_numbers(f"{PAGE}(١)"), ["1"])
    check("its note typed (1)", split_number("(1) note")[0], "1")
    check("its note shown (١)", split_number("(١) note")[0], "1")

    thesis = Path("corpus") / "مقدمة البحث.pdf"
    if thesis.exists():
        print("a real thesis")
        check("its Arial draws ٠-٩ for typed 0-9", shown_digits(thesis),
              "arabic")

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
