#!/usr/bin/env python3
"""Tests for headings being real Word headings, not just bold text.

    python -m harness.test_heading_style

An audit of a converted file found 239 bold runs, 87 justified paragraphs, 91
first-line indents - and zero w:pStyle. Every heading was bold text that merely
looked like a heading. Word could not build a table of contents from it, the
navigation pane was empty, and nothing carried an outline level.

The reason to be careful rather than just assigning the style: Word's built-in
Heading styles bring their own font, size, colour and paragraph spacing. Left
to apply, they would override the measured sizing this converter works hard to
get right, and paragraph spacing is exactly what the page-fitting loop depends
on - PLAN.md records that spacing is zeroed deliberately because a page
overflowing by one line pushes every later page out of step.

So the requirement is both halves at once: the style must be there for
structure, and our own formatting must still win.
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docx import Document

from convert.model import Doc, Block, PARAGRAPH, HEADING
from convert.writer import write

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}  want {want!r}")
    if not ok:
        FAILED.append(name)


ARABIC = "الفصل الأول"
BODY = "هذا نص عادي في فقرة من الفقرات لاختبار التنسيق"


def build(tmp, blocks, stem):
    out = Path(tmp) / f"{stem}.docx"
    write(Doc(blocks=blocks), str(out))
    return out


def main():
    tmp = Path("out/_test_heading_style")
    tmp.mkdir(parents=True, exist_ok=True)

    blocks = [
        Block(kind=HEADING, text=ARABIC, level=1, page=0),
        Block(kind=PARAGRAPH, text=BODY, page=0),
        Block(kind=HEADING, text="المبحث الثاني", level=2, page=0),
        Block(kind=PARAGRAPH, text=BODY, page=0),
    ]
    path = build(tmp, blocks, "headings")
    raw = zipfile.ZipFile(path).read("word/document.xml").decode()
    doc = Document(str(path))
    paras = [p for p in doc.paragraphs if p.text.strip()]

    print("headings must carry a real Word heading style")
    check("document declares heading styles", "w:pStyle" in raw, True)
    styles = [p.style.name for p in paras]
    check("level 1 uses Heading 1", styles[0], "Heading 1")
    check("level 2 uses Heading 2", styles[2], "Heading 2")

    print("\nand body text must NOT be styled as a heading")
    check("body paragraph 1", styles[1], "Normal")
    check("body paragraph 2", styles[3], "Normal")

    print("\nan outline level must be set, or the navigation pane stays empty")
    check("outline levels present", "w:outlineLvl" in raw, True)

    print("\nbut our own formatting must still win over the style's")
    h1 = paras[0]
    check("heading is bold", h1.runs[0].bold, True)
    check("heading keeps our size, not the style's",
          h1.runs[0].font.size is not None, True)
    # Heading 1 in Word is blue by default. On an Arabic document that would be
    # a visible, unasked-for change to how the page looks.
    # Must be set EXPLICITLY. Leaving it unset inherits from the style, and
    # Word's Heading 1 is #2F5496 - blue. An earlier version of this test
    # accepted "unset" as "not blue" and passed while the headings were blue.
    col = h1.runs[0].font.color
    check("heading colour is explicitly black",
          None if col.rgb is None else str(col.rgb), "000000")
    # The fitting loop depends on spacing being what we set, not what the
    # style wants - see the module docstring.
    check("space_after stays as we set it",
          h1.paragraph_format.space_after.pt if
          h1.paragraph_format.space_after is not None else None, 0.0)

    print("\nright-to-left must survive the style being applied")
    check("heading paragraph is still rtl", "w:bidi" in raw, True)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
