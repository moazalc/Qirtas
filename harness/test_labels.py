#!/usr/bin/env python3
"""Tests for the labels route: Word's structure labels over glyph text.

    python -m harness.test_labels

Before this route, the reader ignored the labels on every ordinary Word file -
the tags route reads only /ActualText, which those files do not carry - and
geometry guessed the structure back: no footnote found on any of 36 files, a
third of prose made into list items. Two things went wrong on the way in, and
each has a case here:

  - A list inside a footnote must stay a footnote. Splitting at the list is
    how `الفصل الثالث`'s notes (34) and (35) landed in the body.
  - Fields side by side on one line are one paragraph. `عن بعد` has three,
    labelled separately; stacked as three headings, the one-page form ran onto
    a second page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.model import Doc, Block, PARAGRAPH, HEADING, LIST_ITEM, FOOTNOTE, TABLE
from convert.reader import (_label_kind, _join_same_line, _backfill, _glued,
                            _drop_text_inside_tables, _Run, _rough_spans,
                            _fit_spans, _leans, _mark_slant, ITALIC_FLAG)

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<50} got {got!r}")
    if not ok:
        FAILED.append(name)


def field(text, x0, x1, y=275.0, kind=HEADING):
    return Block(kind=kind, text=text, size=22.0, y=y, y1=y + 33.0,
                 x0=x0, x1=x1, spans=[(text, True, False)])


def tagged_pdf(pieces):
    """A one-paragraph tagged PDF. Each piece is (label text, None) - a Span
    carrying its words, drawn as nothing - or (None, drawn) - a bare piece
    of the page drawing `drawn` in Helvetica."""
    import pikepdf
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(300, 200))
    page = pdf.pages[0]
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
        BaseFont=pikepdf.Name.Helvetica, Encoding=pikepdf.Name.WinAnsiEncoding))
    page.obj.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    ops, kids, x = [], [], 250
    for n, (said, drawn) in enumerate(pieces):
        ops.append(f"/Span << /MCID {n} >> BDC BT /F1 12 Tf {x} 100 Td "
                   f"({drawn or ''}) Tj ET EMC")
        x -= 40
        if said is not None:
            kids.append(pdf.make_indirect(pikepdf.Dictionary(
                Type=pikepdf.Name.StructElem, S=pikepdf.Name.Span,
                ActualText=pikepdf.String(said), Pg=page.obj, K=n)))
        else:
            kids.append(n)
    page.obj.Contents = pdf.make_stream("\n".join(ops).encode())
    page.obj.StructParents = 0
    para = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.StructElem, S=pikepdf.Name.P, Pg=page.obj,
        K=pikepdf.Array(kids)))
    doc = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.StructElem, S=pikepdf.Name.Document, K=pikepdf.Array([para])))
    pdf.Root.StructTreeRoot = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.StructTreeRoot, K=doc))
    out = Path("out/tests/labels")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"tagged{len(list(out.glob('*.pdf')))}.pdf"
    pdf.save(path)
    return str(path)


def main():
    print("what the labels say")
    check("list inside a footnote",
          _label_kind(["Part", "Footnote", "L", "LI", "LBody", "P"]),
          (FOOTNOTE, 0))
    check("H2", _label_kind(["Document", "H2"]), (HEADING, 2))
    check("list item", _label_kind(["Document", "L", "LI", "LBody"]),
          (LIST_ITEM, 0))
    check("table cell stays for read_tables",
          _label_kind(["Table", "TR", "TD", "P"]), (PARAGRAPH, 0))
    check("plain paragraph", _label_kind(["Document", "P"]), (PARAGRAPH, 0))

    print("\nfields on one line")
    # Label order is left to right, as `عن بعد` stores them.
    got = _join_same_line([field(":الرقم", 77, 119), field(":التوقيع", 286, 342),
                           field(":اسم الطالبة", 479, 570)])
    check("three fields become one block", len(got), 1)
    check("joined right to left", got[0].text, ":اسم الطالبة :التوقيع :الرقم")

    stacked = _join_same_line([field(":اسم المسجد", 469, 579, y=155),
                               field(":اسم المعلمة", 478, 572, y=192)])
    check("lines one under another stay apart", len(stacked), 2)

    mixed = _join_same_line([field("مقدمة", 400, 560),
                             field("نص", 80, 380, kind=PARAGRAPH)])
    check("different kinds stay apart", len(mixed), 2)

    notes = _join_same_line([field("(1) انظر", 300, 560, kind=FOOTNOTE),
                             field("(2) انظر", 60, 280, kind=FOOTNOTE)])
    check("footnotes side by side stay apart", len(notes), 2)

    print("\ntext another reading found, put back only if really missing")
    right = ("وقد لعبت منذ نشأتها دورا كبيرا في حفظ التراث الإسلامي "
             "والحفاظ على الهوية الوطنية")
    wrong = ("وقد لعبت منذ نشأهتا ًدورا ًكبريا في حفظ الرتاث الإسالمي "
             "واحلفاظ على اهلوية الوطنية")
    spell = {"نشأهتا": "نشأتها", "ًدورا": "دورا", "ًكبريا": "كبيرا",
             "الرتاث": "التراث", "الإسالمي": "الإسلامي", "واحلفاظ": "والحفاظ",
             "اهلوية": "الهوية"}

    def fix(t):
        for a, b in spell.items():
            t = t.replace(a, b)
        return t

    def docs(have):
        chosen, other = Doc(pages=1), Doc(pages=1)
        chosen.add(Block(kind=PARAGRAPH, text=have, page=0))
        other.add(Block(kind=PARAGRAPH, text=wrong, page=0))
        return chosen, [(0, chosen), (0, other)]
    # The z21762915 case: without the chosen reading's spelling repair, the
    # other reading's misspelled copy looked missing and was added again -
    # a third of that file was a second copy (FLAGS 25).
    chosen, results = docs(right)
    check("a misspelled copy is not added again",
          len(_backfill(chosen, results, None, fix).blocks), 1)
    chosen, results = docs("نص آخر لا علاقة له بما في الصفحة من كلام طويل هنا")
    check("text really missing is still put back",
          len(_backfill(chosen, results, None, fix).blocks), 2)

    # `z21145041` page 11: the other reading has the paragraph backwards, the
    # tanween's alef at the wrong end and two words run together - only five
    # of its eight words are ours exactly turned round.
    right = ("تتبع عملية التحليل مساراً صارماً لمعالجة البيانات لضمان دقة "
             "التنبؤات التشخيصية")
    wrong = ("تراسم ليلحتلا ةيلمع عبت اً مراصاً ةيصيخشتلا تاؤبنتلا ةقد "
             "نامضلتانايبلا ةجلاعمل")
    chosen, results = docs(right)
    results[1][1].blocks[0].text = wrong
    check("a backwards copy, words distorted, is not added again",
          len(_backfill(chosen, results, None).blocks), 1)
    # The title the chosen reading missed, its words used in the body too:
    # the right way round, so asked strictly, and put back.
    chosen, results = docs("المؤشرات الحيوية الحديثة في البول " * 3)
    results[1][1].blocks[0].text = ("تقييم المؤشرات الحيوية الحديثة في البول "
                                    "كأدوات تنبؤية للتشخيص المبكر")
    check("a paragraph the right way round is still put back",
          len(_backfill(chosen, results, None).blocks), 2)

    print("\na word the PDF cut between two pieces")
    import collections

    def piece(text, x0, x1, y1=407.0, size=12.0):
        return {"text": text, "bbox": (x0, y1 - 20, x1, y1), "size": size,
                "flags": 0}
    vocab = collections.Counter({"يحتفظ": 2, "الخزان": 3, "شملت": 1,
                                 "دراستنا": 1})
    # z19773087: "سورية، ي" | "حتفظ المؤلفون", touching at x=503
    check("cut inside a word: joined",
          _glued(piece("سورية، ي", 503, 538), piece("حتفظ المؤلفون", 415, 503),
                 vocab), True)
    check("two real words that touch: not joined (FLAGS 24)",
          _glued(piece("شملت", 300, 330), piece("دراستنا", 250, 300), vocab),
          False)
    check("a space at the seam: not joined",
          _glued(piece("سورية، ي ", 503, 538), piece("حتفظ", 415, 503), vocab),
          False)
    check("apart on the line: not joined",
          _glued(piece("ال", 533, 538), piece("خزان", 480, 520), vocab), False)
    check("Arabic against English: not joined",
          _glued(piece("قام", 400, 430), piece("Yazdanian", 330, 400),
                 collections.Counter({"قامyazdanian": 1})), False)
    check("a word the document never prints whole: not joined",
          _glued(piece("مها", 400, 420), piece("العبد", 360, 400), vocab), False)

    print("\na table's words printed again outside it")
    # z21762915: the header band repeats the title; the title below it stays.
    title = "زاوية الهامل ودورها في حفظ التراث الجزائري"
    band = Block(kind=TABLE, text="", page=0, y=29.0, y1=55.0,
                 rows=[["", ".د بن بوزيد لخضر " + title]])
    d = Doc(pages=1)
    d.add(Block(kind=PARAGRAPH, text=".د بن بوزيد لخضر " + title, page=0,
                y=33.0, y1=50.0))
    d.add(Block(kind=PARAGRAPH, text=title, page=0, y=68.0, y1=93.0))
    _drop_text_inside_tables(d, [band])
    check("the band's own copy dropped, the title kept",
          [b.y for b in d.blocks], [68.0])
    d = Doc(pages=1)
    d.add(Block(kind=PARAGRAPH, text=title, page=0))
    _drop_text_inside_tables(d, [band])
    check("no position: text alone decides, as before", len(d.blocks), 0)

    print("\nthe tags route: each word's bold read from its letters' font")
    b = Block(kind=PARAGRAPH, text="")
    _rough_spans(b, [_Run("قال", (True, False)), _Run(" ", (False, False)),
                     _Run("في", (True, False)), " ",
                     _Run("كتب", (False, False))])
    check("a space label joins the formatting before it",
          [(t, bo) for t, bo, _ in b.spans], [("قال في ", True), ("كتب", False)])
    check("mostly bold letters make the block bold", b.bold, True)
    b = Block(kind=PARAGRAPH, text="")
    _rough_spans(b, ["قال", _Run("في", (False, False))])
    check("no bold or italic anywhere: no spans", b.spans, [])
    b = Block(kind=PARAGRAPH, text="قال في الكتاب",
              spans=[("قال ", True, False), ("فيالكتاب", False, False)])
    _fit_spans(b)
    check("spans laid over the finished text, word by word", b.spans,
          [("قال", True, False), ("في الكتاب", False, False)])
    b = Block(kind=PARAGRAPH, text="- قال في",
              spans=[("قال", True, False), ("في", False, False)])
    _fit_spans(b)
    check("text the spans never had is written, not lost",
          " ".join(t for t, *_ in b.spans), b.text)

    print("\nitalic drawn as a slant, in no italic font")
    check("Word's lean of 0.33 is a slant", _leans((1, 0, 0.3333, 1, 5, 5)), True)
    check("upright text is not", _leans((12, 0, 0, 12, 5, 5)), False)
    check("turned text is not", _leans((0, 1, -1, 0, 5, 5)), False)
    import pymupdf
    d = pymupdf.open()
    page = d.new_page()
    page.insert_text((72, 100), "upright words", fontsize=12)
    page.insert_text((72, 200), "leaning words", fontsize=12,
                     morph=(pymupdf.Point(72, 200), pymupdf.Matrix(1, 0, 0.3333, 1, 0, 0)))
    got = page.get_text("dict")
    _mark_slant(page, got)
    marked = {s["text"]: bool(s["flags"] & ITALIC_FLAG)
              for b in got["blocks"] for l in b["lines"] for s in l["spans"]}
    check("only the leaning line is marked italic", marked,
          {"upright words": False, "leaning words": True})

    print("\nitalic only where the PDF's own font description agrees")
    from convert.reader import _pdf_italic_fonts
    d = pymupdf.open()
    page = d.new_page()
    page.insert_text((72, 100), "upright", fontname="helv", fontsize=12)
    page.insert_text((72, 140), "oblique", fontname="heit", fontsize=12)
    check("an Oblique font is italic, Helvetica is not",
          sorted(_pdf_italic_fonts(page)), ["Helvetica-Oblique"])
    got = page.get_text("dict")
    for b in got["blocks"]:
        for l in b["lines"]:
            for s in l["spans"]:
                s["flags"] |= ITALIC_FLAG       # as a font file might claim
    _mark_slant(page, got)
    marked = {s["text"]: bool(s["flags"] & ITALIC_FLAG)
              for b in got["blocks"] for l in b["lines"] for s in l["spans"]}
    check("a font only its file calls italic is upright", marked,
          {"upright": False, "oblique": True})

    print("\na word put back together takes only itself into the bold")
    # `z17804101`: "الدرام" bold, then "ا، القاهرة، الهيئة" plain.
    import convert.reader as R
    saved = R._glued, R._tight, R._edge_spaces
    R._glued = lambda prev, sp, *a: prev is not None and sp["text"].startswith("ا،")
    R._tight = lambda *a: False
    R._edge_spaces = lambda sp, *a: sp["text"]
    try:
        def sp(text, bold):
            return {"text": text, "flags": R.BOLD_FLAG if bold else 0,
                    "size": 12.0, "bbox": (0, 0, 10, 10)}
        blk = R._rich_block([{"bbox": (0, 0, 100, 10), "lines": [{"spans": [
            sp("مدخل إلى الدرام", True), sp("ا، القاهرة، الهيئة", False)]}]}], 0)
    finally:
        R._glued, R._tight, R._edge_spaces = saved
    check("the word bold, the rest plain", blk.spans,
          [("مدخل إلى الدراما،", True, False), ("القاهرة، الهيئة", False, False)])
    check("the text as before", blk.text, "مدخل إلى الدراما، القاهرة، الهيئة")

    print("\nEnglish in an Arabic line, which the labels leave unsaid (FLAGS 29)")
    # `z22058810`: each Arabic word a label with its text; "COVID19" a bare
    # piece of the page between the last word and the full stop.
    path = tagged_pdf([("جائحة ", None), (None, "COVID19"), (".", None)])
    check("read where it stands", R.read_tags(path).blocks[0].text,
          "جائحة COVID19.")
    check("dropped when switched off", R.read_tags(path, drawn=False).blocks[0].text,
          "جائحة .")
    # `z21145041`: the space between English words is a bare piece too.
    path = tagged_pdf([("ملخص", None), (None, "Urinary"), (None, " "), (None, "Biomarkers")])
    check("spaces between English words kept; set apart from the Arabic",
          R.read_tags(path).blocks[0].text, "ملخص Urinary Biomarkers")
    # A file with no Arabic in its labels keeps its words in the glyphs; the
    # tags route must not start reading them there.
    path = tagged_pdf([(None, "Abstract")])
    check("not on a file whose labels hold no Arabic",
          [b.text for b in R.read_tags(path).blocks], [])

    print("\nEnglish read from the page is set as drawn")
    # `z21145041`'s references: Calibri 12pt, 14.6pt apart, ragged right.
    def piece(text, lines, font="BCEGEE+Calibri", size=12.0):
        p = R._Drawn(text)
        p.marks = [(12, 72.0, x1, 700.0 - 14.6 * k, size, font)
                   for k, x1 in enumerate(lines)]
        return p
    doc = Doc()
    for ends in ([500.0, 300.0], [480.0, 200.0], [523.0, 510.0, 523.0, 100.0]):
        blk = Block(kind=PARAGRAPH, text="x")
        R._drawn_look(blk, [piece("Novel Biomarkers " * 3, ends)])
        doc.add(blk)
    R._drawn_align(doc)
    first = doc.blocks[0]
    check("size, font and line height as drawn",
          (first.text_size, first.latin_font, first.line_pitch),
          (12.0, "Calibri", 14.6))
    check("ragged lines: not justified", [b.align for b in doc.blocks],
          ["start", "start", ""])
    blk = Block(kind=PARAGRAPH, text="x")
    R._drawn_look(blk, ["كلمات عربية كثيرة جدا هنا", piece("AUC", [100.0])])
    check("not a paragraph mostly Arabic", blk.text_size, 0.0)

    print("\ntable cells")
    # `z21145041`: cells stored backwards, the page's own text backwards too;
    # the reading the file is written from settles it.
    doc = Doc()
    doc.add(Block(kind=PARAGRAPH, text="المجموعة الأصحاء بيلة ألبومينية "
                  "النبيب البعيد القريب مؤشرات المؤشر"))
    t = Block(kind=TABLE, text="", rows=[["اةعومجمل", "2.1 ±"],
                                          ["بيرقلا/ديعبلا بيبنلا", "(Cr)"],
                                          ["يلة ألبومينيةب", "المجموعة"]])
    R._turn_cells([t], doc)
    check("a backwards cell turned, its first letter put back",
          t.rows[0], ["المجموعة", "2.1 ±"])
    check("turned with its slash", t.rows[1][0], "النبيب البعيد/القريب")
    check("the right way round, first letter put back", t.rows[2],
          ["بيلة ألبومينية", "المجموعة"])
    # `z18037898` 251ح: the entry's first letter the clip caught.
    import collections as C
    check("a letter not the cell's, off its end",
          R._cell_ends("251ح", (C.Counter(), C.Counter({"ح": 1}))), "251")
    check("a real م after a year stays",
          R._cell_ends("2022 م", (C.Counter(), C.Counter())), "2022 م")
    # `z17931421`: an invisible ۡ and alef at the header's edge.
    check("zero-width marks at a header's end",
          R._cell_ends("الاختالفۡا", (C.Counter({"ۡ": 1, "ا": 1}), C.Counter())),
          "الاختالف")

    print("\nwhat is a table")
    import pymupdf
    box = pymupdf.Rect(72, 636, 540, 720)
    white = [{"type": "f", "rect": pymupdf.Rect(72, 654, 540, 670), "fill": (1, 1, 1)}]
    rule = [{"type": "f", "rect": pymupdf.Rect(72, 660, 540, 660.5), "fill": (0, 0, 0)}]
    above = [{"type": "f", "rect": pymupdf.Rect(419, 634.7, 540, 635.2), "fill": (0, 0, 0)}]
    check("fills behind footnote lines: not a table (z22058810)",
          R._ruled(white + above, box), False)
    check("a hairline fill inside: a table", R._ruled(white + rule, box), True)
    big = Block(kind=TABLE, text="", page=11, x0=32, y=91, x1=535, y1=575, rows=[["a"]])
    piece = Block(kind=TABLE, text="", page=11, x0=39, y=97, x1=220, y1=113, rows=[["b"]])
    other = Block(kind=TABLE, text="", page=12, x0=39, y=97, x1=220, y1=113, rows=[["c"]])
    check("a table inside another is a piece of it (z3387756)",
          [t.rows[0][0] for t in R._drop_pieces([big, piece, other])], ["a", "c"])

    print("\na table wider than the text column (z17931421)")
    from convert.writer import _table_place
    t = Block(kind=TABLE, text="", x0=21.0, x1=570.0)
    widths, indent = _table_place(t, [54.8] * 10, True, 595.0, 72.0, 72.0)
    check("placed by the original's right edge", round(indent), -47)
    check("widths kept when it fits the page", round(sum(widths)), 548)
    widths, indent = _table_place(t, [70.0] * 10, True, 595.0, 72.0, 72.0)
    check("scaled to the page when wider", round(sum(widths)), 559)
    check("and on the page", round(indent), -54)
    widths, indent = _table_place(t, [40.0] * 10, True, 595.0, 72.0, 72.0)
    check("a table within the column is left alone", indent, None)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
