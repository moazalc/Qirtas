#!/usr/bin/env python3
"""Tests for bold and italic inside a paragraph.

    python -m harness.test_inline

Only whole-block boldness used to be carried: _page_rich OR-ed every span's
bold flag into one value for the block and threw the span boundaries away, so a
paragraph containing one bold phrase came out entirely bold, and italics were
not read at all.
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf
from convert.reader import read
from convert.v1 import convert as convert_v1

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<46} got {got!r}")
    if not ok:
        FAILED.append(name)


def _fixture(path):
    """One line: plain text, a bold word, an italic word, plain text again."""
    d = pymupdf.open()
    p = d.new_page(width=400, height=200)
    x = 40
    for text, font in (("plain ", "helv"), ("BOLDWORD ", "hebo"),
                       ("italicword ", "heit"), ("tail", "helv")):
        p.insert_text((x, 60), text, fontname=font, fontsize=12)
        x += len(text) * 6.7
    d.save(path)
    d.close()


def _runs(docx):
    """[(text, bold, italic)] for every run in the document, in order."""
    with zipfile.ZipFile(docx) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    def on(r, tag):
        # python-docx writes an explicit <w:b w:val="0"/> for False, so the
        # presence of the tag says nothing - the value has to be read.
        m = re.search(rf'<w:{tag}(?:/>| [^>]*>)', r)
        if not m:
            return False
        v = re.search(r'w:val="([^"]*)"', m.group(0))
        return v.group(1) not in ("0", "false") if v else True

    out = []
    for m in re.finditer(r"<w:r>(.*?)</w:r>", xml, re.S):
        r = m.group(1)
        t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", r))
        if not t.strip():
            continue
        out.append((t.strip(), on(r, "b"), on(r, "i")))
    return out


def main():
    tmp = Path("out/_test_inline")
    tmp.mkdir(parents=True, exist_ok=True)
    pdf, docx = tmp / "inline.pdf", tmp / "inline.docx"
    _fixture(str(pdf))

    print("the reader must keep each span's own formatting")
    doc = read(str(pdf))
    spans = [s for b in doc.blocks for s in b.spans]
    check("spans kept", len(spans) >= 4, True)
    fmt = {t.strip(): (bo, it) for t, bo, it in spans}
    check("BOLDWORD is bold", fmt.get("BOLDWORD"), (True, False))
    check("italicword is italic", fmt.get("italicword"), (False, True))
    check("plain is neither", fmt.get("plain"), (False, False))
    check("text still assembled whole",
          " ".join(t.strip() for t, _, _ in spans),
          "plain BOLDWORD italicword tail")

    print("\nthe writer must not spread one span's formatting over the rest")
    convert_v1(str(pdf), str(docx))
    runs = _runs(docx)
    got = {t: (b, i) for t, b, i in runs}
    check("BOLDWORD written bold", got.get("BOLDWORD"), (True, False))
    check("italicword written italic", got.get("italicword"), (False, True))
    check("plain written unformatted", got.get("plain"), (False, False))
    check("tail written unformatted", got.get("tail"), (False, False))

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
