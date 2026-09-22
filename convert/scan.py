"""Is this PDF a scan? Scans are out of scope: detected and refused.

A scan is a photograph of a paper page. Some carry no text at all; most in this
corpus carry text a character-recognition program (OCRmyPDF) read off the
photo and laid over it INVISIBLY, so the page can be searched. That text is
noisy, and in this corpus it is stored backwards: 46 of the 52 files whose
text reads backwards were scans (FLAGS.md 1, 2026-09-22). Converting one
gives a Word file nobody can read, while the checker - which reads the same
invisible text - scores it near 100%.

Both kinds are recognised from the file alone. On the files checked, a scan
page had every character invisible over a picture covering 97-100% of the
page; a digital page had no invisible text and pictures under 3%. Nothing in
between, so the thresholds below sit in open space.

Decided with Moaz, 2026-09-22: refuse scans, with a plain message.
"""
import pymupdf

# A picture this big is the page, not a picture on the page.
PAGE_PHOTO = 0.85
# Fewer visible characters than this: the page shows no real text of its own.
# (A page number or a stray mark on a scan is not a text layer.)
MAX_VISIBLE = 20
# Refuse only when most of the document is scanned. A thesis whose title
# page is one photo (`مقدمة البحث`), or with one scanned appendix page, is
# still a digital document.
SCANNED_SHARE = 0.8
SAMPLE = 12             # pages looked at: all of a short file, else spread out

MESSAGE = ("This PDF's pages are pictures - a scan of paper pages, or a design "
           "exported as images - so it has no real text to convert. Qirtas "
           "converts PDFs that were saved from a word processor such as Word. "
           "A scanned document needs a character-recognition program instead.")


class Refused(Exception):
    """The file is outside what Qirtas converts. str() is for the user."""


def _page_is_scan(page):
    """A page showing no text of its own, that is either one photo or carries
    only invisible text. Checked on the corpus, 2026-09-22: OCRmyPDF photos
    cover 97-100% of the page, but z19661622's covers 61% with wide margins -
    its 951 characters are all invisible, which no digital page has. And 29
    Canva files are one full-page picture per page with no text at all."""
    visible = invisible = 0
    for tr in page.get_texttrace():
        n = sum(1 for c in tr.get("chars", ()) if chr(c[0]).strip())
        # Render mode 3 is "neither fill nor stroke": text that is there to
        # be found, not seen. What OCR lays over a photo.
        if tr.get("type") == 3 or tr.get("opacity", 1) == 0:
            invisible += n
        else:
            visible += n
    if visible >= MAX_VISIBLE:
        return False
    if invisible:
        return True
    area = abs(page.rect) or 1.0
    photo = max((abs(pymupdf.Rect(i["bbox"]) & page.rect) / area
                 for i in page.get_image_info()), default=0.0)
    return photo >= PAGE_PHOTO


def scanned(path):
    """-> (is it a scan?, "k of n pages") from a sample of its pages."""
    with pymupdf.open(path) as d:
        n = d.page_count
        if not n:
            return False, "no pages"
        idx = sorted({round(i * (n - 1) / max(1, SAMPLE - 1))
                      for i in range(min(n, SAMPLE))})
        hits = sum(1 for i in idx if _page_is_scan(d[i]))
    return hits >= SCANNED_SHARE * len(idx), f"{hits} of {len(idx)} pages scanned"


def refuse_scans(path):
    """Raise Refused if the file is a scan."""
    is_scan, detail = scanned(path)
    if is_scan:
        raise Refused(f"{MESSAGE} ({detail})")
