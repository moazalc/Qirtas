#!/usr/bin/env python3
"""Tests for the spelling check that does not share our extractor (TASKS N3).

    python -m harness.test_spelling

What was found building it:

  - Word reads some files partly backwards itself ("يف" 77 times beside "في"
    on z21508463). Such words must not vouch for ours, or a backwards file
    reads as 16% confirmed instead of 8%.
  - "Reversed, it is a word" is true of many three-letter fragments: "الإ"
    backwards is "إلا". Short words count as backwards only against the
    commonest words.
  - The Allah ligature is stored "هللا": the lam-alef fault with no pair to
    swap, not a backwards word.
  - A general "some two or three letters are swapped" rule was tried and NOT
    kept: Word swaps "را" itself (رأس -> أرس), so it blamed us for العراق and
    الزراعة, which we spell right. The rule cannot tell whose mistake it is.
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.spelling import (classify, check as count, lam_alef_forms,
                              reversed_share, tokens, vouching, xml_text)

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<55} got {got!r}")
    if not ok:
        FAILED.append(name)


def main():
    check("marks and tatweel go, one letter is not a word",
          tokens("الْكِتَـــاب و x خلال"), ["الكتاب", "خلال"])
    check("display forms are words too", tokens("ﻋﻠﻰ ok"), ["ﻋﻠﻰ"])
    check("runs of one paragraph join, paragraphs do not",
          xml_text("<w:p><w:r><w:t>خل</w:t></w:r><w:r><w:t xml:space=\"preserve\">ال"
                   "</w:t></w:r></w:p><w:p><w:r><w:t>ثم</w:t></w:r></w:p>"), "خلال\nثم\n")

    check("every mix of pairs, the word itself excluded",
          sorted(lam_alef_forms("الاال")), sorted(["لااال", "الالا", "لاالا"]))
    check("hamza alefs form the ligature too", "لإلصابة" in lam_alef_forms("لإلصابة")
          or "للإصابة" in lam_alef_forms("لإلصابة"), True)

    vocab = collections.Counter({"خلال": 5, "في": 40, "الله": 3, "مختلفة": 2,
                                 "كتاب": 4, "إلا": 9})
    common = {"في", "إلا"}
    check("seen by Word", classify("كتاب", vocab, common), "confirmed")
    check("lam-alef stored backwards", classify("خالل", vocab, common), "lam-alef")
    check("the Allah ligature is lam-alef", classify("هللا", vocab, common), "lam-alef")
    check("display form", classify("ﻋﻠﻰ", vocab, common), "display form")
    check("backwards, long word", classify("ةفلتخم", vocab, common), "backwards")
    check("backwards, short but common", classify("يف", vocab, common), "backwards")
    check("a fragment is not backwards", classify("الإ", vocab, {"في"}), "unconfirmed")
    check("unknown stays unconfirmed", classify("قرطاس", vocab, common), "unconfirmed")

    kinds, ex = count(["خالل", "خالل", "كتاب"], vocab, examples=1)
    check("counted by words, not by kinds", dict(kinds),
          {"lam-alef": 2, "confirmed": 1})
    check("examples most frequent first", ex["lam-alef"], [("خالل", 2)])

    word = collections.Counter({"على": 30, "ىلع": 3, "لا": 5, "ال": 8})
    check("a reversal of a commoner word cannot vouch",
          "ىلع" in vouching(word), False)
    # So a two-letter reversal like "يف" is kept out only by dropping the
    # whole reading (reversed_share), which is what caught z21508463.
    check("two-letter pairs are both real words and both stay",
          ("لا" in vouching(word), "ال" in vouching(word)), (True, True))
    check("reversed share", round(reversed_share(
        collections.Counter({"مختلفة": 9, "ةفلتخم": 1})), 2), 0.1)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
