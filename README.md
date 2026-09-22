# Qirtas  ·  قرطاس

Arabic PDF back to editable Word — with the right-to-left parts actually
correct, which no free tool and not Acrobat currently manage.

## where this is

**Picking this up fresh?** `CLAUDE.md` for the project and how to work in
it, `TASKS.md` for what to do next, `FLAGS.md` for what needs deciding.

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

### settled: text stored backwards

**Text layers stored in visual order.** Some Arabic PDFs — typically LaTeX
output — store the character stream already reversed. **Settled
2026-09-22:** 46 of the 52 corpus files that read backwards were scans with
machine-read text laid invisibly over a photo. Scans are now refused with a
plain message (`convert/scan.py`). Of digital files one is really backwards,
`z21889411.pdf` (LaTeX, line by line), parked. See `FLAGS.md` 1.

## setup

    python -m venv .venv
    .venv/Scripts/pip install -r requirements.txt

**Use `.venv/Scripts/python` for everything.** The system Python does not have
pymupdf and will fail in ways that look like corpus problems.

Also needed:

- **Windows with Microsoft Word** — used to render our .docx back to PDF for
  checking (`harness/word.py`, over COM), and by `convert/fit.py` to see which
  pages spilled. Word is the only renderer: it is what readers actually open
  the file in. LibreOffice was used until 2026-09-21 and removed; scores taken
  with it are not comparable to Word ones.
- **Arabic fonts** — these PDFs ask for Simplified Arabic, Traditional Arabic
  and Sakkal Majalla. Install them from Windows' optional Arabic fonts
  (`Language.Fonts.Arab`). Without them Word picks a wider face, text
  overflows, and the converter gets blamed for it. `python -m harness.env`
  reports which are installed.

## corpus

The PDFs are not committed — `corpus/*.pdf` are unpublished thesis chapters (not
ours to publish) and `corpus/wild/` is ~570MB of open-access PDFs from Zenodo.
Two small files that describe the corpus **are** committed, and they are what
makes a fresh checkout usable:

    corpus/wild/manifest.jsonl   225 Zenodo record IDs - the wild corpus itself
    out/split.json               dev/holdout membership, usable flags, refusals

To rebuild the wild corpus on a new machine:

    .venv/Scripts/python -m harness.fetch_corpus --from-manifest --out corpus/wild

**Use `--from-manifest`, not a fresh search.** Running `fetch_corpus --n 120`
does not rebuild this corpus; it builds *a* corpus. The Zenodo query sorts by
`mostrecent`, so it returns whatever Arabic publications exist on the day it
runs. The split is `sha256(filename) % 1000 < 400`, so a different file set is a
different dev/holdout membership — and every score in `PLAN.md` quietly becomes
a number measured against some other collection of documents. Nothing warns you;
the run simply succeeds and reports a mean.

Restoring by manifest keeps the split identical across machines, which is the
only reason previous scores stay comparable.

`--from-manifest` reports any record Zenodo has withdrawn since, and exits
non-zero. Don't wave that through: a corpus one file short still scores fine.

`corpus/*.pdf` cannot be restored by any command — they were never published.
Copy them across by hand. Everything else under `out/` is regenerated output
and is meant to be absent on a fresh checkout.

### where output goes

`out/` was a flat drawer of 78 items with names like `final2`, `mine` and
`fittest`, and no way to tell which number came from which code. Since a score
here means nothing without knowing how it was produced, it now has a shape:

    out/split.json   dev/holdout membership. TRACKED IN GIT, never regenerated
    out/runs/        one folder per measurement, dated and labelled. Keep these
    out/work/        scratch conversions and renders. Safe to delete any time
    out/tests/       what the test suites write. Safe to delete any time
    out/archive/     everything that was loose in out/ before 2026-09-20

**Every eval run records itself** into `out/runs/<date>-<set>-<label>/` with
`results.json` (scores, per-file rows, and the environment) and `summary.txt`.
That is not optional and not something to remember — the run that matters is
always the one nobody saved.

    .venv/Scripts/python -m harness.eval --set regression --label after-some-fix

`out/archive/` holds the pre-2026-09-20 files, several of which are cited as
evidence in `PLAN.md`. Read before deleting.

## running it

Convert one file:

    .venv/Scripts/python -m convert.v1 input.pdf out/output.docx

Score the converter (PDF → DOCX → Word → PDF → compare; no ground-truth
.docx needed):

    .venv/Scripts/python -m harness.eval --n 30          # sample of the tuning set
    .venv/Scripts/python -m harness.eval                 # the whole tuning set
    .venv/Scripts/python -m harness.eval --set regression  # the hard ActualText case

Grade each feature (footnotes, headings, lists, tables, headers) against the
structure labels Word saved into the PDF - the answer key, see `PLAN.md`:

    .venv/Scripts/python -m harness.answerkey --set dev          # ~5 minutes
    .venv/Scripts/python -m harness.answerkey --set regression

Check spelling against Word's own reading of each PDF, which does not share
our extractor (lam-alef, display-form glyphs, backwards words). Run after an
eval; it checks the .docx the eval left in `out/work/eval/docx`. Windows and
Word only; Word's reading is cached in `out/work/wordread/`:

    .venv/Scripts/python -m harness.spelling --set dev -v

A full 102-file run takes roughly 25–35 minutes. It schedules longest-file-first,
so **the long files finish last** — progress through the file count is not
progress through the work, and estimating from early completions will be wrong.

    .venv/Scripts/python -m harness.eval --set holdout

The holdout exists to answer one question at the end — does this generalise, or
have I fitted the files I could see? It has been opened once. Opening it again
during development destroys the only safeguard there is.

Compare two runs, split by document class:

    .venv/Scripts/python -m harness.report_holdout out/eval_a.json out/eval_b.json

### finding out WHERE a file is wrong

A score says a file is bad. These two say where, and between them they have
found more real bugs than any metric has.

    .venv/Scripts/python -m harness.drift original.pdf rebuilt.pdf

For each original page, which of our pages did its words land on. Read the
drift column: a **constant** offset is ONE spurious page and is worth chasing
(that is how the duplicate-backfill bug was found — right page 29.0% → 72.6%);
a **growing** offset is content genuinely overflowing page by page.

    .venv/Scripts/python -m harness.look original.pdf rebuilt.pdf --pages 4 --align

The two pages side by side, ours left, original right. Use `--align` on any
file whose page count moved, or you will compare two pages holding different
content and invent faults that are not there.

    .venv/Scripts/python -m harness.digits --set dev

Finds PDFs that DISPLAY one number and STORE another - `1951` on the page,
`1901` in the text. It reports CANDIDATES, not verdicts: on the dev set 4 of 7
were real once rendered and read. Not our bug, but our output carries the wrong
number and every score says 100%, because both sides share the fault.

**Look before believing a number, and look before reporting a defect.** Both
directions have paid off: looking found black bars on every page of a
regression file that every score rated 100%, and looking *also* produced a
misplaced-full-stop "bug" that turned out to sit identically in the source
PDF's own text layer.

### tests

Twenty-two suites, all passing as of 2026-09-22. Each is a plain script:

    export PYTHONUTF8=1
    for t in harness/test_*.py; do .venv/Scripts/python "$t" || echo "FAILED $t"; done

`PYTHONUTF8=1` matters on Windows: without it, printing Arabic to a pipe or a
log file raises `UnicodeEncodeError` and four suites fail for reasons that have
nothing to do with the converter.

    alignment  answerkey  arabic  digits  fit  footnotes  glyphs  heading_style
    headings  image_drop  images  inline  labels  lists  loss_gate  notes
    pagination  scan  spelling  tables  text_score  xml_safe

Their docstrings are where the failure modes are recorded — `test_arabic.py` and
`test_loss_gate.py` especially are worth reading before touching either area.

## the three scores are not interchangeable

Confusing them has cost real time, twice:

- `harness.loss.coverage()` — **the hard gate.** Is every substantial word still
  present *somewhere*? Ignores order entirely. Must stay at 100%.
- `harness.compare.text_score()` — is the wording still in the **right order**?
  Longest-increasing-subsequence over located sentences.
- `page_score` — did words land on the **matching page**?

`page_score` was not exactly reproducible under LibreOffice, which did not
render identically every time, so movement under about half a point was noise.
Word's run-to-run noise has not been measured yet; assume the same until it is.

## layout

    PDF → reader → description → writer → DOCX
                                    ↑
                          checker scores the result

- `convert/reader.py` — what is in the PDF: headings, paragraphs, footnotes, bold
- `convert/model.py` — a plain ordered list of what was found, not a Word file yet
- `convert/writer.py` — builds the .docx, handling the right-to-left details
- `convert/fit.py` — page-fitting, so page breaks line up with the original
- `convert/arabic.py` — repairs for text the source PDF hands over backwards
- `convert/glyphs.py` — reads a font's shapes when its table names the wrong
  letters (FLAGS 23); needs the font installed
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
