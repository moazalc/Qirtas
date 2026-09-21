#!/usr/bin/env python3
"""Tests for the answer key's grading.

    python -m harness.test_answerkey

The key's first version was wrong three times before it was believed, each
time in a way that looked like a converter fault:

  - The theses' labels hold text in pieces shorter than a matching run, so
    2,709 words of a file the gate calls complete came back "missing".
  - Joining those pieces fixed that and broke the poems: their pieces are
    whole words with no space between them, and joined they read as one word.
    Both are why text is compared as letters, with spaces ignored.
  - A right-to-left table may store its cells in the other order and still
    draw them the same way round. Matched as a stream it scored 0%, while a
    duplicate of its numbers written as loose text took the credit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.answerkey import grade, letters, kind_of, table

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<55} got {got!r}")
    if not ok:
        FAILED.append(name)


PROSE = ("وبناء على هذا فإذا فقدت القراءة شرطا من هذه الشروط صارت القراءة "
         "شاذة عند جمهور العلماء")


def main():
    print("letters")
    check("lam-alef stored backwards matches", letters("خالل"), letters("خلال"))
    check("spaces do not matter", letters("الث لاثة"), letters("الثلاثة"))
    check("marks and tatweel ignored", letters("القُرْآنُ"), letters("القرآن"))
    check("presentation forms fold", letters("ﻤنطقﺔ"), letters("منطقة"))

    print("\nkinds follow the whole chain of labels")
    check("list inside a footnote is a footnote",
          kind_of(["Document", "Footnote", "L", "LI"]), "footnote")
    check("cell paragraph is table", kind_of(["Table", "TR", "TD", "P"]), "table")
    check("plain P", kind_of(["Document", "P"]), "paragraph")

    print("\ngrading")
    # Truth in the shape of the theses: a paragraph cut into pieces mid-word.
    pieces = [("paragraph", PROSE[i:i + 7], 0) for i in range(0, len(PROSE), 7)]
    c = grade(pieces, [("paragraph", PROSE)])
    check("pieces cut mid-word all match", c["paragraph"]["missing"], 0)

    c = table(grade([("footnote", PROSE, 0)], [("list", PROSE)]))
    check("footnote written as a list is found 0%", c["footnote"]["found"], 0.0)
    check("... and says where it went", list(c["footnote"]["went"]), ["list"])

    years = [str(y) for y in range(2009, 2023)]
    truth = [("table", y, 0) for y in years]
    ours = [("paragraph", " ".join(years))] + [("table", y) for y in reversed(years)]
    c = table(grade(truth, ours))
    check("cells stored in the other order still found", c["table"]["found"], 1.0)
    check("duplicate loose copy counted as extra",
          c["paragraph"]["extra"], len(letters(" ".join(years))))

    c = table(grade([("paragraph", PROSE, 0)], [("paragraph", PROSE),
                                                ("paragraph", PROSE)]))
    check("a sentence written twice: second copy is extra",
          c["paragraph"]["extra"], len(letters(PROSE)))

    c = table(grade([("furniture", "مجلة الجامعة", p) for p in range(5)],
                    [("furniture", "مجلة الجامعة")]))
    check("header written once covers every page", c["furniture"]["found"], 1.0)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
