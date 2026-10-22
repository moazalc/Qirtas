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
import collections, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert.glyphs import repaired
from convert.v1 import convert as convert_once
from harness.compare import _page_words

STEP = 0.94          # how much to shrink a page that spilled
FLOOR = 0.70         # never shrink further than this
ROUNDS = 6
# A page that spills has its lines drawn closer first, once, and only then
# its letters made smaller: plain009 came out a size smaller, 16 -> 15pt, for
# a page that ran over by a line (FLAGS 36; QIRTAS_LINES_FIRST=0 off).
LINES_FIRST_ON = os.environ.get("QIRTAS_LINES_FIRST", "1") != "0"
LINES_FLOOR = 0.94


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


# The text started 10-20pt lower than the original's on most pages (FLAGS
# 36): the writer sets each line's exact height, and Word draws the text at
# the bottom of an exact line, where the original's "double" or "1.5" lines
# have it at the top. How far is measured, not worked out from the font -
# the font's metrics missed by 3-5pt on a third of the plain set. The page
# is lifted by that much: the top margin less, the bottom margin as much
# more, so a page holds what it held (QIRTAS_LIFT=0 turns it off).
LIFT_ON = os.environ.get("QIRTAS_LIFT", "1") != "0"
LIFT_MIN = 2.0       # points: less is not worth a render
PAGE_TOPS_ON = os.environ.get("QIRTAS_PAGE_TOPS", "1") != "0"


def _tops(pdf):
    """The top of each page's first line of text, its page number and any
    line repeated on a third of the pages (running headers) left out."""
    with pymupdf.open(pdf) as d:
        pages = []
        for p in d:
            H = p.rect.height
            lines = []
            for b in p.get_text("dict")["blocks"]:
                for ln in b.get("lines", ()):
                    t = "".join(s["text"] for s in ln["spans"]).strip()
                    # not a page number
                    if t.strip("-–()0123456789٠١٢٣٤٥٦٧٨٩ ") and ln["bbox"][1] < 0.9 * H:
                        lines.append((re.sub(r"[0-9٠-٩]+", "", t), ln["bbox"][1]))
            pages.append(lines)
    seen = collections.Counter(t for lines in pages for t in {t for t, _ in lines})
    many = {t for t, k in seen.items() if len(pages) >= 4 and k >= len(pages) / 3}
    return [min((y for t, y in lines if t not in many), default=None)
            for lines in pages]


def _lift(orig_pdf, rebuilt_pdf):
    """How much lower our text starts than the original's, in points: the
    middle of the pages' differences. 0 where the pages do not pair up."""
    a, b = _tops(orig_pdf), _tops(rebuilt_pdf)
    if len(a) != len(b):
        return 0.0
    d = sorted(y - x for x, y in zip(a, b) if x is not None and y is not None)
    return d[len(d) // 2] if d else 0.0


def _pages(pdf):
    with pymupdf.open(pdf) as d:
        return len(d)


def convert(pdf_path, out_path, render=None):
    """render(docx) -> pdf path. Without one this is a single pass."""
    # Matched against the corrected copy when a font needed one: our pages
    # carry the real words, the original's table does not (FLAGS.md 23).
    pdf_path = repaired(pdf_path)
    scale, route = {}, convert_once(pdf_path, out_path)
    if render is None:
        return route
    rebuilt = None
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
            if LINES_FIRST_ON and scale.get(("lines", i), 1.0) * STEP >= LINES_FLOOR:
                scale[("lines", i)] = scale.get(("lines", i), 1.0) * STEP
            else:
                scale[i] = scale.get(i, 1.0) * STEP
        route = convert_once(pdf_path, out_path, scale)
        rebuilt = None
    if LIFT_ON:
        try:
            if rebuilt is None:
                rebuilt = render(out_path)
            lift = _lift(pdf_path, rebuilt)
            if lift >= LIFT_MIN:
                pages, spilled = _pages(rebuilt), _spilled(pdf_path, rebuilt)
                route = convert_once(pdf_path, out_path, {**scale, "lift": lift})
                after = render(out_path)
                # Kept only where no page runs over for it.
                if _pages(after) != pages or \
                        not _spilled(pdf_path, after) <= spilled:
                    route = convert_once(pdf_path, out_path, scale)
                else:
                    scale = {**scale, "lift": lift}
                    rebuilt = after
            route = _drop_tops(pdf_path, out_path, scale, rebuilt, render, route)
        except Exception:
            route = convert_once(pdf_path, out_path, scale)
    return route


def _drop_tops(pdf_path, out_path, scale, rebuilt, render, route):
    """After the lift, a page whose text still starts higher than the
    original's gets the difference as space above its first paragraph: the
    plain set's page 1 began 12pt high on 39 of 40 files - the title, which
    Word sets with space above it (FLAGS 36; QIRTAS_PAGE_TOPS=0 off). Kept
    only where no page runs over for it."""
    if not PAGE_TOPS_ON:
        return route
    a, b = _tops(pdf_path), _tops(rebuilt)
    if len(a) != len(b):
        return route
    tops = {("top", i): round(x - y, 1) for i, (x, y) in enumerate(zip(a, b))
            if x is not None and y is not None and x - y >= LIFT_MIN}
    if not tops:
        return route
    pages, spilled = _pages(rebuilt), _spilled(pdf_path, rebuilt)
    route = convert_once(pdf_path, out_path, {**scale, **tops})
    after = render(out_path)
    if _pages(after) != pages or not _spilled(pdf_path, after) <= spilled:
        route = convert_once(pdf_path, out_path, scale)
    return route
