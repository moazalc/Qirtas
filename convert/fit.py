#!/usr/bin/env python3
"""Make each original page's content fit on one page - by looking, not guessing.

We put a page break before each original page's content, so a page that
overflows by a single line becomes two, and the error repeats all the way down:
page counts swelled by about half. Every attempt to predict the right size from
the PDF was wrong, because Word shapes and wraps Arabic differently than the
original renderer did.

So stop predicting. Convert, render, see which pages actually spilled, shrink
only those, and go again.
"""
import collections, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert.glyphs import repaired
from convert.v1 import convert as convert_once
from harness.compare import _page_words

STEP = 0.94          # how much to shrink a page that spilled
FLOOR = 0.70         # never shrink further than this
ROUNDS = 6


def _spilled(orig_pdf, rebuilt_pdf):
    """Which original pages needed more than one page in our output?"""
    with pymupdf.open(orig_pdf) as A, pymupdf.open(repaired(rebuilt_pdf)) as B:
        orig = [set(_page_words(p)) for p in A]
        ours = [set(_page_words(p)) for p in B]
    # Words on a third or more of the original's pages are its running header
    # and footer, and say nothing about which page is which. Worse once Word
    # draws an alternating header (N5b): the overflow of a page carries the
    # header of the page after it, matched that page, and the loop shrank the
    # wrong one - z19799068 went from 95% to 42% on right page.
    seen = collections.Counter(w for o in orig for w in o)
    furniture = {w for w, k in seen.items() if len(orig) >= 4 and k >= len(orig) / 3}
    orig = [o - furniture for o in orig]
    ours = [o - furniture for o in ours]
    return {i for i, n in collections.Counter(_owners(orig, ours)).items()
            if n > 1}


def _owners(orig, ours):
    """Which original page each rendered page belongs to.

    The writer breaks the page before every original page, so the rendered
    pages fall into one unbroken run per original page, in order. This finds
    the split into runs that shares the most words.

    It used to give each rendered page to whichever original page it shared
    most words with, one at a time, and skip pages with no words. On
    z21760107 nearly every page pushed its last line - a footer picture - onto
    a page of its own, and all of those wordless pages were skipped: 19 pages
    came out as 35 and the loop saw 2 of the 16 spills.

    A page with no words is given to the run before it: the page after it
    starts with a break, so a wordless page in between is overflow.
    """
    n, m = len(orig), len(ours)
    if not n or not m:
        return []
    # Every original page gets at least one rendered page, since each is
    # written even when empty. When there are fewer rendered pages than that,
    # something was lost and an original page may get none.
    every = m >= n
    hit = [[len(r & o) for o in orig] for r in ours]
    NONE = float("-inf")
    # best[j][i]: most shared words with rendered pages 0..j, page j in run i.
    best = [[NONE] * n for _ in range(m)]
    back = [[0] * n for _ in range(m)]
    for i in range(n):
        if i == 0 or not every:
            best[0][i] = hit[0][i]
    for j in range(1, m):
        # best of the runs before i, for when a run may be skipped
        before, before_at = NONE, 0
        for i in range(n):
            stay = best[j - 1][i]
            if every:
                came, came_at = (best[j - 1][i - 1], i - 1) if i else (NONE, 0)
            else:
                came, came_at = before, before_at
            # Ties go to moving on, so that tracing back starts each run as
            # late as it can and a wordless page joins the run before it.
            if came > NONE and came >= stay:
                best[j][i], back[j][i] = came + hit[j][i], came_at
            elif stay > NONE:
                best[j][i], back[j][i] = stay + hit[j][i], i
            if best[j - 1][i] > before:
                before, before_at = best[j - 1][i], i
    i = n - 1 if every else max(range(n), key=lambda k: best[m - 1][k])
    owners = [0] * m
    for j in range(m - 1, -1, -1):
        owners[j] = i
        i = back[j][i]
    return owners


def convert(pdf_path, out_path, render=None):
    """render(docx) -> pdf path. Without one this is a single pass."""
    # Matched against the corrected copy when a font needed one: our pages
    # carry the real words, the original's table does not (FLAGS.md 23).
    pdf_path = repaired(pdf_path)
    scale, route = {}, convert_once(pdf_path, out_path)
    if render is None:
        return route
    for _ in range(ROUNDS):
        try:
            rebuilt = render(out_path)
        except Exception:
            return route
        over = _spilled(pdf_path, rebuilt)
        over = {i for i in over if scale.get(i, 1.0) * STEP >= FLOOR}
        if not over:
            break
        for i in over:
            scale[i] = scale.get(i, 1.0) * STEP
        route = convert_once(pdf_path, out_path, scale)
    return route
