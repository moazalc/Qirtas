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

from convert.v1 import convert as convert_once
from harness.compare import _page_words

STEP = 0.94          # how much to shrink a page that spilled
FLOOR = 0.70         # never shrink further than this
ROUNDS = 4


def _spilled(orig_pdf, rebuilt_pdf):
    """Which original pages needed more than one page in our output?"""
    with pymupdf.open(orig_pdf) as A, pymupdf.open(rebuilt_pdf) as B:
        orig = [set(_page_words(p)) for p in A]
        ours = [set(_page_words(p)) for p in B]
    spread = collections.Counter()
    for j, page in enumerate(ours):
        if not page:
            continue
        # which original page does this rendered page mostly belong to?
        best, score = None, 0
        for i, o in enumerate(orig):
            if not o:
                continue
            hit = len(page & o)
            if hit > score:
                best, score = i, hit
        if best is not None and score:
            spread[best] += 1
    return {i for i, n in spread.items() if n > 1}


def convert(pdf_path, out_path, render=None):
    """render(docx) -> pdf path. Without one this is a single pass."""
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
