#!/usr/bin/env python3
"""Tests for paragraph alignment in both text directions.

    python -m harness.test_alignment

Arabic body text was justified and left-to-right body text was not, so a
Spanish article in the corpus came out ragged-right against a justified
original. The cause was a ternary whose two branches were identical:

    align = LEFT if block.kind != HEADING else LEFT

Both arms return LEFT, so the condition never did anything and every
left-to-right paragraph - heading or not - was left-aligned. It reads as though
a distinction was intended and then lost.

Justification is not decoration here. The page-fitting loop compares where
words land against the original, and a ragged right edge moves every line on
the page, so the whole document scores worse on placement for a reason that has
nothing to do with the converter's understanding of the text.

THE SECOND HALF OF THIS FILE RENDERS, because the first half could not have
caught the bug it now guards. w:jc is logical: "right" means END, which a
right-to-left paragraph puts on the LEFT. Every Arabic heading in the corpus
was against the wrong margin, 420pt out of place, while this file asserted
`alignment == AL.RIGHT` and passed - the test encoded the bug.

Asking the XML what it says can only confirm we wrote what we meant to write.
Only rendering says where the text actually went.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH as AL

from convert.model import Doc, Block, PARAGRAPH, HEADING
from convert.writer import write, ALIGN_START
from convert.footnotes import directional

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<50} got {got}  want {want}")
    if not ok:
        FAILED.append(name)


AR = "هذا نص عربي عادي في فقرة من الفقرات لاختبار المحاذاة الصحيحة"
LA = "This is an ordinary paragraph of left to right text used to check that "\
     "justification is applied to it in the same way"


def render(tmp, blocks, stem):
    out = Path(tmp) / f"{stem}.docx"
    write(Doc(blocks=blocks), str(out))
    return [p for p in Document(str(out)).paragraphs if p.text.strip()]


def main():
    tmp = Path("out/tests/alignment")
    tmp.mkdir(parents=True, exist_ok=True)

    print("right-to-left: body justified, heading to the right")
    ar = render(tmp, [Block(kind=PARAGRAPH, text=AR, page=0),
                      Block(kind=HEADING, text="الفصل الأول", level=1, page=0)],
                "ar")
    check("arabic body is justified", ar[0].alignment, AL.JUSTIFY)
    check("arabic heading is start-aligned", ar[1].alignment, ALIGN_START)

    print("\nleft-to-right: body justified too, heading to the left")
    la = render(tmp, [Block(kind=PARAGRAPH, text=LA, page=0),
                      Block(kind=HEADING, text="Chapter One", level=1, page=0)],
                "la")
    check("latin body is justified", la[0].alignment, AL.JUSTIFY)
    check("latin heading is start-aligned", la[1].alignment, ALIGN_START)

    print("\nsame value both ways - start is the right margin in Arabic and "
          "the left margin in English")
    check("one setting serves both directions", ar[1].alignment, la[1].alignment)

    print("\nand now where the text ACTUALLY lands, which is the only test "
          "that could have caught this")
    where_it_lands(tmp)

    print("\nEnglish in Arabic text: its own run, so a line wrapping inside "
          "it keeps its & in place")
    pieces = directional("العالمي (Lawn & Zumla, 2011; Horrigan et al.)، حيث")
    check("the English is one left-to-right piece", pieces[1],
          ("Lawn & Zumla, 2011; Horrigan et al.", False))
    check("the brackets stay with the Arabic", (pieces[0][1], pieces[2][1]),
          (True, True))
    check("a number alone stays Arabic", len(directional("أكثر من 15% من")), 1)
    check("a bracket opened inside closes inside",
          directional("السل Tuberculosis (TB) أحد")[1][0], "Tuberculosis (TB)")
    where_it_wraps(tmp)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


def where_it_lands(tmp):
    """Render, and measure which margin each heading sits against."""
    import pymupdf
    from harness.roundtrip import docx_to_pdf

    HEAD_AR, HEAD_LA = "عنوان", "Heading"
    out = Path(tmp) / "sides.docx"
    write(Doc(blocks=[Block(kind=HEADING, text=HEAD_AR, level=1, page=0),
                      Block(kind=PARAGRAPH, text=AR, page=0)]), str(out))
    pdf = docx_to_pdf(out, tmp)
    with pymupdf.open(pdf) as d:
        page = d[0]
        w = page.rect.width
        hits = page.search_for(HEAD_AR)
        if not hits:
            check("arabic heading found on the page", bool(hits), True)
            return
        r = hits[0]
        # It only has to be past the middle. Exact position depends on the
        # margins, and pinning that would make this test about margins.
        check("arabic heading sits against the RIGHT margin",
              r.x0 > w / 2, True)
        print(f"        page {w:.0f}pt wide, heading starts at x={r.x0:.0f} "
              f"({w - r.x1:.0f}pt from the right edge)")

    out = Path(tmp) / "sides_la.docx"
    write(Doc(blocks=[Block(kind=HEADING, text=HEAD_LA, level=1, page=0),
                      Block(kind=PARAGRAPH, text=LA, page=0)]), str(out))
    pdf = docx_to_pdf(out, tmp)
    with pymupdf.open(pdf) as d:
        page = d[0]
        w = page.rect.width
        hits = page.search_for(HEAD_LA)
        if not hits:
            check("latin heading found on the page", bool(hits), True)
            return
        check("latin heading sits against the LEFT margin",
              hits[0].x1 < w / 2, True)


def where_it_wraps(tmp):
    """Render a citation that wraps at every place, and look at each line
    holding its &: Word drew `(Zumla, 2011 &` when the English was part of
    the Arabic run (z20252507 page 3)."""
    import pymupdf
    from harness.roundtrip import docx_to_pdf

    cite = "(Lawnnnnnnnnnnnnnn & Zumla, 2011)"
    blocks = [Block(kind=PARAGRAPH, page=0, text=(
        "حيث يصنف " + "ب" * k + " ضمن الأسباب العشرة الأولى للوفاة على "
        "المستوى العالمي " + cite + "، وتعد المتفطرة السلية العامل المسبب"))
        for k in range(0, 60, 2)]
    out = Path(tmp) / "wraps.docx"
    write(Doc(blocks=blocks), str(out))
    pdf = docx_to_pdf(out, tmp)
    wrapped = wrong = 0
    name = "Lawnnnnnnnnnnnnnn"
    with pymupdf.open(pdf) as d:
        for page in d:
            lines = {}                  # the English words, by baseline
            for w in page.get_text("words"):
                word = w[4].strip("()")
                if word in ("&", "Zumla,", name):
                    lines.setdefault(round(w[3]), {})[word] = w[0]
            for at in lines.values():
                if "&" not in at or len(at) == 3:
                    continue
                wrapped += 1
                # & reads after the name and before Zumla, left to right
                if ("Zumla," in at and at["&"] > at["Zumla,"]) or (
                        name in at and at["&"] < at[name]):
                    wrong += 1
    check("the citation wrapped at the & somewhere", wrapped > 0, True)
    check("the & on the right side of every wrapped line", wrong, 0)


if __name__ == "__main__":
    sys.exit(main())
