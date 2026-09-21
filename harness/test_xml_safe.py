#!/usr/bin/env python3
"""Tests for text a PDF carries that XML will not accept.

    python -m harness.test_xml_safe

Three wild files crashed the whole conversion with

    ValueError: All strings must be XML compatible: Unicode or ASCII,
                no NULL bytes or control characters

python-docx hands run text straight to lxml, and lxml enforces the XML 1.0
Char production: of the C0 controls only tab, newline and carriage return are
legal. A PDF text layer can easily carry others - z21889411.pdf has 25 NUL
bytes in it and z20414780.pdf has 14 backspaces - and one of them anywhere in
a 400-page document destroys the entire output rather than the one run that
holds it.

The loss was worse than it sounds because `eval.py` catches the exception per
file, so a crashing document silently left the sample and the reported average
was quietly taken over the files that survived.

What this does NOT do is rescue a document whose text layer is not text at
all. z22244578.pdf extracts as raw glyph indices because its fonts carry no
usable ToUnicode map, and 117 of its 131 pages are more than 2% control
characters. Stripping those would not recover the document, it would only stop
the crash and let nonsense into the corpus, where it would score against an
equally nonsensical round-trip and flatter the average. That file is excluded
as unusable instead, which is a statement about the source, not a fix.
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.model import Doc, Block, PARAGRAPH, HEADING, FOOTNOTE, TABLE
from convert.writer import write, _xml_safe
from harness.compare import text_of_docx

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}  want {want!r}")
    if not ok:
        FAILED.append(name)


ARABIC = "المعرض بوصفه"


def _written(model, tmp, stem):
    """write() the model and read the text back out of the .docx.

    The stem is prefixed because Windows still resolves the DOS device names -
    nul, con, aux, prn, com1..9, lpt1..9 - ahead of any file of that name, in
    any directory and whatever the extension. `nul.docx` IS the null device
    there: every byte written is discarded, the path reports 0 bytes, and
    nothing raises. This test named a case after the character it tests, so on
    Windows it read back an empty file and reported the writer as the fault.
    """
    out = Path(tmp) / f"case_{stem}.docx"
    write(model, str(out))
    return text_of_docx(str(out))


def main():
    tmp = Path("out/tests/xml_safe")
    tmp.mkdir(parents=True, exist_ok=True)

    print("a NUL in paragraph text must not destroy the document")
    m = Doc(blocks=[Block(kind=PARAGRAPH, text=f"{ARABIC}\x00 بعد", page=0)])
    try:
        got = _written(m, tmp, "nul")
        check("wrote without raising", True, True)
        check("the NUL is gone", "\x00" in got, False)
        check("the Arabic survived", ARABIC in got, True)
    except Exception as e:
        check(f"wrote without raising ({type(e).__name__})", False, True)

    print("\nand neither must a backspace, in any of the places text lives")
    cases = {
        "paragraph": Block(kind=PARAGRAPH, text=f"{ARABIC}\x08x"),
        "heading": Block(kind=HEADING, text=f"{ARABIC}\x08x", level=1),
        "footnote": Block(kind=FOOTNOTE, text=f"{ARABIC}\x08x"),
        "spans": Block(kind=PARAGRAPH, text=f"{ARABIC}x",
                       spans=[(f"{ARABIC}\x08", True, False), ("x", False, False)]),
        "table cell": Block(kind=TABLE, text="", rows=[[f"{ARABIC}\x08x", "b"]]),
    }
    for label, block in cases.items():
        try:
            got = _written(Doc(blocks=[block]), tmp, label.replace(" ", "_"))
            check(f"{label}: no control character survives",
                  any(ord(c) < 0x20 and c not in "\t\n\r" for c in got), False)
        except Exception as e:
            check(f"{label}: wrote without raising ({type(e).__name__}: {e})"[:70],
                  False, True)

    print("\nthe three legal control characters must be left alone")
    # Checked in the file rather than through text_of_docx: python-docx turns a
    # tab into a <w:tab/> ELEMENT, which is the correct OOXML for one, and
    # text_of_docx does not turn that back into a character. Asserting on the
    # round-trip would be asserting on the reader, not on the writer.
    check("_xml_safe keeps tab, newline and return",
          _xml_safe("a\tb\nc\rd"), "a\tb\nc\rd")
    m = Doc(blocks=[Block(kind=PARAGRAPH, text="a\tb")])
    write(m, str(Path(tmp) / "tab.docx"))
    raw = zipfile.ZipFile(Path(tmp) / "tab.docx").read("word/document.xml").decode()
    check("a tab reaches the document as <w:tab/>", "<w:tab/>" in raw, True)

    print("\nand text that is not text at all is refused, not laundered")
    # 5% control characters across 27 codepoints is a ToUnicode failure, not
    # debris. _xml_safe would happily strip it and hand back fluent-looking
    # nonsense, so the judgement has to happen before here - in the split.
    junk = "".join(chr(c) for c in (0x0E, 0x1D, 0x04, 0x05, 0x0F)) * 40
    check("stripping junk leaves nothing meaningful", _xml_safe(junk), "")

    print("\nand ordinary text must come through untouched")
    m = Doc(blocks=[Block(kind=PARAGRAPH, text=ARABIC)])
    check("Arabic unchanged", ARABIC in _written(m, tmp, "clean"), True)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
