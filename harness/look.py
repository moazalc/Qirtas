#!/usr/bin/env python3
"""Put the original page and our page side by side, and look at them.

    python -m harness.look original.pdf rebuilt.pdf --pages 1,3,5 --out out/look

The largest correctness problem ever found in this project - a third of the
corpus producing unreadable output while scoring 99% - was found this way and
by no metric. Every score here is blind to something: `right page` cannot see
a missing table, and the text score cannot see text that is perfectly matched
and perfectly backwards. Looking is the only check that sees all of it.

Pages are numbered as the reader sees them, from 1. The original goes on the
RIGHT, because these documents are read right to left and a reviewer's eye
starts there.

Use --align on any file whose page count moved. Our page 5 is not the
original's page 5 once anything has drifted, and comparing two pages that hold
different content invents faults that are not there and hides the ones that
are. With --align the page numbers come from harness.drift, which asks where
each original page's words actually landed.
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

DPI = 110
GAP = 18
LABEL = 34


def _render(pdf, page, dpi=DPI):
    with pymupdf.open(pdf) as d:
        if page < 0 or page >= d.page_count:
            return None
        return d[page].get_pixmap(dpi=dpi)


def pair(orig_pdf, out_pdf, page, dest, dpi=DPI, ours_page=None):
    """One page of each, side by side, saved as a PNG. -> path or None."""
    a = _render(orig_pdf, page, dpi)
    b = _render(out_pdf, page if ours_page is None else ours_page, dpi)
    if a is None and b is None:
        return None
    h = max(x.height for x in (a, b) if x)
    w = sum(x.width for x in (a, b) if x) + GAP
    canvas = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h + LABEL), False)
    canvas.clear_with(255)
    # ours on the left, original on the right - these documents read that way
    x = 0
    for pix in (b, a):
        if pix is None:
            continue
        pix.set_origin(x, LABEL)
        canvas.copy(pix, pix.irect)
        x += pix.width + GAP
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("original")
    ap.add_argument("rebuilt")
    ap.add_argument("--pages", default="1", help="1-based, comma separated")
    ap.add_argument("--out", default="out/work/look")
    ap.add_argument("--dpi", type=int, default=DPI)
    ap.add_argument("--align", action="store_true",
                    help="find OUR page holding each original page's content")
    a = ap.parse_args()

    landed = {}
    if a.align:
        from harness.drift import drift
        landed = {i: j for i, _, j, _, _ in drift(a.original, a.rebuilt)
                  if j is not None}

    stem = Path(a.original).stem[:30]
    made = []
    for s in a.pages.split(","):
        n = int(s.strip())
        ours = landed.get(n - 1, n - 1) if a.align else n - 1
        p = pair(a.original, a.rebuilt, n - 1,
                 Path(a.out) / f"{stem}-p{n}.png", a.dpi, ours_page=ours)
        if p:
            made.append(p)
            note = f"   (original p{n} vs ours p{ours + 1})" if ours != n - 1 else ""
            print(f"  {p}   ours left, original right{note}")
    if not made:
        print("no pages rendered")


if __name__ == "__main__":
    main()
