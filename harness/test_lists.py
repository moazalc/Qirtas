#!/usr/bin/env python3
"""Tests for recognising list items and keeping them apart.

    python -m harness.test_lists

Five clean bullet points came out as one run-on paragraph with the bullets
stranded mid-line. Two separate causes, and the first is the interesting one:

1. **The line-joining rule asked whether a line ENDS like a finished
   sentence.** In right-to-left text the terminating punctuation is frequently
   STORED at the front - `تتمثل أساسا في:` extracts as `':وتتفرع ... في'`,
   colon at index 0 - so `endswith` never saw it and the bullet that followed
   was merged in. Fixed narrowly: a line that OPENS with a list marker starts a
   new item however the line above it ended. (Checking both ends of every line
   was tried, and cost pages across the corpus without helping lists. See
   PLAN.md.)

2. **Nothing marked list items on the geometry route at all** - 0 of them,
   against 8 to 53 paragraphs per file that plainly were.

Order matters: `detect_lists` runs AFTER `detect_headings`, because these
documents number their sections. `1 . مقدمة` is a heading and matches a list
marker just as well, and `detect_headings` only ever looks at paragraphs - so
marking lists first made every numbered heading unrecoverable.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.reader import LIST_MARK, detect_lists, detect_headings
from convert.model import Doc, Block, PARAGRAPH, HEADING, LIST_ITEM

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}")
    if not ok:
        print(f"        want {want!r}")
        FAILED.append(name)


def main():
    print("markers that open a real list item")
    for t in ("• الألم المنتشر : يوصف بأنه ألم مستمر",
              "- ضرب استفاض نقله وتلقاه الأئمة بالقبول",
              "1 . مؤشر الألم المنتشر يقيس مدى انتشار",
              "2- (Wellington Madesha, 2013). Empirical Test",
              "(3) الفقرة الثالثة من المادة"):
        check(t[:30], bool(LIST_MARK.match(t)), True)

    print("\nthings that look like markers and are not")
    # Each of these was matched by an earlier version of the pattern.
    check("a footnote marker", bool(LIST_MARK.match("* Corresponding author. E-mail")), False)
    check("a section divider", bool(LIST_MARK.match("*******")), False)
    check("a citation fragment", bool(LIST_MARK.match("[3] .")), False)
    check("a decimal number", bool(LIST_MARK.match("1.5 متر من الطول")), False)

    print("\na numbered HEADING stays a heading")
    # The ordering test. Both passes run over the same blocks; if lists were
    # marked first this heading would be a list item and unrecoverable.
    doc = Doc(blocks=[
        Block(kind=PARAGRAPH, text="1 . مقدمة", page=0, size=16.0),
        Block(kind=PARAGRAPH, text="نص عادي من الفقرة الأولى في هذا البحث وهو "
                                   "طويل بما يكفي ليكون متن المستند", page=0, size=12.0),
        Block(kind=PARAGRAPH, text="• عنصر أول من عناصر القائمة", page=0, size=12.0),
    ])
    doc = detect_lists(detect_headings(doc))
    kinds = [b.kind for b in doc.blocks]
    check("numbered heading kept as heading", kinds[0], HEADING)
    check("body text left alone", kinds[1], PARAGRAPH)
    check("bullet became a list item", kinds[2], LIST_ITEM)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
