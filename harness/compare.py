"""Compare two PDFs: how much text survived, and does the page still look the same.

Two separate scores, because they fail for different reasons:

  text_score   did the words survive, in the right order?  (immune to fonts)
  ink_score    does the page still LOOK the same?          (catches layout loss)
"""
import collections, difflib, html, re, sys, zipfile
from pathlib import Path
import numpy as np
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.arabic import repair_lam_alef

WORD = re.compile(r"\S+")
TASHKEEL = re.compile(r"[ً-ْٰـ]")   # harakat + tatweel


def words(text, strip_marks=False):
    t = text or ""
    if strip_marks:
        t = TASHKEEL.sub("", t)
    return WORD.findall(t)


def text_of(pdf_path):
    # Repaired here as well as in the reader, and it must be both. The repair
    # fixes text the SOURCE pdf hands over backwards, so if only our output
    # were corrected it would stop matching the still-mangled original it is
    # scored against, and fixing a real defect would read as a regression.
    with pymupdf.open(pdf_path) as d:
        return repair_lam_alef("\n".join(pg.get_text("text") for pg in d))


def text_of_docx(docx_path):
    """Read the Word file's own text.

    The text score must never go through LibreOffice: a render round-trip adds
    its own layout and shaping differences, so scoring a rendered PDF measures
    the renderer as much as us. Rendering is only needed for the look score,
    where we compare pictures.

    This used to say that LibreOffice reverses Arabic letter pairs (لا -> ال).
    That was wrong, and the wrong explanation survived here long enough to be
    repeated as fact. The reversal is in the SOURCE pdf: لا is a ligature whose
    ToUnicode entry lists its two letters backwards, and the .docx carries the
    reversed pair before LibreOffice is ever invoked. Repaired now in
    convert/arabic.py.
    """
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        notes = _footnote_texts(z)
    out, buf, pending = [], [], []

    def end_para():
        if buf:
            out.append("".join(buf))
        buf.clear()

    def end_page():
        # A real footnote lives in footnotes.xml, but on the PAGE it is printed
        # at the bottom - and that is where the original PDF's text extraction
        # finds it too. Flushing each page's notes at its page break puts them
        # back in the order the original reads in; appending them all at the end
        # instead cost 15-30 points of order-aware text score for text that had
        # not moved at all.
        end_para()
        out.extend(pending)
        pending.clear()

    for m in re.finditer(r"<w:p[ >]|<w:t[^>]*>([^<]*)</w:t>"
                         r"|<w:pageBreakBefore/>"
                         r'|<w:footnoteReference w:id="(\d+)"/>', xml):
        tok = m.group(0)
        if tok.startswith("<w:pageBreakBefore"):
            end_page()
        elif tok.startswith("<w:footnoteReference"):
            if m.group(2) in notes:
                pending.append(notes[m.group(2)])
        elif tok.startswith("<w:p"):
            end_para()
        else:
            buf.append(m.group(1))
    end_page()
    # Word stores text XML-escaped: "A & B" is "A &amp; B" on disk. Without
    # unescaping, every ampersand looked like lost text.
    return html.unescape("\n".join(out))


def _footnote_texts(z):
    """{w:id: text} from word/footnotes.xml, skipping Word's two separators."""
    if "word/footnotes.xml" not in z.namelist():
        return {}
    xml = z.read("word/footnotes.xml").decode("utf-8")
    out = {}
    for m in re.finditer(r'<w:footnote (?![^>]*w:type=)[^>]*w:id="(\d+)"[^>]*>'
                         r'(.*?)</w:footnote>', xml, re.S):
        body = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", m.group(2)))
        if body.strip():
            out[m.group(1)] = body
    return out


ALLWS = re.compile(r"\s+")
SENT = re.compile(r"[.؟!؛:\n]+|،")
BIG_DOC = 20000          # sentences; beyond this fall back to a cheap estimate


def _norm(t, strip_marks=False):
    t = t or ""
    if strip_marks:
        t = TASHKEEL.sub("", t)
    return ALLWS.sub("", t)


def _sentences(text, strip_marks=False, min_len=12):
    """Sentences, whitespace stripped so spacing differences don't matter."""
    out = []
    for piece in SENT.split(text or ""):
        piece = _norm(piece, strip_marks)
        if len(piece) >= min_len:
            out.append(piece)
    return out


def _lis_weight(items):
    """Longest run of items whose positions increase, weighted by length.

    items is [(position_in_output, weight)]. Patience sorting, O(n log n).
    """
    import bisect
    if not items:
        return 0
    tails, back, idx = [], [None] * len(items), []
    for n, (pos, _) in enumerate(items):
        i = bisect.bisect_left(tails, pos)
        if i == len(tails):
            tails.append(pos); idx.append(n)
        else:
            tails[i] = pos; idx[i] = n
        back[n] = idx[i - 1] if i else None
    # walk back to total the weights on the winning run
    total, k = 0, idx[len(tails) - 1]
    while k is not None:
        total += items[k][1]
        k = back[k]
    return total


MAX_OCCURRENCES = 64     # a phrase repeated more than this tells us nothing new


def _positions(hay, s, limit=MAX_OCCURRENCES):
    """Every place this sentence occurs, in order."""
    out, i = [], hay.find(s)
    while i >= 0 and len(out) < limit:
        out.append(i)
        i = hay.find(s, i + 1)
    return out


def text_score(a, b, strip_marks=False):
    """0-1. How much of A survives in B, in the same order.

    Two earlier attempts failed. Comparing characters was quadratic - on a
    72-page document it held a core at 97% for an hour without finishing.
    Hashing whole sentences was fast but brittle: one changed character threw
    away the whole sentence, dragging real scores to 7%.

    This locates each of the original's sentences inside the output, then finds
    the longest run of them that appears in increasing order. Substring lookup
    tolerates differences around a sentence; the ordering test is what
    distinguishes text that moved from text that stayed put. O(n log n).

    Every occurrence is offered, not just the first. Taking only the first
    match silently punished repetition: classical Arabic repeats formulae
    constantly - صلى الله عليه وسلم appeared 8 times in one chapter - and all 8
    lookups returned the same position, so at most one could sit on an
    increasing run and the other 7 were scored as lost. A chapter scored 82.8%
    against an output that was missing nothing at all. The occurrences of one
    sentence are offered newest-first so that a run can still take only one.
    """
    sents = _sentences(a, strip_marks)
    if not sents:
        return 0.0
    hay = _norm(b, strip_marks)
    total = sum(len(s) for s in sents)
    found = []
    for s in sents:
        at = _positions(hay, s)
        if not at and len(s) > 24:           # allow a damaged edge
            pad = len(s) // 8
            at = _positions(hay, s[pad:-pad])
        found += [(p, len(s)) for p in reversed(at)]
    if not found:
        return 0.0
    return min(1.0, _lis_weight(found) / total)


def _ink(page, dpi=72):
    """Boolean array: True where the page has ink."""
    pm = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)
    return arr < 200


def _fit(a, b):
    """Crop both to a common shape so pages of slightly different size compare."""
    h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    return a[:h, :w], b[:h, :w]


GRID = 48


def _coarse(mask, grid=None):
    """Ink density on a coarse grid: what fraction of each cell is inked."""
    grid = GRID if grid is None else grid
    h, w = mask.shape
    ch, cw = max(1, h // grid), max(1, w // grid)
    h2, w2 = (h // ch) * ch, (w // cw) * cw
    m = mask[:h2, :w2].astype(np.float32)
    return m.reshape(h2 // ch, ch, w2 // cw, cw).mean(axis=(1, 3))


def ink_iou(pa, pb, dpi=72):
    """How alike do the two pages look?

    Compared on a coarse grid of ink density, not pixel by pixel. Exact pixel
    overlap is unreachable even when the layout is right: Word and LibreOffice
    break Arabic lines at slightly different points, so a correct page can
    score near zero. This asks the useful question instead - is there text in
    roughly the same places, in roughly the same amount?
    """
    a, b = _fit(_ink(pa, dpi), _ink(pb, dpi))
    ca, cb = _coarse(a), _coarse(b)
    h, w = min(ca.shape[0], cb.shape[0]), min(ca.shape[1], cb.shape[1])
    ca, cb = ca[:h, :w], cb[:h, :w]
    denom = np.maximum(ca, cb)
    if denom.sum() == 0:
        return 1.0
    return float(1 - np.abs(ca - cb).sum() / denom.sum())


MIN_WORD = 4


def _page_words(page):
    """Distinctive words on a page - short ones match everywhere, so drop them."""
    return [w for w in WORD.findall(page.get_text("text")) if len(w) >= MIN_WORD]


def page_alignment(orig_pdf, rebuilt_pdf):
    """Did each page's content land on the matching page?

    Replaces ink-density comparison, which turned out to have almost no
    discriminating power: our reconstruction scored 29% against the original
    while unrelated Arabic documents averaged 28%. Ink density only measures
    "there is a block of text here", which is true of every text document.

    Compared as word counts per page. Characters were useless here - any two
    Arabic texts share the same alphabet, so unrelated documents scored 48%.
    Words are distinctive. LibreOffice reverses the odd Arabic letter pair when
    it renders our .docx, which damages a few words per page, not enough to
    matter against thousands.
    """
    with pymupdf.open(orig_pdf) as A, pymupdf.open(rebuilt_pdf) as B:
        pa = [_page_words(p) for p in A]
        pb = [_page_words(p) for p in B]
    if not pa:
        return 0.0, []
    per = []
    for i, a in enumerate(pa):
        if not a:
            per.append(1.0)
            continue
        b = pb[i] if i < len(pb) else ""
        ca, cb = collections.Counter(a), collections.Counter(b)
        per.append(sum((ca & cb).values()) / len(a))
    return float(np.mean(per)), per


MIN_IMAGE_PT = 24.0          # drawn size: anything smaller is a spacer
MIN_IMAGE_PX = 16            # source size: 2x2 pixel images are Word artifacts


def count_pdf_structure(pdf_path):
    """Tables and real pictures in the original.

    Scoring counted only words, so a chemistry page that lost its table and
    both molecular diagrams still scored 86%. Nothing was watching the parts
    that are not text.

    Pictures are counted by how big they are drawn on the page, not by pixel
    size: Word litters pages with 2x2 pixel images stretched into thin bars -
    one page carried 276 of them - and none of those are pictures.
    """
    tables = images = 0
    with pymupdf.open(pdf_path) as d:
        for page in d:
            try:
                tables += len(page.find_tables().tables)
            except Exception:
                pass
            seen = set()
            for info in page.get_images(full=True):
                xref, w, h = info[0], info[2], info[3]
                if xref in seen or w < MIN_IMAGE_PX or h < MIN_IMAGE_PX:
                    continue                      # a 2x2 source is never a picture
                for r in page.get_image_rects(xref) or []:
                    if r.width >= MIN_IMAGE_PT and r.height >= MIN_IMAGE_PT:
                        images += 1
                        seen.add(xref)
                        break
    return tables, images


BLIP = re.compile(r"<a:blip\b")


def count_docx_structure(docx_path, pages=1):
    """Pictures are counted where they are PLACED, not where they are stored.

    Counting files in word/media/ undercounted badly: Word stores each distinct
    picture once and references it from every place it appears. One chapter
    drew the same six separators 44 times, so it stored 6 files and scored
    6/44 = 14% while having lost nothing at all. count_pdf_structure counts
    placements, so this has to count placements too or the two sides are not
    the same question.

    A running header or footer is stored once and drawn by Word on every page,
    so its one blip stands for `pages` placements - which is how the same
    decoration is counted on the PDF side, once per page it appears on.
    """
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        furniture = sum(len(BLIP.findall(z.read(n).decode("utf-8")))
                        for n in z.namelist()
                        if re.match(r"word/(header|footer)\d*\.xml$", n))
    return xml.count("<w:tbl>"), len(BLIP.findall(xml)) + furniture * pages


def structure_score(orig_pdf, docx_path):
    """-> dict of what the original had and what we produced."""
    ot, oi = count_pdf_structure(orig_pdf)
    with pymupdf.open(orig_pdf) as d:
        pages = len(d)
    dt, di = count_docx_structure(docx_path, pages)
    def keep(want, got):
        if not want:
            return 1.0
        return min(1.0, got / want)
    return {"tables_orig": ot, "tables_out": dt,
            "images_orig": oi, "images_out": di,
            "tables_kept": round(keep(ot, dt), 3),
            "images_kept": round(keep(oi, di), 3)}


def compare(orig_pdf, rebuilt_pdf, docx=None, dpi=72):
    """Text is scored from the .docx; only the look score uses the rebuilt PDF."""
    ta = text_of(orig_pdf)
    tb = text_of_docx(docx) if docx else text_of(rebuilt_pdf)
    out = {
        "text_score": round(text_score(ta, tb), 4),
        "text_score_no_marks": round(text_score(ta, tb, strip_marks=True), 4),
        "words_orig": len(words(ta)),
        "words_out": len(words(tb)),
    }
    with pymupdf.open(orig_pdf) as A, pymupdf.open(rebuilt_pdf) as B:
        out["pages_orig"], out["pages_out"] = len(A), len(B)
        n = min(len(A), len(B))
        per = [round(ink_iou(A[i], B[i], dpi), 4) for i in range(n)]
        out["ink_per_page"] = per
        out["ink_score"] = round(float(np.mean(per)), 4) if per else 0.0
    if docx:
        try:
            out.update(structure_score(orig_pdf, docx))
        except Exception:
            pass
    align, per_page = page_alignment(orig_pdf, rebuilt_pdf)
    out["page_score"] = round(align, 4)
    out["worst_pages"] = sorted(range(len(per_page)), key=lambda i: per_page[i])[:5]
    return out
