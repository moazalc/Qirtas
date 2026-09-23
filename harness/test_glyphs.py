#!/usr/bin/env python3
"""Tests for recovering text from fonts that name the wrong letters (FLAGS 23).

    python -m harness.test_glyphs

`convert/glyphs.py` replaces what a PDF says a shape is with what the
installed font says it is. Every rule below was a wrong change seen on a real
file before it was a rule:

  - a typed 2 or ; is DISPLAYED as ٢ or ؛ by Word; the stored one is right
    (z22110258, z19851706)
  - fonts drawing dots as marks over a dotless base name the base of في as
    ڜ; a stored letter with the same base shape is kept (z21095413) - unless
    the font is scrambled, where it is as wrong as the rest (z20393612 kept
    مراحعة for مراجعة until this was split)
  - a hamza drawn as a mark of its own, inserted into a blank, lands before
    its letter (z21760107: ا became ٕا)
  - ﷲ and ﷴ are typed as letters
  - AGA Arabesque stores its signs as private codes: ﷺ and رضي الله عنه
    reached Word as a box (Moaz's theses)
  - a digit or a joined pair the installed font names differently from the
    file: the page decides, read by OCR (convert/witness.py, FLAGS 25)

The table round trip and the name matching are tested too, since a table read
wrongly would "repair" a correct file.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf

from convert.glyphs import (_key, _plain, _same, _trust, diagnose, family,
                            read_tounicode, spell_out, write_tounicode)

FAILED = []
L = lambda *cps: "".join(map(chr, cps))

ALEF, BA, TA, JIM, HA, SIN, FA, LAM, MIM, NUN, WAW, YA = (
    L(0x627), L(0x628), L(0x62A), L(0x62C), L(0x62D), L(0x633), L(0x641),
    L(0x644), L(0x645), L(0x646), L(0x648), L(0x64A))
TATWEEL, SHADDA, HAMZA_BELOW = L(0x640), L(0x651), L(0x655)


def _sign_font():
    """A document holding one font the way Word embeds AGA Arabesque."""
    doc = pymupdf.open()
    tu = doc.get_new_xref()
    doc.update_object(tu, "<<>>")
    doc.update_stream(tu, write_tounicode({0x55: L(0xF072), 0x57: L(0xF074),
                                           0x20: " "}))
    font = doc.get_new_xref()
    doc.update_object(font, "<</Type/Font/Subtype/Type0/BaseFont"
                      "/ABCDEE+AGA#20Arabesque/Encoding/Identity-H"
                      f"/ToUnicode {tu} 0 R>>")
    return doc, font


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<56} got {got!r}")
    if not ok:
        FAILED.append(name)
        print(f"        want {want!r}")


def main():
    print("names")
    check("subset tag dropped", _key("BCDKEE+SimplifiedArabic"),
          "simplifiedarabic")
    check("Times with and without PS/MT", _key("TimesNewRomanPS-BoldMT"),
          _key("Times New Roman,Bold"))
    check("Arial and ArialMT", _key("ArialMT"), _key("Arial"))
    check("Traditional Arabic, both spellings",
          _key("ABCDEE+Traditional Arabic,Bold"), _key("TraditionalArabic-Bold"))

    print("the table")
    table = {3: " ", 0x187: TATWEEL, 0x341: LAM + ALEF, 0x3A5: MIM}
    check("written and read back", read_tounicode(write_tounicode(table)),
          table)
    ranges = (b"beginbfrange\n<0010> <0012> <0030>\n"
              b"<0020> <0021> [<0633> <0644>]\nendbfrange")
    check("ranges, both kinds", read_tounicode(ranges),
          {0x10: "0", 0x11: "1", 0x12: "2", 0x20: SIN, 0x21: LAM})

    print("display signs")
    check("the sign for Allah is typed as letters", _plain(L(0xFDF2)),
          ALEF + LAM + LAM + L(0x647))
    check("the sign for Muhammad is typed as letters", _plain(L(0xFDF4)),
          MIM + HA + MIM + L(0x62F))
    check("the honorific stays", _plain(L(0xFDFA)), L(0xFDFA))

    print("same or not")
    check("a joined pair stored backwards is the same", _same(ALEF + LAM,
                                                              LAM + ALEF), True)
    check("alef with hamza on a plain alef shape", _same(L(0x623), ALEF), True)
    check("a different letter is not", _same(SIN, MIM), False)

    print("what to replace")
    check("the stretching stroke stored as a letter",
          _trust(L(0x631), TATWEEL), True)
    check("a letter stored as a blank", _trust(" ", YA), True)
    check("a letter of another shape", _trust(SIN, MIM), True)
    check("a typed digit shown as Arabic-Indic", _trust("2", L(0x662)), False)
    check("a typed ; shown as the Arabic one", _trust(";", L(0x61B)), False)
    check("same base shape, font otherwise right", _trust(HA, JIM), False)
    check("same base shape, font scrambled", _trust(HA, JIM, scrambled=True),
          True)
    check("a dotless base named after a rare letter", _trust(FA, L(0x69C)),
          False)
    check("a hamza mark into a blank", _trust(" ", HAMZA_BELOW), False)
    check("a vowel mark into a blank", _trust(" ", SHADDA), True)
    check("a vowel mark over a real letter", _trust(NUN, SHADDA), False)
    check("a joined pair over junk", _trust(TA + L(0x661), LAM + MIM), True)
    check("a joined pair over letters", _trust(YA + WAW, YA + HA), False)

    print("signs")
    table, _ = diagnose(*_sign_font())
    check("the prophet's honorific", table and table[0x55], L(0xFDFA))
    check("may God be pleased with him, as one character",
          table and table[0x57], chr(0xFD47))
    check("... written out for Word", spell_out("عثمان " + chr(0xFD47)),
          "عثمان رضي الله عنه")
    check("an ordinary code left alone", table and table[0x20], " ")
    thesis = Path("corpus") / "الفصل الثالث قراءات انفرادات.pdf"
    if thesis.exists():
        # Every word a labelled picture, only the signs real text, under a
        # label with no text: the tags route dropped all of them.
        from convert.glyphs import repaired
        from convert.reader import read_tags
        text = " ".join(b.text for b in read_tags(repaired(thesis)).blocks)
        check("a thesis' unlabelled signs are read",
              (text.count(L(0xFD47)), text.count(L(0xFDFA))), (13, 2))
        check("... in their place", "أبي بكر " + L(0xFD47) + "؛" in text, True)

    print("the page settles what the file and the installed font dispute")
    journal = Path("corpus/wild/z21762915.pdf")
    from convert.witness import PS, settle
    if journal.exists() and PS.exists():
        # The page prints 1315 and محمد; the file stores 3133 and زلمد. The
        # installed font names both right, and the old rules would not use it:
        # never a digit, a joined pair only over junk (FLAGS 25).
        tables = settle(journal)
        body = tables.get(33, ({}, ""))[0]
        check("a 1 stored as 3 is a 1", body.get(20), "1")
        check("a 5 stored as 3 is a 5", body.get(24), "5")
        check("the pair محـ stored as لز", body.get(368), "مح")

    print("a space inside a word, by the shapes round it")
    from convert.glyphs import forms, _index, _key as fkey
    from convert.pdftext import _split_at, _touch, join_map
    check("a font not installed gives no evidence", forms("AL-Mohanad"), None)
    if fkey("ArialMT") in _index():
        from fontTools.ttLib import TTFont
        with TTFont(_index()[fkey("ArialMT")], lazy=True) as t:
            cmap, order = t.getBestCmap(), t.getGlyphOrder()
        gid = {g: i for i, g in enumerate(order)}
        arial = forms("ArialMT")
        # Arial draws ب alike at the start and in the middle of a word: that
        # shape joins the letter after it, never surely the one before.
        check("ب begun: joins forward",
              "init" in arial.get(gid[cmap[0xFE91]], ()), True)
        from convert.glyphs import reference
        ba = {g for g, t in reference("ArialMT")[0].items() if t == BA}
        check("a ب that ends a word: joins back only",
              {"fina"} in [arial.get(g) for g in ba], True)

    def ch(c, x0, x1, y=100.0):
        return {"c": c, "bbox": (x0, y - 12, x1, y), "origin": (x0, y)}
    check("joined letters touch", _touch(ch(NUN, 300, 306), ch(YA, 294, 300)),
          True)
    check("letters apart do not", _touch(ch(NUN, 300, 306), ch(YA, 250, 256)),
          False)
    check("the word is joined, the next left",
          _split_at(list(ALEF + LAM + NUN + " " + YA + " " + FA), {3}),
          [(ALEF + LAM + NUN + " " + YA, ALEF + LAM + NUN + YA)])
    if journal.exists():
        from convert.glyphs import repaired
        joins = join_map(str(repaired(journal)))
        check("الوطن ية is one word", joins.get("الوطن ية"), "الوطنية")
        # Letters stored out of drawing order sit side by side in the text
        # and apart on the page; their joins are to other letters.
        check("م في كان is left alone", "م في كان" in joins, False)

    print("what a font says plainly is not a letter")
    stretched = Path("corpus/wild/z20397518.pdf")
    if stretched.exists():
        import re
        with pymupdf.open(repaired(str(stretched))) as doc:
            page = doc[1].get_text()
        check("the stretching stroke is not a letter (شبببببكات)",
              len(re.findall("ب{3,}", page)), 0)
        check("شبكات reads whole", "شبكات" in page.replace("ـ", ""), True)
        check("a space is not ا (طرابلس تعتمد)",
              "طرابلس تعتمد" in page.replace("ـ", ""), True)

    print("the name Word knows a font by")
    check("the standard Times", family("Times-Roman"), "Times New Roman")
    check("a font not installed keeps its name", family("AL-Mohanad"),
          "AL-Mohanad")
    if family("ArialMT") != "ArialMT":      # only where Arial is installed
        check("Arial's PostScript name", family("ArialMT"), "Arial")
    # Only where the font is installed (Moaz's PC since 2026-09-23).
    if family("AF_Diwani-NormalTraditional") != "AF_Diwani-NormalTraditional":
        check("a name Word cut at 24 characters",
              family("AF_Diwani-NormalTraditio"), "AF_Diwani")
    check("a cut name matches nothing shorter than 24",
          family("AF_Diwani"[:6]), "AF_Diw")
    if family("(A) Arslan Wessam B") == "(A) Arslan Wessam B":
        from convert.glyphs import _path
        check("a font named by its family",
              _path("(A) Arslan Wessam B") is not None, True)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
