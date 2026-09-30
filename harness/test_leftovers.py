#!/usr/bin/env python3
"""Tests for the Part 3 leftovers (2026-09-30).

    python -m harness.test_leftovers

Each is a small piece with no Word in it: brackets turned round a number or
an address, a table's caption row read again under it, page numbers in
stretches, notes numbered plainly, a note in two paragraphs, signs from a
font of signs, web addresses as links, and Word's line numbers.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docx import Document

from convert.footnotes import NOTE_PARA, build_xml
from convert.model import Block, PARAGRAPH, FOOTNOTE
from convert.reader import _held_pieces, _split_typed_notes, _unturn
from convert.writer import _link_runs, _page_stretches, _symbol_runs

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<56} got {got!r}")
    if not ok:
        print(f"        want {want!r}")
        FAILED.append(name)


def main():
    print("brackets turned round one piece")
    check("a caption's number", _unturn("الشكل رقم )59( :"), "الشكل رقم (59) :")
    check("an address", _unturn("داخل مصر)https://www.total.eg( ."),
          "داخل مصر(https://www.total.eg) .")
    check("an address between two openings",
          _unturn("∗ (www.globalreporting.org( هي"), "∗ (www.globalreporting.org) هي")
    check("a year in Arabic digits", _unturn("إليه )٢٠١٩( al"), "إليه (٢٠١٩) al")
    check("a formula stays", _unturn("وفق Y)-(T k)"), "وفق Y)-(T k)")
    check("joined to a letter stays", _unturn(" )i(c في"), " )i(c في")
    check("the right way round stays", _unturn("(59) و (www.a.com)"), "(59) و (www.a.com)")

    print("\na table's caption row read again under it")
    cells = {"M𝑜𝑑𝑒", "4:", "𝑓=", "6.08", "𝐻𝑧", "𝑀𝑜𝑑𝑒", "5:", "6.25", "6:"}
    again = "M 𝑜𝑑𝑒 4: 𝑓= 6.08 𝐻𝑧 𝑀𝑜𝑑𝑒6: 𝑓= 6.25 𝐻𝑧 ا".split()
    check("a word in two pieces, two drawn together, a stray letter",
          _held_pieces(again, cells), True)
    check("a word the table lacks", _held_pieces(again + ["الشكل"], cells), False)
    check("its leading words", _held_pieces(again + ["الشكل", "(17)"], cells, lead=True),
          len(again))

    print("\npage numbers in stretches")

    def foot(page, text):
        return Block(PARAGRAPH, text, page=page)
    cut = [foot(p, str(n)) for p, n in zip(range(13), [1, 2, 3, 21, 22, 23, 24, 25,
                                                      26, 27, 28, 54, 55])]
    check("1-3, 21-28, 54-55", _page_stretches(cut), ((0, 1), {3: 18, 11: 43}))
    check("a number going down is not",
          _page_stretches([foot(p, str(n)) for p, n in enumerate([5, 6, 7, 1, 2, 3])]),
          (None, None))

    print("\nnotes numbered plainly")
    body = Block(PARAGRAPH, "نص¹ ونص² ونص³".replace("¹", "(1)").replace("²", "(2)")
                 .replace("³", "(3)"), page=4)
    note = Block(FOOTNOTE, "1 والتون مايكل (1998) ص 35 . 2 سامية احمد ص180 . 3 نفس المرجع ص185 .",
                 page=4)
    got = [b.text for b in _split_typed_notes([body, note]) if b.kind == FOOTNOTE]
    check("three notes", got, ["1 والتون مايكل (1998) ص 35 .", "2 سامية احمد ص180 .",
                               "3 نفس المرجع ص185 ."])
    verse = Block(FOOTNOTE, "(8) سورة الحجر: (9).", page=4)
    body9 = Block(PARAGRAPH, "نص (8) ونص (9)", page=4)
    check("a verse number is not the next note",
          [b.text for b in _split_typed_notes([body9, verse]) if b.kind == FOOTNOTE],
          ["(8) سورة الحجر: (9)."])

    print("\na note in two paragraphs")
    xml = build_xml([(2, f"سورة النساء: (163). {NOTE_PARA} انظر: الجزائري.")])
    note_xml = xml[xml.index('w:id="2"'):]
    check("two paragraphs in the note", note_xml.count("<w:p>"), 2)
    check("the mark itself is not written", NOTE_PARA in xml, False)

    print("\nsigns from a font of signs, and links")
    doc = Document()
    p = doc.add_paragraph()
    p.add_run(" الباب الثاني see www.example.org.")
    _symbol_runs(doc.element.body, {"": "Webdings"})
    _link_runs(doc)
    body_xml = doc.element.body.xml
    check("the sign in Webdings", bool(re.search(r'w:ascii="Webdings"[^>]*/>\s*</w:rPr>\s*'
                                                 r'<w:t[^>]*></w:t>', body_xml)), True)
    check("the address a link", "<w:hyperlink" in body_xml, True)
    check("the full stop left out of it",
          bool(re.search(r"<w:t[^>]*>www\.example\.org</w:t>", body_xml)), True)
    check("the text kept", "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", body_xml)),
          " الباب الثاني see www.example.org.")

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
