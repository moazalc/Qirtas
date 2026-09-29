#!/usr/bin/env python3
"""Tests for verses in Quran fonts written as the Quran has them
(convert/quran.py, FLAGS 33).

    python -m harness.test_quran

The stored lines are as `z18037898` holds them: letters of joined shapes
missing (ٱلَّذِينَ without its ذ), two-letter shapes turned round (ٱنلَّاس),
marks set apart by spaces (م ِن).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from convert import quran
from convert.quran import apply, build, letters, locate

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<56} got {got!r}")
    if not ok:
        print(f"        want {want!r}")
        FAILED.append(name)


# 49:13, the first line as stored
STORED = "يَـٰٓأَيُّهَا ٱنلَّاس ُ إِنَّا خَلَقۡنََٰكُم م ِن ذَكَر ٖ وَأُنَث ََٰ وَجَعَلۡنََٰكُم"
# its words as Tanzil spells them, found by their letters (a mark's place
# among the others differs between the two texts; the letters do not)
RIGHT = ["يايها", "الناس", "انا", "خلقنكم", "من", "ذكر", "وانثي", "وجعلنكم"]
# 60:1, ٱلَّذِينَ stored without its ذ
STORED_2 = "َيَـٰٓأَيُّه ۡا ٱَّلَِّينَ ءَامَنُوا  َّلَ تَتَّخِذُوا  عَدُو ِي وَعَدُوَّكُمۡ"


def said(text):
    """-> (the letters of each word, is every word one the Quran text has)."""
    ws = text.split()
    return [letters(w) for w in ws], all(w in QURAN for w in ws)


QURAN = set(quran._quran()[0])


def main():
    print("letters")
    check("hamza, alef wasla and marks fold away",
          letters("ٱلۡأَرۡضِ إِلَىٰ"), "الارضالي")

    print("where a stored line is")
    words, qletters, owner, _ = quran._quran()
    spots = locate(letters(STORED))
    check("found", spots is not None, True)
    if spots:
        first = owner[spots[0]]
        check("at 49:13's first word", letters(words[first]), "يايها")
    check("a line of prose is not found",
          locate(letters("وقد ضمن لهم الإسلام حفظ كرامتهم الإنسانية")), None)

    print("the table and its use")
    verses = build([[STORED]], [""])
    check("the line reads as the Quran has it", said(apply(STORED, verses)),
          (RIGHT, True))
    got = apply("﴿ " + STORED + " ﴾ (13)", verses)
    check("the bracket and the verse number stay",
          (got[:2], got[-7:], said(got[2:-7])), ("﴿ ", " ﴾ (13)", (RIGHT, True)))
    # the converter joins the marks the checker keeps apart: same result
    joined = STORED.replace("م ِن", "مِن").replace("ٱنلَّاس ُ", "ٱنلَّاسُ")
    check("the same line held another way", said(apply(joined, verses)),
          (RIGHT, True))
    got = apply(STORED_2, build([[STORED_2]], [""]))
    check("ٱلَّذِينَ gets its ذ, لَا its alef", said(got),
          (["يايها", "الذين", "ءامنوا", "لا", "تتخذوا", "عدوي", "وعدوكم"], True))

    print("the thesis's own writing is left alone")
    with_prose = build([[STORED]], ["قال تعالى: إنا خلقناكم من ذكر"])
    check("من used in prose is not a key", "من" in with_prose, False)
    check("... so prose keeps its من",
          apply("خرج من البيت", with_prose), "خرج من البيت")
    check("a stretch does not reach across a digit",
          apply("خَلَقۡنََٰكُم 3 م ِن ذَكَر ٖ", {"خلقنكممن": "X"}),
          "خَلَقۡنََٰكُم 3 م ِن ذَكَر ٖ")
    check("nothing matched, nothing changed",
          apply("بحث مقدم لنيل درجة", verses), "بحث مقدم لنيل درجة")

    print("a word cut in two")
    # ٱَّلل is ٱللَّهِ without its ه; held as ٱَّلل ه, the ه is right there
    cut = {"الل": "ٱللَّهِ"}
    check("ٱَّلل ه is left alone", apply("بِسۡمِ ٱَّلل ه ِ ٱلرَّحۡمَٰنِ", cut),
          "بِسۡمِ ٱَّلل ه ِ ٱلرَّحۡمَٰنِ")
    check("ٱَّلل on its own is repaired", apply("فَضۡلُ ٱَّللَِّ عَلَيۡكَ", cut),
          "فَضۡلُ ٱللَّهِ عَلَيۡكَ")

    print("groups that do not agree are dropped")
    # a whole that lines up, with one word that belongs somewhere else
    bad = STORED.replace("ذَكَر ٖ", "سَرِيعُ")
    got = apply(bad, build([[bad]], [""]))
    check("سَرِيعُ is not rewritten as ذَكَرٍ", "ذكر" in said(got)[0], False)

    cut = Path(__file__).resolve().parent.parent / "corpus/theses/cuts/z18037898.pdf"
    if cut.exists():
        print("z18037898")
        import os
        from convert.glyphs import repaired
        from convert.pdftext import fix_map
        path = repaired(str(cut))
        fixes = fix_map(path)
        check("its verses give a table", len(fixes.verses) > 100, True)
        # a whole line of 5:5 as stored: ٱَلَۡوۡمَ, ٱَّلَِّينَ, and ٌّ stored as ر
        line = ("ٱَلَۡوۡمَ أُحِلَّ لَكُمُ ٱلطَّي ِبََٰتَُۖ وَطَعَامُ ٱَّلَِّينَ أُوتُوا "
                "ۡٱلۡكِتََٰبَ حِل ر لَّكُمۡ")
        got = apply(line, fixes.verses).split()
        # its last word, لَّكُمۡ, is one the thesis writes too: repaired only
        # with the words after it, which this line stops before
        check("5:5 reads as the Quran has it", said(" ".join(got[:-1])),
              (["اليوم", "احل", "لكم", "الطيبت", "وطعام", "الذين", "اوتوا",
                "الكتب", "حل"], True))
        os.environ["QIRTAS_QURAN"] = "0"
        quran.ON = False
        check("off: no table", bool(fix_map(path).verses), False)
        quran.ON = True

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
