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

    d.close()
    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
