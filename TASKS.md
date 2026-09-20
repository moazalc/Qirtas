# Qirtas — where to pick up

Start a new session here. This is the short version; `PLAN.md` has the full
history and `README.md` has setup and commands.

---

## What this is

Converting Arabic PDFs back into editable Word files. The problem: people
export Word to PDF, lose the Word file, and can't edit the PDF. Every free tool
mangles Arabic, and **Acrobat doesn't support right-to-left PDF→Word export at
all**, so buying it doesn't help.

Getting Arabic *text* out of a PDF is already a solved problem — that was
measured across 105 files. **The gap is writing a correct right-to-left .docx**,
which nothing does. That's the project.

## Where it stands (2026-09-20)

On Moaz's 8 thesis files, measured on the office machine:

    nothing lost     100.0%   <- the hard gate, never broken
    words in order    98.6%
    right page        61.4%   <- goal: >90%
    page inflation     1.00x  <- page counts now exact

All 12 test suites pass. Everything is committed and pushed to `main`.

**Note the office machine scores 61.4% where `PLAN.md` records 49% for the same
code.** Almost certainly the Arabic font substitutions, which are installed
here and probably weren't at home. Every eval run now prints and stores its
environment so this can't silently happen again.

---

## Tasks, in the order worth doing

### A. Toward Moaz's goal: his 8 files above 90% on right page

**A1. Images cost page alignment at full size.** Diagnosed, half-fixed,
in progress when the office session ended. Purely a space problem — at half
size, alignment jumped 19% → 63% and pages went 25→26. The shrink loop in
`convert/fit.py` stops at `FLOOR = 0.70` and needs to reach about 0.5 when
pictures are present. Small change, directly measurable.

**A2. `مقدمة البحث` is an outlier** — 26% → 31% where its siblings reached
~50%. Text and picture scores are both perfect, so whatever is wrong is
positional. Undiagnosed.

**A3. Line-break drift inside correctly-numbered pages.** What remains after
pagination was fixed. It's a wrapping difference between renderers and may not
be worth chasing — check before spending time on it.

### B. Blocking the corpus generally (not Moaz's files)

**B1. Text stored in VISUAL order — the largest known correctness problem, and
it needs a decision, not a patch.** Some Arabic PDFs (typically LaTeX) store the
character stream already reversed. The page looks perfect; the text underneath
runs backwards. We reproduce it faithfully, Word reverses it again, and the
result is unreadable.

**The scorer is structurally blind to it** — our reversed output is compared
against the same reversed source, so they agree. `z21889411.pdf` scores 99.9%
on text and 130→130 pages, was called the best pagination result in the
project, and not a word of its output is readable.

    56 of 172 corpus files (32.6%) are stored this way
    7 of 20 such holdout files score >=95% text, two exactly 100%

Detection is cheap and already prototyped (count common function words against
their reversals; the two cases separate by an order of magnitude). **What to do
about it is Moaz's call**: reorder the text and risk mangling partly-correct
documents, or refuse such files outright. Either changes what the converter
promises.

Found by rendering a page and looking at it. Not by any metric.

**B2. Periodicals are detected then ignored.** `harness/doctype.py` identifies
them; the score then averages them in with ordinary documents, producing a mean
true of neither. Either handle multi-column layout or put them out of scope in
writing.

**B3. Lists.** Numbered items flatten into prose. Not detected at all.

**B4. `z21312494.pdf`** — nine words genuinely missing (author names and
affiliations) across ten of its 432 pages. The only remaining real loss.

### C. Needs a Windows machine with Word

Moaz has Windows and macOS with valid Word licences.

**C1. Is the shrinking fixing real overflow, or LibreOffice font-substitution
overflow?** We detect spill through LibreOffice, which lacks the fonts these
documents ask for. We may be shrinking text to fix spill that doesn't exist in
real Word — making output worse to make a number better.

**C2. Render in Word rather than LibreOffice** for a trustworthy check.

Both are worth doing *after* A and B: every currently-known defect is
verifiable straight from the .docx XML, which is Word's own ground truth.

---

## Traps — each of these already cost real time

**Don't trust a score without its environment.** Two separate drifts have been
caught: the corpus (re-fetching returned whatever Zenodo held that day) and the
renderer (missing font substitutions make text wider, so it overflows and the
converter gets blamed). Both silently turn a score into a number about
something else.

**Restore the corpus with `--from-manifest`, never a fresh `--n 120` search.**
A different file set means a different filename-hash split, and every recorded
number becomes a measurement of some other collection.

**Seven bugs have been found in the measuring tools rather than the
converter** — see "Measurement caveats" in `PLAN.md`. Three times a reported
improvement wasn't real. When a number moves, check the instrument first.

**The three scores are not interchangeable** — see README. "Nothing lost"
ignores order by design. "Right page" is blind to tables and images unless the
structure score is read alongside it.

**`corpus/*.pdf` are someone's unpublished thesis chapters.** Not in the repo,
not restorable by any command, and not ours to publish. Back them up by hand.

---

## Running it

    .venv/bin/python -m harness.env                    # check the environment first
    .venv/bin/python -m harness.eval --set regression  # Moaz's 8 files
    .venv/bin/python -m harness.eval --n 30            # sample of the tuning set
    for t in harness/test_*.py; do .venv/bin/python -m harness.$(basename $t .py); done

LibreOffice is now auto-detected (`QIRTAS_SOFFICE` overrides). The holdout set
is paused at Moaz's request.

## Deeper reading

- `PLAN.md` — full history, every measurement trap, the complete unfinished list
- `README.md` — setup, commands, what the three scores mean
- `RESEARCH.md` — what was established about the problem space; don't redo it
- `docs/fonts.md` — font substitution setup, required for comparable scores
