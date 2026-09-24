#!/usr/bin/env python3
"""Tests for picture extraction.

    python -m harness.test_images

عن بعد.pdf lost its only picture and nothing reported it. The picture is a
valid baseline JPEG, but PDFs routinely store bare DCT streams with no JFIF
wrapper - the PDF object already carries the colorspace and size, so the APP0
segment is redundant - and python-docx identifies a JPEG only by the literal
bytes "JFIF" or "Exif" at offset 6. With no APP0 segment those six bytes are
quantization-table data, no signature matches, and add_picture raises
UnrecognizedImageError. _emit_image caught it and returned None, so the
picture vanished silently.

A second, different case turned up on the wild corpus once drops were being
counted: z20496510.pdf carries JPEGs that declare a pixel density of ZERO.
python-docx identifies those perfectly well and only fails later, when it works
out the native size as pixels / dpi and divides by zero. So "can python-docx
identify these bytes" is the wrong question - the right one is "can it actually
use them", which means asking for the dimensions too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf
from convert.reader import read_images

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<46} got {got!r}  want {want!r}")
    if not ok:
        FAILED.append(name)


def _strip_app0(jpeg):
    """Remove the APP0/JFIF segment, leaving the image data untouched.

    This is what a PDF-embedded JPEG usually looks like.
    """
    assert jpeg[:2] == b"\xff\xd8" and jpeg[2:4] == b"\xff\xe0", "expected SOI+APP0"
    seg = int.from_bytes(jpeg[4:6], "big")
    return jpeg[:2] + jpeg[2 + 2 + seg:]


def _zero_dpi(jpeg):
    """Set the JFIF pixel density to zero, as z20496510.pdf's pictures do.

    APP0 layout: FFE0, length(2), "JFIF\\0"(5), version(2), units(1),
    Xdensity(2), Ydensity(2).
    """
    j = bytearray(jpeg)
    assert j[2:4] == b"\xff\xe0" and j[6:11] == b"JFIF\x00", "expected a JFIF APP0"
    off = 4 + 2 + 5 + 2                      # start of units
    j[off + 1:off + 3] = b"\x00\x00"         # Xdensity
    j[off + 3:off + 5] = b"\x00\x00"         # Ydensity
    return bytes(j)


def _pdf_with(tmp, blob, w, h):
    """A one-page PDF carrying blob as its only picture, drawn large."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(pymupdf.Rect(40, 40, 40 + w, 40 + h), stream=blob)
    out = tmp / "one.pdf"
    doc.save(out)
    doc.close()
    return out


def main():
    tmp = Path("out/tests/images")
    tmp.mkdir(parents=True, exist_ok=True)

    # Build a real JPEG, then take its JFIF header off.
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 320, 120))
    pix.clear_with(128)
    jfif = pix.tobytes("jpeg")
    bare = _strip_app0(jfif)
    nodpi = _zero_dpi(jfif)

    print("the trigger: python-docx cannot identify a JPEG with no APP0 segment")
    from docx.image.image import Image as DocxImage
    def readable(b):
        try:
            DocxImage.from_blob(b)
            return True
        except Exception:
            return False
    def usable(b):
        """Identifying it is not enough - Word needs its size in real units."""
        try:
            im = DocxImage.from_blob(b)
            im.width, im.height
            return True
        except Exception:
            return False
    check("with JFIF header", readable(jfif), True)
    check("with JFIF header stripped", readable(bare), False)

    print("\nand a zero pixel density passes identification, then divides by zero")
    check("zero-dpi JPEG identifies fine", readable(nodpi), True)
    check("...but cannot be measured", usable(nodpi), False)
    check("a normal JPEG can be measured", usable(jfif), True)

    print("\nread_images must hand back something Word can actually open")
    for label, blob in (("normal JPEG", jfif), ("bare JPEG, no JFIF header", bare),
                        ("JPEG declaring zero dpi", nodpi)):
        pdf = _pdf_with(tmp, blob, 320, 120)
        out = tmp / label.replace(" ", "_").replace(",", "")
        blocks = read_images(str(pdf), out)
        check(f"{label}: extracted", len(blocks), 1)
        if blocks:
            data = Path(blocks[0].image).read_bytes()
            check(f"{label}: Word can read it", readable(data), True)
            check(f"{label}: Word can measure it", usable(data), True)

    print("\na picture drawn many times must not score as lost")
    # Same picture on 4 pages: Word stores it once and points at it 4 times.
    doc = pymupdf.open()
    for _ in range(4):
        page = doc.new_page(width=595, height=842)
        page.insert_image(pymupdf.Rect(40, 40, 360, 160), stream=jfif)
    many = tmp / "repeated.pdf"
    doc.save(many); doc.close()
    dst = tmp / "repeated.docx"
    from convert.v1 import convert as convert_v1
    from harness.compare import count_docx_structure, count_pdf_structure
    convert_v1(str(many), str(dst))
    check("original placements", count_pdf_structure(str(many))[1], 4)
    check("placements written to the docx", count_docx_structure(str(dst))[1], 4)

    print("\na picture keeps the shape it was drawn at")
    # Drawn squashed to half its height (z21418248 has one at 2.3 times its
    # own width-to-height), and drawn turned on its side (z20538636 page 17).
    import io, re, zipfile
    from PIL import Image
    # Not flat grey: a flat picture is photographed off the page (_is_flat),
    # which hides the stored shape from this check.
    photo = io.BytesIO()
    Image.effect_noise((320, 120), 60).convert("RGB").save(photo, "JPEG")
    for label, rect, rotate in (("squashed", (40, 40, 360, 100), 0),
                                ("turned on its side", (40, 40, 160, 360), 90)):
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_image(pymupdf.Rect(*rect), stream=photo.getvalue(), rotate=rotate,
                          keep_proportion=False)
        # Text too, or the page reads as a scan and is refused.
        page.insert_text((40, 420), "A line of text under the picture.")
        src = tmp / f"shape-{rotate}.pdf"
        doc.save(src); doc.close()
        dst = tmp / f"shape-{rotate}.docx"
        convert_v1(str(src), str(dst))
        with zipfile.ZipFile(dst) as z:
            xml = z.read("word/document.xml").decode("utf-8")
            media = [n for n in z.namelist() if n.startswith("word/media/")]
            px = Image.open(io.BytesIO(z.read(media[0]))).size if media else (0, 0)
        cx, cy = map(int, re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"', xml).groups())
        drawn = (rect[2] - rect[0]) / (rect[3] - rect[1])
        check(f"{label}: placed at the drawn shape", round(cx / cy, 2), round(drawn, 2))
        check(f"{label}: stored the way round it is drawn", px[0] > px[1], drawn > 1)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
