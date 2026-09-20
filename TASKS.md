# Qirtas — where to pick up

Start a new session here, then read `FLAGS.md`. `CLAUDE.md` explains the
project and how to work in it; `PLAN.md` has the full history; `README.md` has
setup and commands.

Findings go in the right file: design and history in `PLAN.md`, work in this
file, open risks and decisions in `FLAGS.md`.

---

## What this is

Converting Arabic PDFs back into editable Word files. The problem: people
export Word to PDF, lose the Word file, and can't edit the PDF. Every free tool
mangles Arabic, and **Acrobat doesn't support right-to-left PDF→Word export at
all**, so buying it doesn't help.

Getting Arabic *text* out of a PDF is already a solved problem — that was
measured across 105 files. **The gap is writing a correct right-to-left .docx**,
which nothing does. That's the project.

## Where it stands (2026-09-20, end of day)

Moaz's thesis files — **7 of them, not 8: `ödev.pdf` was deleted, see A11**:

    nothing lost     100.0%   <- the hard gate, never broken
    words in order    98.6%
    right page        64.3%   <- goal: >90%
    page inflation     1.00x  <- page counts exact

On 30 files nobody tuned on:

    nothing lost     100.0%
    words in order    73.4%
    right page        26.7%
    page inflation     1.46x

All 14 test suites pass. Everything is committed and pushed to `main`.

**64.3% is not a fall from 68.8%.** The 8-file set scored 68.8%; the same 7
files score 64.3% both before and after every change made today. The whole
difference is the deleted control file, which scored 100%. See A11.

**Run `python -m harness.env` before trusting any number.** A machine without
the Arabic font substitutions falls back to Noto Sans Arabic, which is wider,
so text overflows and the converter takes the blame.

## Two decisions are waiting on Moaz

Nothing else here is blocked; these two are.

1. **Text stored backwards** — a third of the corpus. Reorder it, or refuse the
   file? `FLAGS.md` 1. Nothing further is worth measuring on those files while
   they can score 99% and be unreadable.
2. **Numbers that cannot be trusted** — 4 of 102 files verifiably print one
   number and store another. Warn, or refuse? `FLAGS.md` 13.

A third, smaller one: **was the list fix worth it?** Correct list structure
cost 1.9 points of a score that cannot see lists. Kept, at Moaz's word, but
`FLAGS.md` 16 records the trade.

## What was done today

Eight things, all with write-ups in `PLAN.md`:

- duplicate paragraphs from `_backfill` (A1) — right page 61.4% → 68.8%
- `w:jc` is logical, so every Arabic heading was against the wrong margin (A8)
- running headers, footers and page numbers into Word's header/footer (A5)
- table cells written backwards (A6)
- black bars from transparency-masked pictures (A4)
- header text wrapping (A9)
- lists (A10)
- a measured answer on untrustworthy digits (A7)

Four new tools in `harness/`: `drift`, `look`, `digits`, and the `out/runs/`
layout where every measurement now records itself.

**Two of today's eight were fixes to a diagnosis that was already written
down and wrong.** Re-check the note before trusting it.

---

## Tasks, in the order worth doing

**Next session: A2 is diagnosed and ready to work on.** After that, the two
decisions above are blocking more than anything else in this list.

### A. Toward Moaz's goal: his files above 90% on right page

**A1. DONE (2026-09-20), and the recorded diagnosis was wrong.** It was not
images and not the shrink loop — `FLOOR = 0.70` is unreachable anyway, because
`ROUNDS = 4` at `STEP = 0.94` caps the loop at 0.78. The real fault was
`reader._backfill` duplicating paragraphs that were already present, because
the lam-alef repair is space-sensitive and the two reader routes disagree about
spaces. One spurious page early in a file put every later page one out of step.
**Right page 61.4% → 68.8%**, two files fixed (29.0% → 72.6% and 51.6% →
68.4%), page counts now exact on both. Gate held at 100%, nothing moved beyond
noise on 30 unseen files. Full write-up in `PLAN.md`.

**A2. `مقدمة البحث` — DIAGNOSED, not fixed. Start here.** 33.7% where its
siblings reach 56–73%, and the only regression file still running long (17
pages against 16). `harness.drift` answered it in one run:

    pages 0 and 1   no words at all - picture-only
    page 2 onward   a constant +1, share 58-89%

**One spurious page among the first two, and everything after it one out of
step.** Not twenty bad pages. The per-page share is already 58–89%, so
removing that page should take the file from 33.7% to roughly 75% — the
largest single gain left on Moaz's set.

Both leading pages are picture-only, which is exactly the blind spot in
`FLAGS.md` 9: `fit.py` matches pages by shared words and cannot see a page that
has none, so its fill factor has to be right first time. Look at output page 2
and at `IMAGE_PAGE_FILL` before anything else.

    .venv/bin/python -m harness.drift "corpus/مقدمة البحث.pdf" <our rebuilt pdf>

**A3. Line-break drift inside correctly-numbered pages.** What remains after
pagination was fixed. It's a wrapping difference between renderers and may not
be worth chasing — check before spending time on it.

**A4. DONE (2026-09-20).** Black bars on every page of `الفصل الثالث` and of
`z21358439`. The running-header pictures are solid-black images whose real
shape lives in a transparency mask we dropped. They are now photographed off
the page rather than decoded, because the mask is a pre-multiplied `/Matte`
alpha running 0..64 and not worth rebuilding. Found by looking; every score
rated the file 100% on images throughout. **Fixing it then broke running-header
grouping** — see `FLAGS.md` 15, which is the more useful lesson. `PLAN.md`.

### A5–A12. Found by looking at pages, 2026-09-20

Moaz's call: these outranked the per-file chasing above, and he was right.
Every one was found by putting our page next to the original and looking.
**Most of them moved no score at all** — the black bars, the headings on the
wrong margin and the backwards table cells were all invisible to every number
this project has.

**A5. DONE (2026-09-20).** Running header text and page numbers now go to
Word's header and footer; the page number is a real `PAGE` field starting at
the original's first number. On 30 dev files: **right page 21.3% → 27.7%**,
inflation 1.56x → 1.46x, 15 files improved and none worse, gate held at 100%.
Best single file 28.1% → 96.7%. Full write-up in `PLAN.md`.

**A6. DONE (2026-09-20).** Cells are read by clipping to their own rectangle
rather than flipping the string - flipping also flips the lam-alef ligature,
which is why it failed. New `harness/test_tables.py`. `FLAGS.md` 12.

**A7. MEASURED (2026-09-20) — needs Moaz's decision.** `harness/digits.py`
finds candidates; all seven in 102 dev files were rendered and read, and
**4 are verifiably wrong (3.9%)**. A floor: one sample cannot clear a file.
Warn or refuse is the open question. `FLAGS.md` 13.

**A8. DONE (2026-09-20), and it was worse than "alignment".** `w:jc` is
logical: "right" means END, which a right-to-left paragraph puts on the LEFT.
**Every Arabic heading in the corpus was against the wrong margin** - 420pt out
of place on the file it was found on. Headings and table cells both fixed. No
score moved, which is the point: `right page` cannot see it. The old test
asserted the bug and passed; it now renders and measures. `PLAN.md`.

**A9. DONE (2026-09-20).** Header text uses the block's own measured size (8pt)
instead of a guessed fraction of the body size (9.6pt), which is what made it
wrap.

**A10. DONE (2026-09-20), and it COST score — needs Moaz's call.** Bullets and
numbered items are detected and kept apart; the structure now matches the
original (see the rendered page). But **right page fell 28.6% → 26.7%** on 30
dev files, almost all of it two files that gain exactly one page. Fifty list
items are fifty paragraphs, each ending in a partly-filled line. `fit.py`
cannot recover it without shrinking body text toward half size, which
`FLAGS.md` 6 forbids. Correct structure against 1.9 points of a score blind to
structure. `FLAGS.md` 16, `PLAN.md`.

**A11. DONE (2026-09-20).** A page whose first block is a TABLE had its page
break written onto the paragraph AFTER the table, so the table stayed on the
previous page. 60 of the 72 pages of `z10442411.pdf` begin with a table; none
of Moaz's eight do, which is why no score ever showed it. Break now goes on the
first paragraph of the table's first cell, verified by rendering. 30 dev files:
gate held at 100%, page inflation 1.46x -> 1.42x, `right page` unmoved at 28.5%
(-0.04, inside render noise). Regression set unchanged at 68.8%. `PLAN.md`.

**A12. `ödev.pdf` has been deleted from `corpus/`.** The Turkish left-to-right
control file. Its absence, not any code change, is the whole of the regression
set moving 68.8% → 64.3%; every other file scores identically. It was the only
non-Arabic file in the set and the only check that left-to-right documents are
not being damaged. **`FLAGS.md` 17 — restore it or restate the baseline.**

### B. Blocking the corpus generally (not Moaz's files)

**B1. Text stored in VISUAL order — the largest known correctness problem.
It needs a decision, not a patch: see `FLAGS.md` #1.** Some Arabic PDFs (typically LaTeX) store the
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

**B3. DONE — see A10.** Bullets and numbered items are detected and kept
apart. Note what it cost: `FLAGS.md` 16.

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
**One of them has already been lost** — see A12. Nothing warned.

**Look at a page before believing a number, and before reporting a defect.**
Both directions paid off on 2026-09-20. Looking found black bars on every page
of a file every score rated 100%, Arabic headings against the wrong margin, and
backwards table cells — none of which moved any number we have. Looking also
killed a "misplaced full stop" defect that turned out to sit identically in the
source PDF. `harness.look` and `harness.drift` exist for this.

**A recorded diagnosis can be wrong.** Two of the eight things fixed on
2026-09-20 had a written explanation that did not survive contact with the
instrument: A1 blamed images and the shrink loop, A4 blamed 2x2 stencils. Both
were wrong, and both notes were confident. Re-derive before trusting.

**`left` and `right` mean START and END in Word's format**, and a right-to-left
paragraph swaps which physical side that is. This cost every Arabic heading in
the corpus its margin, and every list item its indent. Measure it on a rendered
page; never reason about it.

**A test can assert the bug.** `test_alignment` checked that Arabic headings
were set to "right" — exactly what the buggy code wrote — and passed happily
while every heading sat on the wrong side. A test that only asks what the XML
says can confirm we wrote what we meant, and nothing more.

**Identify things by what they ARE, not by a hash of what came out.** Running
headers were grouped by hashing the extracted image file. When masked images
started being rendered off the page, every copy became unique, the grouping
collapsed, and a file fell 56.3% -> 28.4% with nothing in the image code
looking wrong. See `FLAGS.md` 15.

---

## Running it

    .venv/bin/python -m harness.env                    # check the environment first
    .venv/bin/python -m harness.eval --set regression --label what-changed
    .venv/bin/python -m harness.eval --n 30 --label what-changed
    for t in harness/test_*.py; do .venv/bin/python -m harness.$(basename $t .py); done

Every eval run records itself in `out/runs/<date>-<set>-<label>/` with the
scores, the per-file rows and the environment. Pass `--label`; a run nobody can
identify later is a run nobody can compare.

Finding out WHERE a file is wrong, which no score tells you:

    .venv/bin/python -m harness.drift original.pdf rebuilt.pdf
    .venv/bin/python -m harness.look  original.pdf rebuilt.pdf --pages 4 --align
    .venv/bin/python -m harness.digits --set dev

`drift` says whether a bad score is ONE spurious page (a constant offset, worth
chasing) or content genuinely overflowing (a growing one). `look` puts the two
pages side by side — use `--align` whenever the page count moved. `digits`
finds files that display one number and store another.

LibreOffice is now auto-detected (`QIRTAS_SOFFICE` overrides). The holdout set
is paused at Moaz's request.

## Deeper reading

- `PLAN.md` — full history, every measurement trap, the complete unfinished list
- `README.md` — setup, commands, what the three scores mean
- `RESEARCH.md` — what was established about the problem space; don't redo it
- `docs/fonts.md` — font substitution setup, required for comparable scores
