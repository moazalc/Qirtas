#!/usr/bin/env python3
"""Structural survey across a whole corpus: who produced these PDFs, are they
tagged, and does the text depend on the accessibility layer?

Answers the go/no-go question: is the ActualText finding general, or a quirk
of one Word version?

    python -m harness.survey corpus/wild/*.pdf --json out/survey.json
"""
import argparse, collections, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.probe import probe
from harness.routes import run_route
from harness.metrics import score

BOLD, DIM, GRN, YEL, RED, OFF = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"

# Collapse "Microsoft® Word 2010" / "Microsoft Word for Microsoft 365" -> family
def producer_family(p):
    s = (p or "").lower()
    for pat, name in [
        (r"microsoft.*word.*(\d{4})", None), (r"microsoft.*word", "MS Word (other)"),
        (r"libreoffice", "LibreOffice"), (r"openoffice", "OpenOffice"),
        (r"acrobat|adobe pdf", "Adobe"), (r"indesign", "InDesign"),
        (r"pdflatex|xetex|luatex|dvips|tex", "TeX"), (r"ghostscript", "Ghostscript"),
        (r"canva", "Canva"), (r"quartz|mac os", "macOS Quartz"),
        (r"skia|chrom", "Chrome/Skia"), (r"itext", "iText"),
        (r"pdfsharp|tcpdf|fpdf|reportlab|wkhtml", "library"),
        (r"scan|xerox|canon|epson|hp ", "scanner"),
    ]:
        m = re.search(pat, s)
        if m:
            if name is None:
                return f"MS Word {m.group(1)}"
            return name
    return (p or "—").strip()[:34] or "(empty)"


def classify(path):
    """One row of the survey."""
    p = probe(path)
    row = {k: p[k] for k in ("file", "pages", "producer", "lang", "tagged",
                             "tag_total", "tag_semantic", "actualtext_elements",
                             "has_headings")}
    row["family"] = producer_family(p["producer"])

    # Which layer holds the text? Compare glyph route against tag route.
    glyph, _ = run_route("pymupdf.dict", path)
    full,  _ = run_route("pymupdf.text", path)
    g, f = score(glyph)["arabic"], score(full)["arabic"]
    row["arabic_glyph"], row["arabic_full"] = g, f
    row["is_arabic"] = f >= 500                  # enough Arabic to judge
    if not row["is_arabic"]:
        row["verdict"] = "not-arabic"
    elif g >= 0.9 * f:
        row["verdict"] = "glyphs-ok"             # normal PDF, any tool works
    elif f > 0:
        row["verdict"] = "needs-tags"            # our case: text only in tag layer
    else:
        row["verdict"] = "no-text"               # scanned; needs OCR
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--json")
    a = ap.parse_args()

    rows, errs = [], 0
    for i, f in enumerate(a.pdfs, 1):
        try:
            rows.append(classify(f))
        except Exception as e:
            errs += 1
            continue
        if i % 10 == 0:
            print(f"{DIM}  ...{i}/{len(a.pdfs)}{OFF}", flush=True)

    ar = [r for r in rows if r["is_arabic"]]
    print(f"\n{BOLD}surveyed {len(rows)} PDFs{OFF} ({errs} unreadable) — "
          f"{len(ar)} with substantial Arabic\n")

    print(f"{BOLD}where the text lives (Arabic files only){OFF}")
    v = collections.Counter(r["verdict"] for r in ar)
    for k in ("glyphs-ok", "needs-tags", "no-text"):
        n = v.get(k, 0)
        pct = n / len(ar) * 100 if ar else 0
        col = GRN if k == "glyphs-ok" else (YEL if k == "needs-tags" else RED)
        print(f"  {col}{k:<12}{OFF} {n:>4}  {pct:>5.1f}%")

    print(f"\n{BOLD}producer × tagged (Arabic files){OFF}")
    fam = collections.Counter(r["family"] for r in ar)
    print(f"  {DIM}{'producer':<24}{'n':>5}{'tagged':>8}{'actualText':>12}{'headings':>10}{OFF}")
    for name, n in fam.most_common(14):
        sub = [r for r in ar if r["family"] == name]
        tg = sum(1 for r in sub if r["tagged"])
        at = sum(1 for r in sub if r["actualtext_elements"] > 0)
        hd = sum(1 for r in sub if r["has_headings"])
        print(f"  {name:<24}{n:>5}{tg:>8}{at:>12}{hd:>10}")

    tagged = [r for r in ar if r["tagged"]]
    print(f"\n{BOLD}summary{OFF}")
    print(f"  tagged:            {len(tagged):>4}/{len(ar)}  "
          f"({len(tagged)/len(ar)*100 if ar else 0:.0f}%)")
    print(f"  with real headings:{sum(1 for r in ar if r['has_headings']):>4}/{len(ar)}")
    print(f"  uses ActualText:   {sum(1 for r in ar if r['actualtext_elements']>0):>4}/{len(ar)}")

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n{DIM}json -> {a.json}{OFF}")


if __name__ == "__main__":
    main()
