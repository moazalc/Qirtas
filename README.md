# Qirtas  ·  قرطاس

Arabic PDF back to editable Word — with the right-to-left parts actually
correct, which no free tool and not Acrobat currently manage.

## where this is

Working converter. Last measured 2026-09-20 over the 102-file development set:

    nothing lost   100.0%   (hard gate; worst single file also 100.0%)
    words in order  79.4%
    right page      21.8%   (unrelated documents score ~13%, so that is the floor)

The holdout set was opened once, on 2026-09-19, and held: ordinary documents
scored 92.2% words / 29.4% right page on 61 unseen files, against 92.0% / 24.3%
on the development set. It generalises.

**Read `PLAN.md` before changing anything.** It carries the work list, what is
known broken, and ten measurement caveats — every one of which made the numbers
lie before it was found. `RESEARCH.md` carries the evidence behind them.

### the one decision waiting on you

**Text layers stored in visual order.** Some Arabic PDFs — typically LaTeX
output — store the character stream already reversed. We reproduce it
faithfully, Word reverses it again, and the output is unreadable. 56 of 172
usable corpus files (32.6%) are like this.

The scorer is structurally blind to it, because our reversed output is compared
against the same reversed source: `z21889411.pdf` scores 99.9% on text and
nobody can read a word of it. Detection is cheap and already prototyped. What to
*do* about it is the open question — reorder the text and risk mangling files
that are partly correct, or refuse them outright the way `z22244578.pdf` is
refused. Both change what this converter promises. See `PLAN.md`, "Known
unfinished".

## setup

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

**Use `.venv/bin/python` for everything.** The system Python does not have
pymupdf and will fail in ways that look like corpus problems.

Also needed:

- **LibreOffice** — used only to render our .docx back to PDF for checking, and
  never in the conversion itself. Path is `SOFFICE` in `harness/roundtrip.py`,
  currently `/snap/bin/libreoffice`. **Adjust this first on a new machine**; it
  is the single most likely thing to break a fresh checkout.
- **Arabic fonts** — these PDFs ask for Simplified Arabic, Traditional Arabic
  and Sakkal Majalla, which are Windows fonts. Without substitutes LibreOffice
  falls back to a wider face, text overflows, and the converter gets blamed for
  it. See `docs/fonts.md` and `docs/60-arabic-substitutes.conf`.

## corpus

Not committed, and not reconstructible from this repo alone. `corpus/*.pdf` are
unpublished thesis chapters (not ours to publish); `corpus/wild/` is ~600MB of
open-access PDFs from Zenodo, which rebuild with:

    .venv/bin/python -m harness.fetch_corpus --n 120 --out corpus/wild
    .venv/bin/python -m harness.split corpus/wild/*.pdf --write out/split.json

`out/` is gitignored too, so a fresh checkout has **no `out/split.json` and no
previous eval results**. Run the two commands above before anything else, or
`harness.eval` will have no file list to work from.

The split is by `sha256(filename) % 1000 < 400`, stratified by producer family,
so it is stable across machines: the same file lands in the same set here and in
the office. Previous scores remain comparable.

## running it

Convert one file:

    .venv/bin/python -m convert.v1 input.pdf out/output.docx

Score the converter (PDF → DOCX → LibreOffice → PDF → compare; no ground-truth
.docx needed):

    .venv/bin/python -m harness.eval --n 30          # sample of the tuning set
    .venv/bin/python -m harness.eval                 # the whole tuning set
    .venv/bin/python -m harness.eval --set regression  # the hard ActualText case

A full 102-file run takes roughly 25–35 minutes. It schedules longest-file-first,
so **the long files finish last** — progress through the file count is not
progress through the work, and estimating from early completions will be wrong.

    .venv/bin/python -m harness.eval --set holdout

The holdout exists to answer one question at the end — does this generalise, or
have I fitted the files I could see? It has been opened once. Opening it again
during development destroys the only safeguard there is.

Compare two runs, split by document class:

    .venv/bin/python -m harness.report_holdout out/eval_a.json out/eval_b.json

### tests

Twelve suites, all passing as of 2026-09-20. Each is a plain script:

    for t in harness/test_*.py; do .venv/bin/python "$t" || echo "FAILED $t"; done

    alignment  arabic  footnotes  heading_style  headings  image_drop
    images  inline  loss_gate  pagination  text_score  xml_safe

Their docstrings are where the failure modes are recorded — `test_arabic.py` and
`test_loss_gate.py` especially are worth reading before touching either area.

## the three scores are not interchangeable

Confusing them has cost real time, twice:

- `harness.loss.coverage()` — **the hard gate.** Is every substantial word still
  present *somewhere*? Ignores order entirely. Must stay at 100%.
- `harness.compare.text_score()` — is the wording still in the **right order**?
  Longest-increasing-subsequence over located sentences.
- `page_score` — did words land on the **matching page**?

`page_score` is not exactly reproducible: LibreOffice does not render
identically every time, so **treat movement under about half a point as noise.**

## layout

    PDF → reader → description → writer → DOCX
                                    ↑
                          checker scores the result

- `convert/reader.py` — what is in the PDF: headings, paragraphs, footnotes, bold
- `convert/model.py` — a plain ordered list of what was found, not a Word file yet
- `convert/writer.py` — builds the .docx, handling the right-to-left details
- `convert/fit.py` — page-fitting, so page breaks line up with the original
- `convert/arabic.py` — repairs for text the source PDF hands over backwards
- `harness/` — the checker, corpus tooling and tests

`convert/arabic.py` is imported by **both** the converter and the checker, and
has to be. Repairing only our side would make our output stop matching the
still-mangled original it is scored against, and a genuine fix would read as a
regression.

## what works now

- correct right-to-left Arabic: correct letters, correct word order
- lines joined into real paragraphs
- real Word heading styles (`Heading 1`–`6`) with outline levels, so navigation
  and table-of-contents work — not bold text that merely resembles a heading
- real Word footnotes via `footnotes.xml`, renumbering per page
- pictures: 315 of 315 placements across the corpus, including JPEGs Word's own
  library refuses to identify, and vector line art rasterised into table cells
- tables with `w:bidiVisual` so columns mirror, and column widths that hold
- a decoration repeating on most pages recognised as a running header
- page size, margins, font size and line spacing measured off the original
- the document's own Arabic font carried through, not a substitute
- justification on both right-to-left and left-to-right paragraphs
- reversed lam-alef ligatures (`ال` → `لا`) repaired — 773 occurrences across
  25 files, against 0 legitimate uses

## findings worth keeping

**Two layers hold the text, and which one works varies per file.** The 6 sample
files recover 0–8% from glyph extraction; their text lives in `/ActualText` on
`/Span` elements in the tagged structure tree. The 88 wild Arabic PDFs extract
fine from glyphs, 88/88, and none need the tag layer.

Two theories for what triggers the difference were tested and **both failed** —
Word version, and undecodable font signature. Conclusion: **don't predict which
route works, measure it per file.** Run both and keep the better result.

**Files can be refused.** `harness/split.py` rejects any PDF whose text is more
than 2% control characters. `z22244578.pdf` had 13,417 control characters across
27 codepoints and mojibake on 117 of its 131 pages. Silently stripping them
would have let nonsense into the corpus, where it would score against an equally
nonsensical round-trip and **raise the average, because a broken file started
passing.**

## notes

- qalam is in a separate venv at `~/.venvs/qalam` (Python 3.14)
- `docs/abandoned-mcid-approach.py` is kept deliberately — it records a route
  that did not work, so it is not tried again
