# Qirtas  ·  قرطاس

Arabic PDF back to editable Word - with the right-to-left parts actually
correct, which no free tool and not Acrobat currently manage.

## setup

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Also needed:
- **LibreOffice** - used only to render our .docx back to PDF for checking.
  On this machine: `/opt/libreoffice26.8/program/soffice` (adjust `SOFFICE` in
  `harness/roundtrip.py` if it lives elsewhere).
- **Arabic fonts** - these PDFs ask for Simplified Arabic, Traditional Arabic
  and Sakkal Majalla, which are Windows fonts. Without substitutes LibreOffice
  falls back to a wider face, text overflows, and the converter gets blamed.
  See `docs/fonts.md`.

## corpus

Not committed. `corpus/*.pdf` are unpublished thesis chapters; `corpus/wild/`
is ~600MB of open-access PDFs that rebuild with:

    .venv/bin/python -m harness.fetch_corpus --n 120 --out corpus/wild
    .venv/bin/python -m harness.split corpus/wild/*.pdf --write out/split.json


Converting Arabic PDFs (mostly Word exports) back to editable .docx.
Currently at the **diagnostic** stage — no converter yet.

## harness

Runs every known extraction route against every PDF and reports which one
actually recovers the text. No ground-truth .docx required.

    .venv/bin/python -m harness.run corpus/*.pdf --json out/report.json --dump out/text

- `harness/probe.py`   structural facts: producer, tags, ActualText count, fonts
- `harness/routes.py`  10 extraction routes (pymupdf ×4, pdfminer, pypdf,
                       poppler ×2, qalam, our own struct-tree walk)
- `harness/metrics.py` scoring: Arabic chars, glyph-corruption, PUA junk

`--dump` writes each route's output so you can read what a route actually saw.

## findings

**Two layers hold the text, and which one works varies per file.**

Our 6 sample files: glyph extraction recovers 0–8%; the text lives in
`/ActualText` on `/Span` elements in the tagged structure tree.

Wild corpus (88 Arabic PDFs from Zenodo): glyph extraction works on
**88/88**. Zero need the tag layer.

Two theories for what triggers the difference were tested and **both failed**:
- *Word version* — no. Wild Word 2010 files extract fine; Word 2016/2019
  files sometimes carry ActualText.
- *Undecodable font signature* (no ToUnicode + WinAnsi/non-embedded) — no.
  30/40 wild files carry such fonts and still extract fine, because there the
  bad font carries Latin digits, not the Arabic body.

Conclusion: **don't predict which route works — measure it per file.** Run
both and keep the better result. `harness/run.py` already does this.

Corpus caveat: Zenodo is academic publishing and may be better-produced than
the ordinary documents this tool targets.

## survey

    .venv/bin/python -m harness.survey corpus/wild/*.pdf --json out/survey.json
    .venv/bin/python -m harness.fetch_corpus --n 100 --out corpus/wild

## corpus

6 × Word 2010 Arabic academic chapters, 1 × Canva Arabic poster,
1 × LibreOffice Turkish doc (LTR control). Needs more Word versions.

## notes

- LibreOffice lives at `/opt/libreoffice26.8/program/soffice` (not on PATH)
- qalam is in a separate venv at `~/.venvs/qalam` (Python 3.14)

## the checker (round-trip)

    .venv/bin/python -m harness.roundtrip corpus/*.pdf

Converts PDF -> .docx -> PDF (LibreOffice) and compares against the original.
No ground-truth .docx needed.

- `text_score` how much wording survived, in order (font-independent)
- `ink_score`  how much the page still looks the same (catches layout loss)

Sanity checked: a PDF against itself scores 1.00 / 1.00; against an unrelated
PDF, 0.02 / 0.07.

### v0 baseline (text dump into an RTL docx, no structure)

    average over 8 files - text 58.3%, ink 2.0%

Known causes of the low ink score: every extracted line becomes its own
paragraph, so page counts explode (20pp -> 201pp) and word counts inflate ~15%
from split fragments. No headings, bold, footnotes, tables or images yet.

Caveat: rebuilt PDFs are rendered by LibreOffice, which lays out Arabic a little
differently than Word. Treat both scores as a progress meter, not a grade.
