#!/usr/bin/env python3
"""Tests for pictures the writer cannot place.

    python -m harness.test_image_drop

python-docx identifies an image by its literal signature bytes, and refuses
anything it does not recognise. The writer used to catch that with a bare
`except` and return None, which had two consequences:

  1. Nothing counted the loss. A bare DCT JPEG with no APP0/JFIF segment was
     being dropped from `عن بعد.pdf` on every run and no output said so - it
     took a scoring fix to notice one picture had gone missing.
  2. `_emit_image` adds its paragraph BEFORE trying to place the picture, so a
     failure left an empty paragraph in the document. That is the exact defect
     the page-break comment in `write()` warns about: an empty paragraph eats a
     line, and on a long document the accumulated overflow pushes pagination
     out of step.

Re-rendering is the first line of defence and lives in the reader. This is the
second: whatever still cannot be placed must be counted and must not leave a
mark on the page.
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert.model import Doc, Block, PARAGRAPH, IMAGE, TABLE
from convert.writer import write

FAILED = []
BLIP = re.compile(r"<a:blip\b")


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}")
    if not ok:
        FAILED.append(name)


def _png(path, w=120, h=80):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h))
    pix.clear_with(128)
    pix.save(path)
    return str(path)


def _junk(path):
    """A file python-docx cannot identify, whatever it is called."""
    Path(path).write_bytes(b"\x00\x01\x02 not an image at all \xff\xfe")
    return str(path)


def _model(pages=1):
    return Doc(pages=pages, page_width=595.0, page_height=842.0,
               margin_top=72.0, margin_bottom=72.0,
               margin_left=72.0, margin_right=72.0, body_size=12.0)


def _counts(docx):
    """(paragraphs, blips) in the body."""
    with zipfile.ZipFile(docx) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return len(re.findall(r"<w:p[ >]", xml)), len(BLIP.findall(xml))


def _blips_in(docx, pattern):
    with zipfile.ZipFile(docx) as z:
        return sum(len(BLIP.findall(z.read(n).decode("utf-8")))
                   for n in z.namelist() if re.match(pattern, n))


def main():
    tmp = Path("out/tests/image_drop")
    tmp.mkdir(parents=True, exist_ok=True)
    good = _png(tmp / "good.png")
    junk = _junk(tmp / "junk.png")

    print("a picture that cannot be placed is counted, not swallowed")
    m = _model()
    m.blocks.append(Block(kind=PARAGRAPH, text="نص قبل الصورة.", page=0, y=100, y1=120))
    m.blocks.append(Block(kind=IMAGE, text="", page=0, image=junk,
                          x0=72, x1=272, y=200, y1=330))
    docx = tmp / "one_bad.docx"
    write(m, str(docx))
    check("one drop recorded", len(m.dropped_images), 1)
    check("the drop names the file", Path(m.dropped_images[0][0]).name, "junk.png")

    print("\nand leaves no empty paragraph behind")
    # Same model with the image block simply absent: the two documents must have
    # the same number of paragraphs, or the failure cost the page a line.
    ref = _model()
    ref.blocks.append(Block(kind=PARAGRAPH, text="نص قبل الصورة.", page=0, y=100, y1=120))
    refdocx = tmp / "no_image.docx"
    write(ref, str(refdocx))
    check("paragraph count matches the image-free document",
          _counts(docx)[0], _counts(refdocx)[0])
    check("no picture was drawn", _counts(docx)[1], 0)

    print("\na picture that CAN be placed is not counted as a drop")
    m = _model()
    m.blocks.append(Block(kind=IMAGE, text="", page=0, image=good,
                          x0=72, x1=192, y=200, y1=280))
    docx = tmp / "one_good.docx"
    write(m, str(docx))
    check("nothing recorded", len(m.dropped_images), 0)
    check("the picture was drawn", _counts(docx)[1], 1)

    print("\nevery drop is counted, not just the first")
    m = _model()
    for n in range(3):
        m.blocks.append(Block(kind=IMAGE, text="", page=0, image=_junk(tmp / f"j{n}.png"),
                              x0=72, x1=272, y=100 + n * 50, y1=140 + n * 50))
    m.blocks.append(Block(kind=IMAGE, text="", page=0, image=good,
                          x0=72, x1=192, y=400, y1=480))
    docx = tmp / "three_bad.docx"
    write(m, str(docx))
    check("three drops recorded", len(m.dropped_images), 3)
    check("the good picture still got through", _counts(docx)[1], 1)

    print("\na running header that cannot be placed is counted too")
    # Recurs on every page and sits above the text column, so it is furniture.
    m = _model(pages=4)
    for p in range(4):
        m.blocks.append(Block(kind=IMAGE, text="", page=p, image=junk,
                              x0=72, x1=272, y=20, y1=60))
        m.blocks.append(Block(kind=PARAGRAPH, text="نص الصفحة.", page=p, y=200, y1=220))
    docx = tmp / "bad_header.docx"
    write(m, str(docx))
    check("the header drop is recorded", len(m.dropped_images), 1)
    check("nothing drawn in the header", _blips_in(docx, r"word/header\d*\.xml$"), 0)

    print("\na picture inside a table cell is counted too")
    m = _model()
    m.blocks.append(Block(kind=TABLE, text="", page=0,
                          rows=[["الأول", "الثاني"], ["واحد", ""]],
                          col_widths=[90.0, 90.0],
                          cell_images={(1, 1): junk},
                          x0=72, x1=252, y=200, y1=300))
    docx = tmp / "bad_cell.docx"
    write(m, str(docx))
    check("the cell drop is recorded", len(m.dropped_images), 1)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
