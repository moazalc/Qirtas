#!/usr/bin/env python3
"""Tests for the colon-ending heading rule.

    python -m harness.test_headings

Every line below is real text taken from the corpus, with the verdict a reader
would give it. detect_headings used to promote ANY short line ending in a
colon, which swept up sentence tails like "على قسمين:" ("...into two
categories:"). Deleting the rule is not an option either - it is the only thing
that finds "الدراسات السابقة:" and "أهداف البحث:", which are real sub-headings
in a thesis that uses no Word heading styles at all.

Length does not separate them: "على قسمين:" is the SHORTEST line here and it is
wrong. What separates them is grammar - a heading is a noun phrase, so it
carries no comma, no internal colon, and does not open with a connective
particle.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.reader import _is_label_heading

FAILED = []

# Real sub-headings. These must survive.
HEADINGS = [
    "الدراسات السابقة:",
    "أهداف البحث:",
    "مشكلة البحث:",
    "مفهوم اللغة في الاصطلاح:",
    "اسمه ونسبه وكنيته وألقابه:",
    "مولده وصفاته وبركات بيت النبوَّة عليه:",
    "منزلته العلمية وثناء العلماء عليه:",
]

# Sentences that merely end in a colon. These must not be promoted.
SENTENCES = [
    "على قسمين:",
    "فالقراءة لها ضوابط لابد من توفرها فيها, وهي:",
    "وقد تناول الإمام ابن الجزري هذه الشروط في منظومته , فقال:",
    "التفسير في الاصطلاح: عرفه العلماء بتعريفات عدة, منها:",
    "وأمَّا القراءة الشاذة ففيها وجهان:",
    "ويتبين من هذا أن النحاة قد اتخذوا من القراءات الشاذة وجهتين:",
    "أبرز تلك التآليف, ما يلي:",
    "أهمية البحث: البحث له أهميتان, وهما:",
    "أما عن عبادته, ومواقفه, ومناصبه:",
]


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name[:58]:<60} got {got}")
    if not ok:
        FAILED.append(name)


def main():
    print("real sub-headings must still be found")
    for t in HEADINGS:
        check(t, _is_label_heading(t), True)

    print("\nsentences ending in a colon must not become headings")
    for t in SENTENCES:
        check(t, _is_label_heading(t), False)

    print("\nlines with no colon are not this rule's business")
    for t in ("المطلب الأول", "نص عادي بدون نقطتين", ""):
        check(t or "(empty)", _is_label_heading(t), False)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
