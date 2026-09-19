#!/usr/bin/env python3
"""Tests for repairing text the source PDF handed us backwards.

    python -m harness.test_arabic

لا is a LIGATURE: one glyph in the PDF, mapped back to two letters by the
font's ToUnicode table. In a large share of this corpus that table lists the
two letters in the wrong order, so لا extracts as ال - a standalone alef-lam.

This is not LibreOffice, and no font is missing. The .docx contains the
reversed pair before LibreOffice is ever invoked, and correctly-ordered words
sit on the same line. compare.py's docstring blamed LibreOffice's PDF export
for years; it was wrong, and this file is where the correction lives.

The repair is safe because a standalone ال is not valid Arabic. The definite
article is a prefix and must attach to the word it defines, so an ال with
whitespace or punctuation on both sides can only be a mangled لا. 773
occurrences in 25 corpus files, against 0 legitimate uses.

Prefixed forms are deliberately NOT repaired. وال (124), بال (21) and فال (5)
also occur, and some of those are genuine words - بال is mind or condition, as
in ما بال, and فأل is an omen. Repairing them would corrupt valid text to fix
a tenth as many cases, so they are left alone and recorded here instead.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.arabic import repair_lam_alef

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<50} got {got!r}")
    if not ok:
        print(f"{'':<58}want {want!r}")
        FAILED.append(name)


def main():
    print("a standalone alef-lam is a mangled lam-alef")
    check("mid sentence", repair_lam_alef("وهذا ال يمكن قبوله"),
          "وهذا لا يمكن قبوله")
    # Deliberately NOT repaired at the very start or end of the string. The
    # reader repairs block by block and the checker repairs the whole document,
    # so an ال at a block edge looks standalone to one and not the other; they
    # then fire different rules and our output stops matching what it is scored
    # against. z21763864.pdf regressed to 98.89% exactly this way.
    check("at the start of the string, left alone",
          repair_lam_alef("ال يجوز ذلك"), "ال يجوز ذلك")
    check("at the very end, left alone", repair_lam_alef("قال ال"), "قال ال")
    check("but repaired with text on both sides",
          repair_lam_alef("وقال ال يجوز"), "وقال لا يجوز")
    check("before punctuation", repair_lam_alef("قال: ال."), "قال: لا.")
    check("more than one", repair_lam_alef("قال ال هذا و ال ذاك بل"),
          "قال لا هذا و لا ذاك بل")

    print("\nbut the definite article, which is attached, must not be touched")
    check("attached to a noun", repair_lam_alef("الكتاب مفيد"), "الكتاب مفيد")
    check("several definite articles",
          repair_lam_alef("الملف العقاري السوري"), "الملف العقاري السوري")
    check("word merely ending in alef-lam",
          repair_lam_alef("قال الرجل"), "قال الرجل")

    print("\nand text that is already correct must come through unchanged")
    check("correct lam-alef", repair_lam_alef("لا يمكن"), "لا يمكن")
    check("empty", repair_lam_alef(""), "")
    check("none", repair_lam_alef(None), None)
    check("latin text", repair_lam_alef("hello world"), "hello world")

    print("\nthe hamza-carrying lam-alef ligatures reverse the same way")
    # لا is not the only lam-alef ligature. لأ لإ لآ are ligatures too, and the
    # same broken ToUnicode reverses them into أل إل آل. After the definite
    # article that produces األ اإل اآل, which is not orthographically possible
    # in Arabic - two alef forms cannot sit together like that - so the repair
    # is as safe as the standalone case.
    check("alef-hamza above", repair_lam_alef("الحساسية واألهمية"),
          "الحساسية والأهمية")
    check("alef-hamza below", repair_lam_alef("اإلسكان الحكومي"),
          "الإسكان الحكومي")
    check("alef madda", repair_lam_alef("اآلخر"), "الآخر")
    check("several in one line", repair_lam_alef("األرض واألسر واإلنسان"),
          "الأرض والأسر والإنسان")
    # Plain alef is the same case: الاستثمار arrives as االستثمار.
    check("plain alef", repair_lam_alef("واالستثمار العقاري"),
          "والاستثمار العقاري")
    check("a word that really does contain alef-lam-alef-lam",
          repair_lam_alef("الالتزام كامل"), "الالتزام كامل")

    print("\nthe two rules must not compete over the same word")
    # z21763864.pdf: the reader and the checker extract the same page by
    # different pymupdf modes, and those disagree about where spaces fall. One
    # yields اآل contiguously (trigram rule -> الآ), the other ال آل (standalone
    # rule -> لا آل). The same words then differed between our output and the
    # text it is scored against, and the hard gate dropped to 98.89%.
    #
    # An ال followed by an alef form is a split ligature, not a standalone word.
    # Left alone, it reads as الآ once whitespace is normalised - matching what
    # the contiguous side produces.
    # Same word both ways: الآلف, mangled. Contiguous it is اآللف; spaced, the
    # other extraction mode splits it as ال آلف.
    check("contiguous form", repair_lam_alef("عىل اآللف من"), "عىل الآلف من")
    check("spaced form is left for normalisation, not turned into لا",
          repair_lam_alef("عىل ال آلف من"), "عىل ال آلف من")
    check("both agree once spaces are stripped",
          repair_lam_alef("عىل اآللف من").replace(" ", ""),
          repair_lam_alef("عىل ال آلف من").replace(" ", ""))

    print("\nbut a word that legitimately starts alef-hamza-lam is untouched")
    # ألف, ألم, ألوان all begin أل and are perfectly ordinary words. Only the
    # trigram alef + hamza-alef + lam is repaired, never a bare أل.
    check("alf, a thousand", repair_lam_alef("ألف كتاب"), "ألف كتاب")
    check("alwan, colours", repair_lam_alef("ألوان زاهية"), "ألوان زاهية")
    check("definite article on alf", repair_lam_alef("الألف"), "الألف")

    print("\nprefixed forms are left alone on purpose - see the module docstring")
    check("bal is a real word", repair_lam_alef("ما بال هذا"), "ما بال هذا")
    check("wal untouched", repair_lam_alef("وال يمكن"), "وال يمكن")

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
