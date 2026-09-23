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
from convert.glyphs import repaired, spell_out
from convert.pdftext import apply_fixes, fix_map
# ١٢١ and 121 are the same number, read the same on both sides. The writer
# shows digits the way the original's pages did (N5a), and the original
# STORES them typed: without this every number it corrected read as lost.
from convert.footnotes import WESTERN

WORD = re.compile(r"\S+")
TASHKEEL = re.compile(r"[ً-ْٰـ]")   # harakat + tatweel


def words(text, strip_marks=False):
    t = text or ""
    if strip_marks:
        t = TASHKEEL.sub("", t)
    return WORD.findall(t)


def text_of(pdf_path, pages=False):
    # Repaired here as well as in the reader, and it must be both. The repair
    # fixes text the SOURCE pdf hands over backwards, so if only our output
    # were corrected it would stop matching the still-mangled original it is
    # scored against, and fixing a real defect would read as a regression.
    #
    # The geometric repairs come in as a text-to-text map derived from this
    # same PDF, so this side and the reader apply exactly the same
    # substitutions to whatever each of them extracted. Deriving them here
    # independently - rather than being handed them - is what makes that true
    # regardless of which route the reader took.
    # A font whose table names the wrong letters is read through the same
    # corrected copy the converter reads (FLAGS.md 23) - on either side:
    # Word's own export of our file drops vowel marks to blanks the same way.
    pdf_path = repaired(pdf_path)
    try:
        fixes = fix_map(pdf_path)
    except Exception:
        fixes = {}
    with pymupdf.open(pdf_path) as d:
        texts = [pg.get_text("text") for pg in d]
    if pages:
        # One string per page, for finding which page a sentence is on.
        return [spell_out(apply_fixes(repair_lam_alef(t), fixes)).translate(WESTERN)
                for t in texts]
    raw = "\n".join(texts)
    # Spelling repair FIRST, then the map - the reader's order (`_clean` as it
    # reads, the map at the end). The spelling repair is not safe to run
    # twice, so the two orders differ on some words: on z20375390 the map's
    # output was spelling-repaired again here and not in the reader, and the
    # gate lost 1.6% (TASKS N3a). The map carries each word both as stored
    # and as the spelling repair leaves it, so either order finds it.
    return spell_out(apply_fixes(repair_lam_alef(raw), fixes)).translate(WESTERN)


def text_of_docx(docx_path, pages=False):
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

    pages=True: a list, one string per original page (the writer breaks the
    page before each one), endnotes with the last - for comparing a page with
    what the original's page shows (harness/truth.py).
    """
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        notes = _footnote_texts(z)
        endnotes = _footnote_texts(z, "endnote")
        furniture = _furniture_texts(z)
    out, buf, pending = [], [], []
    page = [0]
    bounds = []

    def end_para():
        if buf:
            out.append("".join(buf))
        buf.clear()

    def start_page():
        # A running header lives in header1.xml and is DRAWN ON EVERY PAGE, so
        # the original PDF's extraction finds it once per page. Emit it the
        # same way or the text it holds reads as lost - the identical trap
        # footnotes had, and the gate would have blamed the converter for text
        # that is present and correct.
        out.extend(furniture("header", page[0]))

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
        out.extend(furniture("footer", page[0]))
        page[0] += 1
        bounds.append(len(out))

    start_page()
    for m in re.finditer(r"<w:p[ >]|<w:t[^>]*>([^<]*)</w:t>"
                         r"|<w:pageBreakBefore/>"
                         r'|<w:footnoteReference w:id="(\d+)"/>', xml):
        tok = m.group(0)
        if tok.startswith("<w:pageBreakBefore"):
            end_page()
            start_page()
        elif tok.startswith("<w:footnoteReference"):
            if m.group(2) in notes:
                pending.append(notes[m.group(2)])
        elif tok.startswith("<w:p"):
            end_para()
        else:
            buf.append(m.group(1))
    end_page()
    # Endnotes are printed after the last page, as the original printed them.
    # Unread, every one of them would count as lost text.
    out.extend(endnotes[k] for k in sorted(endnotes, key=int))
    if pages:
        cuts = [0] + bounds[:-1] + [len(out)]
        return [html.unescape("\n".join(out[a:b])).translate(WESTERN)
                for a, b in zip(cuts, cuts[1:])]
    # Word stores text XML-escaped: "A & B" is "A &amp; B" on disk. Without
    # unescaping, every ampersand looked like lost text.
    return html.unescape("\n".join(out)).translate(WESTERN)


# Stands in for a PAGE field until the page it is drawn on is known.
PAGE_MARK = "⁣"


def _furniture_texts(z):
    """-> furniture(where, page): the header or footer text Word draws on that
    page (0-based), as a list of paragraphs' text.

    A PAGE field is read as the number Word prints on THAT page, not as its
    cached value: the cache is one number for every page, and counting it
    would compare our "82" against the original's 83, 84, 85. It used to be
    skipped, which was fine while a page number stood alone - not once it sits
    inside a word, "صفحة92" (`z21762458`, N5b), where skipping it left the
    word unmatched on every page.

    Which header a page gets is Word's rule, read from the file: the first
    page's own when the section has one (a photographed title page), the even
    page's on even page NUMBERS when the document has both, else the default.
    Emitting every header on every page read an alternating header - the
    author on one page, the title on the next (N5b) - onto both.
    """
    names = set(z.namelist())
    doc = z.read("word/document.xml").decode("utf-8")
    rels = z.read("word/_rels/document.xml.rels").decode("utf-8")         if "word/_rels/document.xml.rels" in names else ""
    target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    target.update({k: v for v, k in
                   re.findall(r'Target="([^"]+)"[^>]*Id="([^"]+)"', rels)})
    settings = z.read("word/settings.xml").decode("utf-8")         if "word/settings.xml" in names else ""
    even_odd = re.search(r"<w:evenAndOddHeaders(?![^>]*w:val=\"(?:0|false)\")",
                         settings) is not None
    sect = doc[doc.rfind("<w:sectPr"):]
    title_pg = re.search(r"<w:titlePg(?![^>]*w:val=\"(?:0|false)\")", sect) is not None
    m = re.search(r'<w:pgNumType[^>]*w:start="(\d+)"', sect)
    start = int(m.group(1)) if m else 1

    texts = {}
    for kind, typ, rid in re.findall(
            r'<w:(header|footer)Reference\b(?=[^>]*w:type="(\w+)")'
            r'(?=[^>]*r:id="([^"]+)")[^>]*/>', sect):
        name = "word/" + target.get(rid, "").lstrip("/").replace("word/", "")
        if name not in names:
            continue
        xml = z.read(name).decode("utf-8")
        xml = re.sub(r"<w:fldSimple[^>]*w:instr=\"[^\"]*PAGE[^\"]*\"[^>]*>.*?"
                     r"</w:fldSimple>", f"<w:t>{PAGE_MARK}</w:t>", xml, flags=re.S)
        # Runs of one paragraph join as Word shows them, with no space added:
        # "صفحة" and the field after it are one word on the page.
        body = " ".join(p for p in (
            "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para))
            for para in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S))
            if p.strip())
        texts[(kind, typ)] = [body] if body.strip() else []

    def pick(where, page):
        if title_pg and page == 0:
            return texts.get((where, "first"), [])
        if even_odd and (start + page) % 2 == 0:
            return texts.get((where, "even"), [])
        return texts.get((where, "default"), [])

    def furniture(where, page):
        return [t.replace(PAGE_MARK, str(start + page)) for t in pick(where, page)]
    return furniture


def _footnote_texts(z, note="footnote"):
    """{w:id: text} from word/footnotes.xml (or endnotes.xml), skipping
    Word's two separators."""
    if f"word/{note}s.xml" not in z.namelist():
        return {}
    xml = z.read(f"word/{note}s.xml").decode("utf-8")
    out = {}
    for m in re.finditer(rf'<w:{note} (?![^>]*w:type=)[^>]*w:id="(\d+)"[^>]*>'
                         rf'(.*?)</w:{note}>', xml, re.S):
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


def _page_words(page, fixes=None):
    """Distinctive words on a page - short ones match everywhere, so drop them.

    `fixes`: repair the page's text the way `text_of` does before matching.
    Both sides need it. The original's, or every word the converter spells
    right stops matching its stored misspelling - z21095413 0.335 -> 0.318
    the day ligatures were repaired (2026-09-22). And OURS: the rebuilt pdf
    is made by Word, and Word writes its ligatures backwards like everyone
    else, so our correct خلال reads back as خالل. Repairing only the
    original made right page FALL on most files (z19851706 0.824 -> 0.747)."""
    t = page.get_text("text")
    if fixes is not None:
        t = apply_fixes(repair_lam_alef(t), fixes)
    return [w for w in WORD.findall(spell_out(t).translate(WESTERN)) if len(w) >= MIN_WORD]


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
    orig_pdf, rebuilt_pdf = repaired(orig_pdf), repaired(rebuilt_pdf)
    fixes = {}
    for side in (orig_pdf, rebuilt_pdf):
        try:
            fixes[side] = fix_map(side)
        except Exception:
            fixes[side] = {}
    with pymupdf.open(orig_pdf) as A, pymupdf.open(rebuilt_pdf) as B:
        pa = [_page_words(p, fixes[orig_pdf]) for p in A]
        pb = [_page_words(p, fixes[rebuilt_pdf]) for p in B]
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
