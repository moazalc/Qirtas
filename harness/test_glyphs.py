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

The table round trip and the name matching are tested too, since a table read
wrongly would "repair" a correct file.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from convert.glyphs import (_key, _plain, _same, _trust, read_tounicode,
                            write_tounicode)

FAILED = []
L = lambda *cps: "".join(map(chr, cps))

ALEF, BA, TA, JIM, HA, SIN, FA, LAM, MIM, NUN, WAW, YA = (
    L(0x627), L(0x628), L(0x62A), L(0x62C), L(0x62D), L(0x633), L(0x641),
    L(0x644), L(0x645), L(0x646), L(0x648), L(0x64A))
TATWEEL, SHADDA, HAMZA_BELOW = L(0x640), L(0x651), L(0x655)


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

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
