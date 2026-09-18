#!/usr/bin/env python3
"""Tell an ordinary document from a periodical page.

    python -m harness.doctype corpus/wild/*.pdf

The dev set turned out to be two populations, not one, and averaging them
together produced a number that described neither. Half the files are what this
converter is for - theses, reports, articles, one column of 11-13pt text. The
rest are newspaper and magazine pages: five columns of 4-7pt type, 150 to 300
lines on a single A4 page, headlines and rules between them.

A newspaper page cannot survive a converter that emits one linear column, and
it was never meant to. Reading order alone defeats it: five columns of text
extract in an order no single-column flow can reproduce, so the score collapses
whatever the writer does. Nothing here is a bug to fix - it is a document class
that is out of scope, and it belongs in the limitations section of the paper
rather than in the average.

The rule is deliberately crude and measured on the FIRST PAGE ONLY, because it
exists to separate populations, not to classify documents well:

    median body type under 9pt

Line count was tried first, as "under 9pt OR more than 80 lines", and dropped:
on the dev set it misfiled two ordinary documents whose first page happens to
be a long list of short lines, one of which scores 98.4%. Font size alone
separates the dev set completely - periodicals land at 4.0-7.2pt, documents at
10.0pt and above, and nothing at all falls in between - so the threshold is not
doing delicate work and the second clause only added mistakes.

A first page with no text at all (a scanned cover) counts as a document; there
is nothing to measure and guessing would only add noise.

Declared here, separately from any results, and frozen before the holdout set
is opened, so the same rule applies to both without being tuned to what the
holdout says.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

MAX_BODY_PT = 9.0


def measure(path):
    """-> (median font size in points, lines) on the first page."""
    with pymupdf.open(path) as d:
        if not len(d):
            return 0.0, 0
        td = d[0].get_text("dict")
    sizes, lines = [], 0
    for b in td["blocks"]:
        for l in b.get("lines", ()):
            lines += 1
            sizes.extend(s["size"] for s in l["spans"])
    if not sizes:
        return 0.0, lines
    sizes.sort()
    return sizes[len(sizes) // 2], lines


def is_periodical(path):
    size, lines = measure(path)
    if not lines or not size:
        return False
    return size < MAX_BODY_PT


def main():
    print(f"{'file':<20}{'body pt':>9}{'lines':>7}  class")
    for f in sys.argv[1:]:
        size, lines = measure(f)
        kind = "periodical" if is_periodical(f) else "document"
        print(f"{Path(f).name:<20}{size:>9.1f}{lines:>7}  {kind}")


if __name__ == "__main__":
    main()
