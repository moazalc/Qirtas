#!/usr/bin/env python3
"""Render a .docx to PDF with real Microsoft Word, not LibreOffice.

    from harness.word import docx_to_pdf          # same signature as roundtrip's
    python -m harness.word some.docx --outdir out/work/pdf

Why this exists, in the words of the two things it is meant to settle:

  FLAGS.md 6  we may be shrinking text to fix overflow that does not exist.
              `convert/fit.py` detects spill by rendering through LibreOffice,
              which lacks Simplified Arabic, Traditional Arabic and Sakkal
              Majalla and substitutes wider faces. If the spill is the
              substitute's, every shrink is making the document worse for the
              reader in order to make a number better.

  TASKS.md C2 render in Word rather than LibreOffice for a trustworthy check.
              Word is what a reader actually opens the file in, so it is the
              ground truth this project has been approximating all along.

**A score from this renderer is NOT comparable to a score from LibreOffice**,
and mixing the two silently is the corpus-drift and font-drift failure
(`PLAN.md` caveats 7 and 11) in a third place. `harness.env` reports which
renderer produced a run; keep them apart.

Windows only, and needs Word installed. `pywin32` carries an environment marker
in requirements.txt so a Linux checkout still installs.
"""
import argparse
import atexit
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Word's own enum values. Spelled out rather than imported, because the
# constants module only exists after a makepy run and we do not want to depend
# on one having happened.
WD_EXPORT_PDF = 17
WD_EXPORT_DOC = 0            # the whole document, not a selection
MSO_SECURITY_FORCE_DISABLE = 3

_WORD = None


def _word():
    """One Word instance per process, started once and reused.

    Starting Word costs a couple of seconds, and `fit.py` renders the same
    document up to five times, so a fresh instance per call would pay that on
    every round. This is the same reasoning as roundtrip's `_profile()`, for
    the same reason.

    The instance is OURS: it is created here rather than attached to a running
    Word, so quitting it at exit cannot close a document the user had open.
    """
    global _WORD
    if _WORD is None:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        app = win32com.client.DispatchEx("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        # Anything we open came out of a PDF we did not write. Word will not
        # run macros from it, and will not ask the user about them either.
        app.AutomationSecurity = MSO_SECURITY_FORCE_DISABLE
        _WORD = app
        atexit.register(_quit)
    return _WORD


def _quit():
    global _WORD
    if _WORD is not None:
        try:
            _WORD.Quit(SaveChanges=0)
        except Exception:
            pass
        _WORD = None


def docx_to_pdf(docx, outdir):
    """Render with Word. Same signature and return as roundtrip.docx_to_pdf."""
    docx = Path(docx).resolve()
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    pdf = (outdir / (docx.stem + ".pdf")).resolve()

    # Word refuses to export onto a file it already has open, and a stale PDF
    # left behind by a failed run would otherwise read as a success.
    if pdf.exists():
        pdf.unlink()

    app = _word()
    doc = app.Documents.Open(
        str(docx),
        ConfirmConversions=False,
        ReadOnly=True,
        AddToRecentFiles=False,
        Visible=False,
    )
    try:
        # Repaginate before exporting. Word lays out lazily, and a PAGE field
        # or a page count read before this can be the pre-layout one - which
        # would make every page-alignment score measure Word's laziness.
        doc.Repaginate()
        doc.ExportAsFixedFormat(
            OutputFileName=str(pdf),
            ExportFormat=WD_EXPORT_PDF,
            OpenAfterExport=False,
            Range=WD_EXPORT_DOC,
            BitmapMissingFonts=False,
        )
    finally:
        doc.Close(SaveChanges=0)

    if not pdf.exists():
        raise RuntimeError(f"Word produced no pdf for {docx.name}")
    return pdf


def available():
    """Can this machine render with Word? -> (bool, detail)"""
    if sys.platform != "win32":
        return False, f"not Windows ({sys.platform})"
    try:
        return True, "Word " + str(_word().Version)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("docx", nargs="*")
    ap.add_argument("--outdir", default="out/work/pdf")
    a = ap.parse_args()

    ok, detail = available()
    print(f"Word renderer: {'available' if ok else 'UNAVAILABLE'} - {detail}")
    if not ok:
        raise SystemExit(1)

    for d in a.docx:
        out = docx_to_pdf(d, a.outdir)
        print(f"  {Path(d).name} -> {out}  ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
