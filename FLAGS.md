# Qirtas — open flags

Things that need a decision, or that could quietly make the work wrong. Not
tasks (see `TASKS.md`) and not history (see `PLAN.md`).

Each entry says what it is, why it matters, and what would close it.

---

## 1. A third of the corpus produces unreadable output, and the score says 99%

**Status: CLOSED 2026-09-22 (TASKS N3b).** Premise was wrong: the files are
mostly SCANS, now refused (Moaz: "refuse scans, fix the few"). Of digital
files, one is really backwards - `z21889411`, LaTeX, reversed line by line,
130 pages - parked until a short example exists. (Found with N3c: `z19740548`,
20 pages, is partly backwards once its display shapes are folded.) Details in `PLAN.md` "N3b".

**2026-09-22, starting N3b.** Counting function words against their
reversals on the first pages of every corpus file with Arabic text (156):
52 are stored backwards, and **46 of those 52 are scanned pages** - a photo
of a newspaper clipping with machine-read (OCRmyPDF) text laid invisibly on
top. Only 6 are digital (Word, one InDesign) - and looked at, none of the
6 is really backwards (below). "Typically LaTeX
output" below was never checked and is wrong for this corpus.

Scans are recognisable from the file alone, with nothing in between on the
files checked: every character invisible, over a picture covering 97-100% of
the page; digital files have no invisible text and pictures under 3%.

Scanned PDFs are out of scope ("detect and refuse", `CLAUDE.md`, and the
Scope in `PLAN.md`), and their machine-read text is noisy even read in the
right direction. So the decision "reorder" was taken about files that are
mostly ones the project already refuses. Moaz, 2026-09-22: refuse the scans,
fix the few digital ones. Looked at, the "few" were not backwards at all:
`z21763864`, `z21764410`, `z21750616`, `z20752227` read forward - "يف", the
broken في ligature, is its own reversal of في and fooled the count - and
`z21764814`, `z21760325` are garbled fonts (FLAGS 23).

Some Arabic PDFs — typically LaTeX output — store their character stream
already reversed. The page displays perfectly; the text underneath runs
backwards. We reproduce it faithfully, Word applies right-to-left a second
time, and the result is unreadable.

**The scorer is structurally blind to it.** Our reversed output is compared
against the same reversed source, so they agree.

    z21889411.pdf    text 99.9%, pages 130 -> 130
                     called the best pagination result in the project
                     not one word of its output is readable

    56 of 172 corpus files (32.6%) are stored this way
    7 of 20 such holdout files score >=95% text, two exactly 100%

Detection is cheap and already prototyped: count common function words against
their reversals; the two cases separate by an order of magnitude.

**The decision is not technical.** Reorder the text and risk mangling documents
that are partly correct, or refuse such files the way `z22244578.pdf` is
refused. Either changes what Qirtas promises.

*Does not affect Moaz's own files* — they are the other kind.

**Closes when:** Moaz chooses reorder or refuse, and the scorer can tell the
two cases apart.

---

## 2. "Nothing lost 100%" has a known exception, parked in the holdout

**Status: true as stated, but easy to over-read.**

The gate reports 100% across the dev set and the regression set. The one file with
verified real loss — `z21312494.pdf`, nine words of author names and
affiliations across ten of its 432 pages, scoring 99.80% — is in the **holdout
set**, which is paused at Moaz's request.

So the headline is a claim about what we measure, while a known loss sits in
what we don't. Say "100% on the dev and regression sets", not "100%".

**Closes when:** the nine words are recovered, or the holdout is unpaused and
the number is restated to include it.

---

## 3. Scores are not comparable between machines

**Status: instrumented, older numbers still suspect.**

The office machine scores **61.4%** on the regression set where `PLAN.md`
records **49%** for the same code. Almost certainly the Arabic font
substitutions — installed at the office, probably not at home. Without them
everything falls back to Noto Sans Arabic, which is wider, so text overflows
and the converter takes the blame.

Every eval run now prints its environment, warns when substitutions are
missing, and stores the fingerprint with the results. **Numbers recorded before
that carry no environment and cannot be compared to new ones.**

This is the same failure as the corpus drift — the thing being measured moved,
and nothing said so.

**Closes when:** the recorded baselines are re-measured on a known environment,
or explicitly marked as environment-unknown.

---

## 4. The only path back to the corpus has never been run

**Status: untested, single point of failure.**

`--from-manifest` re-downloads the 225 Zenodo records exactly. It has been
verified to parse and its CLI works. **It has never been run end-to-end against
Zenodo.**

It is now the only thing standing between a fresh checkout and 567MB of corpus,
and it should be tested *while the real corpus still exists to compare
against* — not at the moment it is needed.

**Closes when:** it is run on a machine that already has the corpus, and the
restored set matches.

---

## 5. `corpus/*.pdf` cannot be recovered by anything

**Status: needs a manual backup.**

Moaz's 8 thesis chapters, 37MB. Not in the repo — they are someone else's
unpublished work. No command restores them. They are the regression set;
without them there is no measuring the thing this project was built for.

**Closes when:** they are backed up somewhere Moaz controls.

---

## 6. We may be shrinking text to fix overflow that does not exist

**Status: unverifiable without Word. Could be actively harming output.**

`convert/fit.py` detects page overflow by rendering through LibreOffice, which
lacks the fonts these documents ask for and substitutes wider ones. Real Word
on Windows has those fonts.

So we may be reducing font sizes to fix spill that only exists in the measuring
tool — making the document worse for the user to make a number better.

**PART DONE 2026-09-20. Word can now render** - `harness/word.py` drives real
Word over COM, and `QIRTAS_RENDERER=word` routes the whole harness, `fit.py`
included, through it. The Windows VM exists for this.

**The fonts are there too.** The three faces the corpus actually asks for are
installed on that machine, from the Windows `Language.Fonts.Arab` capability:

    Simplified Arabic    -> Simplified Arabic (TrueType)
    Traditional Arabic   -> Traditional Arabic (TrueType)
    Sakkal Majalla       -> Sakkal Majalla (TrueType)
    AGA Arabesque        -> NOT INSTALLED     third-party, not shipped
    Arabic Transparent   -> NOT INSTALLED     legacy, not shipped

**An earlier note here said none of them were installed. That was wrong**, and
it was `harness.env` that was wrong rather than the machine: `_fc_match` shells
out to fc-match, which does not exist on Windows, returns "?", and the old
check `not value.startswith("noto")` passed every face. A machine with no
Arabic fonts scored `substitutions_applied: true`, and the first attempt to fix
that read the registry in a context that could not see it. It now reads the
Windows font registry directly and reports `null` rather than `true` when it
cannot tell - **a check that cannot run must say so, not pass.** Eighth
instrument bug; third that was flattering us.

So this is the first machine in the project's life that can render these
documents in the application people actually open them in, with the fonts they
actually ask for.

**2026-09-21: LibreOffice has been removed; Word is the only renderer.** So
`fit.py` now measures spill in Word with the real fonts, and whatever
LibreOffice made it shrink before no longer happens. What is left is to record
how much it still shrinks in Word - if almost nothing, the old shrinking was
LibreOffice's fonts all along.

**Closes when:** a Word run records `fit.py`'s shrinking per file. See
`TASKS.md` C1.

---

## 18. The page-number box is rasterised into the body, so the number is printed twice

**CLOSED 2026-09-21.** 43 pages -> 37 on `z21358439`, matching the original.
The recorded diagnosis was half wrong: the box is not vector art but a small
PICTURE, stored as a separate object on every page (xref 76, 108, 122...), and
photographed off the page because it has a mask - which is why the number is
inside it. Grouping by position and size catches it now; a photographed
picture with page text inside is lifted but NOT drawn, so page 1's number is
not stamped on every page. The box outline is lost; the number survives as the
footer's PAGE field. Only groups found by position get that rule - applied to
source-object groups it stopped a running-header picture of `الفصل الخامس
المبحث الثالث` being drawn at all.

**Status: confirmed bug, ours, found by looking. Every page of every file that
boxes its page number.**

Found by putting our page next to the original with Word doing the rendering.
`z21358439.pdf` prints its page number inside a thin rectangle at the foot of
the page. The number is text; the box around it is vector drawing. We rasterise
the pair into a picture and place it **inline in the body**, and then ALSO
write the correct `PAGE` field into Word's footer:

    our rebuilt page 2, bottom third
      Rect(282.8, 702.7, 309.0, 723.3)   picture: "47" in a box   <- body
      y = 793.0                          text:    "47"            <- footer

    word/media/ holds 37 of them, one per page

So the reader sees 47 twice, and the picture costs a line of the text column on
every page - the exact mechanism flag 14 records for running TEXT, in a form
flag 14's fix cannot see. That file runs 37 pages to 43.

`_running_furniture` groups repeated decorations by `Block.origin`, which is
right for a decoration drawn from one shared source object (flag 15). A page
number is drawn afresh per page, so every copy has its own origin, nothing ever
groups, and it stays in the body.

**No score moved on it.** Words survive (the footer field is not the picture),
the gate holds, and `right page` reads the inflation as ordinary drift. Same
shape as flags 11 and 12: plainly wrong on the page, invisible to every number.

**Closes when:** furniture that repeats by POSITION and SIZE rather than by
source object is recognised too - or the page number specifically is, since a
box at the foot of every page holding nothing but a changing integer is not
content.

---

## 7. "Right page" is blind to tables and images

**Status: mitigated, not solved.**

A chemistry page that lost its table and both molecular diagrams scored **86%**,
because the score counts words and the words survived.

The structure score now counts tables and pictures, so the blindness is
*visible* — but only if read alongside. `right page` on its own still says
nothing about whether a page kept its non-text content.

**Closes when:** the structure counts are folded into the headline, or the
headline is never quoted alone.

---

## 8. Periodicals are detected, then averaged in anyway

**Status: produces a number true of neither class.**

`harness/doctype.py` tells periodicals from ordinary documents. The score then
averages both into one mean.

    ordinary documents   words 92.2%, right page 29.4%   n=61
    periodicals          words 42.0%, right page  8.8%   n=9

Periodicals score **below the ~13% chance floor** on right page. Mixing them in
drags the mean and hides both.

**Closes when:** multi-column layout is handled, or periodicals are put out of
scope in writing and excluded from the headline.

---

## 9. `fit.py` cannot rescue a picture-only page

**Status: known limitation, worked around.**

`_spilled()` matches output pages to original pages by shared words. A page
of nothing but pictures has none, so when it spills the extra wordless page is
blamed on the page before it, and the wrong page shrinks. Its fill factor has
to be right on the first pass — which is why `IMAGE_PAGE_FILL` is measured
(0.95 spilled, 0.88 fitted) rather than chosen.

2026-09-22 (N2c): the loop used to skip every wordless OUTPUT page too, so a
text page spilling only a footer picture onto the next page went unseen. That
part is fixed - see `PLAN.md` ("N2c"). Only picture-only ORIGINAL pages are
left.

**Closes when:** `_spilled()` can match pages by something other than words.

---

## 10. `مقدمة البحث` is an undiagnosed outlier

**CLOSED 2026-09-21.** The spurious page was the title page, 26 overlapping
pictures stacked into two pages; now photographed whole. 30.1% -> 69.6%, 16
pages -> 16. `TASKS.md` A2, `FLAGS.md` 21.

Was: diagnosed, not fixed.

33.7% where its siblings now reach 56–73%, and the only regression file still
running one page long (17 against 16). `harness.drift` shows one spurious page
among the first two (both picture-only) and a constant +1 on every page after
it - not overflow. Probably flag 9: `fit.py` cannot see a page with no words.

**Closes when:** the spurious page is gone and the file runs 16 pages.

---

## 11. Every page of the regression files carries a solid black bar

**Status: confirmed bug, ours, found by looking. Not visible to any score.**

The running header on `الفصل الثالث` renders as two solid black rectangles at
the top of **every page**. It is not a LibreOffice artifact: `word/media/
image1.png` inside the .docx is itself a solid black rectangle.

The cause is in extraction. The source decorations are 2x2 pixel, 1-bit,
indexed black/white images that carry their actual appearance in an **SMask**
(a transparency mask):

    <</Subtype/Image /Width 2 /Height 2
      /ColorSpace[/Indexed/DeviceRGB 1<000000FFFFFF>]
      /BitsPerComponent 1 /SMask 1001 0 R>>

We take the pixels and drop the mask, so what should be mostly transparent
becomes solid black - then gets stretched to the width of the header.

These are the same "2x2 pixel litter" `PLAN.md` item 4 says is filtered on
stored and drawn size. **The filter is not catching them on the running-header
path.**

**Not one file.** The same black block appears on `z21358439.pdf`, a wild
Zenodo thesis, so this is general rather than a quirk of the regression set.

Every score rates this file 100% on images (21/21 placements) and it is one of
the better files on right page. **A document with a black bar on every page is
not deliverable**, and nothing measures that.

**CLOSED 2026-09-20.** A picture whose appearance is partly in a transparency
mask is taken off the PAGE instead of decoded. The mask itself is a `/Matte`
pre-multiplied alpha running 0..64, not worth reconstructing. Fixing it broke
running-header grouping (which hashed the extracted file) until identity moved
to the source object. See `PLAN.md`.

---

## 12. Table cells come out backwards, and the score cannot see it

**Status: confirmed bug, ours, visible in the .docx. General, not one file.**

`z21011460.pdf`, read straight out of our own output:

    header row   المتغير المستقل | المتغير التابع | نوع العالقة | الفرضية   correct
    data row     ... | (Y) ةيلاملا قراوللأ قشمد قوس | هاجتلا ةيداحأ ةيببس   BACKWARDS

That second row should read `مؤشر سوق دمشق للأوراق المالية` and `سببية أحادية
الاتجاه`. A second table on the same file has `ةنسلا` for `السنة`.

`PLAN.md` item 3 records that cell text arrives reversed from the table finder
and is repaired by probing the page's correct text with a slice from the middle
of the cell. **That repair silently fails on some cells and nothing reports
it.** Where it fails the cell is written backwards and stays backwards.

The same page ALSO carries the table's contents a second time as ordinary
prose, so `_drop_text_inside_tables` missed it - almost certainly the same
exact-match brittleness that caused the duplicate-backfill bug (`PLAN.md`,
2026-09-20), since `العلاقة` extracts as `العالقة` on one side.

**CLOSED 2026-09-20.** Cells are read by clipping to the cell's own rectangle,
through the same extractor that gets body text right, with guards against
swallowing a neighbour and against an unchecked order. Flipping was the wrong
repair: it also flips the lam-alef ligature. `harness/test_tables.py`. See
`PLAN.md`.

---

## 13. A PDF can display one number and store another

**Status: DECIDED 2026-09-21 - warn, not refuse (Moaz). Not built yet.**

Not our bug. Our output is still wrong, and every score says 100%.

`z21358439.pdf` page 8 displays the 1951 Geneva Convention and its 1967
protocol. Its text layer stores **1901** and **1922**. Also `المادة 3` stored as
`المادة1`, and `10 دجنبر 1948` as `14 دجنبر 1900`.

We copy the text layer faithfully, so the Word file says 1901. The scorer
compares our 1901 against the source's 1901 and reports **text 100.0%**.

This is the same structural blindness as flag 1, in a new place: *the scorer
cannot see a fault that both sides share.* It is arguably worse than the
visual-order case, because reversed text is obviously broken to a reader while
a wrong date looks perfectly fine and is legally meaningful.

Unknown how widespread. Detecting it needs the rendered glyphs compared against
the stored characters, which nothing here does yet.

**MEASURED 2026-09-20, still needs Moaz's decision.** `harness/digits.py`
cross-examines the ToUnicode table against the embedded font's own cmap and
flags digits with no correct route. Seven candidates in 102 dev files; all
seven rendered and read; **4 verifiably wrong (3.9%)**.

A floor twice over: a wholly-permuted table is invisible to the test, and one
sample cannot clear a file - `z21358439` prints 2026 correctly on page 1 and
1951-as-1901 on page 8. Two of the four are flag 1 reaching the numbers: 2014
stored as 4102 is the run reversed.

**Decided: warn** (Moaz, 2026-09-21). The file converts; the user is told
which pages may carry wrong numbers. Move the `digits.py` check into the
converter and attach a message - small.

**Correcting, later.** The check that finds a lying entry also knows the
answer: the font says glyph 50 is a 5. A partial mismatch could be corrected to
the digit the page draws. Not yet: it cannot reach a wholly permuted table,
and a silent rewrite of numbers needs its own independent check first - the
same lesson as the spelling repair (FLAGS 20, 22).

---

## 14. Running headers and page numbers land in the body text

**Status: confirmed on every wild file looked at. Moaz raised this.**

The original puts the journal line at the top of the page and the page number
at the bottom. We emit both as ordinary paragraphs in the body:

    z20256558   "A. Abboud, Journal of Al-Wataniya..."  wraps onto TWO body lines
    z21358439   "مجلة مداولة سلسلة الأعداد..." first body line; page no. 53 last
    z21011460   journal line wraps onto two body lines; page no. 82 last

`PLAN.md` records that a repeating DECORATION is recognised as a running header
and moved into Word's header, which is why page counts stopped inflating on
Moaz's files. **That detection is for pictures only. Repeating TEXT is not
detected at all.**

Each one costs two or three lines of the text column on every page, which is
exactly the mechanism that caused the original pagination blow-up - and the
wild files still inflate: 17→23, 37→48, 33→43.

**CLOSED 2026-09-20.** `writer._running_text` lifts repeating text into Word's
header and footer, and the page number is a real `PAGE` field offset to the
original's first number. 30 dev files: right page 21.3% → 27.7%, 15 improved,
none worse, gate held. `text_of_docx` had to learn to read header and footer
text or the gate would have called it lost. See `PLAN.md`.

---

## 15. A fix can break a detector that keys on the wrong thing

**Status: fixed, recorded because the failure mode will recur.**

Running-header detection grouped repeating pictures by hashing the extracted
image FILE. That worked only because the same decoration happened to extract to
identical bytes on every page.

The moment masked images began being rendered off the page (flag 11),
anti-aliasing made every copy unique. 48 header pictures became 39 distinct
hashes, nothing reached the "repeats on most pages" threshold, the header went
back into the body, and `الفصل الرابع` fell **56.3% -> 28.4%** on right page
with two extra pages. Nothing in the image code looked wrong.

Identity now comes from `Block.origin`, the source PDF object - which is what
"the same decoration drawn forty times" actually means.

**The general lesson:** when something is identified by a hash of derived
output rather than by what it IS, any change upstream silently unmakes the
identification. Worth checking `_running_text`'s grouping (normalised text) and
`_drop_text_inside_tables`'s matching against the same question.

**Closes when:** nothing - recorded as a caution.

---

## 16. One wild file writes its text roughly twice

**Status: open, found while measuring something else. Not diagnosed.**

`z10442411.pdf` round-trips to **26,167 words from 15,398** - 1.70x - and 190
pages from 72. The hard gate says 100%, because the gate asks whether anything
went MISSING and duplication is the opposite fault. `right page` reads 14.1%
against a chance floor of ~13%, so for this file the score carries almost no
information.

Most likely the same exact-match brittleness as flags 12 and 15:
`_drop_text_inside_tables` matches a paragraph against the table's joined text
with `in`, and any extraction difference - a space, a repaired lam-alef - makes
the match fail and the page then carries the table's contents twice. The file
has a table on 60 of its 72 pages, which fits.

Worth checking how many other files inflate this way before treating it as one
file's problem. `words_out / words_orig` is already in every `results.json`, so
the count is a query, not a run.

**Closes when:** the duplication is traced, or shown to be confined to files we
refuse.

---

## 19. Correct list structure costs page alignment

*(Numbered 16 until 2026-09-21, which was already taken.)*

**Status: needs Moaz's decision. A trade, not a bug.**

Lists are now detected and kept apart, and the rendered page matches the
original's structure. The score went the other way:

    30 dev files          right page 28.6% -> 26.7%   (gate 100%, words 73.4%)
    z19851706             79.0% -> 37.2%   12 -> 13 pages
    z22110258             38.1% -> 21.3%   131 -> 134 pages

Fifty list items are fifty paragraphs and each ends in a partly-filled line.
The original fits the same fifty items in twelve pages; we need thirteen, and
one extra page early puts every later page out of step.

`fit.py` cannot recover it. Instrumented on `z19851706`: `ROUNDS = 4` stops the
loop with a page still spilling, and continuing hits `FLOOR = 0.70` at scale
0.734 and stops anyway. Recovering the page needs body text near half size -
flag 6 exactly.

Possibly, and unverified: the file asks for `SimplifiedArabic`, which is not
installed here. If the substitute is wider, part of the extra wrapping is the
measuring environment. An attempt to measure that was discarded as invalid.

**Closes when:** Moaz says whether a visibly correct list is worth 1.9 points
of a score that cannot see lists - or the question is settled in real Word.

---

## 17. The left-to-right control file has been deleted

**Status: the regression baseline has moved and nothing said so.**

`corpus/ödev.pdf` is gone. The regression set is 7 files, not 8.

    with it        68.8%
    without it     64.3%

Every remaining file scores **identically** to before, so the entire 4.5-point
move is the missing file. No code regressed.

Two reasons this matters beyond the number:

- It was the only **non-Arabic** file in the set, and the only standing check
  that left-to-right documents are not damaged by right-to-left work. Moaz has
  already caught that failure once.
- It scored 100% and was the only file that did.

This is the corpus-drift failure the project has been bitten by twice, in a
new place. `corpus/*.pdf` are not restorable by any command (flag 5).

**RESTORED 2026-09-20.** `corpus/ödev.pdf` came back with the rest of the
corpus when it was transferred onto the Windows machine - 1 page, 1,321
characters, matching what `RESEARCH.md` records. The regression set is 8 files
again.

**CLOSED 2026-09-20.** An 8-file regression run was recorded in Word:
`out/runs/2026-09-20-regression-word-*`, right page **64.4%**, gate 100%. That
is the baseline now. 68.8% was LibreOffice and is not comparable to it.

---

## 20. The Arabic lam-alef fix breaks the gate on unseen files

**Status: CLOSED 2026-09-22 - traced, fixed, ON by default (TASKS N3a).**
Parked at Moaz's call on 2026-09-21; switched back on under his decision to
fix the spelling (FLAGS 22), once it held the gate. Details in `PLAN.md`
("N3a"). Kept below for the history.

`convert/pdftext.py` (geometric lam-alef and punctuation repair) changed
nothing on the theses - its trust check excludes them by design - so the
unseen files were its first real test. 29 of the 30-file sample, Word, same
code, `QIRTAS_ARABIC_FIX` off then on:

    nothing lost     100.0% -> 98.3%   worst file z22110258 79.9%
    words in order    73.4% -> 70.4%
    right page        31.6% -> 31.5%
    15 files worse, none better

Not diagnosed. Real loss or a scorer disagreement is still open: the ORIGINAL
side's word counts changed between the runs, so the checker's repairs differ
from the converter's somewhere - the same shape as the fix's first failed
attempt (`PLAN.md`). Start with `z22110258`. Runs:
`out/runs/2026-09-20-dev-word-arabic-fix-off`, `2026-09-21-dev-word-arabic-fix-on`.

The repair was also ~100x slower than it needed to be (a regex per fragment,
recompiled per paragraph); fixed, verified byte-identical.

**Now judgeable (2026-09-21):** `harness/spelling.py` counts lam-alef
misspellings against Word's reading, which does not share our extractor.
A working repair shows as that share falling to ~0 (TASKS N3a).

**Traced (2026-09-22): not lost text.** The reader and the checker applied
the spelling repair and the glyph repair in opposite orders, and the spelling
repair is not safe to run twice. On z22110258 the checker got الاسلامية and
we got الاسالمية; the gate read every such sentence as lost. Also fixed on
the way: the map keyed on whitespace tokens (a note number glued to a word
stopped it), the punctuation half of the repair (it made DVB-S into D-VBS,
and is out), words stretched with alefs (z20276145), and a second glyph
signature that finds ~130 more broken words. After, repair on vs off:

    nothing lost      100% on 24 unseen files and the 8 theses
    lam-alef words    1.2% -> 0.1% (harness.spelling, not our extractor)
    words in order    68.9% -> 68.9%     right page 30.7% -> 30.8%

---

## 21. A photographed title page trades editability and a picture count

**Status: a trade made 2026-09-21, recorded for Moaz to overrule.**

When the first page is nothing but overlapping pictures (at most 15 real
words), it is photographed as one picture - A2. Three costs:

- **Two lines of `مقدمة البحث` stop being editable**: "بـحث مقدم لنيل درجة
  العالمية (الدكتوراه في القراءات)" and "بعنوان". They are real text among
  26 pictures. They are in the photo, not lost from the page - but not
  editable, and **the gate cannot see this**: they are not in the PDF's text
  layer, which is what the gate reads. Everything else on that page, and all
  of each chapter's title page, was pictures already.
- **"Pictures kept" falls** - 26 pictures become 1, and the score counts
  placements, not appearance. Chapters show 48 -> 37 and similar. Nothing
  visible was lost; the score cannot tell.
- ~~The title page loses its printed page number~~ - fixed 2026-09-21 on the
  chapters, whose photo stops above the number: the footer is copied onto the
  first page. On `مقدمة البحث` the number is inside the photo, so it shows but
  is not a field.

**Closes when:** Moaz accepts the trade, or asks for the title lines to stay
editable.

---

## 22. Our checker cannot see misspelled Arabic, because it reads the same text we do

**Status: DECIDED 2026-09-21 - fix the spelling (Moaz). Found at checkpoint A
(`PLAN.md`). Changes what "nothing lost" means.**

Every score compares our Word file against text extracted from the PDF by the
same library the converter uses. A fault in that extraction appears on both
sides and cancels out. Scanning the first 10 pages of every wild file:

    225 files   56 little or no text (scanned or picture-only)
               169 with Arabic text
                88 of those (52%) spell common words with lam-alef reversed:
                   خالل for خلال, نالحظ for نلاحظ, داللة for دلالة
                11 come out as presentation-form glyphs (ﻤ ﺔ): not searchable,
                   not spell-checkable, and on z21761968 in reverse word order

Our output carries every one of these into the Word file, and scores ~99%.
This is FLAGS 1 again in a different form: a flaw shared by the converter and
the checker is invisible to the checker. It is also why FLAGS 20 cannot be
judged by the gate: a correct spelling repair makes our output DIFFER from a
misspelled reference, which the gate reads as lost words.

The line in `CLAUDE.md`, "Do not rebuild Arabic text extraction. It works", is
true for recovering the words and false for spelling them right. It should be
reworded once Moaz agrees.

**Measured 2026-09-21 (TASKS N3, `harness/spelling.py`).** Against Word's own
reading of the same files: 1.2% of our words are lam-alef misspelled, on 11 of
13 readable unseen files; two files are almost wholly display-form glyphs; and
our output matches the gate's reference on every count to a tenth of a point.
The check has its own blind spot: ligatures other than lam-alef (lam-meem,
اجملتمع for المجتمع) cannot be told from Word's own swaps (رأس -> أرس), and
stay "unconfirmed". (2026-09-22: those ligatures are now repaired by their
trace on the page, not by this check - `PLAN.md` "Other ligatures". Ya-fa
is ambiguous there too: كيف and في leave the same trace.) What is left open is the repair (FLAGS 20), not the
measuring.

**Closes when:** the checker has a reference that does not share our
extractor - Word's PDF reading as a word-level second opinion, or original
.docx files - and the spelling rate is measured by it. (Word's structure
labels on tagged files are independent for STRUCTURE only; their text usually
comes from the same glyphs.)

---

## 23. Fonts that map letters to the wrong characters

**Status: repaired where the font is installed, 2026-09-22 (Moaz: "we need to
fix flag 23"). Open for fonts that are not installed.**

Some digital files decode to gibberish because the table from each drawn
shape to its letter is wrong: `z20375390` prints يعد السرطان مشكلة صحية
and stores يعد السررررررشكلة صحرررررررة. This note first said "there is no
right text inside the file to recover". **That was wrong.** The shapes are
right, each with its number in the font, and when the font is installed
here its own tables name every shape. `convert/glyphs.py` writes a corrected
table into a copy of the PDF; the converter and every score read that copy.
Write-up in `PLAN.md` ("FLAGS 23").

It is far wider than the three files first seen: 75 of 233 corpus files
have at least one wrong shape, among them 3,371 of 11,097 words of
`z20763272`. Word's OWN export does it too - on this machine it stores vowel
marks as blanks in our rebuilt PDFs - so the checker repairs both sides.

**Two things this leaves:**

- **Fonts not installed here** (AL-Mohanad, Amiri, 29LT Azer, Cairo) cannot
  be named, so their files stay gibberish, silently: `z21760325` and part of
  `z21764814`. A user's machine has fewer fonts than this one.
- **No independent check sees it.** Word's own reading (the spelling check,
  N3) reads through the same broken table - its reading of `z20763272` has
  كالسياسية five times and والسياسية never - so after the repair it marks
  the corrected words "unconfirmed". The gate reads the corrected copy on
  both sides. Only looking at the page verifies it; it was looked at on
  `z20393612`, `z20763272` and `z20375390`.

**Decided 2026-09-22 (Moaz): warn.** When a file uses a font that is not
installed, tell the user which font, and to install it and convert again.
Not built yet (TASKS). The hard part is knowing WHEN to warn: without the
font there is nothing to compare the table against, so a missing font alone
is not a fault - most files with one read fine.

**Closes when:** that warning is built, and something other than Word's
reading checks the repair.

