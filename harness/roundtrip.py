#!/usr/bin/env python3
"""The checker.

  original.pdf --convert--> .docx --LibreOffice--> rebuilt.pdf
                                                        |
                          compare against original <----+

Gives two numbers per file:
  text  how much of the wording survived, in order
  ink   how much the rebuilt page still looks like the original

    python -m harness.roundtrip corpus/*.pdf
"""
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.compare import compare
from convert.v0 import convert as convert_v0
from convert.v1 import convert as convert_v1
from convert.fit import convert as convert_fit

SOFFICE = "/opt/libreoffice26.8/program/soffice"
BOLD, DIM, GRN, YEL, RED, OFF = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def docx_to_pdf(docx, outdir):
    """LibreOffice, headless, with a throwaway profile so runs don't collide."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        r = subprocess.run(
            [SOFFICE, "--headless", "--norestore",
             f"-env:UserInstallation=file://{profile}",
             "--convert-to", "pdf", "--outdir", str(outdir), str(docx)],
            capture_output=True, text=True, timeout=300)
    pdf = outdir / (Path(docx).stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError((r.stderr or r.stdout).strip()[:200] or "no pdf produced")
    return pdf


def colour(v):
    return GRN if v >= 0.8 else (YEL if v >= 0.5 else RED)


def run_one(pdf, workdir, converter=convert_fit):
    stem = Path(pdf).stem[:40]
    docx = Path(workdir) / "docx" / f"{stem}.docx"
    render = lambda d: docx_to_pdf(d, Path(workdir) / "pdf")
    route = converter(pdf, docx, render=render) if converter is convert_fit \
        else converter(pdf, docx)
    rebuilt = docx_to_pdf(docx, Path(workdir) / "pdf")
    res = compare(pdf, rebuilt, docx=docx)
    res.update(file=Path(pdf).name, route=route,
               docx=str(docx), rebuilt=str(rebuilt))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--work", default="out/roundtrip")
    ap.add_argument("--json", default="out/roundtrip.json")
    a = ap.parse_args()

    if not Path(SOFFICE).exists():
        sys.exit(f"LibreOffice not found at {SOFFICE}")

    rows = []
    print(f"{DIM}{'file':<42}{'text':>7}{'pages@':>8}{'look':>7}{'pages':>10}{'words':>14}{OFF}")
    for pdf in a.pdfs:
        try:
            r = run_one(pdf, a.work)
        except Exception as e:
            print(f"{Path(pdf).name[:40]:<42} {RED}FAILED{OFF} {type(e).__name__}: {e}"[:150])
            continue
        rows.append(r)
        t, pa, i = r["text_score"], r["page_score"], r["ink_score"]
        print(f"{r['file'][:40]:<42}"
              f"{colour(t)}{t:>7.1%}{OFF}{colour(pa)}{pa:>8.1%}{OFF}{DIM}{i:>7.1%}{OFF}"
              f"{r['pages_orig']:>5}->{r['pages_out']:<4}"
              f"{r['words_orig']:>7,}->{r['words_out']:<7,}")

    if rows:
        at = sum(r["text_score"] for r in rows) / len(rows)
        aa = sum(r["page_score"] for r in rows) / len(rows)
        print(f"\n{BOLD}average over {len(rows)} files — "
              f"text {colour(at)}{at:.1%}{OFF}{BOLD}, "
              f"right page {colour(aa)}{aa:.1%}{OFF}")
        print(f"{DIM}  text   = words survived, in order (read from the .docx){OFF}")
        print(f"{DIM}  pages@ = words landed on the matching page (unrelated docs score ~13%){OFF}")
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        print(f"{DIM}json -> {a.json}{OFF}")


if __name__ == "__main__":
    main()
