#!/usr/bin/env python3
"""Tests for refusing scans (FLAGS.md 1, decided with Moaz 2026-09-22).

    python -m harness.test_scan

What was found: 46 of the 52 corpus files whose text reads backwards were
scans with OCR text laid invisibly over a photo. 29 more were Canva designs,
one picture per page and no text. Both are refused. A thesis whose title page
is one photo is NOT a scan and must still convert.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf
from convert.scan import scanned, _page_is_scan

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<55} got {got!r}")
    if not ok:
        FAILED.append(name)


def photo(page, share=1.0):
    """A grey picture covering `share` of the page, centred."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    pix.set_rect(pix.irect, (200, 200, 200))
    r = page.rect
    dx, dy = r.width * (1 - share ** 0.5) / 2, r.height * (1 - share ** 0.5) / 2
    page.insert_image(pymupdf.Rect(r.x0 + dx, r.y0 + dy, r.x1 - dx, r.y1 - dy), pixmap=pix)


def text(page, visible=True, n=6):
    for i in range(n):
        page.insert_text((72, 100 + 20 * i), "Lorem ipsum dolor sit amet, consectetur",
                         render_mode=0 if visible else 3)


def main():
    tmp = Path(tempfile.mkdtemp())

    d = pymupdf.open()
    p = d.new_page(); photo(p); text(p, visible=False)
    check("OCR scan: invisible text over a photo", _page_is_scan(p), True)
    p = d.new_page(); photo(p, 0.6); text(p, visible=False)
    check("OCR scan with wide margins (photo 60%)", _page_is_scan(p), True)
    p = d.new_page(); photo(p)
    check("picture-only page (Canva export)", _page_is_scan(p), True)
    p = d.new_page(); text(p)
    check("an ordinary text page", _page_is_scan(p), False)
    p = d.new_page(); photo(p); text(p)
    check("visible text over a background picture", _page_is_scan(p), False)
    p = d.new_page()
    check("a blank page", _page_is_scan(p), False)

    # A thesis: title page one photo, then text.
    d = pymupdf.open()
    photo(d.new_page())
    for _ in range(5):
        text(d.new_page())
    f = tmp / "thesis.pdf"; d.save(f)
    check("thesis with a photographed title page converts", scanned(f)[0], False)

    d = pymupdf.open()
    for _ in range(4):
        p = d.new_page(); photo(p); text(p, visible=False)
    f = tmp / "scan.pdf"; d.save(f)
    check("a scanned document is refused", scanned(f)[0], True)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
