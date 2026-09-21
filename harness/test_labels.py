#!/usr/bin/env python3
"""Tests for the labels route: Word's structure labels over glyph text.

    python -m harness.test_labels

Before this route, the reader ignored the labels on every ordinary Word file -
the tags route reads only /ActualText, which those files do not carry - and
geometry guessed the structure back: no footnote found on any of 36 files, a
third of prose made into list items. Two things went wrong on the way in, and
each has a case here:

  - A list inside a footnote must stay a footnote. Splitting at the list is
    how `الفصل الثالث`'s notes (34) and (35) landed in the body.
  - Fields side by side on one line are one paragraph. `عن بعد` has three,
    labelled separately; stacked as three headings, the one-page form ran onto
    a second page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.model import Block, PARAGRAPH, HEADING, LIST_ITEM, FOOTNOTE
from convert.reader import _label_kind, _join_same_line

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<50} got {got!r}")
    if not ok:
        FAILED.append(name)


def field(text, x0, x1, y=275.0, kind=HEADING):
    return Block(kind=kind, text=text, size=22.0, y=y, y1=y + 33.0,
                 x0=x0, x1=x1, spans=[(text, True, False)])


def main():
    print("what the labels say")
    check("list inside a footnote",
          _label_kind(["Part", "Footnote", "L", "LI", "LBody", "P"]),
          (FOOTNOTE, 0))
    check("H2", _label_kind(["Document", "H2"]), (HEADING, 2))
    check("list item", _label_kind(["Document", "L", "LI", "LBody"]),
          (LIST_ITEM, 0))
    check("table cell stays for read_tables",
          _label_kind(["Table", "TR", "TD", "P"]), (PARAGRAPH, 0))
    check("plain paragraph", _label_kind(["Document", "P"]), (PARAGRAPH, 0))

    print("\nfields on one line")
    # Label order is left to right, as `عن بعد` stores them.
    got = _join_same_line([field(":الرقم", 77, 119), field(":التوقيع", 286, 342),
                           field(":اسم الطالبة", 479, 570)])
    check("three fields become one block", len(got), 1)
    check("joined right to left", got[0].text, ":اسم الطالبة :التوقيع :الرقم")

    stacked = _join_same_line([field(":اسم المسجد", 469, 579, y=155),
                               field(":اسم المعلمة", 478, 572, y=192)])
    check("lines one under another stay apart", len(stacked), 2)

    mixed = _join_same_line([field("مقدمة", 400, 560),
                             field("نص", 80, 380, kind=PARAGRAPH)])
    check("different kinds stay apart", len(mixed), 2)

    notes = _join_same_line([field("(1) انظر", 300, 560, kind=FOOTNOTE),
                             field("(2) انظر", 60, 280, kind=FOOTNOTE)])
    check("footnotes side by side stay apart", len(notes), 2)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
