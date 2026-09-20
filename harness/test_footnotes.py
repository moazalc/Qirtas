#!/usr/bin/env python3
"""Tests for real Word footnotes.

    python -m harness.test_footnotes

Footnotes used to be ordinary paragraphs sitting at the foot of the page under
a drawn rule. They looked right and were not footnotes: Word could not renumber
them, moving text did not move them, and deleting the sentence they belonged to
left them behind.

The corpus gives us what we need to place them properly. A footnote carries its
own number ("1- انظر..." or "(1) انظر..."), and the body text carries the
matching marker inline ("عمر بن الخطاب(3)"). 374 of 399 footnotes in the corpus
can be anchored that way. The rest keep the old behaviour.
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docx import Document

from convert.model import Doc, Block, PARAGRAPH, FOOTNOTE
from convert.writer import write

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<50} got {got!r}")
    if not ok:
        FAILED.append(name)


def _build(tmp):
    """A page with two anchored notes and one whose marker is nowhere."""
    m = Doc(pages=1, body_size=12.0)
    m.blocks = [
        Block(kind=PARAGRAPH, text="قال عمر بن الخطاب(1) ثم روى هشام(2) خبرا.",
              page=0, y=100, y1=120),
        Block(kind=FOOTNOTE, text="1- أخرجه البخاري في صحيحه.", page=0, y=700, y1=712),
        Block(kind=FOOTNOTE, text="2- انظر: منجد المقرئين (ص: 18).", page=0, y=714, y1=726),
        Block(kind=FOOTNOTE, text="9- لا يوجد له مرجع في المتن.", page=0, y=728, y1=740),
    ]
    out = tmp / "fn.docx"
    write(m, str(out))
    return out


def main():
    tmp = Path("out/tests/footnotes")
    tmp.mkdir(parents=True, exist_ok=True)
    docx = _build(tmp)

    with zipfile.ZipFile(docx) as z:
        names = z.namelist()
        body = z.read("word/document.xml").decode("utf-8")
        ctypes = z.read("[Content_Types].xml").decode("utf-8")
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
        notes = z.read("word/footnotes.xml").decode("utf-8") \
            if "word/footnotes.xml" in names else ""

    print("the file must carry a real footnotes part, wired up")
    check("word/footnotes.xml present", "word/footnotes.xml" in names, True)
    check("content type declared", "footnotes+xml" in ctypes, True)
    check("relationship from document", "footnotes.xml" in rels, True)

    print("\nWord needs its two separator notes before any real one")
    check("separator", 'w:type="separator"' in notes, True)
    check("continuationSeparator", 'w:type="continuationSeparator"' in notes, True)
    ids = re.findall(r'<w:footnote [^>]*w:id="(-?\d+)"', notes)
    check("ids in order", ids[:4], ["0", "1", "2", "3"])

    print("\nanchored notes become references in the body")
    refs = re.findall(r'<w:footnoteReference w:id="(\d+)"/>', body)
    check("two references written", refs, ["2", "3"])
    check("marker (1) removed from body text", "(1)" in body, False)
    check("marker (2) removed from body text", "(2)" in body, False)
    check("note text moved out of the body", "أخرجه البخاري" in body, False)
    check("note text is in footnotes.xml", "أخرجه البخاري" in notes, True)
    check("leading number stripped from the note", "1-" in notes, False)

    print("\nan unanchored note keeps the old behaviour")
    check("stays in the body", "لا يوجد له مرجع" in body, True)
    check("not written as a footnote", "لا يوجد له مرجع" in notes, False)

    print("\nthe result must still be a valid Word file")
    try:
        Document(str(docx))
        check("python-docx reopens it", True, True)
    except Exception as e:
        check("python-docx reopens it", f"{type(e).__name__}: {e}", True)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
