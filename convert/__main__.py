#!/usr/bin/env python3
"""Convert one PDF to Word - the command a person runs.

    python -m convert thesis.pdf                 # writes thesis.docx beside it
    python -m convert thesis.pdf out.docx
    python -m convert thesis.pdf --no-wait       # do not stop to ask

Before converting it says which of the PDF's fonts this computer lacks, and
where to get them, and waits while they are installed (convert/fonts.py,
Moaz 2026-09-23). A scan is refused with a plain message (convert/scan.py).
The conversion itself is convert/fit.py with Word checking which pages ran
over - the same path every score in this project is measured on.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from convert import fonts
from convert.scan import Refused, refuse_scans

ANYWAY = {"go", "g", "skip", "s", "no", "n"}


def _ask_fonts(pdf, wait):
    """Tell the person which fonts are missing; wait while they install them.
    Returns when every font is there, or they chose to go on without: the
    fonts still missing."""
    while True:
        found = fonts.missing(pdf)
        if not found:
            return []
        # Which of them will come out as wrong text (FLAGS 23): Windows' OCR
        # reads the pages they are used on.
        fonts.judge(pdf, found)
        print(fonts.message(found))
        # Only a style missing (Word imitates a bold) is not worth stopping for.
        if not wait or all(m.only_style for m in found):
            print("\nConverting without them.\n")
            return found
        print()
        try:
            answer = input("Install them now and press Enter to check again - "
                           "or type 'go' to convert without them: ").strip().lower()
        except EOFError:        # nobody there to answer (Windows' NUL looks like a console)
            print("\nConverting without them.\n")
            return found
        if answer in ANYWAY:
            print()
            return found
        # They may have installed some: forget what was installed and look again.
        fonts.rescan()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m convert",
                                 description="Convert an Arabic PDF to an editable Word file.")
    ap.add_argument("pdf")
    ap.add_argument("docx", nargs="?", help="where to write it (default: beside the PDF)")
    ap.add_argument("--no-wait", action="store_true",
                    help="say which fonts are missing, but do not stop to ask")
    a = ap.parse_args(argv)

    pdf = Path(a.pdf)
    if not pdf.exists():
        sys.exit(f"No such file: {pdf}")
    docx = Path(a.docx) if a.docx else pdf.with_suffix(".docx")

    try:
        refuse_scans(str(pdf))
    except Refused as e:
        sys.exit(str(e))

    left = _ask_fonts(pdf, wait=not a.no_wait and sys.stdin.isatty())

    print(f"Converting {pdf.name} - Word checks the pages as it goes, which takes "
          f"a minute or two for a long file ...")
    from convert.fit import convert
    from harness.word import docx_to_pdf
    import shutil
    import tempfile
    # Word's renders of each attempt, looked at and thrown away. Word itself
    # is closed on exit (harness.word).
    # The pictures are taken out into media/<name> beside the Word file and
    # embedded in it; that folder goes afterwards - only if this run made it.
    media = docx.parent / "media"
    made = [p for p in (media, media / docx.stem) if not p.exists()]
    with tempfile.TemporaryDirectory(prefix="qirtas-pages-") as work:
        convert(str(pdf), str(docx), render=lambda d: docx_to_pdf(d, work))
    for p in reversed(made):
        shutil.rmtree(p, ignore_errors=True) if p == media / docx.stem else \
            (p.rmdir() if p.exists() and not any(p.iterdir()) else None)
    print(f"Done: {docx}")
    # Said again at the end, where it is read: the text in these came out
    # wrong in the Word file just made.
    for m in left:
        if m.wrong:
            print(f"Note: the text in {m.name}{' ' + m.style if m.style else ''}"
                  f"{fonts._pages(m.pages)} came out wrong. Install that font "
                  f"and convert again.")


if __name__ == "__main__":
    main()
