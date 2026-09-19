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
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH as AL

from convert.model import Doc, Block, PARAGRAPH, HEADING
from convert.writer import write

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
    tmp = Path("out/_test_alignment")
    tmp.mkdir(parents=True, exist_ok=True)

    print("right-to-left: body justified, heading to the right")
    ar = render(tmp, [Block(kind=PARAGRAPH, text=AR, page=0),
                      Block(kind=HEADING, text="الفصل الأول", level=1, page=0)],
                "ar")
    check("arabic body is justified", ar[0].alignment, AL.JUSTIFY)
    check("arabic heading is right-aligned", ar[1].alignment, AL.RIGHT)

    print("\nleft-to-right: body justified too, heading to the left")
    la = render(tmp, [Block(kind=PARAGRAPH, text=LA, page=0),
                      Block(kind=HEADING, text="Chapter One", level=1, page=0)],
                "la")
    check("latin body is justified", la[0].alignment, AL.JUSTIFY)
    check("latin heading is left-aligned", la[1].alignment, AL.LEFT)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
