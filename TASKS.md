# Qirtas — where to pick up

Start a new session here, then read `FLAGS.md`. `CLAUDE.md` explains the
project and how to work in it; `PLAN.md` has the full history; `README.md` has
setup and commands.

Findings go in the right file: design and history in `PLAN.md`, work in this
file, open risks and decisions in `FLAGS.md`.

---

## Start here (2026-09-24)

**Focus: Part 1, text accuracy** (Moaz, 22 Sept): the words in the Word file
must match the printed page before any work on looks. The plan and its
progress are in `PROGRESS.md` ("Plan from here").

**The corpus changed on 24 Sept** (Moaz): 37 Word-made Arabic theses, 25 to
work on and 12 held out, plus two of Moaz's chapters (PLAN "The thesis
corpus"). Scores before this are not comparable. New baseline
`2026-09-24-{thesis,regression}-thesis-baseline`: nothing lost 99.4%
(FLAGS 29 - five theses, the reference text looks at fault), wrong words
10.1%, right page 61.1%, pages 1.14x. A quick run after each fix (~10 min),
a full run only at milestones (~25 min) - README "measuring a change".

**Part 2 done 24 Sept** (missing-font message: `convert/fonts.py`,
`python -m convert`; PLAN "Part 2"). **Now Part 3, looks** (Moaz: Parts 2
and 3 before the text list below). Bold DONE 24 Sept (PLAN "Part 3: looks
- bold"): shown bold 18% -> 78%. Headings' own bold and centring DONE 24
Sept (PLAN "Part 3: headings' own bold"). Text size DONE 25 Sept (PLAN "Part 3:
text size"); the gaps above paragraphs tried and left off - they need side
by side fixed first. Side by side DONE 25 Sept (PLAN "Part 3: blocks
side by side") - a looks fix only; it is NOT what makes pages run long, and the gaps
above paragraphs still push pages over with it (tried again, left off).
No header or number on unnumbered front pages DONE 26 Sept (PLAN "Part 3: no
header or number"). Three or more across DONE 27 Sept (PLAN "Part 3: three or more across" -
borderless tables; not yet the logo between two headers). Tables: thin
columns and doubled text DONE 27 Sept (PLAN "Part 3: tables drawn with
double rules"). Tables the right way round, cells across columns, placed
by position, the rest of the doubled text, and spaces stored as U+200C DONE
27 Sept (PLAN "Part 3: tables the right way round"). Tables, still: the
table finder's pieces of one big table found as small tables of their own
(`z3387756` page 12); a stray `ا` in header cells; `z21145041`'s cells
stored backwards (and so its table text written again under it; the same on
`z22058810` page 2, a shaded verse read as a table). Bold on the tags route
DONE 27 Sept (PLAN "Part 3: bold on the tags route"; measure bold by letters
in any order - these PDFs store words backwards). Italic drawn as a slant,
and headers keeping their bold/italic, DONE 27 Sept (PLAN "Part 3: italic
drawn as a slant"). Table cells shaded DONE 27 Sept (PLAN "Part 3: table
cells shaded"). Bands behind ordinary text, and italic only where the PDF
itself says so, DONE 28 Sept (PLAN "Part 3: bands behind ordinary text").
Headers laid out like the original (the line under, two parts at the
edges) DONE 28 Sept (PLAN "Part 3: headers laid out like the original");
header text still bigger and less bold on `z7456037`, `z20973693`.
Footnotes as the original sets them (the line above them, their line
height, bold words inside them) DONE 28 Sept (PLAN "Part 3: footnotes as
the original sets them"); left there: notes numbered "1 ... 2 ... 3" in
one paragraph stay one note (`z17804101` page 5), a note's second
paragraph joins its first (`z18048055`).
The logo between two headers, and a page's number at its foot written at
the top (58 pages), DONE 28 Sept (PLAN "Part 3: the logo between two
headers"); left there: side cells narrower than the original's headers,
which reach into the margins. Seen on the way (`z20585114` page 2): a
full-page picture with text printed over it comes out as a small picture,
the text, then the picture again below it, and the chapter header is drawn
on that front page. Seen 28 Sept (`z18048055` page 9): the footer prints
a fixed "1" on every page where the original numbers them (1-3, 21-28,
54-55 - the sample's cut makes the numbers jump), and the footer's double
line and the number's box are not drawn. The verse marks out of place on
that page are the PDF's own stored text.
Brackets where the page draws them DONE 28 Sept, asked for by Moaz ahead
of the tables (PLAN "Brackets where the page draws them"; measure with
`python -m harness.brackets`): 64.7 -> 78.6% of the theses' brackets in
place. Left: files stored backwards; English citations and formulas cut
into many pieces (`z21644412`, `z3387756`); a caption `)59(` and a URL
`(www.globalreporting.org(` whose brackets are pieces of their own
(`z7456037`, `z18441713`). (FLAGS 27 is not this - it is how "right page"
reads English beside Arabic; still open.)
English and numbers in the tags route's Arabic lines (FLAGS 29), and
numbers read backwards, DONE 28 Sept, asked for by Moaz ahead of the tables
(PLAN "English in the theses' Arabic lines"): nothing lost 100%, page truth
wrong 8.3 -> 7.9%; years were backwards in seven theses. That English set
at its own size, font, line height and alignment DONE the same day (PLAN
"The English set as drawn"): `z21145041` 17 -> 15 pages. Backwards second
copies from the backfill DONE the same day (PLAN "Backwards second copies
from the backfill"; the gate's excuse for backwards sentences now needs
their words together in ours): page truth wrong 7.9 -> 7.2%. Left: a
backwards verse on `z22058810` page 2 (FLAGS 32); "COVID19." drawn with the
full stop on the word's left; headings in that English not centred; web
addresses not links.
Tables, first batch DONE 28 Sept (PLAN "Tables: written twice, cells
backwards, stray letters, off the page"): `z17931421`'s wide table on the
page and not written again (17 -> 15 pages), `z21145041`'s backwards cells
(15 -> 14), the stray `ا` in header cells, `z18037898`'s entry numbers.
Second batch DONE 29 Sept: tables that are not tables (fills behind text:
footnotes, a verse, reference lists, a cover title), pieces of one table
found as tables of their own (`z3387756` 15 -> 14 pages). Tables still to
do: `z21644412` page 12's table in many narrow empty columns (22 columns, 14
widths - Word shares them out); stray single letters in the thin sliver
columns of double-ruled tables (`z3387756` page 12); rows still written
again where a word is drawn with a space inside (`ال رجلين`, `z17931421`)
or a note reference sits in the cell (`z3387756`). Footnote and page numbers as fixed text: parked by Moaz 25 Sept (FLAGS 31).
List dashes: fine on the theses (282 spaced, 3 glued) - Moaz's own chapters
only. Measure bold as Word draws it (the
rendered PDF's fonts), never the Word file's markup.

**FLAGS 29 done 24 Sept** (nothing lost 100.0%, wrong words 10.1 -> 9.0%,
full run `flags29c` was the baseline; now `2026-09-27-*-part3d`: nothing lost 100.0% on every file, wrong words 8.4%, right page 69.4%, pages 1.00x). **Next:** the English the tags
reading drops inside Arabic lines (FLAGS 29, still open) - it is put back on
a line of its own, which reads wrong; then the list below re-checked against
the theses - it was drawn up on the old corpus. Pages were the plain problem
on the theses (11 of 25 came out 3+ pages long); since the table fixes,
1.00x overall, longest `z17931421` 17 for 14.

**Old corpus, for the record** - full run `2026-09-24-{dev,regression}-fonts-baseline`:
page-truth wrong words 7.8% on the 48 dev files (floor: Moaz's theses 2.8%),
found 91.9%, nothing lost 100% on every file but the parked `z21763864`
(90.0%). Citations done and committed (b14135b); fonts installed.

**Next, in this order** (agreed with Moaz 2026-09-24; 2 and 4 re-scoped the
same day by what the breakdown found - PLAN "What the rest of the wrong
words are"):
1. ~~Brackets around English citations~~ - DONE 24 Sept (PLAN "Citations
   where a line wraps"). Left: `Tuberculosis(TB)`, a bracket the PDF stores
   in the wrong piece; moving it risks the gate. FLAGS 27 needs Moaz.
2. **Pictures drawn squashed** - DONE 24 Sept, measured on the old
   corpus's picture files; in the thesis baseline (PLAN "Pictures at the shape they are drawn"). Right page
   62.0 -> 64.7% on 11 picture files. Left: pictures side by side in the
   original are written one above the other (`z19773087` page 18, now one
   page long) - Part 3.
3. **Glued words, the rest**: nearly all `z20276275`, which stores whole
   phrases with no space - a space where two letters are drawn 0.15 of the
   type size apart; also words glued to a number in journal headers
   (`العدد6`). A couple of hours.
4. **Words not on the page at all**, file by file; some are the PDF storing
   text broken (`ربع أ عقد وست ج در ات` for أربع عقد وست درجات,
   `z19773087` page 19). A third of the "one letter off" words look right
   and may be the OCR. Half a day.
Fonts installed and the fresh full run done (`fonts-baseline`, 2026-09-24):
compare against that. `z21751977` is not a font problem: its body text is
~130 small picture tiles a page (FLAGS 28).
Then Part 2, the missing-font message (below), then Part 3, looks - Moaz's
thesis page 13 of الفصل الثاني shows the list: bold lost, text too small
(footnotes worst), Arabic-style digits and commas (the file stores `1`, `,`
and Word shows `(١)`, `،`), list dashes. New, lower: journal line numbers
in the margin written into the text (`z19773087`), "Mode" captions of a
picture grid written twice.

**How to measure** (details in `README.md`, "measuring a change"): a quick
run on 11 files with the change on and off, each in its own `--work`
folder, then `harness.truth` on each; a full run before calling it done.
The quick set is mostly untagged PDFs - a change to how text is read must
also be checked on tagged files (PLAN "The full run caught what the quick
set could not").

## What this is

Converting Arabic PDFs back into editable Word files. The problem: people
export Word to PDF, lose the Word file, and can't edit the PDF. Every free tool
mangles Arabic, and **Acrobat doesn't support right-to-left PDF→Word export at
all**, so buying it doesn't help.

Getting Arabic *text* out of a PDF is already a solved problem — that was
measured across 105 files. **The gap is writing a correct right-to-left .docx**,
which nothing does. That's the project.

## Where it stands (2026-09-21)

**The theses are the priority** (Moaz, 2026-09-21). Measured in Word, all 8
regression files:

    nothing lost     100.0%   <- the hard gate, never broken
    words in order    98.8%
    right page        69.4%   <- goal: >90%   (64.4% yesterday, Word)
    page inflation     1.00x  <- page counts exact, all 8

On 24 unseen files (the 30-file sample, six over 60 pages skipped), Word:

    nothing lost     100.0%
    words in order    67.6%
    right page        31.5%

Every one of the 24 came out IDENTICAL before and after today's two fixes -
none has a boxed page number or a picture-collage title page. Safe, but not
evidence they generalise; `z21358439` (43 -> 37 pages) is the only unseen
file they have been shown to help. The old 26.7% / 1.46x were LibreOffice.

All 14 test suites pass, rendering through Word. `PYTHONUTF8=1` is needed on
Windows. Committed locally; not yet pushed.

**Word is the only renderer** since 2026-09-21. **Runs skip files over 60
pages** (`--max-pages`, Moaz's call: no more long waits); a regression run
takes under two minutes.

**The Arabic lam-alef fix is ON by default since 2026-09-22** (N3a). It was
parked after breaking the gate on unseen files - `FLAGS.md` 20, now closed.

**Run `python -m harness.env` before trusting any number.** It reports the Word
version, which Arabic faces are installed, and whether the Arabic fix was on.
Without the document's own face Word picks a wider one, so text overflows and
the converter takes the blame.

## Decisions (settled 2026-09-21)

Moaz: reorder backwards text, warn on untrustworthy numbers, and fix the
lam-alef spelling (`FLAGS.md` 22). Kept below for the reasoning.

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

## New direction, 2026-09-21 — this replaces the order below

Moaz's call after `update.md`: stop fixing file by file; build a way to grade
each feature, then fix in order of how often each problem occurs. Right page
becomes a safety check, not the goal. The goal is a Word file you can edit
straight away: every word there and spelled right, built with real headings,
footnotes, lists and tables, and honest about what it could not do.

**Checkpoint A is done** (`PLAN.md`): Word's own PDF opening fails the theses
completely and the backwards-stored files too, so we keep building. It also
showed our checker cannot see misspelled Arabic (`FLAGS.md` 22).

In order:

- **N1. DONE.** Moaz, 2026-09-21: **reorder** backwards text, **fix** the
  lam-alef spelling, **warn** on untrustworthy numbers. Scope written into
  `PLAN.md` ("Scope"). Building the reorder and spelling fixes waits for N3,
  so they can be checked by something that does not share our extractor.
- **N2. DONE (2026-09-21).** `python -m harness.answerkey --set dev` (and
  `--set regression`). Baseline and what it found in `PLAN.md` ("The answer
  key"). Run it after every structural change, beside the gate.
- **N2a. DONE (2026-09-21).** `reader.read_labels`. Headings 31% -> 98%,
  lists 31% -> 100% right, gate held at 100%. Write-up in `PLAN.md` ("N2a").
- **N2b. DONE (2026-09-21).** Footnotes 6% -> 74% on the dev files, real
  Word endnotes, and Moaz's `الفصل الثالث` notes back at the foot of the page.
  Write-up in `PLAN.md` ("N2b"). Left: notes not starting with their number,
  full-size "9 - ... 10 -" numbering, and the (34)/(35) notes becoming real
  Word footnotes though the page never cites them.
- **N2c. DONE (2026-09-22).** The shrinking loop now sees a page that spills
  only pictures onto a wordless page. `z21760107` 35 -> 21 pages (of 19),
  small files' right page 52.0% -> 54.4%, theses unchanged, gate 100%.
  Write-up in `PLAN.md` ("N2c"). Left on `z21760107`: its title-page table
  has a column a few words wide, so the title takes two pages and every page
  after is one late - a tables item.
- Seen on the way, not yet counted: table cell text stored backwards on
  `z21760107` (FLAGS 12 was closed for another file), the journal logo drawn
  twice on its first page.
- Tables are the largest gap left on the scorecard: 47,132 letters of cells
  come out as paragraphs, and 16,036 are extra - tables written twice.
- **N3. DONE (2026-09-21).** `python -m harness.spelling`. Word's own PDF
  reading as a word list. On 24 unseen files: 1.2% of words lam-alef
  misspelled (11 of 13 readable files), two files almost wholly display-form
  glyphs, backwards files 35% provably backwards - and our output matches
  the gate's reference on every count, so the gate sees none of it. Write-up
  in `PLAN.md` ("N3").
- **N3a. DONE (2026-09-22).** The lam-alef repair, on by default. Lam-alef
  misspellings 1.2% -> 0.1% of words on the 24 unseen files, gate 100% there
  and on the theses, nothing else moved. The old 20% "loss" was the two
  sides repairing in different orders. Write-up in `PLAN.md` ("N3a").
  Left: `z22246498` (over 60 pages, not in the sample) had ~290 more words
  backwards in an unrecorded older output - check it with the repair on.
- **Seen 2026-09-22, looking at `z22110258` p.38 (not yet counted):** a
  sentence ending in a note number is printed twice - once in its paragraph
  with the number now a real footnote reference, once again at the page
  foot as plain text ending "1". Likely backfill: the sentence with "1" is
  not found once the "1" became a note, so it is added again. Same page: its
  three notes merged into note 1; the running header sits in the body on
  every page; "في" comes out "يف" and "المعلومات" as "املعلومات" (other
  ligatures stored backwards - lam-meem, and ya-fa), visible on every line.
- **N3a+. DONE (2026-09-22): other backwards ligatures** (في, المجتمع,
  التي). Confirmed words 81.6% -> 84.1% on the small readable files, one
  file 77.7% -> 88.5%, gate 100%. Write-up in `PLAN.md` ("Other ligatures").
  Right page read Word's own backwards ligatures on OUR side and the stored
  misspellings on the original's; both are now repaired (`PLAN.md`
  caveat 0). Same output re-scored: small unseen 30.6% -> 35.2%, theses
  68.2% -> 73.1%. Older right-page numbers are not comparable.
- **N3b. DONE (2026-09-22), not as planned.** The backwards files were
  scans (46 of 52); refused now, Moaz's call (`convert/scan.py`). No other
  digital file is backwards except `z21889411` (LaTeX, 130 pages), parked.
  Averages jump because scans left them - not comparable with before.
  Write-up in `PLAN.md` ("N3b"). New: garbled fonts, FLAGS 23.
- **FLAGS 23. DONE where the font is installed (2026-09-22).** Fonts that
  name the wrong letters are read by their shapes: 75 of 233 corpus files
  touched, `z20763272` 3,371 words recovered, gate 100%, theses unchanged
  but for an instrument change. Write-up in `PLAN.md` ("FLAGS 23"). Left:
  fonts not installed (FLAGS 23), and no check but looking.
- **Warn when a font is not installed** (Moaz, 2026-09-22): name the font,
  say to install it and convert again. Warn only where the text looks wrong,
  not for every missing font - see FLAGS 23.
- **N3c. DONE (2026-09-22).** Display shapes folded to letters: four small
  files from 3-34% confirmed words to 80-91%, gate 100%, theses unchanged.
  Write-up in `PLAN.md` ("N3c"). Found: `z19740548` (20 pages) is partly
  stored backwards - the short example for a line reorder, if wanted.
- ~~N3b. Build the reorder of backwards files~~ (FLAGS 1), judged the same
  way: the 11 backwards files' 35% backwards / 14% confirmed should swap
  (same Word cache, or the lexicon differs).
- **N3c. Display-form glyphs** (`z21508463`, `z21761968`): fold to ordinary
  letters (Unicode NFKC does it) - a scope question for Moaz only if the
  fold breaks something.
- **N4. DONE (2026-09-22).** 49 random pages looked at: 110 defects, every
  page has one. Count and method in `PLAN.md` ("N4"); log in
  `out/work/n4/defects.json`.
- **N5. Fix from the top of the N4 count.** Order agreed with Moaz
  2026-09-22. Each step: fix, tests, small-file eval + theses, gate 100%,
  and look at the N4 pages it touched.
  - **N5a. Look of the theses** - DONE 2026-09-22 (PLAN "N5a"). The body
    font by the letters each font draws, under the name Word knows it by;
    ﷺ and رضي الله عنه read and written; digits shown as the original
    showed them. Left: page numbers stay in the reader's setting (Word
    cannot be told), and FLAGS 24 - four small files losing text since
    before this - to trace next.
  - **FLAGS 24** - looked at 2026-09-22: none of the four files loses a
    word. Left: a word split where PyMuPDF cuts a line (real, ours), and
    two things the gate cannot see (Word's own note numbers, and its own
    backwards reading). Four fixes tried and reverted - see FLAGS 24 before
    trying a fifth.
  - **N5b. Headers, footers, page numbers** - DONE 2026-09-22 (PLAN "N5b").
    Every repeating piece lifted, even/odd headers, page numbers by the
    number that follows the page, header bands found as tables lifted.
    Right page 57.5 -> 60.0%, 8 files better, 0 worse, theses unchanged.
    Left: text that is not text in the PDF (`z21763864`), page numbers in a
    broken font (`z19799068`), header banners photographed with their text
    (not drawn), alternating footer pictures drawn on every page.
  - **TEXT FIRST (Moaz, 2026-09-22).** Accuracy against the page comes
    before the look (FLAGS 25). DONE 2026-09-23: page-truth score
    (`harness/truth.py`), OCR settles disputed font shapes
    (`convert/witness.py`), duplicate copies stopped (N5f's cause on
    `z21762915`). 2026-09-23: the gate asks the page (FLAGS 25); split
    pieces joined (12 better, 0 worse). Left, by size: spaces Word stores
    inside words (most split words - joined by the letters' shapes
    2026-09-23, 24 files better, 0 worse; spaces after ا د ذ ر ز و and words the page draws broken joined by where
the space is drawn 2026-09-23, quick run 7.2 -> 6.1% wrong),
    letters in the wrong order (22% of wrong words), `z20397518` alone
    (23% of them), files with no installed font (`z21751977`). DONE
    2026-09-23: the article title dropped as a header band's copy (PLAN);
    wrong-order pairs keyed with a neighbour (6 better, 0 worse); footer
    issue printed once. DONE 2026-09-23: the stretching stroke and spaces
    stored as letters (`z20397518` wrong 54 -> 8%, `z20276145` 18 -> 7%);
    the gate's page check asks of whole words (PLAN "What the remaining
    wrong words are"). Left, by that breakdown (about 10 points ours, 3.6
    the OCR's): words not near any page word, pieces and run-together words
    (punctuation inside words, N5c), letters in another order (whole words
    reversed were table cells - FIXED 2026-09-23, 300 cells; امل for الم
    FIXED 2026-09-23 by the shared edge (PLAN); left: `z21763864`, whose
    widths are not trusted, and 81 short cells), numbers (CHECKED
    2026-09-23: 272 of 336 unconfirmed numbers are the OCR misreading; no
    fix - PLAN "Words cut between touching pieces"). Words cut between two
    touching pieces (التأ هيلي) DONE 2026-09-23 by the letters either side.
  - **Ask the user to install a missing font (Moaz, 2026-09-23).** Before
    converting, name the fonts the PDF uses that are not installed and
    offer to wait while the user installs them: several repairs read the
    installed font, and Word lays out the page with it. The converter must
    still work without them. Needs: the list of missing fonts per file
    (`glyphs._path` finds a font by PostScript name, family name, or a name
    Word cut at 24 characters), a plain message, and where each font can
    be had.
  - **N5c. Punctuation and full stops** - DONE for Arabic lines
    2026-09-23, third attempt (`convert/order.py`, PLAN "third attempt"):
    every reading of the page goes through one function. Lines with
    digits or Latin DONE 2026-09-23 (`_order_mixed`: marks, and spaces and
    brackets stranded at the line's end); English lines with Arabic words
    left alone. Symbol's and Wingdings' dashes and bullets as real
    characters, not boxes, DONE 2026-09-23. Left: brackets on mixed lines
    where a word is next to them (اختبار فيشر ( لنموذج).
    Earlier notes: order them by where they are
    drawn: العرا .ق, ،دراسة, 2 . 11 . (15 pages, 9 files). Careful: the
    last attempt broke DVB-S (N3a) - tests first.
    Second attempt 2026-09-23 (text map, Arabic lines only) REVERTED: the
    gate fell on two files, words in order on `عن بعد` 100 -> 66% (PLAN).
    Needs a fix that stays inside one word, or one applied to the
    characters before either side extracts.
  - **N5d. Footnotes and endnotes** - notes as body text, the list inside a
    note escaping (`الفصل الثالث`). Endnotes: Moaz chose **real Word
    endnotes, numbered 1, 2, 3 like the original** (not xxv, xxvi).
  - **N5e. Tables** - written twice, columns not mirrored, invented tables
    from a reference list, squeezed columns, shaded boxes as grids.
  - **N5f. Pages written twice** (`z21762915`, 23 -> 39 pages). Cause
    found 2026-09-23: the backfill compared repaired text with unrepaired
    (PLAN "The page as the reference"); `z21762915` now 24 pages.
  - Then: headings/lists merged, bold/italic/underline, overlaid pictures
    (the `الفصل الثالث` box: the box alone, at its size), letters.
- **N6. Try PyMuPDF-Layout** on the label-stripped copies only; keep it only
  if it beats our rules on the N2 scorecard.

## Tasks, in the order worth doing (before 2026-09-21)

**Superseded by the list above.** Kept for the detail of each item.

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

**A2. DONE (2026-09-21) - 30.1% -> 69.6%, 16 pages -> 16, every page on its
own number.** The spurious page was the title page: 26 overlapping pictures
(frame, crest, title lines) stacked one under another took two pages. The first
page is now photographed whole when it holds nothing but pictures - see
`reader._collage` and `FLAGS.md` 21 for what that trades. The same rule caught
every chapter's title page too, and they are better for it: the old output
showed each heading TWICE and lost the rounded frame. Found by looking.
Regression right page 64.4% -> 69.4%; no other file's page score moved.

Original diagnosis, kept for the record: 33.7% where its
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

    .venv/Scripts/python -m harness.drift "corpus/مقدمة البحث.pdf" <our rebuilt pdf>

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

**A13. DONE (2026-09-21).** Every page of all five chapters now prints the
original's page number, title pages included - checked page by page against
the source. Three faults, found in turn:

- Word marks a page number as page furniture, so it is absent from the
  structure labels the theses are read from. `reader._page_numbers` takes it
  from the text layer when an edge carries a lone number on half the pages.
- A title page's number is the only text on its page, so it was both first
  and last there and got filed as a header. Position now breaks the tie.
- Keeping it exposed a sliver of body text under every running header: each
  copy of the header is photographed off its own page and most catch the tops
  of the line beneath. `_mark_edge_ink` measures ink along each copy's top and
  bottom edge and the header uses the cleanest. Three attempts to remove the
  intruder before photographing failed - these files draw their text as
  glyphs that do not decode, so neither "remove text" nor "remove pictures"
  touches it.

No score moved; none can see page numbers. Found and checked by looking.

**A14. NEW - page numbers print as 48, the original shows ٤٨.** The PDF stores
the Western digits and only DRAWS them Arabic-Indic. Word's PAGE field shows
Western digits. Likely a field switch or the paragraph's language/numeral
setting; verify in Word before choosing.

Original note: **the theses print no page numbers.** Found while
looking at A2. Every page of `الفصل الخامس المبحث الثالث` in our output ends
without its number, and did yesterday too - not caused by A2 or C3. Likely:
the number is an untagged artifact, the tag route never sees it, so
`_running_text` has nothing to turn into a PAGE field. Check across all six
chapters before fixing. The page-number box picture (one shared object, xref 8)
may be drawn in the footer with nothing in it.

### C. The Windows machine with Word

Set up 2026-09-20 as a VM: Python 3.13, the full corpus restored and verified
against `out/split.json`, and Office 16.

**C2. DONE (2026-09-20).** `harness/word.py` renders through real Word over
COM. Since 2026-09-21 it is the only renderer, `fit.py` included; LibreOffice
has been removed. Word scores are **not comparable** to older LibreOffice ones.

**C1. Ready to answer, not yet answered.** The VM has Simplified Arabic,
Traditional Arabic and Sakkal Majalla installed, so a Word run there renders
with the documents' own faces and nothing substituted — the first machine in
the project that can. What is left is to record one regression run on it and
~~compare page counts against a LibreOffice run of the same code~~ - there is
no LibreOffice any more. The question is now simply: rendering in Word, does
`fit.py` shrink anything, and on which files? If it barely does, the old
shrinking was LibreOffice's fonts. `FLAGS.md` 6.

**C3. DONE (2026-09-21).** `z21358439` 43 pages -> 37, matching the original;
the number now appears once, in the footer. The box was a picture, not vector
art as recorded, with a separate copy on every page - so grouping by source
object never matched. Furniture is now also grouped by position and size, and
a photographed picture with page text inside it is lifted without being drawn.
The box outline itself is lost. `FLAGS.md` 18.

Original note: **the page-number box is printed twice.** Found immediately on the
first Word comparison. A boxed page number is rasterised into the body AND
written as a `PAGE` field in the footer, so the reader sees it twice and the
picture costs a line of every page. 37 pages → 43 on `z21358439.pdf`. No score
shows it. `FLAGS.md` 18.

**C4. DONE (2026-09-20).** 8-file regression baseline recorded in Word with
its environment: right page **64.4%**, gate 100%, words 98.8%, pages 1.00x.
`out/runs/2026-09-20-regression-word-*`. This replaces 68.8% (LibreOffice).

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

    export PYTHONUTF8=1                                   # else Arabic output crashes on Windows
    .venv/Scripts/python -m harness.env                    # check the environment first
    .venv/Scripts/python -m harness.eval --set regression --label what-changed
    .venv/Scripts/python -m harness.eval --n 30 --label what-changed
    for t in harness/test_*.py; do .venv/Scripts/python -m harness.$(basename $t .py); done

`QIRTAS_ARABIC_FIX=off` turns the geometric lam-alef repair (on by default) off on both sides
at once, for measuring it against its own absence. `harness.env` records it.

Every eval run records itself in `out/runs/<date>-<set>-<label>/` with the
scores, the per-file rows and the environment. Pass `--label`; a run nobody can
identify later is a run nobody can compare.

Finding out WHERE a file is wrong, which no score tells you:

    .venv/Scripts/python -m harness.drift original.pdf rebuilt.pdf
    .venv/Scripts/python -m harness.look  original.pdf rebuilt.pdf --pages 4 --align
    .venv/Scripts/python -m harness.digits --set dev

`drift` says whether a bad score is ONE spurious page (a constant offset, worth
chasing) or content genuinely overflowing (a growing one). `look` puts the two
pages side by side — use `--align` whenever the page count moved. `digits`
finds files that display one number and store another.

Rendering is Word only, over COM, so this runs on Windows with Office
installed. The holdout set is paused at Moaz's request.

## Deeper reading

- `PLAN.md` — full history, every measurement trap, the complete unfinished list
- `README.md` — setup, commands, what the three scores mean
- `RESEARCH.md` — what was established about the problem space; don't redo it
