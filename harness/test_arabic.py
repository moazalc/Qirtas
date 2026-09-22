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
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.arabic import (logical_text, reorder_neutrals, repair_lam_alef,
                            repair_ligatures)
from convert.reader import _present

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

    print("\nand the backfill must not be fooled by that same disagreement")
    # The cost of the space-sensitivity above is paid in reader._backfill.
    # One reader route yields "ومنها الشاذ", the other "ومنهالا شاذ" - the same
    # words, repaired on one side only. An exact substring test called the
    # second one missing and added the whole paragraph a second time. Five such
    # duplicates on one chapter added a page, and every page after it was one
    # out of step: right page 29.0% -> 72.6% when this was fixed.
    have = "فالقراءاتمنهاالمقبولومنهاالشاذوقدتسابقالعلماءفيالتصنيففيها"
    same = "فالقراءاتمنهاالمقبولومنهالاشاذوقدتسابقالعلماءفيالتصنيففيها"
    check("a repaired/unrepaired pair reads as already present",
          _present(same, have), True)
    check("an exact test would have missed it", same in have, False)

    print("\nbut genuinely absent text must still read as missing")
    # This is what backfill exists for: one Quranic verse, 110 characters,
    # present in the geometry reading and absent from the labels. A presence
    # test that swallows that loses text, which is the one thing not allowed.
    check("unrelated Arabic is missing",
          _present("وإذاقيللهملاتفسدوافيالأرضقالواإنمانحنمصلحون", have), False)
    check("empty haystack", _present("فالقراءاتمنهاالمقبول", ""), False)
    check("a sentence is present in itself", _present(have, have), True)

    print("\nthe geometric repair reaches what orthography cannot")
    # The rules above can only repair what Arabic spelling makes impossible,
    # and that leaves the commonest case untouched: a lam-alef reversed at the
    # END of a word. حاملا arrives as حامال and no spelling rule can help,
    # because مال, حال, شمال and جمال are all real words ending the same way.
    #
    # The glyphs were never ambiguous. لا is ONE glyph, so when its ToUnicode
    # lists the letters backwards the first character comes back with NO WIDTH
    # and the second carries the whole advance. A real alef beside a real lam
    # is two glyphs with two boxes. Measured on z21358439.pdf, page 3: 11
    # zero-width pairs, all reversed ligatures; 26 two-box pairs, all the
    # definite article.
    def line(text, widths):
        """(char, x0, x1) running right to left, as an RTL line does."""
        items, x = [], 500.0
        for c, w in zip(text, widths):
            items.append((c, x - w, x))
            x -= w
        return items

    # حامال : the final alef has no box of its own, so the pair is a ligature.
    got = "".join(t[0] for t in repair_ligatures(
        line("حامال", [3, 3, 3, 0, 3])))
    check("word-final ligature is repaired", got, "حاملا")

    # جمال : four real glyphs, four real boxes. Untouched.
    got = "".join(t[0] for t in repair_ligatures(
        line("جمال", [3, 3, 3, 3])))
    check("a real word ending alef-lam is left alone", got, "جمال")

    # z22110258's bibliography font: the ligature's alef has a real width, but
    # it and the lam are one glyph, so they END AT THE SAME EDGE and the lam
    # runs on past the alef. Stored االعالم for الاعلام.
    items = [("ا", 440, 443), ("ا", 436, 440), ("ل", 431, 436), ("ع", 425, 431),
             ("ا", 424, 430), ("ل", 418, 430), ("م", 414, 418)]
    got = "".join(t[0] for t in repair_ligatures(items))
    check("a ligature with a wide alef, by its shared edge", got, "االعلام")

    # غزال: a real alef that overlaps the letter before it, as kerning does.
    # Its own box, and it does not end where the lam ends. Untouched - the
    # looser test "the alef sits inside its neighbour" changed this word.
    items = [("غ", 440, 446), ("ز", 434, 440), ("ا", 434, 437), ("ل", 428, 434)]
    got = "".join(t[0] for t in repair_ligatures(items))
    check("a kerned real alef is left alone", got, "غزال")

    print("\nand neutrals go where the page says they go")
    # `مقدمة:` is stored `:مقدمة`, colon first, and the first line of a
    # paragraph stores its TRAILING space second - so `تبدأ` arrives as `ت بدأ`,
    # a word split by a space that belongs at the far end of the line. No
    # pymupdf mode orders either correctly: text, sort=True, blocks and words
    # were all tried.
    heading = [(":", 10.0, 13.0)] + [
        (c, 100.0 - 3 * i, 103.0 - 3 * i) for i, c in enumerate("مقدمة")]
    check("a leading colon moves to the end",
          "".join(t[0] for t in reorder_neutrals(heading)), "مقدمة:")

    # ت at the right edge, then the line's trailing space at the far left,
    # then the rest of the word.
    split = [("ت", 97.0, 100.0), (" ", 10.0, 13.0)] + [
        (c, 94.0 - 3 * i, 97.0 - 3 * i) for i, c in enumerate("بدأ")]
    check("a displaced space rejoins the word",
          "".join(t[0] for t in reorder_neutrals(split)), "تبدأ ")

    print("\nnone of which may touch a line that is not Arabic")
    # Only neutrals ever move, so an embedded English phrase or a year cannot
    # be reversed - and a line that is not overwhelmingly Arabic is skipped
    # outright. An English abstract has its own direction and nothing here
    # would improve it.
    latin = [(c, 10.0 + 3 * i, 13.0 + 3 * i) for i, c in enumerate("Hello, world")]
    check("a latin line is returned exactly as stored",
          "".join(t[0] for t in reorder_neutrals(latin)), "Hello, world")
    year = [(c, 100.0 - 3 * i, 103.0 - 3 * i) for i, c in enumerate("سنة")] + \
           [(c, 88.0 + 3 * i, 91.0 + 3 * i) for i, c in enumerate("2026")]
    check("digits keep their own order inside an arabic line",
          "".join(t[0] for t in reorder_neutrals(year)), "سنة2026")

    print("\nand a combining mark is part of its letter, not a neutral")
    # A haraka has no width and sits on top of the letter it belongs to, so its
    # x is that letter's x. Treated as a neutral it cannot be placed, and the
    # marks of a fully-vowelled text drift onto their neighbours. Caught on a
    # Quranic verse, every letter of which is vowelled; it cost the hard gate
    # 1.000 -> 0.944 before NSM was added to the set that never moves.
    vowelled = []
    x = 100.0
    for c in "وَالَّذِين":
        w = 0.0 if unicodedata.combining(c) else 3.0
        vowelled.append((c, x - w, x))
        x -= w
    check("a vowelled word is returned exactly as stored",
          "".join(t[0] for t in reorder_neutrals(vowelled)),
          "وَالَّذِين")

    print("\nand correctly stored text must come through untouched")
    good = [(c, 100.0 - 3 * i, 103.0 - 3 * i) for i, c in enumerate("قال لا شيء")]
    check("a well-formed rtl line is a no-op",
          "".join(t[0] for t in reorder_neutrals(good)), "قال لا شيء")
    check("empty line", logical_text([]), "")

    print("\nand the fix map works in words, whatever sits beside them")
    # FLAGS 20: the map was keyed on whitespace tokens with a word of context.
    # A note number glued on ("واإلسالميني1") became a real note in our text
    # and stayed in the checker's, so the repair fired on one side only.
    from convert.pdftext import _fragments, apply_fixes
    check("one pair per changed word, letters only",
          list(_fragments("للعرب واإلسالميني1 .", "للعرب والإسلاميني1 .")),
          [("واإلسالميني", "والإسلاميني")])
    # z20276145 stretches words with alefs (المصلحة as المصاااالحة). Those
    # alefs are filler; the two sides moved different ones and the gate fell
    # to 95% with this rule off.
    check("a word stretched with alefs is left to the spelling rules",
          list(_fragments("المصاااالحة", "المصااالاحة")), [])
    check("no pair when the lengths differ (not a swap)",
          list(_fragments("اال", "الا ")), [])
    fixes = {"واإلسالميني": "والإسلاميني"}
    check("fires beside a digit or a bracket",
          apply_fixes("(واإلسالميني1)", fixes), "(والإسلاميني1)")
    check("never inside a longer word",
          apply_fixes("كواإلسالميني", fixes), "كواإلسالميني")

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
