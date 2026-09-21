#!/usr/bin/env python3
"""Tests for notes as Word prints them: raised numbers, and endnotes.

    python -m harness.test_notes

The theses type their references "(13)". Word-made files draw them as small
raised digits - "شاتليه¹³" - and on 36 such files the writer turned 6% of the
notes into real notes. What was found on the way (TASKS N2b):

  - A reference is found by SIZE against the whole labelled piece. The
    superscript flag is set on some and not others in one paragraph, and the
    raised digits sit on a line of their own in PyMuPDF's view.
  - A number can arrive in pieces and in brackets: "(1" then "1" is note 11.
  - Several notes are often labelled as ONE piece and must be split by number.
  - A reference no note claims is written back raised, not as "(13)", which
    the original never printed.
  - Endnotes: notes printed together at the end, cited from earlier pages.
    Only when the document really ends with them - a heading "1.1" with a
    small "1" was once paired with a page-13 note as an "endnote".
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.footnotes import MARK_OPEN, MARK_CLOSE, marker_numbers
from convert.model import Doc, Block, PARAGRAPH, FOOTNOTE
from convert.reader import _mark_note_numbers, _split_notes, _split_typed_notes
from convert.writer import write

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<55} got {got!r}")
    if not ok:
        FAILED.append(name)


def span(text, size, flags=4):
    return {"text": text, "size": size, "flags": flags}


def block(*spans):
    return {"lines": [{"spans": list(spans)}]}


def raised(n):
    return MARK_OPEN + n + MARK_CLOSE


def main():
    print("finding raised numbers")
    b = block(span("قال شاتليه", 16.0), span("13", 10.6, 5),
              span(" ثم روى ", 16.0), span("14", 10.6, 4))
    _mark_note_numbers([b])
    got = [s["text"] for s in b["lines"][0]["spans"]]
    check("raised digits marked, flag or not", marker_numbers("".join(got)),
          ["13", "14"])
    b = block(span("نص طويل من المتن", 16.0), span("(1", 10.6), span("1", 10.6),
              span(")", 10.6), span(" وبعد", 16.0))
    _mark_note_numbers([b])
    check("(1 + 1 + ) is note 11",
          marker_numbers("".join(s["text"] for s in b["lines"][0]["spans"])),
          ["11"])
    b = block(span("سنة", 16.0), span("1956", 16.0))
    _mark_note_numbers([b])
    check("full-size year left alone",
          marker_numbers("".join(s["text"] for s in b["lines"][0]["spans"])), [])

    print("\nsplitting notes labelled as one piece")
    note = Block(kind=FOOTNOTE, page=3,
                 text=f"{raised('1')} انظر الأول {raised('2')} انظر الثاني")
    parts = [p.text for p in _split_notes(note)]
    check("two notes", parts, ["(1) انظر الأول", "(2) انظر الثاني"])
    body = Block(kind=PARAGRAPH, page=3, text="قال(7) ثم قال(8) وقال(2)")
    typed = Block(kind=FOOTNOTE, page=3,
                  text="(7) صحيفة فلسطين ج(2) ص4 (8) خالد العظم")
    parts = [p.text for p in _split_typed_notes([body, typed]) if p.kind == FOOTNOTE]
    check("typed (7) (8) split, volume ج(2) kept",
          parts, ["(7) صحيفة فلسطين ج(2) ص4", "(8) خالد العظم"])

    tmp = Path("out/tests/notes")
    tmp.mkdir(parents=True, exist_ok=True)

    print("\na reference with no note stays raised, without brackets")
    m = Doc(pages=1, body_size=12.0)
    m.blocks = [Block(kind=PARAGRAPH, page=0, y=100, y1=120,
                      text=f"قال شاتليه{raised('13')} في كتابه")]
    out = tmp / "orphan.docx"
    write(m, str(out))
    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
    check("no (13) in the text", "(13)" in xml, False)
    check("digits written raised",
          bool(re.search(r'<w:vertAlign w:val="superscript"/>.*?<w:t[^>]*>13<', xml,
                         re.S)), True)
    check("no private marker left", MARK_OPEN in xml or MARK_CLOSE in xml, False)

    print("\nendnotes: notes at the end, cited earlier")
    m = Doc(pages=4, body_size=12.0)
    m.blocks = [
        Block(kind=PARAGRAPH, page=0, y=100, y1=120,
              text=f"الأول{raised('1')} والثاني{raised('2')}"),
        Block(kind=PARAGRAPH, page=1, y=100, y1=120, text=f"والثالث{raised('3')}"),
        Block(kind=PARAGRAPH, page=2, y=40, y1=50, text="2016 - 26 -"),
        Block(kind=FOOTNOTE, page=2, y=100, y1=120, text="(1) المرجع الأول"),
        Block(kind=FOOTNOTE, page=2, y=130, y1=150, text="(2) المرجع الثاني"),
        Block(kind=FOOTNOTE, page=3, y=100, y1=120, text="(3) المرجع الثالث"),
        Block(kind=PARAGRAPH, page=3, y=300, y1=320,
              text="قائمة المراجع: شاتليه، الغارة على العالم الإسلامي، ترجمة "
                   "محب الدين الخطيب، الطبعة الثانية، جدة"),
    ]
    out = tmp / "endnotes.docx"
    write(m, str(out))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        doc = z.read("word/document.xml").decode("utf-8")
        ends = z.read("word/endnotes.xml").decode("utf-8") \
            if "word/endnotes.xml" in names else ""
        ctypes = z.read("[Content_Types].xml").decode("utf-8")
    check("word/endnotes.xml present", "word/endnotes.xml" in names, True)
    check("content type declared", "endnotes+xml" in ctypes, True)
    check("three endnotes", len(re.findall(r'<w:endnote w:id="\d+">', ends)), 3)
    check("three references", doc.count("w:endnoteReference"), 3)
    check("the scrap of a note-only page is kept", "2016" in doc, True)
    check("page emptied of notes is gone (3 breaks -> 2)",
          doc.count("w:pageBreakBefore"), 2)

    print("\nnot endnotes: a document with only one late note")
    m = Doc(pages=3, body_size=12.0)
    m.blocks = [
        Block(kind=PARAGRAPH, page=0, y=100, y1=120, text=f"1.{raised('1')} مقدمة"),
        Block(kind=PARAGRAPH, page=2, y=100, y1=120, text="نص الصفحة"),
        Block(kind=FOOTNOTE, page=2, y=700, y1=712, text="(1) حاشية بلا إحالة"),
    ]
    out = tmp / "not-endnotes.docx"
    write(m, str(out))
    names = zipfile.ZipFile(out).namelist()
    check("no endnotes part", "word/endnotes.xml" in names, False)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
