#!/usr/bin/env python3
"""Where did each original page's words actually land in our output?

    python -m harness.drift original.pdf rebuilt.pdf

The scores say a file is bad. They do not say WHERE, and the difference
matters: a file scoring 29% because twenty pages are each slightly wrong is a
completely different problem from one scoring 29% because a single spurious
page early on pushed every later page out of step by one.

That second case is real. It was `الفصل الثالث`, and this tool is what found
it - the per-page map showed pages 0-4 correct and every page from 5 on
drifted by exactly +1, which pointed straight at one bad page instead of
twenty. Right page went 29.0% -> 72.6% once that page was removed. The shrink
loop, which the recorded diagnosis blamed, was never involved.

Read the drift column first. A constant offset is one insertion or deletion
and is worth chasing. Drift that grows steadily is content genuinely
overflowing page by page. Drift of 0 with a low share is line-break
difference inside correctly numbered pages, which is a wrapping difference
between renderers and may not be worth chasing at all.

A page with no words - a picture-only page - is reported rather than skipped,
because those are invisible to fit.py's correction loop (see FLAGS.md 9) and
are exactly where an unexplained extra page tends to come from.
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf
from harness.compare import _page_words

DIM, BOLD, GRN, YEL, RED, OFF = ("\033[2m", "\033[1m", "\033[32m",
                                 "\033[33m", "\033[31m", "\033[0m")


def drift(orig_pdf, out_pdf):
    """-> [(orig_page, n_words, landed_on, share, drift)] , one row per page.

    landed_on is None for a page with no words to trace.
    """
    with pymupdf.open(orig_pdf) as A, pymupdf.open(out_pdf) as B:
        orig = [set(_page_words(p)) for p in A]
        ours = [set(_page_words(p)) for p in B]
    rows = []
    for i, o in enumerate(orig):
        if not o:
            rows.append((i, 0, None, 0.0, None))
            continue
        best, share = None, 0.0
        for j, p in enumerate(ours):
            hit = len(o & p) / len(o)
            if hit > share:
                best, share = j, hit
        rows.append((i, len(o), best, share, None if best is None else best - i))
    return rows


def report(orig_pdf, out_pdf):
    rows = drift(orig_pdf, out_pdf)
    with pymupdf.open(out_pdf) as B:
        nout = B.page_count
    print(f"{BOLD}{Path(orig_pdf).name}{OFF}")
    print(f"  {len(rows)} pages in, {nout} pages out")
    print(f"\n  {'page':>5} {'words':>6} {'landed':>7} {'share':>6}  drift")
    for i, n, best, share, d in rows:
        if best is None:
            print(f"  {i:>5} {DIM}     -       -      -   (no words: "
                  f"picture-only or blank){OFF}")
            continue
        col = GRN if d == 0 else (YEL if abs(d) == 1 else RED)
        print(f"  {i:>5} {n:>6} {best:>7} {share:>5.0%}  {col}{d:+d}{OFF}")

    moved = [d for *_, d in rows if d is not None]
    if not moved:
        return
    print()
    if all(d == 0 for d in moved):
        print(f"  {GRN}every page landed on its own number{OFF} - what is left "
              f"is line-break difference inside pages")
    else:
        first = next(i for i, _, _, _, d in rows if d not in (None, 0))
        run = [d for d in moved if d]
        print(f"  first page out of step: {BOLD}{first}{OFF}")
        if len(set(run)) == 1:
            print(f"  {YEL}a constant {run[0]:+d} from there on{OFF} - that is ONE "
                  f"spurious page, not many bad ones. Look at output page "
                  f"{first + run[0] if run[0] > 0 else first}.")
        else:
            print(f"  drift grows {min(run):+d} -> {max(run):+d} - content is "
                  f"overflowing progressively, not one bad page")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("original")
    ap.add_argument("rebuilt")
    a = ap.parse_args()
    report(a.original, a.rebuilt)


if __name__ == "__main__":
    main()
