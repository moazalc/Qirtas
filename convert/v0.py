"""v0 converter: the simplest thing that could work.

Pulls the text out, writes it into a right-to-left Word file. No headings, no
tables, no footnotes, no images. This exists to give the checker something to
score, and to be the baseline every later version must beat.
"""
import sys
from pathlib import Path

import pymupdf
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Emu

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.routes import run_route
from harness.metrics import score

PT_PER_EMU = 12700
ARABIC_FONT = "Arial"


def _flag(el, tag):
    """Add a <w:tag w:val="1"/> switch."""
    e = OxmlElement(tag)
    e.set(qn("w:val"), "1")
    el.append(e)


def rtl_paragraph(p):
    _flag(p._p.get_or_add_pPr(), "w:bidi")


def rtl_run(run, font=ARABIC_FONT, size=12):
    rPr = run._r.get_or_add_rPr()
    _flag(rPr, "w:rtl")
    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:cs"), font)          # complex-script font = the Arabic one
    fonts.set(qn("w:ascii"), font)
    fonts.set(qn("w:hAnsi"), font)
    rPr.append(fonts)
    szcs = OxmlElement("w:szCs")         # complex-script size
    szcs.set(qn("w:val"), str(int(size * 2)))
    rPr.append(szcs)


def best_text(pdf_path):
    """Run both routes, keep whichever recovers more Arabic. Measure, don't predict."""
    results = {}
    for name in ("pymupdf.text", "structtree.actualtext"):
        text, err = run_route(name, pdf_path)
        results[name] = (text, score(text)["arabic"])
    winner = max(results, key=lambda k: results[k][1])
    return results[winner][0], winner


def page_setup(doc, pdf_path):
    """Match the original page size so the comparison is fair."""
    with pymupdf.open(pdf_path) as d:
        r = d[0].rect
    s = doc.sections[0]
    s.page_width = Emu(int(r.width * PT_PER_EMU))
    s.page_height = Emu(int(r.height * PT_PER_EMU))
    for m in ("left_margin", "right_margin"):
        setattr(s, m, Emu(int(72 * PT_PER_EMU)))
    for m in ("top_margin", "bottom_margin"):
        setattr(s, m, Emu(int(72 * PT_PER_EMU)))
    # make the whole section right-to-left
    _flag(s._sectPr, "w:bidi")


def convert(pdf_path, out_path, size=12):
    text, route = best_text(str(pdf_path))
    doc = Document()
    page_setup(doc, pdf_path)

    for block in [b.strip() for b in text.split("\n") if b.strip()]:
        p = doc.add_paragraph()
        rtl_paragraph(p)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(block)
        run.font.size = Pt(size)
        rtl_run(run, size=size)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return route


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    print("route:", convert(src, dst), "->", dst)
