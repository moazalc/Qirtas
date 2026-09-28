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


def _look(tmp):
    from convert.footnotes import build_xml, _add_settings
    from convert.reader import _split_notes, MARK_OPEN, MARK_CLOSE

    # Word's own 2-inch line, at the right: its separator, set right to left.
    xml = build_xml([(2, "نص")], rule=(144, "right", 4, "000000"), width=430)
    sep = re.search(r'<w:footnote w:type="separator".*?</w:footnote>', xml).group(0)
    check("2-inch line: Word's own", "<w:separator/>" in sep, True)
    check("2-inch line: at the right", "<w:bidi/>" in sep, True)
    # Longer: an empty paragraph's edge, cut from the far end.
    xml = build_xml([(2, "نص")], rule=(288, "right", 2, "808080"), width=430)
    sep = re.search(r'<w:footnote w:type="separator".*?</w:footnote>', xml).group(0)
    check("288pt line: drawn as an edge", '<w:bottom w:val="single" w:sz="2"' in sep, True)
    check("288pt line: its colour", 'w:color="808080"' in sep, True)
    check("288pt line: shortened by 142pt", 'w:right="2840"' in sep, True)
    # At the left, as `z14065750` has it.
    xml = build_xml([(2, "نص")], rule=(144, "left", 4, "000000"), width=430)
    sep = re.search(r'<w:footnote w:type="separator".*?</w:footnote>', xml).group(0)
    check("line at the left: no bidi", "<w:bidi/>" in sep, False)
    # The notes' own distance between lines.
    xml = build_xml([(2, "نص")], pitch=15.6, rule=())
    check("line height exact", 'w:line="312" w:lineRule="exact"' in xml, True)
    # Bold words inside a note.
    xml = build_xml([(2, [("انظر ", False, False), ("صحيح البخاري", True, False)])])
    check("a bold word in a note", bool(re.search(
        r"<w:b/><w:bCs/>.*?صحيح البخاري", xml)), True)
    check("the rest not bold", bool(re.search(
        r"<w:b/><w:bCs/>[^/]*?انظر", xml)), False)
    # Word draws its own separator unless settings.xml points at ours.
    s = _add_settings('<w:settings><w:zoom/><w:compat/></w:settings>')
    check("settings point at the separators", s ==
          '<w:settings><w:zoom/><w:footnotePr><w:footnote w:id="0"/>'
          '<w:footnote w:id="1"/></w:footnotePr><w:compat/></w:settings>', True)

    # A page's notes read as one piece keep their bold words when split.
    one = Block(kind=FOOTNOTE, page=0,
                text=f"{MARK_OPEN}1{MARK_CLOSE} سورة البقرة: 2. "
                     f"{MARK_OPEN}2{MARK_CLOSE} انظر صحيح مسلم.",
                spans=[(f"{MARK_OPEN}1{MARK_CLOSE}", False, False),
                       ("سورة البقرة:", True, False), ("2.", False, False),
                       (f"{MARK_OPEN}2{MARK_CLOSE} انظر", False, False),
                       ("صحيح مسلم.", True, False)])
    got = _split_notes(one)
    check("split into two notes", [b.text for b in got],
          ["(1) سورة البقرة: 2.", "(2) انظر صحيح مسلم."])
    check("note 1 keeps its bold", got[0].spans,
          [("(1)", False, False), ("سورة البقرة:", True, False), ("2.", False, False)])
    check("note 2 keeps its bold", got[1].spans,
          [("(2) انظر", False, False), ("صحيح مسلم.", True, False)])

    # And through the writer: the pieces reach footnotes.xml.
    m = Doc(pages=1, body_size=12.0)
    m.blocks = [Block(kind=PARAGRAPH, text="قال تعالى(1) خبرا.", page=0, y=100, y1=120)] + got[:1]
    m.note_rule, m.note_pitch = (288, "right", 2, "000000"), 15.0
    out = tmp / "look.docx"
    write(m, str(out))
    with zipfile.ZipFile(out) as z:
        notes = z.read("word/footnotes.xml").decode("utf-8")
        settings = z.read("word/settings.xml").decode("utf-8")
    check("written: bold sura name", bool(re.search(
        r"<w:b/><w:bCs/>[^>]*>(?:<[^>]*>)*?[^<]*سورة البقرة", notes)), True)
    check("written: line 288pt", "w:pBdr" in notes, True)
    check("written: settings point at it", "<w:footnotePr><w:footnote w:id=\"0\"/>" in settings, True)


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

    print("\nthe notes look as the original set them (QIRTAS_NOTE_LOOK)")
    _look(tmp)

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
