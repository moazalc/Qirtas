#!/usr/bin/env python3
"""Tests for the labels route: Word's structure labels over glyph text.

    python -m harness.test_labels

Before this route, the reader ignored the labels on every ordinary Word file -
the tags route reads only /ActualText, which those files do not carry - and
geometry guessed the structure back: no footnote found on any of 36 files, a
third of prose made into list items. Two things went wrong on the way in, and
each has a case here:

  - A list inside a footnote must stay a footnote. Splitting at the list is
    how `الفصل الثالث`'s notes (34) and (35) landed in the body.
  - Fields side by side on one line are one paragraph. `عن بعد` has three,
    labelled separately; stacked as three headings, the one-page form ran onto
    a second page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.model import Doc, Block, PARAGRAPH, HEADING, LIST_ITEM, FOOTNOTE, TABLE
from convert.reader import (_label_kind, _join_same_line, _backfill, _glued,
                            _drop_text_inside_tables)

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<50} got {got!r}")
    if not ok:
        FAILED.append(name)


def field(text, x0, x1, y=275.0, kind=HEADING):
    return Block(kind=kind, text=text, size=22.0, y=y, y1=y + 33.0,
                 x0=x0, x1=x1, spans=[(text, True, False)])


def main():
    print("what the labels say")
    check("list inside a footnote",
          _label_kind(["Part", "Footnote", "L", "LI", "LBody", "P"]),
          (FOOTNOTE, 0))
    check("H2", _label_kind(["Document", "H2"]), (HEADING, 2))
    check("list item", _label_kind(["Document", "L", "LI", "LBody"]),
          (LIST_ITEM, 0))
    check("table cell stays for read_tables",
          _label_kind(["Table", "TR", "TD", "P"]), (PARAGRAPH, 0))
    check("plain paragraph", _label_kind(["Document", "P"]), (PARAGRAPH, 0))

    print("\nfields on one line")
    # Label order is left to right, as `عن بعد` stores them.
    got = _join_same_line([field(":الرقم", 77, 119), field(":التوقيع", 286, 342),
                           field(":اسم الطالبة", 479, 570)])
    check("three fields become one block", len(got), 1)
    check("joined right to left", got[0].text, ":اسم الطالبة :التوقيع :الرقم")

    stacked = _join_same_line([field(":اسم المسجد", 469, 579, y=155),
                               field(":اسم المعلمة", 478, 572, y=192)])
    check("lines one under another stay apart", len(stacked), 2)

    mixed = _join_same_line([field("مقدمة", 400, 560),
                             field("نص", 80, 380, kind=PARAGRAPH)])
    check("different kinds stay apart", len(mixed), 2)

    notes = _join_same_line([field("(1) انظر", 300, 560, kind=FOOTNOTE),
                             field("(2) انظر", 60, 280, kind=FOOTNOTE)])
    check("footnotes side by side stay apart", len(notes), 2)

    print("\ntext another reading found, put back only if really missing")
    right = ("وقد لعبت منذ نشأتها دورا كبيرا في حفظ التراث الإسلامي "
             "والحفاظ على الهوية الوطنية")
    wrong = ("وقد لعبت منذ نشأهتا ًدورا ًكبريا في حفظ الرتاث الإسالمي "
             "واحلفاظ على اهلوية الوطنية")
    spell = {"نشأهتا": "نشأتها", "ًدورا": "دورا", "ًكبريا": "كبيرا",
             "الرتاث": "التراث", "الإسالمي": "الإسلامي", "واحلفاظ": "والحفاظ",
             "اهلوية": "الهوية"}

    def fix(t):
        for a, b in spell.items():
            t = t.replace(a, b)
        return t

    def docs(have):
        chosen, other = Doc(pages=1), Doc(pages=1)
        chosen.add(Block(kind=PARAGRAPH, text=have, page=0))
        other.add(Block(kind=PARAGRAPH, text=wrong, page=0))
        return chosen, [(0, chosen), (0, other)]
    # The z21762915 case: without the chosen reading's spelling repair, the
    # other reading's misspelled copy looked missing and was added again -
    # a third of that file was a second copy (FLAGS 25).
    chosen, results = docs(right)
    check("a misspelled copy is not added again",
          len(_backfill(chosen, results, None, fix).blocks), 1)
    chosen, results = docs("نص آخر لا علاقة له بما في الصفحة من كلام طويل هنا")
    check("text really missing is still put back",
          len(_backfill(chosen, results, None, fix).blocks), 2)

    print("\na word the PDF cut between two pieces")
    import collections

    def piece(text, x0, x1, y1=407.0, size=12.0):
        return {"text": text, "bbox": (x0, y1 - 20, x1, y1), "size": size,
                "flags": 0}
    vocab = collections.Counter({"يحتفظ": 2, "الخزان": 3, "شملت": 1,
                                 "دراستنا": 1})
    # z19773087: "سورية، ي" | "حتفظ المؤلفون", touching at x=503
    check("cut inside a word: joined",
          _glued(piece("سورية، ي", 503, 538), piece("حتفظ المؤلفون", 415, 503),
                 vocab), True)
    check("two real words that touch: not joined (FLAGS 24)",
          _glued(piece("شملت", 300, 330), piece("دراستنا", 250, 300), vocab),
          False)
    check("a space at the seam: not joined",
          _glued(piece("سورية، ي ", 503, 538), piece("حتفظ", 415, 503), vocab),
          False)
    check("apart on the line: not joined",
          _glued(piece("ال", 533, 538), piece("خزان", 480, 520), vocab), False)
    check("Arabic against English: not joined",
          _glued(piece("قام", 400, 430), piece("Yazdanian", 330, 400),
                 collections.Counter({"قامyazdanian": 1})), False)
    check("a word the document never prints whole: not joined",
          _glued(piece("مها", 400, 420), piece("العبد", 360, 400), vocab), False)

    print("\na table's words printed again outside it")
    # z21762915: the header band repeats the title; the title below it stays.
    title = "زاوية الهامل ودورها في حفظ التراث الجزائري"
    band = Block(kind=TABLE, text="", page=0, y=29.0, y1=55.0,
                 rows=[["", ".د بن بوزيد لخضر " + title]])
    d = Doc(pages=1)
    d.add(Block(kind=PARAGRAPH, text=".د بن بوزيد لخضر " + title, page=0,
                y=33.0, y1=50.0))
    d.add(Block(kind=PARAGRAPH, text=title, page=0, y=68.0, y1=93.0))
    _drop_text_inside_tables(d, [band])
    check("the band's own copy dropped, the title kept",
          [b.y for b in d.blocks], [68.0])
    d = Doc(pages=1)
    d.add(Block(kind=PARAGRAPH, text=title, page=0))
    _drop_text_inside_tables(d, [band])
    check("no position: text alone decides, as before", len(d.blocks), 0)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
