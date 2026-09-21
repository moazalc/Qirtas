# Qirtas - Arabic PDF back to Word: the plan

Last updated 2026-09-21.

## Picking this up again

State as of 2026-09-20: everything below is committed and pushed to `main`, all
twelve test suites pass, and the last full dev run gave nothing lost 100.0%,
words 79.37%, right page 21.75%.

On a machine that has not run this before, the PDFs are gitignored, so restore
them before anything else:

    .venv/bin/python -m harness.fetch_corpus --from-manifest --out corpus/wild

**`--from-manifest`, not a fresh `--n 120` search.** The search sorts by
`mostrecent` and returns whatever Zenodo holds that day; a different file set
means a different filename-hash split, and every number in this file becomes a
measurement of some other collection of documents. Nothing warns you.
`corpus/*.pdf` were never published and no command restores them — copy those
across by hand. `out/split.json` and `corpus/wild/manifest.jsonl` are committed
and need no rebuilding.

LibreOffice is found automatically now (`QIRTAS_SOFFICE` overrides), so the
old instruction to edit an absolute path no longer applies.

Run `python -m harness.env` before trusting any score. A machine without the
Arabic font substitutions falls back to Noto Sans Arabic, which is wider, so
text overflows and the converter takes the blame. The office machine scores
61.4% on the regression set against the 49% recorded further down this file for
the same code - almost certainly that, not the converter.

**`TASKS.md` is the short version of what follows** - start there, come back
here for the history.

Next in line, in the order they are worth doing:

1. **Decide the visual-order question** (see "Known unfinished" below). It is
   the largest known correctness problem, it affects a third of the corpus, and
   it needs a judgement about what this converter promises rather than a patch.
   Nothing further is worth measuring while a third of the files can score 99%
   and be unreadable.
2. **Periodicals**: detected, then averaged into a mean that is true of neither
   class. Handle multi-column layout, or put them out of scope in writing.
3. **Lists**: numbered items flatten into prose. Not detected at all yet.
4. **`z21312494.pdf`**: nine words genuinely missing, author names and
   affiliations, across ten of its 432 pages. The only remaining real loss.

Item 5 (is the shrinking fixing real spill, or LibreOffice font-substitution
spill?) and item 6 (render in Word rather than LibreOffice) both need Word, and
so need a Windows machine or VM. They are worth doing *after* the above, not
before: every defect currently known is verifiable straight from the .docx XML,
which is Word's own ground truth.

## The problem

People export a Word file to PDF, lose the Word file, and later need to edit it.
Converting the PDF back to Word mangles Arabic. Paid tools do not solve this
either — Adobe Acrobat does not support right-to-left PDF-to-Word export at all.

## What research already settled (don't redo this)

**Getting the Arabic text out is a solved problem.** A survey of 105 real Arabic
PDFs found the text came out clean and correctly ordered every time.

**The 6 sample files are a rare exception.** In those, the text is not in the
glyphs at all — it lives in the PDF's hidden accessibility labels. A second
extraction route covers them.

**Don't predict which route works — measure.** Two theories for what makes a
file need the fallback route (Word version, font encoding) were both tested and
disproved. Run both routes per file and keep whichever recovers more.

**The real gap is writing the Word file.** Every tool stops short here.
pdf2docx marked right-to-left won't-fix. html-to-docx silently strips every
right-to-left marker (verified: 0 occurrences of w:bidi, w:rtl, bidiVisual).
Our rough first attempt already produces correct right-to-left Arabic — that
part works. What's missing is structure and layout.

## Shape of the thing

    PDF → reader → description → writer → DOCX
                                    ↑
                          checker scores the result

Three separate parts, so each can be tested and improved alone.

- **reader** works out what's in the PDF: headings, paragraphs, footnotes, bold
- **description** a plain ordered list of what was found — not a Word file yet
- **writer** builds the Word file, handling all right-to-left details
- **checker** converts back to PDF and compares against the original

The reader uses two sources and combines them:

1. **Hidden labels.** ~76% of PDFs carry tags saying "this is a paragraph / list
   / footnote". Reliable where present, so trust them.
2. **Shapes on the page.** Where labels are missing, infer from font size,
   weight and position.

Neither alone is enough. Our files have some labels but no heading labels;
44% of wild files do have heading labels.

## Order of work

Ranked by expected effect on the two scores. Run the checker after each step.

1. Join lines into paragraphs  ← biggest win; also fixes the page-count blowup
2. Page setup: size, margins, real page breaks
3. Headings: find them, size and weight them
4. Footnotes: back to the bottom of the page
5. Bold, italic, size, colour
6. Paragraph shape: indents, spacing, alignment
7. Tables
8. Images, minus the invisible junk ones

## Explicitly not doing

**Not matching the original pixel for pixel.** Word and PDF lay text out
differently; chasing that burns weeks for nothing. The goal is a document that
looks like the original and can be *edited*. Different line breaks are fine.

**Not handling scanned PDFs.** Needs image recognition — a separate project.
Detect them and say so rather than producing garbage.

**Not going through HTML.** It would discard the right-to-left information,
which is the one thing already working. Useful only for browser previews later.

## Known risks

**Footnotes.** Word treats them specially. Getting them to sit at the bottom of
the page rather than floating in the text may cost more than its place in the
list suggests.

**Tables.** Only one of the eight sample files has one, so there is almost
nothing to learn from until more files arrive.

**The checker is a progress meter, not a grade.** Rebuilt PDFs are rendered by
LibreOffice, which lays out Arabic a little differently than Word, so the
scores will never reach 100% even when the output is right. Watch the trend.

## Progress

                                        no text lost   words   right page
    v0  text dumped, no structure            100%      96.6%       -
    v1  lines joined into paragraphs         100%      88.7%       -
    v2  page breaks, headings, footnotes     100%      97.6%      38%
    v3  measured layout, page alignment      100%      96.7%      65%
    v4  images, footnotes, page decoration   100%      98.3%      49%

    on 70 unseen files, the holdout opened once at the end (2026-09-19):
    ordinary documents  words 92.2%, right page 29.4%, n=61
    periodicals         words 42.0%, right page  8.8%, n=9

    the same measurement over the whole 102-file development set:
    ordinary documents  words 92.0%, right page 24.3%, n=78
    periodicals         words 38.2%, right page 12.4%, n=24

The v0-v3 rows are kept as they were recorded, but **they were measured with a
scorer that has since been found wrong twice** - see below. Do not compare them
against v4.

**No text lost is the hard gate. On 2026-09-19 it appeared to break on three
holdout files, and on investigation the gate was wrong about two of them.**

`loss.py` had always documented itself as ignoring order, and did not: it
looked for each sentence as one contiguous run, so moving a phrase within a
sentence reported the whole sentence as lost. Fixed in 9ff42e8. What the three
files actually were:

    file            gate said   truth
    z21762343.pdf     95.83%    100.00%. Nothing lost, ever. A French keyword
                                list on the title page had two phrases
                                swapped. With only 24 scoreable sentences one
                                false flag cost 4.17% - which made it the
                                worst-scoring file in the whole corpus.
    z20251974.pdf     99.19%     99.19%. Real, and tiny: a two-character
                                fragment "ne". Both neighbouring tokens
                                survive.
    z21312494.pdf     99.80%     99.86%. Real. Nine words genuinely absent -
                                author names and affiliations - across about
                                ten of its 432 pages.

**The file that looked worst had lost nothing, and the file that looked best
was the only one dropping words.** A gate that inverts the ranking of its own
failures cannot be used to decide what to fix, which is why it was fixed before
the remaining loss was chased.

What is genuinely open is `z21312494.pdf`: nine missing words, verified absent
with and against diacritics, in author-name and affiliation lines. Small and
localised rather than systemic. Across the whole 102-file dev set the gate now
holds on every file.

"Right page" means words landing on the matching page; unrelated documents
score ~13%, so it is measured against that floor, not against zero.

**The drop from 65% to 49% on right page is not a regression, and the jump to
98.3% on words is not an improvement.** Both are the scorer changing under us.
Two of its own bugs were found and fixed during v4, and both were flattering us:

  - It counted a repeated sentence once, so a document that repeats a phrase -
    which every one of these theses does, constantly - could not score 100% even
    against itself. Fixed in 999270d. **This is why `words` jumped.** The
    converter did not get better at keeping text; the ruler got fixed.
  - It counted pictures by *stored file* rather than by *placement*. Word stores
    one copy of a picture drawn forty times, so a file that dropped most of its
    pictures could still score 100% on images. Fixed in 67879bb.

The two runs that can be compared directly are `out/regression.json` (v3,
15:50) and `out/roundtrip.json` (v4, 18:31). **`page_score` is the one column
whose algorithm was untouched by either fix**, so only that column is a
like-for-like comparison:

    file                                  right page    words        pages   images
                                          v3    v4    v3*   v4      v4       v4
    ödev (Turkish, LTR control)          100   100   100   100     1->1     0/0
    عن بعد (short Arabic)                 92    92   100   100     1->1     1/1
    الفصل الثاني - انفرادات القراء         15    58    83   100    20->20   44/44
    مقدمة البحث                            26    31    89   100    16->17   21/21
    الفصل الرابع - مبحث أول                14    57    91    99    24->24   64/64
    الفصل الخامس المبحث الأول              15    47    88    98    25->26   66/66
    الفصل الخامس المبحث الثالث             14    48    85    97    18->19   48/48
    الفصل الثالث قراءات انفرادات           19    41    93    97    25->26   71/71

    weighted by words:                    17    49    88    98

    * v3 words measured with the broken scorer; not comparable to v4.

So the real v4 result is **right page 17% -> 49%**, which is the number to
quote. Pictures: **315 of 315 placements**, every file at 100%; the v3 figure
cannot be restated because the old scorer could not measure placements at all.
Two files now land on exactly the right page count and none is more than one
page out, where under v3 the worst was four.

## What works now

- correct right-to-left Arabic, correct letters, correct word order
- lines joined into real paragraphs
- headings found and styled (from heading labels, font size, or line shape)
- real Word footnotes, renumbering per page, not paragraphs pretending to be
  footnotes
- pictures: 315 of 315 placements across the corpus, including JPEGs Word's own
  library refuses to identify
- a decoration that repeats on most pages is recognised as a running header and
  put in the Word header, where it costs the text column nothing
- page size, margins, font size and line spacing measured off the original
- the document's own Arabic font carried through, not a substitute
- page breaks aligned to the original's pages

## Work list (rewritten 2026-09-17 after seeing wild output)

**Blocking - nothing can be measured honestly until these are done**

1. DONE. The check now locates each sentence of the original in the output and
   measures the longest run that stayed in order - O(n log n). A 418,000
   character document scores in 0.14s where the character comparison held a
   core at 97% for an hour. Validated: identical 100%, unrelated 0%, reversed
   25%, one sentence moved 75%, half the document 50% - see
   `harness/test_text_score.py`.
   The "identical 100%" claim was **false when first written**: the scorer found
   only the first occurrence of a repeated sentence, so a document that repeats
   a phrase scored below 100% against itself. Repeated-sentence cases are now
   part of the test.  Was: O(n-squared) on characters. It pinned a core at
   97% for an hour on a 72-page file and never finished. Everything else waits
   on this.
2. DONE. Scoring now counts tables and pictures.  Was: blind to tables and images. A chemistry page whose table and two
   molecular diagrams were dropped entirely scored 86%, because the score only
   counts words and the words survived. Count tables and figures in the
   original and check the output has them.

**Correctness - things that destroy documents**

3. Tables. DONE in part: detected, de-duplicated against body text, written as
   real Word tables with w:bidiVisual so columns mirror. 6/6 and 10/10 on the
   test files. Cell text arrives reversed from the table finder (it does not
   apply the logical ordering the text extractor does) and is repaired by
   probing the page's correct text with a slice from the middle of the cell.
   Column widths now hold: a table needs BOTH a fixed w:tblLayout and a real
   w:tblGrid; cell widths alone are ignored (this cost two failed attempts).
   Verified on 16 unseen files: 1/1, 2/2, 20/20, 103/103 - tables are general.
4. Images. DONE: 4/4, 9/9, 21/21 extracted and placed. Word's 2x2 pixel litter
   is filtered on both stored size and drawn size.
   Pictures now go into the table cell they sit in.
   The molecular structures turned out not to be images at all but VECTOR
   DRAWINGS, which is why nothing extracted them. Table cells that hold line
   art and no text are now rendered to a raster and placed in the cell.
   RESOLVED 2026-09-18, and it was two separate things, only one a real bug:
     - Mostly a **counting** error. The check counted files in `word/media/`
       against placements in the PDF. Word stores one copy of a picture drawn
       forty times, so ratios like 62->13 were measuring deduplication, not
       loss. Counting `<a:blip>` placements instead - and multiplying a header
       or footer picture by the page count, since Word draws it on every page -
       gives 315/315 across all eight files.
     - One **real** loss. `عن بعد.pdf` holds a bare DCT JPEG with no APP0/JFIF
       segment. python-docx identifies images by literal signature bytes and
       only accepts `JFIF` or `Exif` at offset 6, so it raised
       `UnrecognizedImageError` - which `_emit_image`'s bare `except` swallowed.
       Anything python-docx will not take is now re-rendered to PNG first.
   A chart's axis labels are still picked up as a table.
   The bare `except` that made the loss silent is gone. All three placement
   sites go through one `_place` helper which records (path, reason) on the
   model, and `write()` warns on stderr. It also turned out to be hiding a
   second defect: `_emit_image` added its paragraph *before* placing the
   picture, so a failure left an empty paragraph eating a line - the very thing
   the page-break comment warns about. A failed placement now removes its own
   paragraph. The corpus converts with zero drops, so 315/315 is now measured
   rather than inferred.

4b. DIRECTION IS NOW PER-BLOCK, NOT BLANKET. Everything used to be forced
   right-to-left, so an all-English chemistry table was mirrored and Latin
   paragraphs were flipped. Direction is a property of the content: each
   paragraph, each table and each cell is measured, and the section is set from
   the document as a whole.
5. Check that per-page shrinking is not harming real output. It detects
   overflow through LibreOffice, which lacks the fonts these documents ask for
   and substitutes wider ones. We may be shrinking text to fix spill that only
   exists in the measuring tool. Needs one run against real Word.

**Measurement**

6. Renderer-agnostic checking plus a Word render script for Windows and macOS.
   The user has both; Word is what readers will actually open the file in.
7. DONE. Amiri, Scheherazade New, Lateef, Cairo and Markazi installed to
   ~/.local/share/fonts/arabic, with fontconfig rules in
   ~/.config/fontconfig/conf.d/60-arabic-substitutes.conf mapping Simplified
   Arabic, Traditional Arabic, Sakkal Majalla, AGA Arabesque and Arabic
   Transparent onto them. Everything used to fall back to Noto Sans Arabic,
   which is wider, so text overflowed and the converter got the blame.
   Effect: مقدمة البحث 70% -> 80% on right page, z20266552 82% -> 85%, and
   both went to exactly the right page count.

**Fidelity**

8. Bold and italic inside a paragraph. DONE in the writer: each block carries a
   list of spans and each span becomes its own run.
   **But it is inert on 6 of the 8 corpus files.** Their Arabic glyphs expose
   almost no font information - one page with 1,305 Arabic characters yields 9
   spans covering 4 of them. The writer is ready; the reader cannot see the
   formatting to hand it over. Fixing that is a different job, in extraction.
9. Heading detection over-fires on any short line ending in a colon. DONE.
   The colon rule cannot just be deleted - it is the only thing that finds real
   sub-headings in theses that use no Word heading styles. Length does not
   separate the good from the bad: the shortest colon line in the corpus
   ("على قسمين:") is a sentence fragment, the longest is a real heading.
   Grammar does: a heading is a noun phrase, so no comma, no second colon, no
   leading connective particle, 60 characters at most. 80 headings -> 58, and
   all 22 dropped were checked by hand and are sentences.
10. Real Word footnotes. DONE. `convert/footnotes.py` hand-builds
    `word/footnotes.xml` plus the `[Content_Types].xml` override and the
    document relationship, then rewrites the saved .docx.
    Anchoring comes from the documents themselves: the note carries its number
    ("1- انظر") and the body carries the marker inline ("ابن مجاهد(2)").
    **373 of 399 notes anchor (93.5%)**, and every note written carries exactly
    one reference - refs and notes match per file. The remaining 26 have no
    findable marker and stay as plain paragraphs rather than being attached to
    the wrong sentence.
    Word and LibreOffice both number footnotes continuously by default, which
    renumbered page 3's first note as 5; `w:numRestart eachPage` fixes it.
    Note for whoever touches the checker next: footnote text lives in
    `footnotes.xml`, not `document.xml`. `text_of_docx` has to splice each
    page's notes in at its page break or the score reads them as lost text.

**Last**

11. DONE (2026-09-19). Opened the holdout once. **It generalised.** Against the
    development set, the unseen files are equal or better on every
    document-class statistic:

        class                  n    words   median   right page   >=95%
        dev  document         78    92.0%    99.0%       24.3%      73%
        holdout document      61    92.2%    99.1%       29.4%      77%
        dev  periodical       24    38.2%    32.8%       12.4%       8%
        holdout periodical     9    42.0%    32.6%        8.8%      11%

    (Dev figures are over all 102 usable development files, re-scored after the
    loss gate was fixed. Earlier drafts quoted a 30-file sample of them.)

    Rules overfit as readily as models do, so this was the question the split
    existed to answer, and the answer is that the eight files developed against
    did not become the only eight files this works on.

    Four things must be read alongside that:

      - **The hard gate appeared to break on three of these files, and was
        wrong about two of them** - see Progress above. Only `z21312494.pdf`
        loses text that matters, nine words on ten of 432 pages.
      - **Periodicals score 8.8% on right page, below the ~13% chance floor.**
        On newspaper layout this converter is worse than pairing two unrelated
        documents. `harness/doctype.py` detects them; nothing acts on it yet.
      - **The first run silently dropped three files.** They crashed on control
        characters XML cannot hold, `eval.py` caught it per file, and the
        average was quietly taken over the survivors. Fixed in 17d7a25; the
        re-run scores 70 files with nothing dropped. Both runs are kept
        (`out/eval_holdout.json`, `out/holdout_postfix.json`) and reported
        together, because looking at a holdout twice is only dishonest if you
        SELECT between the results. On the 68 files common to both, the fix
        moved nothing: words 85.4% -> 85.4%, right page 26.5% -> 26.5%.
      - **One file was excluded as unusable, and that is a real decision.**
        z22244578.pdf's fonts carry no usable ToUnicode map, so 117 of its 131
        pages extract as mojibake. Once the writer stopped crashing, that file
        would have entered the corpus and scored its nonsense against an
        equally nonsensical round-trip - a rising average caused by a broken
        file starting to pass. `harness/split.py` now judges the text layer and
        refuses such files with a stated reason. It caught a dev file too,
        z22245438.pdf, that had never been run, so the rule detects a class
        rather than the one file that happened to crash.

## Layout work, 2026-09-19

Prompted by rendering pages and looking at them rather than by any number. An
audit of a converted file found 239 bold runs, 87 justified paragraphs, 91
first-line indents — and **zero `w:pStyle`**.

12. DONE. **Reversed lam-alef ligatures repaired** (`convert/arabic.py`). Two
    unambiguous cases: a standalone ال, which cannot exist because the definite
    article is a prefix (773 occurrences, 37 of 40 files); and ا + أإآا + ل,
    because two alef forms cannot sit together (282 occurrences). Applied in
    the reader AND in the checker's `text_of` — it must be both, or our
    corrected output stops matching the still-mangled original it is scored
    against and a real fix reads as a regression.

    The two rules then competed. The reader and the checker extract through
    different pymupdf modes which disagree about where spaces fall, so one saw
    اآللف and the other ال آلف, and the same word came out الآلف on one side
    and لا آلف on the other. `z21763864.pdf` lost its hard gate at 98.89% until
    an ال followed by an alef form was excluded from the standalone rule.

13. DONE. **Headings are real Word headings** — `Heading 1`–`6` with explicit
    outline levels, so a table of contents and the navigation pane work. The
    style is applied first and our measured formatting re-asserted over it,
    because Word's Heading styles carry their own font, size, colour and
    **spacing**, and spacing is what `fit.py` depends on. Colour is stated
    outright: Word's Heading 1 is #2F5496, blue, and these documents are not.

14. DONE. **Left-to-right paragraphs are justified too.** The line read
    `align = LEFT if block.kind != HEADING else LEFT` — both arms identical, so
    the condition never did anything and every Latin-script paragraph came out
    ragged-right against a justified original.

Measured over all 102 dev files: nothing lost 100.0% (worst file 100.0%), words
79.37% against 79.34%, right page 21.75% against 21.47%. No file scored worse
than before; one improved 88.2% -> 93.0%.

## The duplicate-backfill bug, 2026-09-20

A1 was recorded as "images cost page alignment at full size; the shrink loop
stops at FLOOR = 0.70 and needs to reach about 0.5". **That diagnosis was
wrong, and the shrink loop was never the constraint.** Two things worth keeping:

`ROUNDS = 4` at `STEP = 0.94` caps the loop at 0.94^4 = 0.78, so `FLOOR = 0.70`
has never once been reached. It is unreachable code. Anyone planning to "raise
the floor" would have changed nothing.

What actually happened, found by instrumenting the loop rather than by reading
the note: on `الفصل الثالث` the loop shrank one page, then reported nothing
spilled - while the output was still 26 pages against 25. Mapping where each
page's words landed showed pages 0-4 correct and **every page from 5 on drifted
by exactly +1**. One spurious page early in the document was costing the whole
file: 29.0% on right page.

Output page 5 held four mangled tokens that duplicated text already on page 4.
The cause is `_backfill`, and it is the same space-sensitivity recorded in
caveat 1, now biting between the two READER routes rather than reader against
checker:

    tags route      ...ومنهاالشاذ      (ا ل ش)
    geometry route  ...ومنهالاشاذ      (ل ا ش)

The lam-alef repair is space-sensitive; the two routes disagree about where
spaces fall; so the repair fires on one route and not the other. `_backfill`
asked whether a sentence was already present with an exact substring test, got
"no" for text that was fully present, and added the whole paragraph again.
Five such duplicates on this file, two on another.

**Folding both letter orders onto one symbol does not work** - tried and
discarded. The two strings consume different pairs (`منها|الشاذ` against
`منه|الاشاذ`) and the misalignment cascades through the rest of the string.

The fix is `reader._present`: sample five fixed windows of 12 characters and
call the sentence present if 60% of them are found. Text that is genuinely
absent - the Quranic verse this function exists to recover - matches no window
at all, while text differing by a character or two still matches most.

    regression set          before   after
    nothing lost            100.0%   100.0%
    words in order           98.6%    98.8%
    right page               61.4%    68.8%
    page inflation           1.00x    1.00x

    الفصل الثالث             29.0%    72.6%    26 -> 25 pages
    الفصل الخامس الثالث      51.6%    68.4%    19 -> 18 pages

Four files moved -0.1 to -0.5, all inside the noise floor in caveat 8. On 30
dev files not tuned on: **no file moved beyond noise, and the gate held at
100.0% on every one**. All 12 suites pass; the case is pinned in
`harness/test_arabic.py`, next to the repair whose space-sensitivity causes it.

**`مقدمة البحث` is untouched by this** - still 17 pages against 16, still
33.7%. Whatever is wrong there is a different fault; see `FLAGS.md` 10.

## w:jc is logical, and every Arabic heading was on the wrong side, 2026-09-20

Raised by Moaz from a rendered page: "we need text on RTL not the opposite."

In OOXML `w:jc` values are **logical**. "left" means START and "right" means
END, and a right-to-left paragraph swaps which physical margin those are. So
`WD_ALIGN_PARAGRAPH.RIGHT` on an Arabic heading put it against the **left**
margin - the opposite of both the name and the intent.

Measured rather than reasoned about. One RTL paragraph rendered at each
setting, on a 612pt page:

    w:jc = right   -> x0 = 93     (LEFT margin)
    w:jc = left    -> x0 = 515    (RIGHT margin)
    w:jc = center  -> x0 = 306

On `z21011460.pdf` the heading `متغيرات البحث` sat 380pt from the right edge
where the original has it 89pt from the right edge. After the fix ours is at
x0 = 421 against the original's x0 = 421.2.

Two sites had it: headings in `_emit`, and table cells in `_emit_table`. Both
now use `ALIGN_START`, which is spelled `LEFT` and is correct in both
directions - start is the right margin in Arabic and the left margin in
English. The `if not rtl` branch for headings collapsed entirely.

**The test suite asserted the bug and passed.** `test_alignment.py` checked
`alignment == AL.RIGHT` for Arabic headings, which is exactly what the code
wrote, so the test confirmed we had written what we meant and said nothing
about where the text went. It now renders the page and measures which margin
the heading is against - the only form of this test that could have caught it.

**No score moved.** Regression 68.8% before and after; 30 dev files, nothing
beyond noise; gate 100% throughout. Headings are a small share of the words, so
`right page` cannot see this - and neither could anything else we measure. That
is the point: it was found by looking at a page, like the other large faults in
this file.

Verified through LibreOffice. This is ECMA-376 behaviour rather than a renderer
quirk, but it is unconfirmed in real Word - `FLAGS.md` 6.

## Running text goes to the header and footer, 2026-09-20

Raised by Moaz from a rendered page: the journal line "should be in the head
section of the document, same thing with the pagination".

`_running_furniture` already did this for PICTURES - which is why Moaz's own
files stopped inflating - but repeating TEXT was never detected, so the journal
line and the page number were emitted as ordinary body paragraphs, costing two
or three lines of every page's column. `_running_text` now handles text.

Three things had to be got right, and two of them were not obvious:

1. **The page number differs on every page**, so grouping by exact text finds
   nothing. Digits are replaced by a placeholder before grouping.

2. **Position cannot find the header, and the reason is circular.** The margins
   are measured FROM the content, and the running header is part of that
   content, so the column is drawn to include it and it never looks outside.
   The first attempt found every page number (clearly below the column) and not
   one journal line. Reading order is the fallback: first block on the page, or
   last. Repetition is what makes that safe - being first on the page is
   ordinary; being first with the same words every time is furniture.

3. **The tags route carries no coordinates for text at all** (geometry does),
   so a position-only rule would have worked on half the corpus.

A page number becomes a real `PAGE` field, not the literal digits, with
`w:pgNumType/@w:start` set so numbering begins where the original's did - page
9 of `z21011460` is printed 82, and a bare field would have said 10.

**The scorer had to change too, and this was the trap.** Header text lives in
`header1.xml`, not `document.xml`, so `text_of_docx` could not see it and the
hard gate would have reported perfectly good text as lost - the identical trap
footnotes had. Word DRAWS the header on every page and the original PDF's
extraction finds it once per page, so `text_of_docx` now emits it at every page
boundary. A PAGE field's cached number is skipped, or our "82" would be
compared against the original's 83, 84, 85.

That change is a no-op on any file with no header/footer text, so runs recorded
before it stay comparable.

    30 dev files                 before    after
    nothing lost                 100.0%    100.0%   (worst file 100.0%)
    words in order                73.0%     73.3%
    right page                    21.3%     27.7%
    page inflation                1.56x     1.46x

    15 files improved, 0 worse, 15 unchanged

    z22179435    28.1% -> 96.7%    29 -> 28 pages (orig 28)
    z21761968    11.9% -> 58.2%    25 -> 21 pages (orig 20)
    z19851706    36.8% -> 79.0%    14 -> 12 pages (orig 12)

The regression set is untouched at 68.8%: Moaz's files carry their running
header as a PICTURE, which was already handled.

## Tables, masked pictures, header size, and a number for the digits, 2026-09-20

### Table cells were written backwards, and flipping was the wrong repair

`_unreverse` flipped the string when the table finder returned visual order.
**Flipping is not the inverse of visual order**: it also flips the two
characters inside a lam-alef ligature, so `للأوراق` came back as `أللوارق`,
matched nothing on the page, and the cell was written backwards. Two of eight
cells on one table, silently.

Cells are now read by clipping to the cell's own rectangle, which goes through
the SAME extractor that gets body text right - so the order is right for the
same reason it is right everywhere else, and it agrees with the text the scorer
reads, which a flipped string never did.

Two guards, because a clip can go wrong in exactly two ways: it can swallow a
neighbouring cell (so it must be about as long as the table finder's reading),
and it must be in logical order (so a probe from it must be found forward in
the page text). **Character multisets were tried first and rejected**: the
lam-alef ligature expands to a different number of characters in the two
extraction modes, so identical content compares unequal, and one correct cell
in four was thrown away.

`harness/test_tables.py` is new. It tests the DECISION, not Arabic order - a
PDF built with `insert_textbox` stores presentation-form glyphs rather than the
logical characters a real Word export stores, so a synthetic page is not a
model of this bug. The first version of that test asserted against one and
failed on correct code.

### Black bars came from transparency masks, and the fix broke something else

`الفصل الثالث` carried its running header as 676x132 RGB images that are solid
black, with the actual Arabic in an 8-bit SMask. `z21358439` had the same.

Reconstructing the mask is not worth attempting: it is a `/Matte`
pre-multiplied alpha whose values run 0..64 rather than 0..255, and
`Pixmap(doc, xref)` does not apply it at all - it hands back the same solid
black with an alpha channel of 255. The picture is taken off the PAGE instead,
the same trick `render_vector_cells` already used for line art.

**Flatness alone was not a sufficient trigger**, which cost one attempt: the
second header image is a black box with a white border - 26 distinct colours -
whose text lives entirely in the mask. Having a mask is the trigger; flatness
is kept as a second one.

**That fix then broke the running-header detection**, which is worth recording
because the failure was invisible in the code and obvious in the numbers.
`_running_furniture` grouped repeated decorations by hashing the extracted
FILE. Rendering each copy off its own page makes every copy unique - 48 header
pictures became 39 distinct hashes, nothing grouped, the header went back into
the body, and `الفصل الرابع` fell **56.3% -> 28.4%** with two extra pages.
Identity now comes from the source object (`Block.origin`), which is what
"the same decoration" actually means.

### Header text used a guessed size

The journal line on `z21011460` is 8pt and drawn 332pt wide in a 378pt column.
Written at 0.8 x 12pt body it became 9.6pt, about 398pt, and wrapped onto a
second line the original never had. It now uses the block's own measured size.

    30 dev files              before    after
    nothing lost              100.0%    100.0%
    words in order             73.3%     73.4%
    right page                 27.7%     28.6%
    page inflation             1.46x     1.46x

    4 files improved, 2 worse. Best +24.6 (z19799524 38.5% -> 63.0%),
    worst -5.0 (z20375390). Regression set unchanged at 68.8%.

### A number for the wrong digits - and it is smaller than the tool first said

`harness/digits.py` is new. A PDF draws glyphs; its ToUnicode table claims what
they mean; when that table lies, extraction cannot tell. The embedded font
carries its own opinion in its cmap, so ask both.

**Three approaches were wrong before one worked**, all recorded in the tool:

1. "Two glyphs claiming the same digit" - came from a sloppy CMap read that
   paired hex tokens across entry boundaries. Properly parsed, the table is
   one to one.
2. "Digit glyphs should ascend with glyph id" - they need not; subsetters
   assign ids in order of first use. Flagged healthy files.
3. "Check every font" - in a simple font the code is the CHARACTER code (48 is
   "0" because that is ASCII), so comparing it to a glyph id disagrees on
   principle. Flagged most of the corpus. **Identity-H only.**

What works: flag a digit that has NO correct route - one reachable only through
an entry the font contradicts. A healthy file often carries spare entries that
disagree while the right one still exists.

**Then every candidate was rendered and read, because a structural test cannot
settle this:**

    z21358439   shows 1951   stores 1901   WRONG
    z19799068   shows 2014   stores 4102   WRONG
    z19799524   shows 2014   stores 4102   WRONG
    z21490618   shows 2019   stores 2112   WRONG
    z19773087   shows 1989   stores 1989   right where looked
    z20276145   shows 3059   stores 3059   right where looked
    z21813345   shows 2020   stores 2020   right where looked

**4 of 102 files (3.9%) carry verifiably wrong numbers.** A floor, twice over:
the test cannot see a wholly-permuted table, and **one sample cannot clear a
file** - `z21358439` prints 2026 correctly on page 1 and 1951-as-1901 on page
8. Two of the four are the visual-order problem reaching the numbers: 2014
stored as 4102 is the run reversed, not mis-identified.

## A page that begins with a table kept the table on the previous page, 2026-09-20

Found by reading `write()`, not by a score. A `w:tbl` cannot carry
`w:pageBreakBefore`, so the table branch emitted the table and then added a
trailing paragraph - and the break was put on that paragraph. It therefore
arrived AFTER the table, leaving a page that begins with a table stranded on
the page before, with everything on it one out of step.

The break now goes on the first paragraph of the table's first cell, which is
where a renderer looks to start a table on a new page. Confirmed by rendering,
not by reading the XML: the XML can only say what we wrote.

**It is not rare.** Counting pages whose first block after `_interleave` is a
table: 60 of the 72 pages of `z10442411.pdf`. Zero across Moaz's eight files,
which is why nothing ever showed it - and the regression set is unchanged at
68.8% for the same reason.

    30 dev files (seed 7)        before    after
    nothing lost                 100.0%    100.0%   (worst file 100.0%)
    words in order                73.4%     73.4%
    right page                    28.6%     28.5%
    page inflation                1.46x     1.42x

    4 files moved; page counts 797->787, 268->267, 10->9, 537->538

**No headline score improved, and that is the expected result.** `right page`
moved -0.04 points, inside the half-point of render noise. Page inflation is
the number that moved: the median file now needs 1.42x the original's pages
rather than 1.46x. The same shape as the heading-alignment fix - a defect that
is plainly wrong on the page and invisible to every metric we have.

`z10442411.pdf` was the wrong file to quote as evidence, and the run is kept
here as a caution: 202 -> 190 pages, `right page` 14.5% -> 14.1%. Its
pagination is dominated by something else - see `FLAGS.md` 16.

`harness/test_pagination.py` gained the case. It renders, because the first
version of the check asserted that the break must textually precede `<w:tbl>`,
which is an assertion about how the fix was written rather than about where
the table lands.

## Lists, 2026-09-20 - correct structure, and the score went DOWN

Bullets and numbered items came out as one run-on paragraph with the markers
stranded mid-line. Two causes.

**The line-joining rule asked whether a line ENDS like a finished sentence.**
In right-to-left text the terminating punctuation is frequently STORED at the
front: `تتمثل أساسا في:` extracts as `':وتتفرع عن هذه الإشكالية ... في'`, colon
at index 0. `endswith` never saw it, the line read as unfinished, and the
bullet list below was merged into it.

Checking BOTH ends of every line was the obvious fix and **was tried and
rejected**: it cost pages across the corpus (z20397518 12 -> 14) without being
needed for lists. The narrow rule does the job - a line that OPENS with a list
marker starts a new item however the line above ended.

**Nothing marked list items on the geometry route at all** - 0, against 8 to 53
paragraphs per file that plainly were. `detect_lists` runs AFTER
`detect_headings`, and the order is the whole trick: these documents number
their sections, so `1 . مقدمة` matches a list marker exactly as well as a
heading, and `detect_headings` only looks at paragraphs. Marking lists first
turned every numbered heading in `z21011460` into an unrecoverable list item.

The marker pattern was tightened twice. `* Corresponding author` (a footnote
marker on half the journal papers), `*******` (a divider), `[3] .` (a citation
fragment) and `1.5 متر` all matched earlier versions.

Indentation uses `left_indent`, which means START - the same logical/physical
trap as `w:jc`. Measured: in an RTL paragraph `left_indent` moves text 72pt off
the RIGHT margin, `right_indent` moves it nowhere visible. The old line set
`right_indent` "because this is RTL", which indented the far edge and left the
marker where it was.

### The uncomfortable part

    30 dev files              before    after
    nothing lost              100.0%    100.0%
    words in order             73.4%     73.4%
    right page                 28.6%     26.7%     <- WORSE
    page inflation             1.46x     1.46x

    2 improved, 3 worse, 25 unchanged. Regression set unchanged at 64.3%.

Nearly all of it is two files: `z19851706` 79.0% -> 37.2% and `z22110258`
38.1% -> 21.3%. Both gain exactly ONE page, and one extra page early puts
every later page out of step - the mechanism this file has documented three
times now.

**The page is the price of the structure being right.** Fifty list items are
fifty paragraphs, and each ends with a partly-filled line. The original has
the same fifty items and fits them in twelve pages; we need thirteen.

`fit.py` cannot recover it, and that is settled rather than assumed. The loop
was instrumented on `z19851706`:

    round 0: 12 -> 19 pages, 7 pages spilling
    round 3: 12 -> 13 pages, page 1 still spilling   <- ROUNDS=4 stops here
    round 5: 12 -> 13 pages, page 1 blocked by FLOOR=0.70 at scale 0.734

So BOTH limits bind on this file, where on `الفصل الثالث` neither did. Getting
that page back needs body text shrunk toward half size, which is exactly what
`FLAGS.md` 6 warns against: making the document worse for the reader to make a
number better. **Not done.**

One caveat that is plausible and NOT established: `z19851706` asks for
`SimplifiedArabic`, which is not installed here (fontconfig substitutes Amiri).
If the substitute is wider, some of the extra wrapping is the measuring
environment rather than the converter. An attempt to measure this by counting
text lines per page was thrown out as invalid - the original's blocks are
per-line fragments while ours are paragraphs, so the two counts are not
comparable. It needs real Word, like the rest of `FLAGS.md` 6.

**This is a judgement call and it is Moaz's**: a visibly correct list structure
against 1.9 points of a score that cannot see list structure at all.

## Word renders now, and it did not settle what it was meant to, 2026-09-20

A Windows VM with Office was set up so the checker could render through real
Word rather than LibreOffice - items 5 and 6 above, `FLAGS.md` 6, `TASKS.md` C.

`harness/word.py` drives Word over COM: one instance per process (starting Word
costs seconds and `fit.py` renders the same document up to five times),
`ExportAsFixedFormat` rather than SaveAs, and `Repaginate()` before export
because Word lays out lazily and a page count read before that is the
pre-layout one. `QIRTAS_RENDERER=word` routes `roundtrip.docx_to_pdf`, and so
`eval` and `fit` as well. LibreOffice stays the default: the two renderers are
not comparable and a run that silently changed one would be caveat 7 again.

Simplified Arabic, Traditional Arabic and Sakkal Majalla are all installed on
that machine, from the Windows `Language.Fonts.Arab` capability. So for the
first time in this project the checker can render these documents in the
application people open them in, using the faces they ask for, with nothing
substituted. AGA Arabesque and Arabic Transparent are still absent; neither
ships with Windows or Office.

**A note written here earlier said the machine had none of them. That was
wrong, and the instrument was what was wrong.** `harness.env` shells out to
fc-match, which does not exist on Windows; it returned "?", and the check
`not value.startswith("noto")` passed every face - so a machine with no Arabic
fonts at all would have scored `substitutions_applied: true`. The first attempt
to fix it read the font registry in a context that could not see it and
reported the opposite error, NOT INSTALLED for faces that were present. It now
reads the registry directly and returns `null` rather than `true` when it
cannot tell. **A check that cannot run must say so, not pass.** Eighth
instrument bug in this project; third that was flattering us; and the only one
so far that managed to be wrong in both directions before it was right.

First comparison, `z21358439.pdf` rendered by Word, 37 pages -> 43, words
100.0%, right page 21.1%. Two things came out of looking at it rather than at
the numbers:

  - the page-number box is rasterised into the body and printed a second time,
    on every page - `FLAGS.md` 18, new;
  - the Arabic on the page reads wrong in places (`اللاجئين` as `الالجئين`,
    `المؤقت` as `المقق`) and **it is not ours**. Every count matches the source
    exactly: 100/100, 34/34, 11/11. The source PDF draws the right glyphs and
    stores the wrong characters, so the page looks correct and the text layer
    is not, and the scorer reports 100% because both sides carry the fault.
    `FLAGS.md` 13 was written about digits on this same file; it is not
    confined to digits.

## Arabic that reads wrong on the page, settled by geometry, 2026-09-20

Raised by Moaz from a rendered page, and every one of them turned out to be in
the SOURCE text layer rather than something we did:

    اللاجئين  stored  الالجئين     a lam-alef ligature, reversed
    حاملا      stored  حامال        the same, at the END of a word
    زيلالي     stored  زياللي       the same, inside a name
    مقدمة:     stored  :مقدمة       the colon stored at the front of the line
    تبدأ       stored  ت بدأ        the line's TRAILING space stored second

The orthographic rules in `convert/arabic.py` could not reach any of them. They
repair only what Arabic spelling makes impossible - a standalone ال, or two
alef forms together - and `حامال` is not impossible: مال, حال, شمال and جمال
are all real words ending the same way. Guessing there corrupts valid text to
fix invalid text.

**The glyphs were never ambiguous, only the characters were.** لا is ONE glyph.
When the font's ToUnicode lists its two letters backwards, pymupdf hands back
two characters from a single glyph, so the first has NO WIDTH and the second
carries the whole advance. Measured on `z21358439.pdf` page 3, every ALEF
followed by LAM:

    two boxes   26   العامة العدد الحكاية اللحظة   the definite article
    zero width  11   حامال تحوال واالجت ال         reversed ligatures

The same for order. A character belongs where the page draws it, so in a
right-to-left line the reading order is descending x - and the colon and the
displaced space fall into place with no orthography at all. No pymupdf mode
does this already; `text`, `sort=True`, `blocks` and `words` were all tried.

### Three attempts, and the first two broke the hard gate

**Attempt 1 - repair at the point of extraction.** Reader and checker both read
through `rawdict` and repaired as they went. **Gate 100.0% -> 96.2%, one file's
text score 0.998 -> 0.000** - while `page_score` did not move on a single file.
The converter's output had not changed at all. Six of the eight regression
files come through the TAG route, whose `/ActualText` carries no glyph boxes,
so the checker repaired the original and the reader did not. That is caveat 1
and the invariant at the top of `convert/arabic.py`, in a new place: **a repair
applied to one side and not the other is worse than no repair.**

**Attempt 2 - derive the repairs once, apply them as text.** `fix_map(pdf)`
returns {broken -> repaired} over whole words; both sides derive it from the
same file and apply it to whatever they extracted, so neither can be repaired
without the other. Gate 98.4%. Better, still broken, and for three reasons
worth keeping:

  - *A fragment that deletes.* A full stop moving from the front of a line to
    the end gave `.طنجة، المملكة` -> `طنجة، المملكة` and
    `المملكة المغربية` -> `المملكة المغربية.`, a matched pair that balances
    only if BOTH fire. Singly, each changes the text: 72 characters went
    missing from one file. Fixed by requiring a fragment to be a permutation of
    itself, ignoring spaces - a repair reorders, it never adds or removes.
  - *A ligature swapped twice.* The swap left the alef at i+1, where the next
    step saw it beside the FOLLOWING lam and swapped again: زيلالي stored as
    زياللي came back زيللاي. A ligature is one glyph and can be swapped once.
  - *Combining marks are not neutrals.* A haraka has no width and sits on top
    of its letter, so its x IS that letter's x and the slot arithmetic cannot
    place it. On a fully vowelled Quranic verse in `الفصل الخامس المبحث الثالث`
    the marks drifted onto their neighbours - `{َوَالَّذِين` came back
    `{ََواَّلِذين`. NSM now never moves.

**Attempt 3 - and ask whether the glyphs are worth reading at all.** The
premise is that a zero-width character is half a ligature. On the six hard
thesis files the glyph layer barely decodes (RESEARCH.md: 0-8% recovered), so
its widths mean nothing, and the repair "fixed" every definite article: الله
came back لاله. The two groups are two orders of magnitude apart on both
counts:

    z21358439        10,961 chars    2.14% zero width
    z21011460        14,060 chars    1.56%
    ödev              1,120 chars    0.00%
    الفصل الخامس الثالث   11 chars   27.27%
    الفصل الخامس الأول    37 chars   67.57%
    مقدمة البحث          202 chars   96.04%

`pdftext.trustworthy()` refuses a file with under 200 decodable characters or
over 10% of them zero-width, so all six thesis files get an EMPTY map and are
left exactly as they were. The thresholds sit in open space rather than on a
boundary.

    regression set, 8 files, rendered by Word      before    after
    nothing lost                                   100.0%    100.0%
    words in order                                  98.8%     98.8%
    right page                                      64.4%     64.4%
    page inflation                                  1.00x     1.00x

Identical, file by file, which is the expected result: Moaz's own files are the
ones the trust check excludes. The repair is for the wild corpus, where a
single file yields ~900 fragments and the character multiset is unchanged.

**What this cost to get right is the point.** Three attempts, two of them
caught only by the hard gate, and one of those was mangling a Quranic verse -
the same verse `reader._backfill` exists to protect. Nothing but the gate said
so; `page_score` was flat throughout.

## Checkpoint A: does Word already do this? 2026-09-21

The question behind the whole project had never been asked of the most obvious
competitor. RESEARCH.md tested Acrobat, pdf2docx and html-to-docx - not Word,
which has opened PDFs as editable documents ("PDF Reflow") since 2013, and not
ABBYY FineReader. Asked now of Word, on the regression set and on the same 24
dev files as `out/runs/2026-09-21-dev-thesis-page-numbers`, scored by the same
`compare()`. Word needs `DisableConvertPdfWarning=1` under
`HKCU\Software\Microsoft\Office\16.0\Word\Options` or it blocks on a hidden
dialog; set for the run and removed after. Script and outputs were scratch,
not committed.

**On the theses Word fails outright.** 0% text on all six chapters: they are
the ActualText case, the glyphs decode to nothing, and Word turns every page
into hundreds of pictures (`الفصل الرابع` -> 5,233 pictures, 38 pages from
24). Ours: ~98%. The project's reason to exist holds for Moaz's files.

**On the dev set, three groups, and the text score misreads two of them.**

    11 files  stored backwards (FLAGS 1)   Word: a picture of each page, 0 words
                                           ours: every word, unreadable, scores ~100%
    13 files  ordinary                     Word: 57-99% of words at all (median ~0.82)
                                           ours: 100% by the same count

Word's text score on the ordinary 13 is 0.02-0.99 and not to be trusted: it
lays most text out in floating text boxes (up to 328 per file), which is bad
for editing and wrecks order, and our reference text has its own faults (next
paragraph). A presence count - fraction of the original's words found at all -
is the fairer measure and is the one quoted above.

**The comparison exposed a fault in our own reference, which is the real
finding.** On the words Word "lost", Word was often right and the reference
wrong: `خلال`, `نلاحظ`, `دلالة`, `معدلات` where the PDF's text layer - and so
both our output and our checker - reads `خالل`, `نالحظ`, `داللة`, `معدالت`.
On `z21761968` our output is presentation-form glyphs (ﻤ ﺔ) with words
reversed inside each line, and scores 99% because the checker reads the same
thing. Word's text there reads naturally. Word has its own damage (`رأس` ->
`أرس` 69 times, words split mid-way), so it is not a reference either - but it
is an INDEPENDENT one, which ours is not. See FLAGS 22 for the scale.

**Decision: keep building.** Word cannot do the theses, cannot do backwards
files, and its output is floating boxes rather than an editable document. But
not as before: "extracting Arabic is solved" is true for recovering the words,
false for spelling them right in over half the corpus, and nothing we measure
can see the difference.

## Scope: what Qirtas promises, 2026-09-21

Set by Moaz after checkpoint A. Every task is judged against this; anything
outside it gets a warning or a refusal, never a silent guess.

**Promised.** A digital Arabic PDF, typically saved from Word, becomes a Word
file you can edit straight away:

1. Every word is there, readable, in the right order and direction, and
   **spelled as printed**. Lam-alef stored backwards is repaired (FLAGS 22);
   text stored backwards is reordered (FLAGS 1). Both need a check that does
   not share our extractor before they count as done.
2. Built the way Word builds documents: real headings, footnotes, lists and
   tables, with headers, footers and page numbers in Word's own header and
   footer.
3. Close to the original in look: fonts, pictures in place, roughly the same
   pages.

**Warned, not refused.** Numbers the PDF prints one way and stores another
(FLAGS 13): the file converts, and the user is told which pages to check.

**Refused.** Scanned PDFs.

**Not promised, for now.** Multi-column periodicals, equations, exact
page-for-page layout. Right page stays a safety check, not a goal.

**Proven on files we did not tune on**, one score per feature (TASKS N2).

## The answer key, and the first honest scorecard, 2026-09-21

`harness/answerkey.py`. Word writes structure labels into the PDFs it saves:
what each piece of text was (paragraph, heading, list item, footnote, table
cell), with running headers and page numbers left outside them. That is the
answer key; nobody had to make one. The key reads the labels, lines them up
against our .docx, and reports per feature:

    found   of the text the labels call X, the share we made X
    right   of the text we made X, the share that really was X
    extra   text we wrote as X that the original does not have

It was wrong three times before it was believed, all caught because the gate
disagreed with it (`harness/test_answerkey.py` keeps each case): label pieces
shorter than a matching run read as missing; joining the pieces glued the
poems' words together; a right-to-left table stored in the other order scored
0% while a duplicate of its numbers as loose text took the credit. Text is now
compared as bare letters, spaces ignored, lam-alef runs sorted; table cells
and headers matched whole.

**Baseline, `out/runs/2026-09-21-dev-answerkey-baseline`: 36 Word-made tuning files**
(13 skipped: over 60 pages, or unlabelled). Sizes in letters.

                 size     found   right    extra   where the rest went
    heading     13,290    31.2%   47.6%       66   paragraph 8,718
    paragraph  666,909    89.1%   85.8%   15,607   list 65,826
    list        56,816    64.2%   30.6%      229   paragraph 19,804
    footnote    36,435     0.0%     -          0   paragraph 24,021, list 11,641
    table       69,983    34.4%   72.3%   13,440   paragraph 39,734
    furniture   34,823    59.9%  100.0%        0   table 6,730, paragraph 6,354

**Theses, `out/runs/2026-09-21-regression-answerkey-baseline`: 7 graded** (one over the
label threshold). Paragraph 96.4%, list 99.8%, footnote 84.9% (4,391 letters
as body text, 1,347 as list items - the `الفصل الثالث` case). The theses have
no heading labels at all: the author never used heading styles, so every
heading we make counts against us. Read that row as "the author did not", not
"we are wrong".

**The largest finding is not in the table. On all 36 ordinary files the
converter ignored the labels.** The tags route reads only `/ActualText`, which
ordinary files do not carry, so it recovers almost nothing and geometry wins
every time. Graded with labels kept and with labels stripped, the two results
are identical. The structure that 40% of the corpus hands us for free is
thrown away, and the geometry route then guesses it - finding no footnotes at
all, and making lists of prose.

## N2a: reading Word's labels on ordinary files, 2026-09-21

`reader.read_labels`: Word's labels for what each piece IS, over the glyph
text for what it SAYS. Run beside tags and geometry; preferred, like tags,
when it recovers within 3% of the best. `detect_lists` is skipped on it - the
labels already say which paragraphs are list items.

    dev scorecard (36 Word-made files)    before        after
    heading      found / right            31% / 48%     98% / 84%
    list         found / right            64% / 31%    100% / 100%
    paragraph    found / right            89% / 86%     99% / 88%
    footnote     found                     0%            6%
    table, furniture                      unchanged (not in scope)

    gate                                  before        after
    theses       nothing lost             100.0%        100.0%
                 right page                69.4%         68.3%
    24 unseen    nothing lost             100.0%        100.0%
                 words in order            67.6%         68.9%
                 right page                31.5%         30.9%
                 page inflation            1.51x         1.54x

The theses are identical file by file except `عن بعد`, a one-page form:
0.83 -> 0.75, one token, because the original page glues three fields into
`الطالبة:التوقيع:الرقم` and ours spaces them. No word is missing.

Found by looking, on the way in - each has a test in `harness/test_labels.py`:

- **Fields side by side** (`عن بعد`) were labelled separately and stacked as
  three headings; the form ran to two pages. Same-kind pieces on one line are
  joined, right to left for Arabic.
- **A chart's axis numbers** sit inside a Figure label; one paragraph each,
  they stacked down the page and `z20375390` went 24 -> 29 pages. A Figure is
  now one piece, like a footnote or list item.
- **A picture's description was backfilled as text** - Word's "A green circle
  with white letters AI-generated content may be incorrect", an ORCID icon's
  /Alt - and took a page of its own in `z21095413`. Present before N2a too.
  `_backfill` now skips /Alt text.

**Right page is 0.6 points down on unseen files, and it is the shrinking loop,
not the reading.** `z21760107` went 29 -> 32 pages. Unshrunk, the new reading
is SHORTER (38 pages against geometry's 39); `fit._spilled` attributes each
rendered page to the original page it overlaps most, misses spills where a
page holds the end of one original page and the start of the next, and so
shrinks a different set of pages each time. Recorded as a task.

**Footnotes are still 6%, and it is now the writer.** The reader finds them;
the writer only makes a real Word footnote when it can match the note's
number to a marker in the text, and on these files several notes arrive as one
block ("9 - ... 10 - ..."), with endnote-style bibliography entries labelled
as notes too (`z21764080`).

## Known unfinished

- **Pagination.** 49% of words land on the right page, up from 17%. The story
  that used to be written here - "a page overflows by one line and becomes two"
  - was wrong, and checking it was what moved the number. Mapping where each
  page's words actually landed showed **pure drift**: content intact and in
  order, shifted +1, then +2, then +4. Neither cause was text overflow.
    1. Two decorations sat at y=31 against a 71.6pt top margin - above the text
       column, so they were a running header. Emitted as ordinary paragraphs
       they stole 96pt from every page's 735pt.
    2. A title page of 14 pictures was stacked one under another to 1158pt
       against 735pt, taking two pages before a word had been read. That is
       where the first +1 came from.
  What is left is line-break drift *within* correctly numbered pages, which is
  a wrapping difference between renderers and may not be worth chasing.
- **`fit.py` cannot rescue a picture-only page.** `_spilled()` matches output
  pages to original pages by shared words and skips originals that have none, so
  a page of nothing but pictures is invisible to the correction loop. Its fill
  factor has to be right on the first pass, which is why `IMAGE_PAGE_FILL` is
  measured (0.95 spilled, 0.88 fitted) rather than chosen.
- **`مقدمة البحث` is the outlier**, 26% -> 31% where its siblings went to ~50%.
  Undiagnosed. Its text and picture scores are both perfect, so whatever is
  wrong is positional.
- **Inline bold and italic are carried but almost never seen** - see item 8.
- **Shrinkage is judged by LibreOffice, not Word** - see item 5.
- **Text layers stored in VISUAL order, and the scorer cannot see them.** This
  is the largest known correctness problem in the project. Some Arabic PDFs -
  typically LaTeX output - position every glyph individually and store the
  character stream already reversed. The page displays perfectly; the text
  underneath runs backwards. We reproduce it faithfully, Word applies
  right-to-left a second time, and the double reversal is unreadable.

  **The score is structurally blind to it**: our reversed output is compared
  against the same reversed source, so the two agree. `z21889411.pdf` scores
  99.9% on text and 130 pages to 130 - it was called the best pagination result
  in this project - and no one can read a word of its output.

      56 of 172 usable corpus files (32.6%) are stored this way
      20 of the 70 holdout files
      7 of those 20 score >=95% text, two of them exactly 100%

  Detection is cheap and already prototyped: count common function words
  against their reversals, and the two cases separate by an order of magnitude.
  What to DO about it is a real decision and not only a technical one - reorder
  the text and risk mangling documents that are partly correct, or refuse such
  files the way `z22244578.pdf` is refused. Either changes what this converter
  promises, so it needs deciding rather than defaulting.

  Found by rendering a page and looking at it. Not by any metric.
- **Periodicals are detected and then ignored.** `harness/doctype.py` tells a
  newspaper page from an ordinary one by body font size, and the holdout showed
  why that mattered: ordinary documents place 29.4% of words on the right page,
  periodicals 8.8%, which is *below* the ~13% two-unrelated-documents floor.
  Averaging the two produces a number true of neither. The detection exists so
  the classes can be reported apart; nothing yet acts on it. Two honest ways
  out - handle multi-column layout, or put periodicals out of scope in writing.
  Quietly leaving them in the mean is not one of them.

## Measurement caveats, learned the hard way

Every one of these made the numbers lie before it was found:

1. **~~LibreOffice reverses Arabic letter pairs~~ (لا -> ال) — WRONG, and the
   wrong explanation sat here long enough to be repeated as fact.** The
   reversal is in the SOURCE pdf. لا is a ligature, one glyph, and the font's
   ToUnicode table lists its two letters backwards, so it extracts as ال. The
   .docx carries the reversed pair before LibreOffice is invoked at all, and
   correctly-ordered words sit on the same line; the codepoints are ALEF then
   LAM straight out of pymupdf. Repaired in `convert/arabic.py` (2026-09-19).
   Reading text from the .docx rather than a render is still right, but for the
   ordinary reason that a render adds the renderer's own layout and shaping.
2. **Word stores text XML-escaped**, so every "&" looked like lost text.
3. **Word-level scoring punished correctness**: PDF extraction glues
   line-broken words ("أنهلا"); joining them properly changed every token.
   Characters are compared now.
4. **Ink-density comparison had no discriminating power** - our reconstruction
   scored 29% against the original while unrelated Arabic documents averaged
   28%. Replaced with per-page word matching.
5. **The "unrelated document" baseline was another chapter of the same thesis**
   - same template, so not a baseline at all.
6. **Fixed-size chunk matching confused "moved" with "missing"**. Sentences are
   the unit that survives reordering.
7. **The fonts these documents ask for are not installed here** (only Noto
   Arabic is), so LibreOffice substitutes a wider face when rendering. Some of
   the remaining page inflation is this, not us.

8. **`page_score` is not exactly reproducible.** Running the same 68 files
   twice on the same code gave identical results on 66 of them and differed on
   two, by 0.07 and 0.54 points - `page_score` only; `text_score`, `kept` and
   the page counts matched exactly. LibreOffice does not render identically
   every time, and `fit.py` decides which pages spilled by looking at what it
   rendered, so a hairline difference there can change a shrink decision.
   **Treat any `page_score` movement under about half a point as noise.**
   Several comparisons in this file are finer-grained than that and should not
   be trusted at that resolution.

9. **The hard gate measured contiguity and called it presence.** `loss.py`
   promised in its own docstring to ignore order, then looked for each sentence
   as one unbroken run, so a phrase moving within a sentence read as lost text.
   It made the corpus's worst-scoring file (95.83%) one that had lost nothing
   at all, while the genuinely faulty file scored 99.80% and looked fine.
   Fixed in 9ff42e8 by falling back to asking whether every substantial word
   survives somewhere. **Note how this one was found**: not by the score moving,
   but by opening the worst file and reading what it supposedly lost. Three of
   the caveats in this list were found that way and none by the aggregate.

10. **A crash removes a file from the average instead of failing the run.**
   `eval.py` catches per file so one bad document cannot cost a whole run, but
   the printed mean is then taken over the survivors and says nothing about
   what left. Three files vanished this way from the first holdout run without
   the summary line mentioning it. If a run reports fewer files than the set
   holds, that gap is the story.

11. **The corpus was documented as reproducible and was not.** `.gitignore` and
   the README both said `corpus/wild/` rebuilds with `fetch_corpus`. It does
   not: the Zenodo query sorts by `mostrecent` and returns whatever exists the
   day it runs. Since the split is a hash of the filename, a rebuilt corpus is a
   *different* split, and every score in this file would have become a number
   about some other collection of documents — with no warning, because the run
   succeeds and prints a mean either way.
   The thing that actually pinned it, `manifest.jsonl`, was sitting **inside the
   gitignored corpus directory**, where a fresh checkout could never see it.
   `out/split.json` was in the same trap. Both are now committed and
   `--from-manifest` restores by record ID (2026-09-20).
   **Found by being asked whether the corpus could go in git** — not by any run,
   and it would have surfaced as inexplicable score drift on a new machine.

12. **A test can be defeated by the name of the file it writes.** On Windows
   `harness/test_xml_safe.py` reported the writer as producing a corrupt .docx
   for a NUL in paragraph text. The writer was correct; the test named that
   case `nul`, and Windows resolves the DOS device names - `nul`, `con`, `aux`,
   `prn`, `com1..9`, `lpt1..9` - ahead of any real file of that name, in any
   directory and whatever the extension follows. `nul.docx` IS the null device:
   `doc.save()` succeeded, every byte went nowhere, the path reported 0 bytes,
   and `text_of_docx` then raised `BadZipFile`. Nothing anywhere raised at the
   point of loss. Cases are now written as `case_<stem>.docx` (2026-09-20).
   Worth remembering when items 5 and 6 above are finally done in real Word,
   since that work happens on Windows by definition - a harness written on
   Linux can fail there for reasons that have nothing to do with the converter,
   and this one accused the converter by name.
