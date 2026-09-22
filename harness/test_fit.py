#!/usr/bin/env python3
"""Tests for how the shrinking loop decides which pages spilled.

    python -m harness.test_fit

`convert/fit.py` shrinks only the original pages that took more than one page
in our output, so everything rests on telling which rendered pages belong to
which original page. It used to give each rendered page to the original page
it shared most words with, one page at a time, and skip pages with no words.

On z21760107 nearly every page pushed its last line - a footer picture - onto
a page of its own. Those overflow pages carry no words, so all of them were
skipped: 19 pages came out as 35, and the loop saw 2 of the 16 spills.

The writer breaks the page before every original page, so the rendered pages
fall into one unbroken run per original page, in order. The fix finds that
split instead of voting page by page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from convert.fit import _owners

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}")
    if not ok:
        FAILED.append(name)
        print(f"        want {want!r}")


def page(*words):
    return set(words)


def main():
    a, b, c = page("a1", "a2", "a3"), page("b1", "b2", "b3"), page("c1", "c2")
    blank = set()

    check("each page on one page",
          _owners([a, b, c], [a, b, c]), [0, 1, 2])
    check("a spill with words",
          _owners([a, b, c], [a, page("a3"), b, c]), [0, 0, 1, 2])
    # The case the old vote could not see.
    check("a spill onto a page with no words",
          _owners([a, b, c], [a, blank, b, blank, c]), [0, 0, 1, 1, 2])
    check("a wordless page at the very end",
          _owners([a, b], [a, b, blank]), [0, 1, 1])
    # A picture-only original page is written as its own page; the wordless
    # page before b is it, not a spill of a.
    check("a picture-only original page is not a spill",
          _owners([a, blank, b], [a, blank, b]), [0, 1, 2])
    check("a spill before a picture-only page",
          _owners([a, blank, b], [a, blank, blank, b]), [0, 0, 1, 2])
    # Words shared with a far page (common words) must not pull a rendered
    # page out of order.
    check("order beats a stray shared word",
          _owners([a, b, page("c1", "a1")], [a, b, page("c1", "a1")]),
          [0, 1, 2])
    # Fewer rendered pages than original ones: something was lost, and an
    # original page may end up with none.
    check("a lost page",
          _owners([a, b, c], [a, c]), [0, 2])
    check("nothing rendered", _owners([a], []), [])

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
