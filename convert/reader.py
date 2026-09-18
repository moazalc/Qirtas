"""The reader: work out what is in the PDF.

Two ways of looking, because no single one works everywhere:

  tags      the PDF's own hidden labels say "this is a paragraph". Exact where
            present (~76% of files).
  geometry  group lines by position on the page. Works when labels are missing.

We run both and keep whichever recovered more Arabic — measure, don't predict.
"""
import re
from pathlib import Path
import pikepdf
import pymupdf

from convert.model import Doc, Block, PARAGRAPH, HEADING, LIST_ITEM, FOOTNOTE, IMAGE, TABLE

# Structure labels that mean "a block starts here".
BLOCK_TAGS = {
    "/P": PARAGRAPH, "/Textbox": PARAGRAPH, "/Caption": PARAGRAPH,
    "/Title": HEADING, "/H": HEADING,
    "/H1": HEADING, "/H2": HEADING, "/H3": HEADING,
    "/H4": HEADING, "/H5": HEADING, "/H6": HEADING,
    "/LI": LIST_ITEM,
    "/Footnote": FOOTNOTE, "/Note": FOOTNOTE,
}
ARABIC = re.compile(r"[؀-ۿ]")
WS = re.compile(r"[ \t ]+")


def _clean(s):
    return WS.sub(" ", (s or "").replace("\r", " ").replace("\n", " ")).strip()


SENT_SPLIT = re.compile(r"[.؟!؛:\n]+|،")
MIN_SENT = 40


def _sentences(t):
    return [x for x in (WS.sub("", s or "") for s in SENT_SPLIT.split(t or ""))
            if len(x) >= MIN_SENT]


def _backfill(chosen, results, path):
    """Recover anything the chosen reader missed but another reader found.

    Preferring the labelled reader for its structure cost one Quranic verse on
    one file: 110 characters present in the geometry reading and absent from
    the labels. Losing text is the one thing that is not allowed, so rather
    than trade structure against completeness, take the structure and put back
    whatever went missing.

    Recovered text is placed on the page it actually appears on, so page
    alignment is not disturbed.
    """
    have = "".join(WS.sub("", b.text) for b in chosen.blocks)
    added = False
    for _, other in results:
        if other is chosen:
            continue
        for b in other.blocks:
            sents = _sentences(b.text)
            if not sents:
                continue
            missing = [x for x in sents if x not in have]
            # Only take a block that is genuinely absent. Adding one whose text
            # is mostly present already duplicated whole paragraphs and pushed
            # word counts above the original.
            if len(missing) < len(sents) * 0.6:
                continue
            chosen.add(Block(kind=PARAGRAPH, text=b.text, page=b.page))
            have += WS.sub("", b.text)
            added = True
    if added:
        chosen.blocks.sort(key=lambda b: b.page)
    return chosen


def _recovered(doc):
    """How much did this reader actually get? Arabic if any, else total text.

    Scoring by Arabic alone made non-Arabic documents pick an empty reader.
    """
    ar = sum(len(ARABIC.findall(b.text)) for b in doc.blocks)
    return ar if ar else sum(len(b.text) for b in doc.blocks)


# ---------------------------------------------------------------- tags

def _page_index(pdf):
    """Map a page object's id -> its 0-based number, so blocks know their page."""
    return {pg.obj.objgen: i for i, pg in enumerate(pdf.pages)}


def _text_under(node, depth=0):
    """All text beneath this node, ignoring nested blocks (they emit separately)."""
    if depth > 80:
        return ""
    if isinstance(node, pikepdf.Array):
        return "".join(_text_under(k, depth + 1) for k in node)
    if not isinstance(node, pikepdf.Dictionary):
        return ""
    out = ""
    at = node.get("/ActualText") or node.get("/Alt")
    if at is not None:
        out += str(at)
    kids = node.get("/K")
    if kids is not None:
        out += _text_under(kids, depth + 1)
    return out


def _walk(node, doc, pages, pending, depth=0, ctx=None, state=None):
    """Emit a block per block-level label.

    Text that sits under no block label (inside /Figure, /Table cells, bare
    /Span under the root) used to be returned upward and silently dropped.
    It now collects in `pending` and is flushed as a paragraph in document
    order, so nothing is lost.
    """
    if depth > 80:
        return
    if state is None:
        state = {"page": 0}
    if isinstance(node, pikepdf.Array):
        for k in node:
            _walk(k, doc, pages, pending, depth + 1, ctx, state)
        return
    if not isinstance(node, pikepdf.Dictionary):
        return

    tag = str(node.get("/S", ""))
    if tag in BLOCK_TAGS:
        _flush(doc, pending, state["page"])
        ref = node.get("/Pg")
        pg = pages.get(ref.objgen, state["page"]) if ref is not None else state["page"]
        state["page"] = pg
        kind = BLOCK_TAGS[tag]
        # A /Footnote holds its text in nested /P children. Those emit their own
        # blocks, leaving the footnote itself empty and dropped. Push the kind
        # down so the nested paragraphs come out as footnotes.
        if ctx in (FOOTNOTE,) and kind == PARAGRAPH:
            kind = ctx
        text = str(node.get("/ActualText") or "")
        inner = []
        _walk(node.get("/K"), doc, pages, inner, depth + 1,
              kind if kind in (FOOTNOTE,) else ctx, state)
        doc.add(Block(kind=kind, text=_clean(text + "".join(inner)), page=pg))
        return

    ref = node.get("/Pg")
    if ref is not None:
        state["page"] = pages.get(ref.objgen, state["page"])
    at = node.get("/ActualText") or node.get("/Alt")
    if at is not None:
        pending.append(str(at))
    kids = node.get("/K")
    if kids is not None:
        _walk(kids, doc, pages, pending, depth + 1, ctx, state)


def _flush(doc, pending, page=0):
    """Loose text kept defaulting to page 0, piling a whole document onto the
    first page and leaving later pages empty. Carry the current page."""
    if pending:
        doc.add(Block(kind=PARAGRAPH, text=_clean("".join(pending)), page=page))
        pending.clear()


def read_tags(path):
    doc = Doc(source_route="tags")
    with pikepdf.open(path) as pdf:
        if "/StructTreeRoot" not in pdf.Root:
            raise RuntimeError("not tagged")
        pages = _page_index(pdf)
        doc.pages = len(pdf.pages)
        pending, state = [], {"page": 0}
        _walk(pdf.Root["/StructTreeRoot"].get("/K"), doc, pages, pending, state=state)
        _flush(doc, pending, state["page"])
    return doc


# ------------------------------------------------------------ geometry

BOLD_FLAG = 1 << 4


def read_geometry(path):
    """Group lines by position on the page.

    Prefers the detailed view, which carries font size and boldness. Where the
    glyphs cannot be decoded that view comes back nearly empty, so we fall back
    to the plain block view: text but no formatting.
    """
    doc = Doc(source_route="geometry")
    with pymupdf.open(path) as d:
        doc.pages = len(d)
        for i, page in enumerate(d):
            rich = _page_rich(page, i)
            plain_len = len(ARABIC.findall(page.get_text("text")))
            rich_len = sum(len(ARABIC.findall(b.text)) for b in rich)
            if plain_len and rich_len < plain_len * 0.5:
                rich = [Block(kind=PARAGRAPH, text=_clean(b[4]), page=i)
                        for b in sorted(page.get_text("blocks"),
                                        key=lambda b: (round(b[1]), b[0]))
                        if b[6] == 0]
            for b in rich:
                doc.add(b)
    return doc


def _page_rich(page, i):
    out = []
    for b in sorted(page.get_text("dict")["blocks"], key=lambda b: (round(b["bbox"][1]), b["bbox"][0])):
        if b.get("type") != 0:
            continue
        text, size, bold, spans = [], 0.0, False, 0
        for line in b["lines"]:
            for sp in line["spans"]:
                if not sp["text"].strip():
                    continue
                text.append(sp["text"])
                size = max(size, sp["size"])
                bold = bold or bool(sp["flags"] & BOLD_FLAG)
                spans += 1
        if spans:
            out.append(Block(kind=PARAGRAPH, text=_clean(" ".join(text)),
                             page=i, size=round(size, 1), bold=bold,
                             y=round(b["bbox"][1], 1), y1=round(b["bbox"][3], 1),
                             x0=round(b["bbox"][0], 1), x1=round(b["bbox"][2], 1)))
    return _join_lines(out)


ENDS_PARA = (".", "؟", "!", ":", "؛")


def _join_lines(blocks):
    """Merge consecutive lines back into paragraphs.

    The detailed page view hands back one entry per line as often as per
    paragraph - 290 entries for an 11-page document. Emitting each as its own
    Word paragraph forced a line break after every line, so pages held half the
    text they should and page counts doubled.

    Two entries join when they sit directly under one another at body spacing,
    share a font size, and the upper one does not end like a finished sentence.
    """
    if not blocks:
        return blocks
    gaps = sorted(b.y - a.y1 for a, b in zip(blocks, blocks[1:])
                  if b.page == a.page and b.y >= a.y1)
    lead = gaps[len(gaps) // 2] if gaps else 2.0
    out = [blocks[0]]
    for b in blocks[1:]:
        a = out[-1]
        same_page = b.page == a.page
        stacked = same_page and -2 <= (b.y - a.y1) <= max(4.0, lead * 2.2)
        same_size = abs(b.size - a.size) < 0.6 and b.bold == a.bold
        open_end = not a.text.rstrip().endswith(ENDS_PARA)
        wide = (a.x1 - a.x0) > 0 and (b.x1 - b.x0) > (a.x1 - a.x0) * 0.4
        if stacked and same_size and open_end and wide:
            a.text = (a.text + " " + b.text).strip()
            a.y1 = b.y1
            a.x0 = min(a.x0, b.x0); a.x1 = max(a.x1, b.x1)
        else:
            out.append(b)
    return out


# ---------------------------------------------------------------- pick

HEAD_WORDS = ("المطلب", "المبحث", "الفصل", "تمهيد", "المقدمة", "الخاتمة",
              "الفهرس", "المراجع", "التوطئة", "أولا", "أولاً", "ثانيا", "ثانياً",
              "ثالثا", "ثالثاً", "رابعا", "رابعاً", "خامسا", "خامساً")
ENDS_SENTENCE = (".", "،", "؛", "؟", "!")
MAX_HEADING_CHARS = 90

# Particles that open a continuation, never a heading. The waw and the fa are
# written joined to the following word, so "وقد" and "فالقراءة" are caught by
# their first letter.
CONNECTIVES = ("و", "ف", "ثم", "بل", "أو", "على", "حتى", "كما", "إذ",
               "أما", "أمَّا", "لكن", "لأن", "قال")
COLONS = (":", "：")
MAX_LABEL_CHARS = 60


def _is_label_heading(t):
    """Is this short line ending in a colon a real sub-heading?

    These theses use no Word heading styles, so a line like "أهداف البحث:" is
    the only marker a section gets and the rule has to stay. But promoting
    EVERY colon-terminated line swept up sentence tails - "على قسمين:"
    ("...into two categories:") became a heading.

    Length cannot separate them: "على قسمين:" is the shortest such line in the
    corpus and it is wrong, while "مولده وصفاته وبركات بيت النبوَّة عليه:" is
    the longest and it is right. Grammar separates them. A heading is a noun
    phrase, so it carries no comma and no second colon, and it does not open
    with a connective particle - those always continue the sentence before.
    """
    t = (t or "").strip()
    if not t.endswith(COLONS) or len(t) > MAX_LABEL_CHARS:
        return False
    if "," in t or "،" in t:            # a comma means a clause, not a label
        return False
    if any(c in t[:-1] for c in COLONS):   # "أهمية البحث: البحث له أهميتان,"
        return False
    return not t.startswith(CONNECTIVES)


def detect_headings(doc):
    """Mark headings.

    Three sources, best first: the PDF's own heading labels; font size, where
    the glyphs were readable; and failing both, the shape of the line. The last
    is needed because none of the sample files use Word heading styles - their
    author just made text bigger by hand - while 44% of PDFs in the wild do
    carry real heading labels.
    """
    if any(b.kind == HEADING for b in doc.blocks):
        return doc

    body = _body_size(doc)
    if body:
        for b in doc.blocks:
            if b.kind == PARAGRAPH and b.size >= body * 1.15 and len(b.text) <= 160:
                b.kind = HEADING
                b.level = 1 if b.size >= body * 1.4 else 2
        if any(b.kind == HEADING for b in doc.blocks):
            return doc

    for b in doc.blocks:
        if b.kind != PARAGRAPH or not b.text:
            continue
        t = b.text.strip()
        if len(t) > MAX_HEADING_CHARS or t.endswith(ENDS_SENTENCE):
            continue
        if t.startswith(HEAD_WORDS) or _is_label_heading(t):
            b.kind = HEADING
            b.level = 1 if t.startswith(HEAD_WORDS[:6]) else 2
    return doc


def _body_size(doc):
    """Most common font size, weighted by how much text is set in it."""
    weight = {}
    for b in doc.blocks:
        if b.size:
            weight[b.size] = weight.get(b.size, 0) + len(b.text)
    if not weight:
        return 0.0
    return max(weight, key=weight.get)


SANE_PT = (6.0, 30.0)
MIN_SPAN_CHARS = 500    # enough decodable text to trust the stated font size
TIE_MARGIN = 0.97       # keep the labelled reader unless it loses >3% of the text
GLYPH_RATIO = 0.94      # inked band height as a fraction of font size, measured


def measure_layout(path, doc):
    """Read the original's margins and body font size off the page.

    Guessing 1-inch margins and 12pt put our pages visibly out of step with the
    originals. Both numbers are measurable, so measure them.

    Edges come from the middle of the distribution, not the extremes: page
    numbers and headers sit further out than the body and would drag the
    margins wrong. Font sizes are filtered to a believable range first, because
    undecodable decorative glyphs report sizes like 90pt.
    """
    import statistics
    lefts, rights, tops, bottoms = [], [], [], []
    heights, pitches, spans = [], [], []
    with pymupdf.open(path) as d:
        if not len(d):
            return doc
        w, h = d[0].rect.width, d[0].rect.height
        for page in d:
            for b in page.get_text("blocks"):
                if b[6] != 0 or not str(b[4]).strip():
                    continue
                if (b[2] - b[0]) < w * 0.35:      # skip page numbers, stray marks
                    continue
                lefts.append(b[0]); rights.append(b[2])
                tops.append(b[1]); bottoms.append(b[3])
            hh, pit = _ink_rows(page)
            heights.extend(hh); pitches.extend(pit)
            for bl in page.get_text("dict")["blocks"]:
                if bl.get("type") != 0:
                    continue
                for line in bl["lines"]:
                    for sp in line["spans"]:
                        t = sp["text"].strip()
                        if t and SANE_PT[0] <= sp["size"] <= SANE_PT[1]:
                            spans.extend([sp["size"]] * len(t))
    doc.font = _dominant_font(path)
    if lefts:
        doc.margin_left = max(18.0, statistics.median(lefts))
        doc.margin_right = max(18.0, w - statistics.median(rights))
        doc.margin_top = max(18.0, min(tops))
        doc.margin_bottom = max(18.0, h - max(bottoms))
    # Where the glyphs decode, the font size is stated outright - use it.
    # The ink estimate is for files whose Arabic cannot be decoded, and it
    # overestimated badly on ordinary files, doubling their page count.
    if len(spans) >= MIN_SPAN_CHARS:
        doc.body_size = round(statistics.median(spans), 1)
        if pitches:
            doc.line_pitch = round(statistics.median(pitches), 1)
            doc.line_spacing = round(min(3.0, max(0.9, doc.line_pitch / doc.body_size)), 2)
    elif heights:
        size = statistics.median(heights) / GLYPH_RATIO
        doc.body_size = round(min(SANE_PT[1], max(SANE_PT[0], size)), 1)
        if pitches:
            doc.line_pitch = round(statistics.median(pitches), 1)
            doc.line_spacing = round(min(3.0, max(0.9, doc.line_pitch / doc.body_size)), 2)
    return doc


SUBSET = re.compile(r"^[A-Z]{6}\+")
GENERIC = ("arial", "calibri", "times", "helvetica", "cambria", "wingdings", "symbol")


def _dominant_font(path):
    """The document's own Arabic font.

    Setting everything in Arial made our text noticeably wider than the
    original - Arial's Arabic is wide, and fonts like Sakkal Majalla or
    Simplified Arabic are not - which stretched every page.
    """
    import collections
    weight = collections.Counter()
    with pymupdf.open(path) as d:
        for i, page in enumerate(d):
            for f in page.get_fonts(full=True):
                name = SUBSET.sub("", str(f[3])).split(",")[0].strip()
                name = re.sub(r"[-,]?(Bold|Italic|BoldItalic|Regular|Light|MT|PS)$", "", name)
                if name and not any(g in name.lower() for g in GENERIC):
                    weight[name] += 1
            if i >= 9:
                break
    return weight.most_common(1)[0][0] if weight else ""


def _ink_rows(page):
    """Measure text lines off the page image: how tall, and how far apart.

    Font size could not be read from the text spans - on these files the Arabic
    glyphs do not decode, so the only spans reporting a size are Latin digits
    and decorative marks, which gave 18pt for 12pt body text. Ink does not care
    whether a glyph decodes.

    Line *pitch* alone was not enough either: it confuses a large font with a
    generously spaced small one. Measuring the height of the inked band gives
    the glyph size directly, and pitch divided by that gives the line spacing.
    """
    import numpy as np
    pm = page.get_pixmap(dpi=72, colorspace=pymupdf.csGRAY)
    a = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)
    rows = (a < 200).sum(axis=1)
    if not rows.max():
        return [], []
    inked = rows > max(2, rows.max() * 0.06)
    runs, start = [], None
    for j, v in enumerate(inked):
        if v and start is None:
            start = j
        elif not v and start is not None:
            runs.append(j - start); start = None
    starts = [j for j in range(1, len(inked)) if inked[j] and not inked[j - 1]]
    pitch = [starts[k + 1] - starts[k] for k in range(len(starts) - 1)]
    return ([r for r in runs if 3 < r < 40], [p for p in pitch if 4 < p < 60])


MIN_IMAGE_PT = 24.0      # drawn size below this is a spacer, not a picture
MIN_IMAGE_PX = 16        # Word scatters 2x2 pixel images across every page


def _word_can_read(blob):
    """Ask python-docx itself whether it can identify these bytes.

    Measured, not predicted. The file extension does not tell us: a PDF hands
    back valid JPEGs that python-docx rejects, and guessing which ones from the
    format name would mean reimplementing its parser.
    """
    try:
        from docx.image.image import Image
        Image.from_blob(blob)
        return True
    except Exception:
        return False


def _repaint(doc, xref):
    """Re-render one image through pymupdf as a PNG, or None if that fails."""
    try:
        pix = pymupdf.Pixmap(doc, xref)
        if pix.colorspace and pix.n - pix.alpha > 3:      # CMYK and friends
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        return pix.tobytes("png")
    except Exception:
        return None


def read_images(path, outdir):
    """Pull the real pictures out of the PDF, ignoring Word's pixel litter.

    One page carried 276 images of which 275 were 2x2 pixels stretched into
    thin bars. Filtering on both the stored size and the drawn size leaves the
    actual figures.

    Anything Word cannot identify is re-rendered as a PNG. PDFs routinely store
    bare DCT streams with no JFIF wrapper, because the PDF object already
    carries the colorspace and size, so the APP0 segment is redundant.
    python-docx identifies a JPEG only by the literal bytes "JFIF" or "Exif" at
    offset 6, so those images raise UnrecognizedImageError, and the writer
    caught that and dropped the picture without a word. Re-rendering costs
    nothing on the common path: images Word already accepts are written through
    untouched.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    blocks = []
    with pymupdf.open(path) as d:
        for i, page in enumerate(d):
            seen = set()
            for info in page.get_images(full=True):
                xref, w, h = info[0], info[2], info[3]
                if xref in seen or w < MIN_IMAGE_PX or h < MIN_IMAGE_PX:
                    continue
                rects = [r for r in (page.get_image_rects(xref) or [])
                         if r.width >= MIN_IMAGE_PT and r.height >= MIN_IMAGE_PT]
                if not rects:
                    continue
                seen.add(xref)
                try:
                    raw = d.extract_image(xref)
                except Exception:
                    continue
                blob, ext = raw["image"], raw.get("ext", "png")
                if not _word_can_read(blob):
                    blob, ext = _repaint(d, xref), "png"
                    if blob is None:
                        continue
                dest = outdir / f"p{i}_x{xref}.{ext}"
                dest.write_bytes(blob)
                r = rects[0]
                blocks.append(Block(kind=IMAGE, text="", page=i, image=str(dest),
                                    x0=r.x0, x1=r.x1, y=r.y0, y1=r.y1))
    return blocks


def _unreverse(cell, page_flat):
    """Table extraction hands back Arabic in visual order.

    The table finder does not apply the logical ordering the text extractor
    does, so cells come out backwards ("مدختسملا" for "المستخدم"). Writing that
    into a Word file would be corruption, so check each cell against the page's
    correctly ordered text and flip the ones that only match reversed.
    """
    flat = WS.sub("", cell)
    if len(flat) < 6 or not ARABIC.search(flat):
        return cell
    # Probe with a slice from the middle rather than the whole cell: cell edges
    # pick up stray characters that break an exact match even when the body of
    # the text is present.
    n = min(14, max(6, len(flat) // 2))
    mid = (len(flat) - n) // 2
    probe = flat[mid:mid + n]
    if probe in page_flat:
        return cell
    if probe[::-1] in page_flat:
        return cell[::-1]
    return cell


def read_tables(path):
    """Find tables and return them as blocks of rows."""
    blocks = []
    with pymupdf.open(path) as d:
        for i, page in enumerate(d):
            try:
                found = page.find_tables().tables
            except Exception:
                continue
            page_flat = WS.sub("", page.get_text("text"))
            for t in found:
                try:
                    rows = [[_unreverse(_clean(c or ""), page_flat) for c in row]
                            for row in t.extract()]
                except Exception:
                    continue
                if not rows or not any(any(c for c in r) for r in rows):
                    continue
                r = t.bbox
                widths = _col_widths(t)
                boxes = []
                try:
                    boxes = [[c for c in row.cells] for row in t.rows]
                except Exception:
                    boxes = []
                blocks.append(Block(kind=TABLE, text="", page=i, rows=rows,
                                    col_widths=widths, cell_boxes=boxes,
                                    x0=r[0], y=r[1], x1=r[2], y1=r[3]))
    return blocks


def _col_widths(table):
    """Column widths in points, read off the cell boxes.

    Without them Word splits every column evenly and long cells wrap one word
    per line, turning a compact table into a tall ladder.
    """
    try:
        cells = [c for c in (table.rows[0].cells if table.rows else []) if c]
        w = [round(c[2] - c[0], 1) for c in cells]
        return w if all(x > 1 for x in w) else []
    except Exception:
        return []


VECTOR_MIN = 6           # drawings in a cell before we treat it as a figure
RENDER_DPI = 200


def render_vector_cells(path, tables, outdir):
    """Draw empty-looking table cells that actually contain line art.

    The molecular structures in one paper are not images - they are vector
    drawings, so nothing extracts them and the cells came out blank. Anything
    drawn rather than placed has to be rendered to be carried into Word.

    Only cells with no text of their own are rendered, so this never turns a
    text cell into a picture.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(path) as d:
        for t in tables:
            if not t.cell_boxes or t.page >= len(d):
                continue
            page = d[t.page]
            try:
                drawings = page.get_drawings()
            except Exception:
                continue
            for ri, row in enumerate(t.cell_boxes):
                for ci, box in enumerate(row):
                    if not box or (ri, ci) in t.cell_images:
                        continue
                    text = t.rows[ri][ci] if ri < len(t.rows) and ci < len(t.rows[ri]) else ""
                    if text.strip():
                        continue
                    rect = pymupdf.Rect(*box)
                    if rect.width < 20 or rect.height < 20:
                        continue
                    n = sum(1 for g in drawings if rect.contains(g["rect"]))
                    if n < VECTOR_MIN:
                        continue
                    try:
                        pm = page.get_pixmap(clip=rect, dpi=RENDER_DPI)
                        dest = outdir / f"vec_p{t.page}_{ri}_{ci}.png"
                        pm.save(str(dest))
                        t.cell_images[(ri, ci)] = str(dest)
                    except Exception:
                        continue


def _put_images_in_cells(tables, images):
    """Move a picture into the table cell it sits in.

    Pictures were appended to the foot of the page, so a table of molecular
    structures came out with empty cells and the diagrams stranded below it.

    Returns the pictures that belong to no cell, to be placed as before.
    """
    loose = []
    for img in images:
        placed = False
        cx = (img.x0 + img.x1) / 2.0
        cy = (img.y + img.y1) / 2.0
        for t in tables:
            if t.page != img.page or not t.cell_boxes:
                continue
            for ri, row in enumerate(t.cell_boxes):
                for ci, box in enumerate(row):
                    if not box:
                        continue
                    if box[0] <= cx <= box[2] and box[1] <= cy <= box[3]:
                        t.cell_images[(ri, ci)] = img.image
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break
        if not placed:
            loose.append(img)
    return loose


def _drop_text_inside_tables(doc, tables):
    """Remove paragraphs whose text the table already carries.

    The table's words are also picked up as ordinary text, so without this the
    document says everything twice.
    """
    if not tables:
        return
    by_page = {}
    for t in tables:
        joined = WS.sub("", " ".join(c for row in t.rows for c in row))
        by_page.setdefault(t.page, []).append(joined)
    keep = []
    for b in doc.blocks:
        if b.kind in (TABLE, IMAGE) or not b.text:
            keep.append(b)
            continue
        flat = WS.sub("", b.text)
        if len(flat) >= 6 and any(flat in joined for joined in by_page.get(b.page, [])):
            continue
        keep.append(b)
    doc.blocks = keep


def read(path, image_dir=None):
    """Run both, keep whichever recovered more Arabic."""
    results = []
    for fn in (read_tags, read_geometry):
        try:
            d = fn(path)
            results.append((_recovered(d), d))
        except Exception:
            continue
    if not results:
        raise RuntimeError("no reader succeeded")

    # Prefer the labels when they recover essentially as much text. One file
    # picked geometry by 0.6% and lost every footnote and list item with it -
    # a rounding-error win on quantity, a real loss on structure.
    top = max(r[0] for r in results)
    tagged = [r for r in results if r[1].source_route == "tags"]
    if tagged and tagged[0][0] >= top * TIE_MARGIN:
        best = tagged[0][1]
    else:
        best = max(results, key=lambda r: r[0])[1]
    tables = []
    try:
        tables = read_tables(path)
    except Exception:
        tables = []
    pictures = []
    if image_dir:
        try:
            pictures = read_images(path, image_dir)
        except Exception:
            pictures = []
    if tables:
        _drop_text_inside_tables(best, tables)
        pictures = _put_images_in_cells(tables, pictures)
        if image_dir:
            try:
                render_vector_cells(path, tables, image_dir)
            except Exception:
                pass
        for t in tables:
            best.add(t)
    for b in pictures:
        best.add(b)
    best = _backfill(best, results, path)
    best = detect_headings(best)
    measure_layout(path, best)
    with pymupdf.open(path) as d:
        r = d[0].rect
        best.page_width, best.page_height = r.width, r.height
    return best
