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

## N2b: notes as Word prints them, 2026-09-21

The labels found the notes (N2a); the writer made real notes of 6% of them.
It paired a note with its reference only through a typed "(13)", and Word
draws references as small raised digits. Now:

- **The reader finds raised references by size** (<= 0.8 of the labelled
  piece's usual size), not by the superscript flag - set on some and not
  others in one paragraph - and not by line, since PyMuPDF puts raised digits
  on a line of their own. Pieces in brackets are one number: "(1" + "1" is 11.
  They travel as private-use marks (`footnotes.MARK_OPEN`), so an author's own
  "(2)" is never taken for one, and one no note claims is written back raised,
  not as "(13)". Headings are skipped: a small "1" in "1.1" was taken for one.
- **Notes labelled as one piece are split** at their raised numbers, and at a
  typed "(k)" when k is the next number and the page refers to it.
- **A note referenced inside a list item is still a note** (it was absorbed).
- **Endnotes**, written as real Word endnotes (`footnotes.py` now builds both
  parts). A note is one when its page does not cite it but an earlier page
  does - only if at least 3 pair up and all sit after the last citing page.
  Pages left with only a scrap of text once their notes leave are folded into
  the page before. The checker reads endnotes (`compare.text_of_docx`), or
  every one would count as lost.
- **The thesis reader**, same bug in its own code: a list item inside a
  footnote now stays a footnote. Moaz's `الفصل الثالث` example - notes (34)
  and (35) sat in the middle of the last page and are now at its foot, under
  the rule. They are not yet real Word footnotes: the page cites only (1) and
  (2), so nothing in the text to attach them to.

The grader was wrong twice more and is fixed, with tests: a bibliography
repeating a note's citation took the match, and a matching run crossing from
one piece into the next handed the second the first one's kind. Both change
earlier numbers, so "before" below is the N2a code re-graded.

    dev (36 Word-made files)       before (re-graded)    after
    footnote   found / right       6.3% / 100%           73.7% / 99.7%
    paragraph  right               88.7%                 91.7%
    theses     footnote found      84.9%                 88.1%
               list right          93.2%                 98.4%
               words in order      98.8%                 99.0%
    gate       nothing lost        100% theses and 24 unseen, both runs

Right page on unseen files 30.9% -> 30.7%: `z21760107` again (32 -> 35
pages), the shrinking loop's file (N2c), and 1.5 points on one other.
Endnote files lose some order on purpose - Word prints endnotes after the last
page, the original just before its last page's references.

Left: a note that does not start with its own number (`z21760107` p.5);
endnotes numbered "9 - ... 10 - ..." at full size (`z21764080`); and
`z21762915` spills every page onto two, before N2b as after.

## N3: a spelling check that does not read the PDF our way, 2026-09-21

`python -m harness.spelling`. Every other score reads the PDF with PyMuPDF,
as the converter does, so a misspelling in extraction is on both sides and
invisible (FLAGS 22). This one asks Word: it opens the PDF itself (Reflow),
and its reading is used as a VOCABULARY only - never its order, which its
floating text boxes wreck. Each word we wrote is confirmed (Word saw it),
lam-alef (Word saw it with a stored "ال" as "لا"), display form
(presentation glyphs), backwards (Word saw it reversed), or unconfirmed.
Files Word draws as pictures are checked against a lexicon of everything
Word read in the other files instead, and reported apart.

On the 24 unseen files of the standard sample, our latest output
(`out/runs/2026-09-21-dev-spelling-n2b`, the outputs of the N2b eval):

    13 files Word could read       confirmed  lam-alef  display  backwards  unconfirmed
      ours                           58.8%      1.2%     31.0%     1.0%       8.0%
      the checker's reference        59.2%      1.2%     31.2%     0.6%       7.8%
    11 files Word drew as pictures (lexicon only, 33,333 words)
      ours                           13.7%      0.1%      0.0%    34.5%      51.7%

    23 of 24 files have over 1% of their words in a named fault.

**What it says.** The converter copies every extraction fault faithfully -
ours and the reference match to a tenth of a point - and the gate, reading
the reference, scores all of it 100%. Lam-alef is 0.7-3.1% of the words on 11
of the 13 readable files: about one word in forty, typically خالل, داللة,
معدالت. Two files are almost wholly display-form glyphs (`z21508463` 93%,
`z21761968` 62%): they look right in Word and cannot be searched. The 11
backwards files are 35% provably backwards against 14% confirmed; a working
reorder (FLAGS 1) should swap those two numbers, so this is its test. The
lexicon grows with every file Word reads, so those two rows compare only
between runs over the same cache (each row records its lexicon size).

**How it was checked, and what was wrong on the way.**

- Word's own reading has no lam-alef fault: on 13 readings, no word is a
  lam-alef swap of another word Word read, apart from the pair لا / ال, both
  real. So Word cannot confirm our misspelling by sharing it.
- Two outputs left in the work folder by earlier runs got into a first
  baseline and halved its lam-alef count. The check now takes its files from
  one eval record and leaves out any .docx over an hour older than the rest.
  One (`z20496510`) is from the run with the old lam-alef repair on. The
  other, `z22246498`, is in no eval record, so the code that made it is not
  known - but its output had 632 lam-alef words against the reference's
  2,570, and ~290 more backwards words. A lead for FLAGS 20, not a finding.
- Word reads `z21508463` partly backwards itself (3.0% of its words against
  0.0-0.6% on the rest), and its "يف" put backwards words into the lexicon:
  backwards files read 16% confirmed. Readings over 1% backwards are now left
  out of the lexicon, and a word whose reversal is commoner cannot vouch.
- Three-letter fragments reverse into words ("الإ" -> "إلا"), so short words
  count as backwards only against the 50 commonest. هللا (the Allah
  ligature) is the lam-alef fault, not a backwards word.
- **Tried and not kept:** "some two or three letters swapped" as a general
  ligature rule. It finds real faults on `z20763272` (اجملتمع for المجتمع,
  اليت for التي - lam-meem stored backwards), but Word swaps "را" itself
  (رأس -> أرس), so on `z21760107` it blamed us for العراق and الزراعة, which
  we spell right. It cannot tell whose mistake it is. Those faults stay in
  "unconfirmed", which is why that share is the check's blind spot.

**Not covered.** The theses: Word gives nothing (their text is only in the
labels), and their text is Word's own /ActualText, already independent of
PyMuPDF. The paused holdout. Word's reading takes 5-50s a file and is cached
in `out/work/wordread/`.

**Next, now unblocked:** the lam-alef repair (FLAGS 20) judged by this - the
lam-alef share should fall to ~0 and confirmed rise by the same, with the
gate reading the same repair on both sides.

## N3a: the lam-alef repair, on and holding the gate, 2026-09-22

The glyph repair (`convert/pdftext.py`) was parked on 2026-09-21 after it
cost the gate 20% on `z22110258` (FLAGS 20). N3 gave a way to judge it that
does not share our extractor, so it was taken apart.

**The 20% was not lost text.** Two repairs touch lam-alef: the spelling
rules (`arabic.repair_lam_alef`, always on) and the glyph map. The reader
ran spelling first, as it read, and the map at the end; the checker ran the
map first. A word with two broken ligatures, االسالمية for الاسلامية, was
half-repaired by spelling to الاسالمية, and the map - keyed on the stored
form - no longer recognised it. The checker had the right word, we did not,
and every sentence holding one read as lost. The spelling rules are also
not safe to run twice, which is what the last two failures turned out to be.

What changed, each found by a run that failed:

- **Both sides run the same order:** spelling as read, then the map
  (`compare.text_of` was the other way round). The map carries each word
  both as stored and as the spelling rules leave it. The reader does not
  run the spelling rules a second time - on `z20276145` that moved alefs
  one place further and cost 21% of the gate.
- **The map is keyed on words, not whitespace tokens.** A word is a run of
  Arabic letters, so a note number glued to it (`واإلسالميني1`) - which N2b
  turns into a real note on our side only - no longer stops the repair on
  one side.
- **The punctuation half is out.** The repair also moved spaces and marks
  to where the page draws them. Those moves cross words and only fire where
  both sides split words alike; it gave the checker `D-VBS` for DVB-S and
  `دراسةم لأمون`. `arabic.reorder_neutrals` still exists, unused by the map.
- **A second glyph signature.** In some fonts the ligature's alef is not
  zero width. It and the lam still END AT THE SAME EDGE, being one glyph.
  On ten files every zero-width case had the shared edge too, and the edge
  alone found ~130 more broken words (االعالم, األجل) with no false hit. A
  looser test - the alef inside its neighbour's box - changed غزال and تزال.
- **Words stretched with alefs are skipped** (`z20276145` sets المصلحة as
  المصاااالحة). Three alefs in a row are never spelling; the two sides
  moved different filler alefs. Without this rule that file keeps 95.2%.

Repair on vs off, same 24 unseen files and the theses
(`out/runs/2026-09-22-dev-n3a-fix-on-v3`, `-regression-n3a-fix-on-v3`,
`-dev-spelling-n3a-v3`, against `2026-09-21-dev-n2b`):

    nothing lost          100% / 100% theses        100% / 100%
    lam-alef words        1.2%                      0.1%    (harness.spelling)
    confirmed words       58.8%                     60.0%
    words in order        68.9%                     68.9%
    right page            30.7%                     30.8%   same page counts

The theses do not change: their glyphs are untrustworthy by the existing
check, so the map is empty there. **On by default** since this run;
`QIRTAS_ARABIC_FIX=off` turns it off on both sides.

Left: the 11 backwards-stored files moved from 34.5% to 36.5% "backwards"
by the spelling check, as ligatures inside reversed words were put right -
consistent with, not a substitute for, the reorder (N3b). Other broken
ligatures, like lam-meem (اجملتمع for المجتمع), are untouched.

## Other ligatures stored backwards, 2026-09-22

Looking at `z22110258` p.38 showed the lam-alef repair was not the biggest
visible fault: في printed "يف", المعلومات printed "املعلومات", on almost
every line. Same fault, other ligatures: a glyph standing for several
letters, listed backwards in the font. Same trace on the page - every letter
but the last has no width, at the glyph's right edge, and the last ends at
the same edge (يف, the lam-meem-jeem of اجملتمع, the ta-ya of اليت).

**Checked before building**, against Word's reading of ten small files: for
every word holding such a group, reversing the group gave the word Word read
2,597 times, keeping it once (مال / ملا). In EVERY font of every file the
lam-alef glyphs came out backwards, never once correct - this looks like how
Word writes PDFs, not a quirk of some fonts.

**The trap:** for lam-alef the page settles the order, because alef never
joins the next letter, so "alef, lam" cannot be one glyph. Ya and fa join
both ways. كيف was flagged 22 times as a backwards ya-fa glyph; reversed it
is كفي, wrong. It was spared only because one copy was not flagged and the
map requires every copy to agree. So that rule stays strict - a majority
vote would have let كيف through at 22 to 1 - and after the change, of the
words the map rewrote in our output, 2,545 are the spelling Word read, 332
neither, and **none** where Word read the stored spelling.

What was built:

- `arabic.repair_ligatures` reverses any such group of LETTERS (a vowel mark
  is zero width by nature and belongs to the letter before; "١ت", a digit
  glued to a letter, fits the geometry but neither order is a word).
- A spelling rule: يف standing alone -> في. Two-letter words stay out of the
  map (رب, a real word, would go to بر), but يف alone is not Arabic and في is
  the commonest word. Word never read it as a word in 13 files.

Small files of the standard sample (`--max-pages 30`, 23 files) and the
theses, against the lam-alef-only code (`2026-09-22-dev-spelling-n3a-v3`
vs `-dev-spelling-ligatures-fi`):

    nothing lost            100% / theses 100%
    confirmed words         81.6% -> 84.1%   (12 files Word could read)
      z20763272             77.7% -> 88.5%   backwards words 3.2% -> 0.3%
      z21095413             88.2% -> 95.0%
      z20393612             63.6% -> 66.6%
    words in order          67.6% -> 67.5%   right page 30.7% -> 30.6%

The 0.1 of words in order is the يف rule at the edges of a block: like the
ال rule it needs a real character on both sides, and the reader repairs a
block at a time while the checker reads the whole document, so a few are
fixed on one side only. The gate does not see it (it skips two-letter
words). Right page dips on the files that gained most - `z21095413` 0.335 ->
0.318 - because it compares our pages with the original's words AS STORED,
misspellings and all, so every word put right stops matching. An instrument
fault, next to fix.

## N3b: the backwards files were scans, now refused, 2026-09-22

FLAGS 1 said a third of the corpus stores its text backwards, "typically
LaTeX output", and Moaz decided to reorder it. Starting the reorder, the
files turned out to be something else. Of 156 corpus files with Arabic text,
52 read backwards by function words (في, من, على... against their
reversals), and **46 of the 52 are scans**: a photo of a newspaper clipping
with OCRmyPDF text laid invisibly on top, noisy even read the right way.
The 6 digital ones were not backwards when looked at - four read forward
and were counted backwards through "يف" (the broken في), two are garbled
fonts (FLAGS 23). The one real digital case is `z21889411`, the named
example: LaTeX, reversed line by line, 130 pages. Parked until a short one.

Scans are out of scope. Moaz, 2026-09-22: refuse them. `convert/scan.py`,
called first thing in `v1.convert`: a page is a scan if it shows under 20
visible characters and either carries invisible text or is one picture
covering 85% of the page; a file is refused when 80% of up to 12 sampled
pages are. So a thesis with a photographed title page still converts
(`test_scan.py`). Over the whole corpus (233 files) it refuses all 46 OCR
scans, 29 Canva designs exported as one picture per page with no text, 2
Konica scanner files, and 2 other single-photo PDFs; no Word-made file and
none of the theses. The eval counts refused files apart and averages the
rest.

Small files of the sample (`--max-pages 30`) and the theses
(`2026-09-22-dev-refuse-scans`, `-regression-refuse-scans`):

    11 of 23 refused, all scans; the other 12 identical to before
    nothing lost      100% / theses 100%
    words in order    67.5% -> 99.5%   \  NOT the converter improving: the
    right page        35.2% -> 49.1%    > unreadable scans left the average
    page inflation    1.75x -> 1.12x   /
    theses            unchanged, right page 73.1%

**Every dev-set average before this includes about a third scans** and is
not comparable with one after. The spelling check's "backwards" rows for
those files go away with them.

## N3c: display shapes folded to letters, 2026-09-22

Some PDF makers store Arabic as presentation forms - one codepoint per SHAPE
of a letter (initial, medial, final, isolated) rather than the letter. It
looks right and cannot be searched, spell-checked or reshaped by Word.
`arabic.fold_display_forms` maps each shape back to its letter (Unicode
NFKC, per character), and the lam-alef shapes to لا لأ in reading order. It
runs inside `repair_lam_alef`, so the reader, the gate's reference and right
page all get it at the same point. Kept as typed: ﷺ ﷻ ﷽ and the Quran
brackets ﴾ ﴿, which NFKC would expand or flatten.

Spelling check (Word's own reading), our output before -> after, all four
at 100% nothing lost both ways:

    z20679271   9 pages   confirmed  4.6% -> 91.4%   display 95.0% -> 0
    z20276275  18 pages              2.5% -> 88.6%           97.4% -> 0
    z19740548  20 pages              2.5% -> 80.5%           97.0% -> 0
    z21761968  20 pages             33.9% -> 87.5%           61.5% -> 0

Small files of the sample and the theses (`2026-09-22-dev-n3c-display`):
gate 100%, only z21761968 moved - right page 0.331 -> 0.683, as its text now
matches what Word prints - average 49.1% -> 52.0%. Theses unchanged.

**Revealed, not caused:** 14% of z19740548's words now read backwards
(لصاوتلا for التواصل). Part of it is stored in screen order; as display
shapes those words were unreadable too. It is the short digital backwards
file N3b lacked (FLAGS 1) - 20 pages, the one to build a line reorder on.
z21761968 also has words in reverse order within some lines.

## N2c: the shrinking loop sees wordless spills, 2026-09-22

`fit.py` shrinks the original pages that took more than one page in Word.
It decided which by giving each rendered page to the original page it shared
most words with, and skipped rendered pages with no words. On `z21760107`
(19 pages) nearly every page ended in two footer pictures - the journal logo
and a page-number box - that did not fit and went onto a page of their own.
Those pages have no words, so the loop saw 2 of 16 spills: 35 pages out.
TASKS had "29 pages one run, 32 the next"; two runs today gave the same 35
each, so the swing was not the loop being random - most likely other changes
landing between those runs.

`fit._owners` now uses what the writer guarantees: a page break before every
original page, so rendered pages fall into one unbroken run per original page,
in order. It finds the split that shares the most words; a wordless page joins
the run before it. `ROUNDS` 4 -> 6: z21760107 still had two pages over after
four. Tests: `harness/test_fit.py`.

    small files of the sample   right page 52.0% -> 54.4%   pages 1.12x -> 1.10x
    (2026-09-22-dev-n2c-spill)  z21760107 35 -> 21 pages, z20276145 32 -> 28,
                                z20375390 24 -> 22 (right page 0.33 -> 0.47),
                                z20763272 27 -> 26 (0.76 -> 0.83)
    theses                      unchanged, 73.1%, 1.00x
    gate                        100% both

z21760107 still scores only 0.17 right page: its title page takes two, so
every page after is one late. The abstract table there has a column squeezed
to a few words wide - a table-layout fault shrinking cannot fix (tables).

Left: a picture-only ORIGINAL page that spills is still blamed on the page
before it (FLAGS 9).

## FLAGS 23: fonts naming the wrong letters, repaired, 2026-09-22

A PDF stores, for each letter, the SHAPE drawn (its number in the font) and
a table saying which character the shape is. Word's export writes that table
wrong for some fonts, and every reader - PyMuPDF, Word's own PDF reading,
copy and paste - trusts it. The page looks right and reads as gibberish;
the gate saw 100%, because it read the same gibberish.

`convert/glyphs.py`. For each composite font whose codes are shape numbers
(Identity-H), look the font up among the installed ones and name each shape
from the font's own tables: the character map, then the shaping rules
(GSUB) for letter forms and joined pairs. Word keeps the installed font's
shape numbers when it embeds part of it; that is checked per font - 90% of
the widths the PDF records must equal the installed font's - before
anything changes. A corrected copy is written (cached in the temp folder by
content), and `v1.convert`, `fit`, `compare.text_of` and `page_alignment`
all read it.

Replacing is per shape, and only where it is safe. Every rule was a wrong
change on a real file first (tests in `harness/test_glyphs.py`):

    kept as stored   a typed 2 or ; that Word DISPLAYS as ٢ or ؛  (z22110258)
                     a letter with its vowel mark - تِ is one shape, and
                     the rules named it تن                        (our own)
                     a letter with the same base shape as the name,
                     unless the font is scrambled (dots drawn as marks
                     name the base of في as ڜ)                     (z21095413)
                     a hamza drawn as its own mark                 (z21760107)
    replaced         the stretching stroke stored as ر ي ذ or blank
                     a letter stored as a blank or a letter of another shape
                     a joined pair or vowel mark stored as junk

The best check was our own files: we know exactly what text went into the
rebuilt PDFs, so every proposed change there could be checked against it.
After the rules, the only changes left there were vowel marks Word stored as
blanks - all in our text.

    small files (2026-09-22-dev-glyph-repair-2)   right page 54.4% -> 55.3%
                  z20763272 0.83 -> 0.96, z19851706 0.82 -> 0.84;
                  z20375390 0.47 -> 0.45, z20397518 0.45 -> 0.43 (not looked at)
    theses        right page 73.1% -> 73.9% - an instrument change, not a
                  converter one: our rebuilt PDFs' vowel marks now read
    gate          100% both

Word-reading spelling check: 74.8% confirmed, and it FELL on the repaired
files (z20763272 88.5% -> 59.6%) - Word reads through the broken table
too, so its word list is the gibberish. Not usable for these files; see
FLAGS 23. Looked at instead: z20393612 (مراجعة نقدية مقارنة recovered from
مغاحعت هلض ًت ملاعهت), z20763272 (العلوم القانونية والسياسية), z20375390.

Where the stretching stroke was stored as a letter, it becomes the stroke
character (ـ) in our Word file, as the page drew it. An empty entry would
have been cleaner but readers then fall back to a Latin-1 letter (»).

## N4: 49 pages looked at, defects counted, 2026-09-22

The scores cannot see most of what is wrong - the box drawn twice, a whole
page written twice, gibberish all scored "nothing lost 100%". So: 49 random
pages, looked at against the original, every defect logged by cause and
severity (3 can't use it / 2 fix by hand / 1 cosmetic). Sample fixed by seed
2026 (`out/work/n4/sample.json`): 14 of Moaz's thesis pages (7 chapters,
`عن بعد` has one page, hence 49) and 35 from 15 small wild files, at most 3
per file. Log: `out/work/n4/defects.json`. Each suspected defect was checked
against the original first - the box on `الفصل الثالث` turned out to be
PICTURES in the original too, not text we duplicated.

**Every one of the 49 pages has at least one defect. 110 in all.**

    cause                                               pages files  weight
    running header / page-number graphics in the body     16    7      34
    punctuation, numbers, brackets misplaced in RTL lines  15    9      29
    footnotes/endnotes: in the body, lists escaping,
      Roman numerals                                       12    8      23
    wrong body font                                        10    5      20
    tables: written twice, squeezed, boxes as grids,
      false tables                                          7    7      17
    headings, lists, title blocks merged / marks lost      10    7      15
    letters wrong (stretch strokes as alef, jumbled
      header, honorific lost, loose marks)                  6    5      13
    formatting lost (bold, italic, underline, colour)      12    8      12
    Arabic-Indic digits shown as Western                   10    5      10
    whole text or entries written twice                     3    2       8
    wrong page numbers                                      3    1       6
    lines stored backwards                                  2    1       4
    overlaid pictures stacked                               1    1       2

    weight = severity summed over defects

**On Moaz's theses** (14 pages) the text is right almost everywhere; what is
wrong is how it looks: digits (10 pages), the wrong font (8), bold lost (6),
three footnote faults, the honorific ﷺ lost twice.

**The wrong-font bug** is one line of cause: `reader._dominant_font` counts
fonts by pages seen and skips Arial, Calibri and Times as generic - and the
theses' body IS Arial, so the only candidate left is a font seen once. Three
chapters come out entirely in AGA Arabesque, a symbol font not installed
here; `مقدمة البحث` in Sakkal Majalla.

**The worst files are journals**: running headers, page-number graphics and
coloured bands in the body (FLAGS 14 was closed for repeating TEXT; these
are pictures, boxes and one-off headers it does not catch), and three files
two-thirds longer than the original - `z21762915` writes each page's text
twice (23 -> 39 pages), `z21087226` reads its English references as tables
(23 -> 41), `z21418248` overflows every page (22 -> 36).

Seen outside the sample, not counted: `الفصل الثالث` writes its opening
heading three times (تمهيدتمهيدتمهيد) and doubles its first paragraph.

**Moaz reviewed all 49 pages against the log** (2026-09-22): 42 agree, 7
"missed something", none too harsh or too lenient. So the grading
undercounts, it does not inflate. His additions (13, now 123 defects):
page numbers wrong or missing on 4 files (a consequence of overflow where
Word counts its own pages, or no number at all); a full stop inside a word
(العرا .ق - stored so in the source: this file has 50 word-initial full
stops, and we copy every one); a table running left-to-right; a chart title
misplaced; a page with no header or footer at all. On `الفصل الثالث` p.16
he reads the stacked line pictures as the text twice; the fix he wants is
the one the log names - only the box, at the right size.

## N5a: the look of the theses - font, signs, digits, 2026-09-22

Three faults N4 found on Moaz's theses, all on how the text LOOKS.

**The body font.** `_dominant_font` counted the pages each font appeared on
and skipped Arial, Calibri and Times as "generic". The theses' body IS
Arial, and their words are pictures labelled with their text (the tags
route), so no font draws them: what was left was a font seen once. Three
chapters came out in AGA Arabesque, one in Sakkal Majalla. Now it counts
the letters each font draws - Arabic ones, or ones that do not decode;
Latin only when there is no Arabic - and skips only fonts of signs. All six
chapters now pick Arial.

It found a second fault on the way: **the font was written under its PDF
name**, `SimplifiedArabic`, `SakkalMajalla`, `TimesNewRomanPSMT`. Word looks
fonts up by family name, finds nothing and substitutes. `glyphs.family()`
turns the PDF name into the installed family's (`Simplified Arabic`); 168
of 233 corpus files choose differently now, most of them only by that name.
Many now pick Times New Roman - it is what draws their Arabic (Word's default
complex-script font), counted, not assumed: `z20129076` draws 9,746 Arabic
letters in it and 911 in Simplified Arabic.

**The signs ﷺ and رضي الله عنه.** AGA Arabesque stores them as private codes
(F072, F074), and they were dropped altogether: on the tags route a sign is
the only real text on the page, under a label with no text, and the route
reads labels only. Two changes:
- `glyphs.SYMBOL_FONTS` names the signs in the repaired copy: F072 as ﷺ
  (U+FDFA, in every common font), F074 as U+FD47. No font here draws FD47,
  so the writer and the checker both spell it out (`spell_out`). Named by the
  three words directly, the line holding it came out BACKWARDS in PyMuPDF
  and the gate fell to 97.9% - a PDF table entry must be one character.
- `reader._sign_reader`: a label with no text of its own takes the text its
  content draws, in a font of signs only - every other file reads as before.
`الفصل الثالث` now has all 13 رضي الله عنه and both ﷺ, each in its place.

**Digits.** Word stores a typed 121 and, set to Hindi or Context numbers,
draws ١٢١. The theses show ١٢١; ours showed 121, since that is a setting of
the reader's Word, not of the file. `glyphs.shown_digits` asks the font
embedded in the PDF what it drew for each typed digit - in the theses the
shape stored as 5 is the embedded Arial's `uni0665`. Six theses and six wild
files show Arabic-Indic. For those the writer writes ١٢١ after Arabic and
121 after Latin (Word's own Context rule). Footnote pairing and the checker
read ١٢١ and 121 as one number (`footnotes.WESTERN`).
- **Page numbers cannot follow.** They are Word's PAGE field, drawn in the
  reader's setting. `hindiNumbers` is Devanagari (१२१), `\* Arabic` and an
  Arabic language tag change nothing - all tried in Word.
- A first try matched Persian digits: Arial draws ٤ and ۴ with one shape.

**Results** (`--max-pages 30`, `2026-09-22-{dev,regression}-n5a-font-digits-3`):

    theses          nothing lost 100%, words in order 97.6 -> 99.0%,
                    right page 80.4%, every chapter its own page count
    dev, all 48     nothing lost 99.9% - four files, and ALL FOUR lose the
                    same with the code before this change (FLAGS 24)

Looked at (`out/work/n5a/look`): `الفصل الثالث` page 20 and `مقدمة البحث`
page 4 - Arial, ١١٥٧/٣ and ١٤٨ as in the original, the signs in place.
Still different there: bold body text lost, page numbers 66 not ٦٦, Word's
footnote numbers 1, 2, 3 (N5d).

## N5b: headers, footers, page numbers, 2026-09-22

N4 counted journal headers, page-number graphics and header bands in the
body on 16 pages of 7 files, and wrong or missing page numbers on 4 files.
Nine files traced (`out/work/n5b`); five separate causes, all in
`writer._running_text` / `_running_furniture`:

1. **One piece per edge.** A header in two lines, English and Arabic
   (`z21095413`), a page number printed twice on itself (`z22051439`), an
   author on even pages and a title on odd ones (`z21761968`): only the
   piece on most pages was taken, the rest stayed in the body. Now every
   group that repeats is taken; pieces on one line are one paragraph.
2. **Alternating headers** go into Word's even and odd headers
   (`evenAndOddHeaders`). Word picks by the page NUMBER, so the printed
   numbering decides. Checked in Word: page 129 shows the title, 130 the
   author, as the original. A footer read in another order on its mirrored
   pages (`z21763864`: "2016 10 - 8 -") looks alternating too; a one-sided
   piece carrying nothing the other side does not is the same furniture.
3. **Edges found by position, not only reading order.** The margins are
   measured from the content, header included, so on `z21095413` the page
   number sat inside the "column" and mid reading order. Now the outer 12%
   of the page counts (`EDGE_ZONE`), for text and pictures; which edge is
   settled by which half of the page, not by coming first - `z21763864`
   reads its footer first and it was filed as a header.
4. **Page numbers.** The number whose value less the page is the same on
   most copies (`_page_run`), not the first copy's: `z20538636`'s title
   page has a year read backwards, ٥٢٠٢, and the file was numbered from
   5202. Only copies that agree are lifted - the year stays. A number inside
   a line - "- 8 - 10 2016", "صفحة92" - is a PAGE field in its place; the
   whole line used to be copied from page one. The field carries the
   footer's size.
5. **Header bands found as tables** (`z21762915`: two rules above and below
   the header, an empty grid on every page) are lifted; their text goes to
   the header, their pictures too (`z20276275` keeps its logo in a cell).
   A band whose letters another piece already draws is not drawn again.

Pictures: a repeated picture with no clean copy - every photo caught its
page's text - is lifted and NOT drawn. `z22051439` photographs its corner
graphic with the number on it, and drew page one's 80 on every page. For
position groups the old "any copy caught text" became "most copies": the
`z21760107` logo caught a word on 1 of 16 pages and was dropped everywhere.

**The fit loop was fooled by the headers.** `fit._spilled` matches our pages
to the original's by shared words. With alternating headers the overflow
page carries the next page's header, matched it, and the loop shrank the
wrong page: `z19799068` 95% -> 42% right page. Words on a third or more of
the original's pages are now left out of the matching.

**The checker** (`compare._furniture_texts`) now gives each page the header
Word draws there (first / even / default), and reads a PAGE field as the
number that page shows instead of skipping it, so "صفحة92" matches. Scored
both ways on the same output, neither change moves any file's number.

**Results** (`--max-pages 30`, `2026-09-22-{dev,regression}-n5b-headers-3`):

    dev, all 48     nothing lost 99.9% (unchanged, FLAGS 24)
                    words in order 97.6%, right page 57.5 -> 60.0%
                    8 files better on right page, 0 worse
    theses          unchanged: 100% / 99.0% / 80.4%

    z21762915   13% -> 71%   39 -> 26 pages (orig 23)
    z21761968   73% -> 97%   21 -> 20 pages (orig 20)
    z21751977   31% -> 47%   21 -> 19
    z20538636   14% -> 22%   numbered 157.. not 5202..

**What the numbers do not say:**
- `z21762458` words in order 97.9 -> 96.4%. Same words; the original's text
  layer lists its footer right after the header, at the TOP of each page,
  and we now print it at the foot where it is. The checker's order, not ours.
- The table score falls on three files (`z21762915` 46 -> 0 tables): the
  PDF side counts the header bands as tables. Not tables lost.
- Pictures not drawn, on purpose: `z21418248`'s two header banners (every
  photo carries the header text, which is now in the header as text) and
  `z22051439`'s corner graphic. The decoration is gone, not the text.
- `z21763864`: the journal name and running title are not text in the PDF
  (only "- 8 - 10 2016" is), so they are still missing.
- `z19799068`'s page numbers come through a broken font (594, 594, 599,
  411 ...): no number follows the page, so "594" is printed on every page.
  It was a field counting from 594 before - wrong either way.
- `z20276275`'s header title is stretched letters in pieces, jumbled as read;
  it is now jumbled in the header instead of the body.
- `z21760107` alternates two footer pictures; both are drawn on every page.
- Page numbers are Word's digits, not ٦٦ (N5a).

Looked at (`out/work/n5b/look`): `z21762915` p10, `z20276275` p12,
`z21761968` p4, `z22051439` p5, `z21763864` p3 header and footer. Also seen,
not this step: `z21762915` still writes each page's text twice (N5f).

## The page as the reference, 2026-09-22/23 (FLAGS 25)

Moaz, from page 1 of `z21762915`: numbers wrong, words wrong - "our main
concern is 100% text accuracy". He was right, and no score could see it.
The page prints 1315, 1897, محمد; the PDF's hidden text says 3133, 3675,
زلمد; we copied it, and every score compares with that hidden text. The
project's "extraction works, 88/88" measured that Arabic came out, not that
it was the right Arabic. His theses are fine because their text comes from
/ActualText labels, which are right.

**The instrument** (`harness/truth.py`): Windows' own Arabic OCR
(Windows.Media.Ocr, installed; `convert/ocr_windows.ps1`) reads three pages
of each original; each is compared with our page of the same number, both
ways - found (page words we have) and wrong (our words the page does not
show). Built three times before it could be trusted:
- vowel marks cut words in two until they were removed before splitting
- numbers are cut differently on each side (1831 against 18 31): compared as
  runs of digits
- leaving out words inside pictures left out ALL of the theses - each of
  their words is a picture labelled with its text. Running headers are left
  out instead: words at the top or bottom of more than one page read
Calibrated on the theses, whose text is known right: found 91.5%, wrong
3.5% - OCR misreadings (انغظر, الوقودد) and note numbers Word draws itself.
English and Turkish are not counted: this OCR reads them badly.

**Cause 1: the font repair would not believe the installed font where it
mattered** (`convert/witness.py`). `z21762915`'s body font stores the
shape of 1 as "3" and the joined pair محـ as "لز"; the installed Traditional
Arabic names both right. FLAGS 23's rules refused: never change a stored
digit (because Word shows 2 as ٢ - but here 3 is not 1 in any script), and
a joined pair only over junk (one shape can be named several ways). And the
installed names can be nonsense - the embedded Times New Roman Bold is
numbered differently (ئإ, ڡ) - yet were used where the stored looked like
junk. Now, for every shape where the file and the installed font disagree,
up to four pages are read by OCR and each word compared with the same spot
read both ways; a match on one side only votes for every disputed shape in
it. Shapes not seen follow their font's lean (5+ settled, 4:1). OCR never
writes text: it only chooses between two names, so a misreading matches
neither and votes for nothing. `z21762915` page 1: 22 wrong words -> 2.

**Cause 2: a third of `z21762915` was a second copy of itself.** `_backfill`
puts back text another reading found and the chosen one lacks. It compared
the chosen reading, spelling-repaired, with the others, unrepaired: الهوية
did not match اهلوية, looked missing, and 3,482 of 9,629 words were added
again, misspelled. Now the others are repaired the same way and compared
without vowel marks; table cells count as present. 3,482 -> 0.

**Results** (`2026-09-23-{dev,regression}-decoded`, the three files Word
held locked re-run apart):

    page truth, 48 small     found 87.2 -> 88.1%, wrong 17.1 -> 15.5%
                             16 files better, 0 worse
    z21762915                found 80 -> 96%, wrong 54 -> 12%, 26 -> 24 pages
    z20763272                found 84 -> 95%
    theses                   unchanged: 91.5% / 3.5%, gate 100%,
                             right page 80.4 -> 80.6%
    dev right page           60.0 -> 62.7%, words in order 97.6 -> 96.9%

**The gate fell on three files, and each time the gate's reference is the
one that is wrong:** `z21763864` 98.9 -> 81.5%, `z21764254` 100 -> 98.8%,
`z21762458` 98.7 -> 98.3%. Checked sentence by sentence: we write الإ where
the reference has الٕ with no alef, كبير ا where it has كبيرر ا; on
`z21762458` only note numbers differ (FLAGS 24). The misspelled duplicate
had been matching the reference's own mistakes. Words in order falls for
the same reason. The page-truth score did not fall on any of the three.

**Not helped:** `z21751977` (3% found - its body text is picture tiles, not
text; found 2026-09-24, FLAGS 28), `z21763864` (34% - its words are drawn, not
stored as text), words split where the font changes (FLAGS 24 cause 2:
بمجالات, بين read بني).

### The gate asks the page; split words, 2026-09-23

**The gate** (`harness.loss.judge`; confirmed by Moaz 2026-09-23): a sentence coverage()
flags is taken to its page and read by OCR. If the page shows any word the
reference says we lack, the loss is real. If it shows none - while plainly
reading the rest of the sentence - the reference was wrong there, and the
sentence is excused and listed in the run. Checked both ways: five real
sentences deleted from a clean file are still caught; on `z21763864` the
sentences still flagged are ones where our text is wrong too (املس يحية).
Eval reports `kept` (judged), `kept_strict`, and every excused sentence.

**Split words** (FLAGS 24 cause 2). Our wrong words, sorted by cause across
the sampled pages: one or two letters differ 37%, letters in the wrong order
22%, a word cut in two 21%, not on the page 19%. Half of the missing side is
OCR noise (the theses miss 8.5%); the gap is the WRONG side, 15.5% against
the theses' 3.5%, and one file (`z20397518`) holds 23% of it.

- A PDF writes one line as several pieces and can cut a word between them
  (`z19773087`: "سورية، ي" | "حتفظ المؤلفون", touching at x=503). FLAGS 24
  joined every touching pair and glued real words. Now `reader._glued`
  joins only when they touch on one line, an Arabic letter meets an Arabic
  letter with no space from either side, and the joined word is one the
  document prints whole inside a single piece elsewhere
  (`reader.vocabulary`; the page's plain text already glues touching pieces
  and would vouch for قامYazdanian). 12 files better on the page, 0 worse;
  wrong 15.5 -> 15.1%; theses unchanged.
- **Most splits are not at pieces at all** (350 of 453 left): Word stores a
  real space character inside the word - الواحد as "الواح د", the space
  drawn on top of the د; إيجاد as "إ يجاد", the space drawn after the last
  letter. Moving each space to where it is drawn was tried and REVERTED:
  wrong 14.8 -> 14.6%, but 8 files worse on the page, 10 files lost real
  sentences (`z21764410` 95.4%), right page 62.4 -> 60.6%. Two letters that
  touch round a space also happen at real word boundaries. Needs a better
  signal - the letters' own joining forms are the candidate.

Runs: `2026-09-23-{dev,regression}-splitwords` (kept), `-respace` (reverted).

**The title that went missing** (found in the before/after of `z21762915`
page 1). The article title and author were absent from the body, and it was
not N5b lifting them into the header, as first thought. `reader.
_drop_text_inside_tables` removed any paragraph whose text a table on the same
page carried, wherever on the page either sat. The header band repeats title
and author, and once the band's font was repaired (witness) the words matched,
so the title 40pt below the band went as its copy. Now a paragraph with a
position must also sit inside the table's height; without one (tags route)
text alone decides, as before. Four more paragraphs came back on dev, all real:
two more article titles under a repeating band (`z21094872`, `z21095413`), and
two lines belonging to one table but matched against ANOTHER on the page - a
row of years the table-finder left above its table (`z20252151`), and a survey
heading the first table holds only in pieces (`z20589058`). Nothing lost,
pages and every other file unchanged; `z21095413` words in order 98.9 -> 99.6%,
right page 37.3 -> 38.4%. Runs: `2026-09-23-{dev,regression}-titlekept`.

**Spaces inside words, by the letters' shapes** (`pdftext.join_map`, second
attempt; Moaz's go 2026-09-23). A letter drawn in a joining form is joined
across the space on the page, so the space is no word boundary. The form is
read from the installed font's shaping features (`glyphs.forms`): the shape
an `init`/`medi` rule makes joins forward, `medi`/`fina` back. Three guards,
each from a wrong join seen first:

- A shape serving several forms is evidence only if every one joins: Arial
  draws ب alike at the start and middle of a word, and taking it as `medi`
  glued names whole (لخضربنبوزيد, جامعةمحمدخيضر on `z21760107`).
- The two letters must touch on the page. Where letters are stored out of
  drawing order, neighbours in the text are apart on the page and joined to
  other letters: "م في كان" became ميفكان, "ي ب ف الطريقة" يبفالطريقة.
- The installed font must name the shape as the letter the page says, and -
  as for lam-alef - a stored word that also appears without the evidence is
  left alone everywhere. A font not installed gives no evidence.

It is a text-to-text map inside `fix_map`, so the reader and the checker
apply it alike. 1,573 candidate spaces on dev before the guards; typical
joins الوطن ية, ع ل ى, ف لسطين, املس يحية. Page truth on dev: wrong 14.8 ->
14.3%, found 88.7 -> 89.1%, 24 files better, 0 worse; theses 91.5/3.5%
unchanged. Words in order, right page, pages: unchanged on every file.
Nothing lost: dev and regression unchanged strict; `z21763864` (shapes-drawn,
reference misspelled) judged 90.0 -> 89.7% because the page tie-breaker
excuses a slightly different set of its sentences - strict unchanged at
81.5%, and on the same output the joins raise it (89.0 without, 89.7 with).
Left alone by design: a space after a letter that never joins forward
(إ يجاد - ا د ذ ر ز و carry no evidence), fonts not installed.
Runs: `2026-09-23-{dev,regression}-joinforms`.

**Letters in the wrong order: one thing tried and reverted.** Traditional
Arabic draws لم, في, لج, مح, ين as one shape each, Word names each in reading
order, and the extractor reverses a right-to-left line letter by letter - a
shape's own letters with it (بين read بني). Storing every such shape turned
round in the repaired copy (`glyphs.drawn_order`) was REVERTED: page truth
did not move on a single file (0 better), while nothing-lost fell 99.8 ->
95.7% and words-in-order collapsed on the Traditional Arabic files
(`z21763864` 4.6%). The geometric repair (`arabic.repair_ligatures`, a59436e)
already turns these pairs back, from the zero-width half each leaves; given
them the right way round it turned them wrong again, on one side. Runs:
`2026-09-23-{dev,regression}-drawnorder` (reverted - the regression half of
that run also carried the footer change below).

What really leaves بني is the map's safety rule: a repaired word that also
appears unrepaired somewhere is dropped everywhere, and بني is also a word
(printed unrepaired seven times in `z21762915`). Such a word is now keyed
with the word beside it - "بني الجزائريين", "العالقة بني", "يف ثالث" - when
that pair never appears unrepaired (`pdftext._with_neighbours`). Page
truth on dev: wrong 14.3 -> 14.1%, found 89.1 -> 89.4%, 6 files better, 0
worse; every other score and the theses unchanged.

**The footer that said the issue twice** (`z21762915`): the footer band
ends ":العدد05 - أفريل2017" and the line holding the page number repeats it.
A text piece at the same edge as a drawn band now leaves out the words the
band prints (`Furniture.shown`), keeping the page number, whose position in
the line is recounted. Measured with the neighbour keys above: no score
moved on any other file. Runs: `2026-09-23-{dev,regression}-neighbours`.

**Punctuation where it is drawn: tried a second time and REVERTED.** Word
stores some marks away from where it draws them: the full stop ending a
line at its start or inside a word (اله.امل), the colon after المفتاحية at
the start of the line. `pdftext.punct_map` moved each mark to its drawn
place on lines of Arabic only (no Latin, never beside a digit, only across
a stretch that runs cleanly right to left) and carried it as a text map
like the others. Nothing lost fell on two files (`z20397518` 98.5%,
`z22658522` 99.3%), words in order on `عن بعد` 100 -> 66%, page truth 4
files better and 5 worse. The cause is the one `line_items` records from
the first attempt: a moved mark crosses words - a line-final stop stored
at the start makes the whole line the key - and a key several words long
fires only where the reader and the checker split and spaced the text
alike. A fix has to stay inside one word, or be applied to the characters
before either side extracts. Run: `2026-09-23-{dev,regression}-punct`.

### Punctuation where it is drawn, third attempt: kept, 2026-09-23

Why the marks move: Word draws a right-to-left line in runs, each laid out
left to right; MuPDF turns a run's Arabic letters round into reading order
but leaves a comma or full stop at the run's left end where it was. So
`،عشر` for عشر،, `ا،جلزائر`, `اهل.امل`, a line-final full stop first.

Tried first and dropped: changing the order the repaired copy STORES the
marks in (moving the mark into a text block of its own, or placing each
character by its own position). MuPDF's line building then broke the line
(ومع on a line of its own) or lost the word entirely - it depends on
guesses about the stream that are not ours to rely on.

What is kept: `convert/order.py`. Every one of the 19 places the reader,
the pair repairs (`pdftext`) and the checker (`compare`) read a page's text
goes through `order.get_text`. Each line's marks go right after the word
drawn nearest on their right; letters and spaces never move, so the pair
repairs see the extractor's letter order as before. The order is worked out
once per line from the characters' positions (rawdict) and applied to
every reading of that line - for plain text and the structure tree, by
looking the line up by its text, a letter and its vowel marks counted as
one (the plain reading keeps marks the others drop). Left alone: lines with
digits, %, or Latin (they run left to right inside the line); lines whose
characters have no place of their own (the theses: every character at x
310, a label over a drawing); lines stored in drawing order as a whole
(فدهلا). A vowel mark stored after a moved comma stays on the word
(مبكراً،), and a mark that was all that parted two words (بإدارة،الرصف,
2.5 points apart) leaves a space.

Checks: with the move switched off (`QIRTAS_PUNCT_ORDER=0`) every reading
equals MuPDF's on all 1,033 dev and regression pages; with it on, the
dict and rawdict readings agree on every page, and 3,321 of 3,326 moved
lines are found in the plain reading (the 5 left are two-letter pieces in
the theses). On 9 files, off against on: nothing lost 100% throughout;
page-truth wrong words `z21762915` 8.2 -> 7.1%, `z20397518` 7.7 -> 7.2%,
`z22658522` 10.6 -> 10.4%, `z20128978` 10.4 -> 10.2%, none worse; theses'
words in order unchanged (100, 100, 96.4%). Words in order dips on some
files (`z20128978` 92.9 -> 91.9%) while finding one sentence MORE - it
weighs where sentences land, and the moved marks re-cut them. Right page
rises on most files, the theses too (`مقدمة البحث` 83.5 -> 92.9%) - there
it is the READING BACK of Word's PDF of our file that improves, not our
file: that side goes through the same extractor. Runs:
`2026-09-23-quick-punct3-{off,on}`.

What went wrong on the way: the first version moved a comma to the end of
the line, collecting every space it passed; the theses' zero-width labels
sent every full stop to the first word; the structure reading splits lines
its own way and was left unfixed until its lines were looked up from a
rawdict read with the same flags; and `z20397518` glued words the moved
comma had parted, until the gap rule.

Left: marks beside digits or Latin (`الإ8 ،براهيمي`, `:العدد05`), brackets.

### Page truth counted header numbers against us; the breakdown redone, 2026-09-23

Two faults in `harness/truth.py`, found by breaking down the wrong words
on the full run. (1) Running headers and footers are left out of both
sides - but numbers only out of the page's side, so a header's volume and
year (المجلد36 العدد6 2014, "2(2) 2024, pp. 1-17") read as wrong on every
page of ours; and the OCR reads "pp. 106-116" as one number, 106116, which
matched none of ours. (2) Only OCR words made wholly of digits counted as
the page's numbers, so بحوالي6000 hid the 6000 we wrote. Now header numbers
leave ours too (exact, or two digits or more held in the header's digits),
and every run of digits in an OCR word counts. Rescored on the same Word
files (the newbase run): dev wrong 11.8 -> 9.3%, found 90.8 -> 90.7%, no
file worse; theses 3.5 -> 2.8% wrong, 91.5 -> 91.2% found. Numbers before
this are not comparable: compare the gap above the theses instead - 8.3
points under the old score, 6.5 under the new, on the same files.

Breakdown under it (dev, word-weighted 8.4%; theses 3.1%), each group
against the theses' share: pieces of words 2.43 vs 0.47%, two words glued
1.28 vs 0.29, letters in another order 0.77 vs 0 (mostly `z21763864`),
numbers 1.43 vs 0.69, not near any page word 1.55 vs 1.09, another page
0.37 vs 0.11, one letter off 0.60 vs 0.44. Of the pieces, 380 of 400 are
in the PDF's own text as stored: spaces Word stores inside words
(م رجعية, للعلا قات, الا ستنتا) where `join_map` found no evidence. The
other 20 are ours, most of them one figure's labels (`z19798743`).

Why `join_map` leaves them, for the 66 spaces whose two sides joined are a
word the page's OCR reads whole: 64% the letter before the space never
joins forward (إ يجاد, زود نا, و المحسوبة - no shape evidence either way,
and some are how the author typed it); 29% both letters drawn in their
unjoined shapes (الم ستخرجة, ال بدئي, المن تجة - the page itself draws the
word broken, and only the OCR reads it whole); 8% a gap drawn. What is
left of the group is not reachable from the letters' shapes. An idea not
yet tried: join two pieces where the joined word stands whole elsewhere in
the same document and a piece does not stand alone there.

### The space's own place, 2026-09-23

Where the letters' shapes say nothing, where the space character is drawn
does. Measured on the dev set's OCR'd pages (`2026-09-23-dev-newbase`),
every stored space between two Arabic letters labelled by the OCR: FAKE
where the two sides joined are a word the page shows (238), REAL where both
sides are shown as words and the joined one is not (9183).

- The space's own drawn width does not separate them (same for both: it is
  the font's space advance). This was the idea from other extractors
  (pdf_oxide #1109); it does not hold for Word's PDFs.
- The gap between the two letters does: FAKE median 0.004 of the type size,
  REAL at least 0.15 (5th percentile). Alone, below 0.1: 222 of 238 FAKE,
  142 REAL wrongly.
- Where the space is drawn: REAL spaces sit between their letters 98% of
  the time, FAKE 10% - Word draws the stored space somewhere else on the
  line. Close letters AND the space elsewhere: 210 FAKE, 52 REAL.
- 37 of those 52 are one file (`z21761968`), and `z22179435` another few:
  pages whose spaces are drawn away from their words in general. Only pages
  where at least 80% of the spaces between Arabic letters sit between them
  count: 209 FAKE, 10 REAL.

`join_map` takes this as a second kind of evidence, after the shapes, and
with `_touch` still required, and closer than `_touch` (0.1 of the type size:
"مباشر أو" is 0.15 apart with its space drawn away). The "every occurrence
must carry the evidence" rule still holds. `QIRTAS_SPACE_PLACE=0` turns it
off.

Quick run, 11 files (9 with the most split words, the two pages above, two
theses), off vs on (`2026-09-23-quick-space-place-{0b,1}`; `-0` has the
truth score, taken before its Word files were overwritten): gate 100% both;
page-truth wrong 7.2% -> 6.1%; 7 files better, none worse; `z21761968`,
`z22179435` and the theses unchanged. About 500 words joined, 317 distinct;
read through, one wrong: في منحني -> فيمنحني (`z19799068`). The document-
vocabulary idea above was not needed for this part.

### امل for الم: the lam pairs by their shared edge, 2026-09-23

Full run first (`2026-09-23-{dev,regression}-newbase`, fonts installed,
stretching stroke + table cells + punctuation): page truth on dev wrong
14.1 -> 11.9%, found 89.4 -> 90.7%, 22 files better, 0 worse; theses
unchanged (3.5 / 91.5%); nothing lost unchanged; right page 62.5 -> 64.6%;
words in order 97.0 -> 96.5% (the cells and the marks, above).

`z21095413` keeps املهاجرين, املغاربة, الأملاني in its body although the
geometric repair turns each round there. Its running header, in Sakkal
Majalla at a larger size, stores the same word with a meem that is NOT zero
width (6.4 pt) - but it ends at the lam's edge, the lam running on past it,
the signature the alef-lam case already reads. The header copy went
unrepaired, so the map's safety rule dropped the word everywhere.
`repair_ligatures` now reads the shared edge for لم لح لج لخ and في too.
Only these: the same test on any two letters changed 293 words on dev, 195
of them from a spelling seen elsewhere to one never seen (مركز -> مكرز,
الصراع -> الصرعا - a ra's tail and an alef end where their neighbour ends).
Restricted, it changes 21, and 19 become a spelling seen elsewhere (the
other two, المقاولاتية and والخاسر, are plainly right). جم/مج is left out:
جملة is a word.

And `join_map` joined "امل حددات" to املحددات: it built the joined word
from the stored letters. It now builds it from the pair repair's reading,
whose spaces sit where the stored ones do.

Page truth on 7 files against the full run: `z21095413` wrong 9.8 -> 6.4%,
found 94.8 -> 98.2%; `z20763272` 9.5 -> 9.3%; `z21418248` 9.3 -> 9.1%;
the rest and the thesis unchanged; nothing lost 100%. Run:
`2026-09-23-quick-lampairs`. Left: `z21763864`, whose widths are not
trusted, so no pair repair runs there.

### What the remaining wrong words are; the stretching stroke, 2026-09-23

**Breakdown** of the 3,390 words on dev pages that OCR does not read
(`2026-09-23-dev-neighbours`, each word put in the first group it fits):
not near any word on the page 21%, numbers 20%, a piece of a page word 20%,
two page words run together 16%, the letters of a page word in another
order 14%, one letter off 6%, a word from another page of the file 4%. The
same count on the theses, whose text is right, is the OCR's own share -
3.6% of words: numbers 1.4 points, runs-together 0.8, pieces 0.5, one letter
off 0.5, not near 0.4, other order 0. So of dev's 13.9%, about 10 points are
ours; most of "numbers", "pieces" and "run together" there is the OCR.

**The largest single cause was one fault in two files.** Word justifies a
line by drawing a stretching stroke between letters: a shape of Times New
Roman's and Arial's (glyph 1127) with no letter of its own, 125/1000 em
wide. `z20397518` stores every one as ب (شبببببكات for شبكات), `z20276145`
as ا or ت (تعاارف), and `z20397518` also stores Simplified Arabic's space
as ا - whole paragraphs read as one word. The installed font names neither
as an Arabic letter, so `diagnose` left both. Now a shape the font gives no
text, at most `KASHIDA` (150/1000 em) wide, stored as a single letter, is
stored as the stretching stroke, and a shape the font names a space, stored
as a letter, as a space (REPAIR_VERSION 5). Across all dev and regression
files only these two files and `z21763864` hold such shapes.
Page truth: `z20397518` wrong 54.4 -> 7.7%, found 51.1 -> 95.5%;
`z20276145` wrong 18.4 -> 6.9%, found 82.5 -> 96.5%; five other files
unchanged. On the 48-file average that is about 14.1 -> 12.9%, an estimate
until the next full run. Run: `2026-09-23-quick-stretch` (7 files).

**A gate fault it exposed.** With its spaces back, `z20397518`'s reference
splits into sentences, and five hold ص where the page prints ، (a comma
the scrambled Simplified Arabic stores as ص, which the page's OCR could
not settle). The gate's page check should excuse them, but asked whether
the page shows الطرقص by searching all the page's words run together - and
found it in الطرق followed by صيانة. Now asked of whole words, or two or
three side by side (a word the OCR cut in two). The looser search stays for
"did the OCR read the rest of the sentence", which `z21763864` needs.
Re-judged every file with excused or lost sentences: no change. This is
likely what cost the gate on `z20397518` in the punctuation attempt above.
Words in order on `z20397518` fell 99.9 -> 96.4% for the same reason: the
reference is wrong there and we are right.

**Words written backwards were mostly table cells.** Of the words OCR
reads in another order, most (`z22639353`, `z21013208`, `z20375390`'s
header band, `z21764080`, `z19799524`, `z21760107`) were never backwards in
the PDF: they sit in cells, and the table finder returns Arabic in visual
order. `_cell_text` already re-reads each cell off the page, and trusts that
reading only if a 14-letter probe from the middle of the cell is found in
the page's text. In a cell of several lines the probe crosses a line break,
and the page's text puts the cell's lines among its other text - so the
probe was found nowhere, and the cell fell back to the table finder's
backwards text. Now every line of the cell is probed on its own. Across dev
and regression, 300 cells change from the backwards fallback to the page's
reading; 81 still fall back (mostly cells a few letters long, where the
cell's edge cuts a word). Page truth on 7 short files: wrong words
`z22639353` 9.9 -> 5.0%, `z21013208` 21.8 -> 17.9%, `z22658522` 11.8 ->
10.6%, `z21067084` 11.9 -> 11.2%, the rest unchanged; gate 100%. Words in
order on `z22639353` fell 78.9 -> 72.9%, and its words out fell 819 -> 763
(the original has 722): read backwards, the cells were not recognised as
the body text's copy, so both were written; now one is, and the table's
cells come in table order, which that score reads as moved. Run:
`2026-09-23-quick-cells`. Not yet measured on the longer files it touches.

The rest of that group is a different fault: `امل` for `الم` (املسلمون,
املحددات - `z21763864`, `z21095413`, `z21094872`, `z21418248`), a joined
pair stored the wrong way round that the existing pair repairs miss.

**Fonts named differently from the installed file** were read as not
installed: Word cuts a PostScript name at 24 characters
(AF_Diwani-NormalTraditio), and some files name a font by its family
("(A) Arslan Wessam B"). `glyphs._path` now matches both. The repaired copy
is also cached against the list of installed fonts, so installing one
redoes the repair.

### Words cut between touching pieces; marks beside numbers; Symbol's dashes, 2026-09-23

Found on a random page no fix was tuned on (`z21490618` page 12), which
still showed التأ هيلي, والخد مي, `المصرفية ،`, `1.2.3 .متطلبات` and the
list dashes as boxes.

**Words cut between two touching pieces.** Those two are not a stored
space: the PDF writes the line as two pieces that touch, and cuts the word
between them. `_glued` joined such pieces only when the whole word is
printed somewhere else in the document; these are not. Measured on the dev
set's OCR'd pages (`2026-09-23-dev-newbase`), every pair of touching pieces
on one line with an Arabic letter either side and no space, labelled by
the OCR as in "The space's own place": 174 cut words, 143 two words.
- The pieces' own boxes do not separate them: a piece's box runs on over
  the space after it, so two words' pieces "touch" as closely as a cut
  word's (both medians 0.004 of the type size).
- The letters either side of the cut do: cut words median 0.002 of the
  type size apart (95% under 0.02); two words at least 0.25 (5th
  percentile), a space's width. Between -0.05 and 0.05, and not after
  ة or ى (which end a word - two of the few two-word cases): 75 more cut
  words joined than the vocabulary finds, no two words wrongly.

`_glued` now takes this as evidence after the vocabulary, from
`_letter_ends` (a rawdict read with the same flags, keyed by the piece's
box). On the quick set's files it joins 169 more; read through, none
wrong (ك|أوكرانيا, ف|قامت are the prefix, rightly). `QIRTAS_SEAM_TOUCH=0`
turns it off.

**Marks, spaces and brackets beside numbers and Latin.** On a line
holding digits or Latin, the extractor stores what stands between the last
Arabic word and the number at the line's far end: ` وبأطوال30` for
وبأطوال 30, `:المجلد07` for المجلد: 07, `( ،فارس2002)` for فارس، (2002).
Of 871 such lines on the dev sample pages, most change. This is also a
share of "two page words run together" (الشكل7, في60). `order._order_mixed`
now reads these lines: each run of digits or Latin is one word, with what
is stored and drawn inside it (2.11, DVB-S, Omega loop); a mark goes after
the word drawn on its right, as on Arabic lines; a space or bracket moves
only when stranded at the line's end or beside a mark, and only when drawn
beside a number or Latin run. Two faults found by reading 40 lines each
time, both fixed before measuring: brackets beside Latin came out mirrored
(`)TGV(`), and a space between two Arabic words drawn out of place was
moved, gluing them (سبققدّم). A third found by the gate: English lines
with an Arabic word in them (`z22179435`, `z21760107`'s abstracts) were
read as right to left and text went missing - gate 98.8% and 99.6%. Lines
with more Latin letters than Arabic are now left alone. And a fourth, also
by the gate: `(Evershed,` at a line's end in `z21760107` - the comma is
the Latin run's, drawn at its right end, and was moved after the Arabic
word beyond; the checker's plain-text reading moved it and ours did not, so
a sentence we wrote right read as lost. A mark stored right after a number
or Latin run and drawn at its right end now stays.

**The full run caught what the quick set could not** (`2026-09-23-dev-textfixes3`):
the gate fell on 7 files (98.4-99.6%), all tagged PDFs, all at a bracket or
comma beside English or a number (`معين (Benchmark`, `(Kim`, `[16`).
Word labels an English word or a number apart, so `read_tags`, reading the
page by its labels, never sees `معين` and `Benchmark` on one line; the
checker's plain reading does, and moved the bracket. The two disagreed and a
sentence we wrote as the file stores it read as lost. The quick set's files
are mostly untagged, which is why it showed nothing. Now (`order._Whole`) a
line with numbers or Latin is reordered only where the structure-tree reading
also has it as one line; where Word split it, both readings leave it as
before. The 8 files (the 7 and `z20276145`, whose Word file was locked by a
stray Word process in that run and failed to save): gate 100%, wrong words
kept their gain (`z20252126` 4.2 -> 2.9%, `z20276145` 5.0 -> 3.7%,
`z22658522` 10.2 -> 9.0%); quick set unchanged at 5.2%
(`2026-09-23-quick-gatefix`, `2026-09-24-quick-all-on-4`).

Full run (`2026-09-24-{dev,regression}-textfixes4`, with the space's place
above): dev page-truth wrong 9.3 -> 7.8%, found 90.7 -> 91.9%, 36 files
better, none worse; theses 2.8% unchanged; gate 99.8%, only `z21763864`
under 100% (89.7 -> 90.0%); words in order 96.5 -> 96.4%, right page 64.6
-> 65.4%; regression unchanged, gate 100%.
`QIRTAS_PUNCT_MIXED=0` turns it off. A moved space or bracket joins the
span before it, like a moved mark.

**Symbol and Wingdings.** Word's list dashes and bullets, and Greek and
maths signs, are typed in Symbol or Wingdings, which store them as private
codes (U+F02D, U+F0B7): the code reaches Word without the font and shows
as a box. 96 in 5 dev files (42 in `z21490618`). They go through the same
repair as AGA Arabesque's signs, by Adobe's table for Symbol and the shapes
looked at for Wingdings (REPAIR_VERSION 6). Wingdings 2 and codes not in
the tables are left. `QIRTAS_SYMBOLS=0` turns it off.

**Numbers were checked, not fixed.** Of 4,437 numbers on our dev sample
pages, 336 are not read by OCR on the page. 272 of those are exactly what
the PDF stores, and looking at 25: the OCR's misreadings (l for 1 in
DOIs, 20l0, whole references read as one number). 45 look reversed, but
are chance matches in reference lists. Real: a handful (`z20276145`'s
0302). No fix: the numbers task is mostly the instrument.

Quick set, page truth wrong words (11 files, `2026-09-23-quick-*`): before
all three 6.1%; touching pieces only 5.8% (`mixed-off`); marks beside
numbers only 5.5% (`seam-off`); both 5.2% (`mixed-seam-on`, before the
English-line fix, gate 99.9%). With the English-line and Evershed fixes and
the Symbol table (`all-on-3`): wrong 6.1 -> 5.2%, found 95.3 -> 95.9%, gate 100%
on every file, words in order 98.7% as before; 7 files better, none worse,
the theses unchanged (`z19798743` 8.6 -> 5.8%, `z19799068` 8.5 -> 5.0%).

### Citations where a line wraps; a % stored at the wrong end, 2026-09-24

**The diagnosis in TASKS was half right.** The note said `(Shegaze et al.,
2020)` is written `العالمي( Shegaze et al., 2020 )` and that Word then puts
the brackets in the wrong place where the line wraps. The spacing was
wrong, but the brackets were not: measured by drawn position and glyph
shape (a tool that prints each rendered line left to right, with each
bracket shown as the shape actually drawn), Word draws them the way it
draws them in any Arabic document typed in Word. The real fault was what
lies INSIDE the citation. The whole paragraph was one right-to-left run,
and where a line wraps inside the English, Word treats a `&`, comma or full
stop at the start or end of a line as Arabic and moves it to the far end:
`(Zumla, 2011 &` for `(& Zumla, 2011` (`z20252507` page 3, line 3).
Measured in Word on three ways of writing the same citation at 34 column
widths: one right-to-left run (ours) moved the `&` wherever the line broke before
it; the English as a left-to-right run of its own, brackets left in the
Arabic run, never did, and draws exactly like the other ways when
the citation does not wrap.

**Writer:** English inside an Arabic paragraph - from its first Latin
letter to its last letter or digit, with a closing full stop and a bracket
opened inside - is now its own left-to-right run, in body text, table cells
and notes (`footnotes.directional`). A number alone stays in the Arabic run.
`QIRTAS_LTR_RUNS=0` turns it off. `test_alignment` renders a citation
wrapping at 30 places and checks the `&` on every line (2 wrong with the
switch off, 0 on).

**Reader: the spaces.** Where Arabic meets English or a number, each is its
own piece, and the pieces were joined with a space: `( Shegaze ... 2020 )`,
`15 %`. Now (`reader._tight`) two pieces meeting at a bracket or `%` are
joined without one when their inked edges touch on the page (within 0.05 of
the type size). And (`reader._edge_spaces`) spaces the extractor stored at a
right-to-left piece's start go where they are drawn: at its left end they
end it (` . إنّ` after `2005)`), just right of a bracket that ends it they
stand before it (` المستوى العالمي(` - the original prints العالمي (Shegaze).
Two faults found by reading every change across the 86 dev and regression
files, both fixed before measuring:
- On pieces the PDF stores backwards (`z20161304`, ةليلقلا), moving the
  space changed which word the spelling repairs saw: في became يف in 24
  places. Both rules now act only on pieces whose letters run right to left.
- A space moved off the start of a paragraph's first word broke the
  lam-alef repair, which reads a word's start by the space before it:
  لا يوجد became ال يوجد (`z20589058`, `z21087226`). A space before a word
  now stays; only one before a mark, bracket or % moves.

**A `%` stored at the wrong end** (`order._percent_first`, both readings):
`15 من حالات%` - the 15 is the piece before, and this one stores its % last
but draws it at its right end, against the 15. Now `15% من حالات`. Across
the 86 files: 197 changes that touch letters, all a `%` back beside its
number (`84 في%` -> `84% في`, `إلى% 44` -> `إلى 44%`) or a repair now
reaching its word (يف -> في 4, ال% -> لا 1). `QIRTAS_TIGHT=0` turns off
this and the two reader rules.

**Not fixed:** `Tuberculosis(TB)` on the same page. The PDF stores the `(`
at the start of the Arabic piece before TB; the reading by structure labels
sees that piece without TB, the plain reading with it, and moving the
bracket in one and not the other is what broke the gate on 7 files on 23
Sept. Left.

**"Right page" is thrown by the English runs, not the page.** Quick set
(`2026-09-24-quick-cite-{off,on}`, 11 files): gate 100%, page-truth wrong
5.2% both, found 95.9% both, words in order 98.6% both; right page 72.8 ->
72.4%. Isolated (`cite-ltroff`, 3 files): the drop is the English runs.
Read back from our rendered page, a left-to-right run comes out glued to
the Arabic word before it (`الأنظمةHallonsten, 2021`, `منChatGPT`), though
the page draws the space; the glued word matches nothing on the original
page. Split at a change of script on both sides, right page reads 72.93 ->
72.78%. The rest is lines breaking in other places. FLAGS 27.

Full run (`2026-09-24-{dev,regression}-cite`, against `textfixes4`): the
gate unchanged on every file (99.8%, only `z21763864` under 100%, 90.0%);
page-truth wrong 7.8% and found 91.9%, the same on every file - it counts
Arabic words of three letters or more, and none of this changes one; words
in order 96.4% as before; right page 65.4 -> 65.7% even with FLAGS 27
(`z19799524` 21 -> 20 pages, its own count, 72.9 -> 93.1%; `z21418248` 29
-> 30, the squashed pictures below). Regression identical.

### What the rest of the wrong words are; pictures drawn squashed, 2026-09-24

Looked at while the full run above ran, so on the 25 dev files it had not
yet reached (`textfixes4`'s Word files, 530 wrong words, every one counted
rather than the 15 a page `truth.json` keeps):

    one letter off          31%   many correct words (قام, ابراهيم): OCR
    not on the page         26%
    one word cut in two     17%   + a piece of a word 9%
    other words overlap      8%
    two words glued          5%   + glued to a number (العدد6) 3%

**Glued words are nearly all one file.** `z20276275` stores whole phrases
with no space (`ﻟﺘﻄﺒﯿﻘﺎتﻣﻘﺎرﻧﺔﻣﻨﮭﺠﯿﺔ`); the page draws the gaps. Two letters
side by side with no space between, drawn at least 0.15 of the type size
apart: 308 places in that file, at most one in any other of the 48. Its
display shapes also say where a word ends (a both-sides-joining letter in
its end or alone shape), but only at 92 of them - it stores some letters as
plain Persian ی and ھ. Two files carry 2.4 of the 7.8 points of wrong words:
`z21763864` (drawn as shapes, parked) and `z21751977` (its font is not
installed).

**The file 24 pages against 23 (`z21762915`) is a picture.** Its pages
1-17 land exactly; page 18 holds a photo the author's Word squashed to fit
- 438x333 pixels drawn 350x221pt - and we place it at its drawn width only,
so Word keeps its own shape: 41pt taller. The notes after it spill onto a
new page, and every page after is one late. 107 pictures in 23 of the dev
and regression files are drawn out of their own proportions by more than
5pt; `z21418248` adds up to 580pt, most of a page (22 -> 30 pages). The
writer should give Word the drawn height as well as the width. Some large
negative ones (`z21751977`) may be pictures turned on their side - check.

**Fonts Moaz installed, 2026-09-24.** Every one found by `glyphs._path`
under the PDF's own name (`BoutrosNewsH1-Bold`, `AF_Diwani-NormalTraditio`,
`DecoTypeNaskhSpecial`, `MunaBlack`) except `MunaRegular`: the installed
Muna (alfont.com's copy) has PostScript name `Muna`. A key ending in
"regular" now also tries the name without it. Muna Bold not installed
(`z20538636`, 1,000 letters). Word gets the family, "Muna", either way.
`z20276275` page 12 converted alone and looked at: fonts right; the table
mirrored wrong, squeezed and written twice, the kashida-stretched title in
pieces - the same in the whole-document run, so not the cut.

**Full run after the fonts, 2026-09-24 (`fonts-baseline`, the new
baseline).** Against `cite`, the same code: nothing lost unchanged on every
file (dev 99.8%, worst 90.0% the parked `z21763864`; regression 100%);
words in order unchanged (96.4% / 99.0%); wrong words 7.8% dev,
unchanged. Right page dev 65.7% -> 65.1%, regression 83.6% -> 87.0%.
Only two files moved: `عن بعد.pdf` (regression, 1 page) 0.73 -> 1.00, and
`z21751977` 0.47 -> 0.17, now 20 pages against 18 (was 19). First put
down to DecoType Naskh Special being taller than Word's stand-in - wrong,
see "Pictures at the shape they are drawn" below: the file's body text is
not text at all. `harness.truth` crashed printing
Arabic file names to the console; run it with PYTHONIOENCODING=utf-8.

### Pictures at the shape they are drawn, 2026-09-24

The writer gave Word only a picture's drawn width, so Word used the file's
own shape. Across the 56 dev and regression files, 157 of 1,036 pictures
are drawn at a different shape from the one stored, most by 15-40%, the
worst 2.3 times (`z21418248`); among them the journal logo repeated in the
header of every page of `z21760107` and `z21764080`. Six are drawn turned
on their side (`z20252507` pages 4-6, `z20538636` page 17); none flipped.

Now: the drawn height goes to Word too (`_emit_image`, and the running
pictures in headers and footers), scaled with the width when the width is
capped to the column. A turned picture is photographed off the page
(`reader._turned`), since its stored pixels are the wrong way round for the
drawn box. `_image_fit` already sized pages by drawn height, so the step
that shrinks pictures on crowded pages and the writer now agree. Switch
`QIRTAS_IMG_SHAPE=0`. Test: `harness.test_images`, a squashed and a turned
picture; fails 3 of 4 with the switch off.

Quick run on 11 picture-heavy files (`2026-09-24-quick-pics-{off,on}`):
nothing lost 100% both; words in order 96.2% both; wrong words 8.8% both;
right page 62.0 -> 64.7%. `z20256558` 49 -> 94%, 18 pages -> 17, its exact
count. Worse: `z19773087` 88 -> 72%, 23 -> 24 pages. Its page 18 has two
pictures side by side, which we write one above the other; drawn at their
own shape the chart was shorter and the page just fit. Side-by-side
pictures are the real fault (Part 3). `z21751977` 20 -> 21 pages, but its
body text is picture tiles (FLAGS 28) and its score is noise.

## The thesis corpus, 2026-09-24

**Why.** Moaz: the Zenodo corpus did not match the plan - digitally born
Arabic theses first. Counted: of 225 files, 118 journal articles (median 8
pages), 5 theses (3 usable), 38 scans, half not made by Word; of the 135 dev
files, 33 refused and 15 thin or mostly not Arabic. Moaz's 8 chapters had
stopped moving (100% nothing lost, 2.8% wrong words) and had been tuned on
for weeks. And a full run took three hours.

**What.** Zenodo holds 137 records typed thesis with language Arabic
(`type=publication&subtype=dissertation`, `q=language:ara`; searching Arabic
words matches nearly everything). 114 carry a PDF; 113 are 60MB or less and
were downloaded (637MB). `harness.theses --pick` keeps 37: 42 are not made by
Word, 25 are under 30 pages, 7 mostly not Arabic, 1 picture tiles, 1 thin.
`--cut` takes 13-14 fixed pages from each (README). Split by a hash of the
name: 25 dev, 12 holdout. Regression: two of Moaz's chapters (الفصل الثاني,
with the page-13 looks list; مقدمة البحث, a title page that is a photo).

**Two traps met building it.** Taking pages out leaves the hidden label tree
whole: the tags route read 41,746 words from a 14-page cut of `z22058810`,
and the dead pages stayed in the files (310MB). `_prune` cuts the tree to the
kept pages (69MB). The text of the kept pages is unchanged by cutting -
checked on two old-corpus theses, 100% and 99.9% the same. And `harness.truth`
found files by name anywhere under corpus/, so it scored our 14 pages against
3 pages of the whole thesis (found 78.9%, wrong 23.9%, on 17 files); runs
now record each file's path.

**Baseline** (`2026-09-24-{thesis,regression}-thesis-baseline`, pictures fix
on): thesis set nothing lost 99.4% (worst 94.8%), words in order 94.3%, right
page 61.1%, page inflation 1.14x; page check found 91.7%, wrong 10.1% on all
25. Regression: 100%, 99.9%, 86.6%; wrong 2.2%. 21 minutes for the thesis set,
1 for regression, 1 for the page check - against three hours.

Nothing lost is under 100% on five theses (`z22058810` 94.8%, `z21145041`
95.6%, `z21850164` 97.8%, `z21644412` 98.8%, `z21728839` 99.0%). What reads
as lost is the PDF's hidden text stored backwards (يمازلإلا for الإلزامي) and
invisible joiners where spaces belong - the reference, not us, so far as seen.
FLAGS 29. Page inflation is the other plain finding: 11 of 25 come out 3 or
more pages long, `z3387756` 33 pages for 14.

### FLAGS 29: what the five theses were losing, 2026-09-24

Every sentence the gate called lost on the five was looked at. Four causes,
two of them ours:

1. **The PDF's hidden text stored backwards** (يمازلإلا for الإلزامي,
   `z22058810`, `z21145041`), **zero-width joiners where spaces belong**
   (`z21850164`), **words glued to a neighbour's letter** (هباصاداهجا0) and a
   **broken font table** (أّب for أبي). The reference, not us. The gate now
   splits words at joiners (`loss.WS`), ignores spacing when asking whether
   a word is in ours, excuses a sentence when 80% of its words are in ours
   turned round and the page shows them that way, and one whose every word -
   short ones too - is in ours and differs only in punctuation.
2. **Our output carried most of those theses twice.** The fill-in step
   (`reader._backfill`) compared the other reading - which has the lines
   backwards - with the chosen one, found no match, and added the backwards
   text: `z21145041` wrote 1,431 of its 2,151 Arabic words a second time.
   It had passed every gate because the backwards copy matched the
   backwards reference. Now a paragraph is skipped when 80% of its Arabic
   words are already there either way round (`QIRTAS_BACKFILL_TURN`), and
   only its English and numbers the chosen reading lacks are put back, as a
   line of their own - the tags reading drops English inside Arabic lines
   (eGFR, T2DM, COVID19), and skipping the whole paragraph lost them; the
   gate caught it at 86.7%.
3. **Near-repeats were never put back.** The same step called a sentence
   present if five samples of it were found anywhere; a reference list
   repeats itself, and entry 30 of `z21145041` (entry 16's title, another
   publisher) was lost. Now the samples must sit together and 90% of the
   sentence's letters must line up there (`QIRTAS_NEAR`) - two swapped
   letters in ومنها الشاذ / ومنهالا شاذ still pass.
4. **The font repair ran twice, and the first pass was incomplete.**
   `fit.convert` repairs, then `v1.convert` repaired the repaired copy.
   The page witness reads four page images, the four richest in disputed
   shapes; a shape on none of them kept the file's name. The second pass
   picked four other pages and fixed what the first missed - Calibri's 0 and
   2 stored as 1, the ً of اً stored as ا - and broke الله: its shadda is a
   shape of its own which the file's table calls ه. Now: a repaired copy is
   not repaired again (`QIRTAS_REPAIR_ONCE`); the witness adds pages until
   every disputed shape has been seen, up to 10, and counts a reading with
   the page's letters out of order as agreeing (`QIRTAS_WITNESS_COVER`,
   REPAIR_VERSION 7); and الل or للا with a shadda at a word's end gets its
   ه back, in `repair_lam_alef` and in the fix map's replacements
   (`QIRTAS_ALLAH`). All 37 theses go through the font repair (Word's
   Symbol and Wingdings bullets alone trigger it).

Full run `2026-09-24-{thesis,regression}-flags29c`, against
`thesis-baseline`: nothing lost 99.4 -> 100.0% (worst `z21145041` 99.3%, one
reversed sentence with a و and a slash glued in); wrong words 10.1 -> 9.0%
(`z21145041` 32.6 -> 13.7%, `z22058810` 27.6 -> 20.2%, which is now exactly 14
pages); words in order 94.3 -> 93.4%; right page 61.1 -> 60.1%, all of it
`z21145041` 0.65 -> 0.36 - an instrument effect: 520 of its 1,218 reference
words exist in ours only turned round, and right page compares with that
backwards hidden text. Regression unchanged. `harness.truth`, which reads
the page, is the score to trust on these files.

Looked at `z22058810` page 3: reads right, no backwards copy; COVID19 sits
alone at the end instead of inside its sentence (the English put back on
its own line), the page number reads 57 where the page shows ب, the title
lost bold and centring.

## Part 2: the missing-font message, 2026-09-24

`convert/fonts.py`: the fonts a PDF uses that this computer lacks, with how
much text each carries and where to get it; `python -m convert` asks before
converting and waits while they are installed (Enter checks again). Tested
on made-up PDFs (`harness.test_fonts`).

**What counts as installed** is what the converter finds (`glyphs._path`)
OR what Windows lists (the Fonts registry keys, machine and user) - which is
what Word uses. The converter's own index reads single font files only, so
asked alone it called Cambria Math missing: it lives in cambria.ttc on every
Windows computer. A name Word cut at 24 characters is matched by its start
(Times New Roman PS-Bold Ital). A bold or italic whose regular face is here
is only mentioned (Muna Bold, `z20538636`): Word imitates it, and stopping
for it is not worth it. Not listed: fonts under 20 characters of text,
nameless ones (F1, GlyphLessFont) and the PDF standard's built-ins.

**Where to get** is said only where it is certain: Windows' optional
"Arabic Supplemental Fonts" (Simplified/Traditional Arabic, Sakkal
Majalla ...), Google Fonts (Amiri, Cairo, Almarai ...), Office, Adobe's
apps, the King Fahd Quran Printing Complex (KFGQPC), Arabeyes ("ae" fonts).
Anything else: search its name, or ask whoever made the PDF.

Across the 37 theses on this computer, 30 fonts are missing, most with a
few hundred characters; the most text is KFGQPC Uthmanic Script Hafs (3,709
characters, one thesis) and PT Bold Heading (1,935, six theses).

## Part 3: looks - bold, 2026-09-24

**Arabic bold was never written.** Word keeps bold and italic twice - w:b
and w:i for Latin, w:bCs and w:iCs for right-to-left scripts - and Arabic in
a right-to-left run follows only the second. python-docx's run.bold writes
w:b alone. Size was already written both ways (w:szCs); bold and italic
never were, so every bold Arabic word in every file came out regular.
`writer._style` writes both, each straight after its Latin twin (schema
order); footnotes.xml gets them too (`footnotes._rpr`). And a page's notes
labelled as one piece and split apart (`reader._split_notes`) were set plain
- they keep what most of the piece was, as does each note written to
footnotes.xml (`writer._note_style`). Notes are set at the size the original
used (`writer._note_size`, the commonest size of note text), not 0.78 of the
body. Switches `QIRTAS_CS_STYLE`, `QIRTAS_NOTE_SIZE`.

**Measured as Word draws it.** A first audit read the Word file's markup and
could not see the change - w:b was there before as well - and it normalised
whole lines before splitting words, so every line was one "word"; its 23%
was meaningless. The measure that counts reads Word's own render (the
rendered PDF carries a bold font only where Word shows bold): words bold in
the original shown bold, on the 8 quick-set theses, 18% -> 78%; our bold on
words the original does not bold, 47% -> 29%. Text scores unchanged, right
page 58.5 -> 58.8%.

**Left:** the two theses read through the tags route (`z21145041`,
`z22058810`) stay at 7% and 15% - that route reads /ActualText and carries
no formatting. Most wrong bold is headings: the writer makes a heading bold
as a whole, and some paragraphs are taken for headings that are not
(`z3387756`'s thanks page). Italic on Arabic headings: Word fakes it by
skewing the text, and the PDF marks no font italic - reading the skew means
parsing the content stream; not done. Moaz's own chapters draw every word
as a labelled picture, so their bold is in the pictures, not in any font.

### Part 3: headings' own bold, centring, digits, 2026-09-24

**Headings keep their own bold** where the reading kept formatting
(`QIRTAS_HEADING_OWN`); bold as a whole only where it did not. An author
can style a plain sentence as a heading (`z3387756`'s thanks page). As Word
draws the quick set: our bold on words the original does not bold 29% ->
22%, the original's bold kept 78%. Right page 58.8 -> 53.4% - all of it
`z15446639`, same 13 pages matching the same originals; the font repair of
Word's render garbled it (FLAGS 30).

**Centring** (`writer._centred`, `QIRTAS_CENTRE`): a heading or paragraph
narrower than 70% of the column with its middle within 4% of the column's
is centred. Of 37 lines centred in the quick-set originals, 11 were centred
in ours, now 30; lines centred in ours and not in the original 9 -> 14.
Nothing else moved. Measured on Word's render, lines matched by their words.

**Digits.** Written as the page shows them already (N5a, `_show_digits`):
the 8 theses that show ١٢٣ have them in ours, in note text too. Left: the
numbers Word makes itself - footnote references and page numbers - take
their digits from each reader's Word ("Numeral": Context shows ١, Arabic
shows 1). Only typing them in as fixed text would force the look, and they
would then not renumber on editing. Moaz to decide.

**Full run** `2026-09-25-{thesis,regression}-part3a` (Parts 2 and 3 so far),
against `flags29c`: nothing lost 100.0% (worst 99.3%), wrong words 9.0%,
words in order 93.4%, all unchanged; right page 60.1 -> 58.0%, all of it
`z15446639` 0.82 -> 0.30 on the same 13 matching pages (FLAGS 30), and
`z3387756` one page longer (34 against 14, already far over). Regression
unchanged.

**Looked at** `z20782957`'s title page: centred now, but the title is far
smaller than the original's and the page is bunched at the top (the page
fitting shrinking a page that runs over?), the two supervisors side by side
are stacked, and a page number is printed where the original has none.

### Part 3: text size, and the gaps that did not fit, 2026-09-25

**Each paragraph at its own size.** The reader measured every paragraph and
the writer ignored it: body text went out at the body size and headings at
1.15 or 1.35 of it, so `z20782957`'s 22pt title came out near 14pt and its
18pt names at 12. Now `Block.text_size` - the size most of its letters are
set at (`size` stays the largest, which heading detection wants) - is
written, times the page's fitting scale (`QIRTAS_OWN_SIZE`). The line height
grows and shrinks with it: at the body's exact line height the title's two
lines were drawn over each other. Measured on Word's render, lines matched
by their words: within 10% of the original's size 67% -> 81%; lines set at
16pt or more 17/43 -> 36/48. Nothing else moved on the quick set.

**The space above paragraphs - tried, left off.** Every paragraph is
written with no space above, so a title page spread down the page comes out
bunched at the top. Putting back the original's gaps (`writer._gap_above`)
pushed pages over: right page 53.4 -> 40.2% on the quick set, `z20782957`
13 pages -> 14. Kept to pages under 150 words and measured from a picture's
foot (a first line under a logo had got the logo's height again as space),
still three theses gained 1-3 pages, right page 48.6%, and the fitting then
shrank the text to make room. Our pages hold more than the original's - two
supervisors side by side come out stacked - so the original's gaps do not
fit. `QIRTAS_GAP=1` to try it; off by default.

### Part 3: blocks side by side, 2026-09-25

A title page's two supervisors, drawn next to each other, were written one
under the other. `writer._beside` now finds them: the reading goes back UP
the page - a block starts above where the one before it ended - and the two
runs sit clear of each other across the page and share at least half the
height of the shorter. The two runs go into a borderless table of two cells,
the run read first in cell one (mirrored when it is on the right), each
side centred when its blocks are centred on each other, never justified
(`QIRTAS_BESIDE`). Found on 7 of the 25 dev theses' title pages and on
tables drawn without borders.

Two things that pass that test and are not side by side: a page number at
the foot, read before the text at the top (the runs must share height, and
walking back must go up the page); and an entry's number set out in the
margin level with its first line ("47 -" beside "( روسو...") - 50 on the dev
theses, 45 of them on two reference lists. That number is joined onto the front of its
entry instead of written on a line of its own. A table read just before a
block is never one side: that crashed `z3387756`.

**What it did not do.** The quick set's scores and page counts did not move
(right page 53.35 -> 53.37%, nothing lost 99.9%). The guess in TASKS that
stacked blocks were what made pages run long was wrong: `z3387756` is still
34 pages for 14, `z21850164` 27. It is a looks fix. Still wrong on
`z21850164`'s title page: the logo between the French and Arabic headers
is put above them (three across is not handled), and the running header
and a page number are drawn on it.

The gaps above paragraphs, tried again on top of it (`QIRTAS_GAP=1`): still
worse - right page 53.4 -> 49.5%, `z20973693` 22 pages -> 24 and its right
page 70 -> 34%. Left off until whatever makes pages run long is found.

### Part 3: no header or number on unnumbered front pages, 2026-09-26

Word draws the running header and footer on every page, so a thesis's
title page got the chapter's header and a page number ("70" under
`z20782957`'s supervisors), and so did the unnumbered pages after it. The
pages before the first one anything was lifted from (`writer._bare_front`)
now go into a section of their own with no header or footer
(`writer._end_front`, `QIRTAS_BARE_FRONT`). The break is CONTINUOUS, at
the end of the last bare page: every page keeps its own page break, which
is where the scoring splits pages, and Word takes a page's header from the
section in force at its top. The main section's first number moves on by
the bare pages. Checked in Word on a four-line file before building it,
then on `z20782957`: no number on its first three pages, 73-80 after, as
the original.

The scoring had to learn it too: `compare._furniture_texts` drew the
header on every page. It now counts the pages before the first section
break as having none, and numbers from the page after.

On the dev theses 24 of 25 start bare, nearly all for 3 pages - the cut
takes the front 3 pages of each thesis. Not handled: bare pages later on
(a chapter cover). Pages 11-13 of most cuts also read as bare, but that is
the cut: their numbers jump (80, then 13) and nothing lifts a jumping
number. A whole thesis does not jump.

Quick set (`2026-09-27-quick-look-front` against `-look-beside2`): nothing
lost, words in order, right page and page counts unchanged; the page check's
wrong words 10.3 -> 9.2% (`z20973693` 22.3 -> 16.8%, `z20585114` 7.6 ->
5.4%) - the header and number no longer on pages whose original has
neither. Converter and scoring changed together here; the scoring's reading
was checked against Word's render of `z20782957`, page by page.

### Part 3: three or more across, 2026-09-27

Side by side took two runs; a third was stacked under the second. Three
or more across is nearly always a table drawn without borders, read cell by
cell - a questionnaire's header row "م | العبارة | موافق بشدة | محايد | غير
موافق بشدة" (`z17804101`), a committee row "name | post | role"
(`z22828583`). `writer._beside` now takes any number of runs: a block
clear of every run so far, starting back up above the last run's foot and
further along the same way, starts another; the table gets a cell each,
their edges halfway across each gap. A run that is not clear of the others
or not level with the first goes back to the page. On the dev theses: 5
rows of 5 cells, 7 of 3 or 4. The logo between two headers on
`z21850164`'s title page is still not one of them.

Quick set unchanged (`2026-09-27-quick-look-across`). Looked at on
`z17804101`: the header row lies across as the original. The same page
shows a worse problem that was there before: the questionnaire table comes
out as a ladder of too many columns, and its text is written again below
it as loose lines. That is table reading - Part 3's "tables" item.

### Part 3: tables drawn with double rules, and table text written twice, 2026-09-27

Two faults, found looking at `z17804101` page 14.

**Columns in the gap of a double rule.** A table whose rules are drawn
double is found with a column between each pair: 5pt wide, empty in every
row. 29 of the 79 tables on the dev theses had them; `z17804101`'s 7-column
questionnaire came out with 19, and `z3387756`'s causality table as a
ladder one letter wide over several pages - most of why that file ran to
34 pages for 14. `reader._drop_thin_columns` takes out a column under 8pt
that holds nothing in any row, its width to the column beside it
(`QIRTAS_TABLE_THIN`). 9 tables still have one, holding text or with rows
of different lengths.

**The table's text again as loose lines.** The table's words are read as
paragraphs too, and a paragraph was dropped only when its exact text was
in the table. A cell the table read in pieces - a heading cell of two
lines split over two rows - failed that, and about 3,100 words on the dev
theses were written twice (4% of their text). Now a paragraph inside the
table's box is dropped also when every one of its words is in the table
(`reader._held_by`, `QIRTAS_TABLE_WORDS`) - every word, so nothing the
table lacks goes. 1,550 of the 3,100 still stay: the table lacks a word or
two of theirs (a cell read differently, a word split).

Quick set (`2026-09-27-quick-look-tables` against `-look-across`):
`z3387756` 34 -> 20 pages, `z21850164` 27 -> 22, `z20585114` 16 -> 15,
`z20973693` 22 -> 21; right page 53.35 -> 53.91%; nothing lost unchanged;
words in order 89.0 -> 88.6% (a table's text now read cell by cell only);
wrong words 9.2 -> 9.3%. Looked at on `z3387756` page 7: the table reads,
where it was a ladder. Still wrong there: the header row squashed into
narrow cells a letter per line, the caption put under the table, and the
rows the strict test kept, written again below.

**Full run** (`2026-09-27-{thesis,regression}-part3b` against `part3a`,
which also covers side by side, bare front pages and three across since):
nothing lost 100.0% (worst `z21145041` 99.3%, as before); pages 1.14x ->
1.07x; right page 58.0 -> 58.6%; page check wrong words 9.0 -> 8.4%, found
91.7% unchanged; words in order 93.4 -> 92.9%. Regression unchanged (100%,
86.7%, wrong 2.2%). Right page fell on `z22828583` (15.7 -> 12.4%) and
`z7456037` (17.8 -> 14.3%): both still 8 and 15 pages long, one or two
shorter, so their pages meet the original at other places.

### Part 3: tables the right way round, cells across columns, 2026-09-27

Looked at four table pages in three theses before touching anything; every
one had the same faults.

**Every right-to-left table was mirrored.** The table finder lists a row's
cells left to right, as drawn. The writer marks an Arabic table
`w:bidiVisual`, which puts cell one on the RIGHT - so the original's
rightmost column came out leftmost, on every Arabic table. Seen on
`z20276275` on 24 Sept ("mirrored wrong") and never fixed; the widths were
reversed, the cells were not. `writer._emit_table` now hands a right-to-left
table over in reverse, with its widths, cell pictures and spans
(`QIRTAS_TABLE_FLIP`). No score can see it: the words are the same either
way round.

**A cell across several columns was written into the first.** The table
finder gives such a cell at its first column and None for the columns it
covers. On a table drawn with double rules the first is often a 5pt gap
column, so the cell's text went into a sliver, one letter a line - the
"header row squashed" of the last section. `reader._spans` reads the span
off the geometry (a None whose column the cell to its left reaches), the
writer merges the cells (`gridSpan`), and widths now come from every row's
edges, not the first row's alone, which missed a column whenever it held a
merged cell (`QIRTAS_TABLE_SPAN`). A None the cell to its left does not
reach is the row above reaching down, and stays an empty cell.
`_drop_thin_columns` moves a span's text along when its first column goes,
and drops a thin column whose only text is a copy of the cell beside it
(a 5pt clip catching its neighbour, `z21145041`).

Two traps on the way, both found by a file getting longer:
- A frame drawn round a whole page (`z20782957` page 11) is found as a
  "table" whose cells lie inside each other. Read as a grid, a 6pt column got
  the page's text: 13 pages -> 19. Rejecting every table with overlapping
  cells then threw out a real one in `z3387756` (15 -> 18 pages) that has one
  nested cell. What works: a cell inside another of its row whose text the
  outer one already has is the same text read twice - blanked, and the outer
  cell spans (`reader._unnest`). An inner cell with text of its own leaves
  the table as it was found.

**The table put into the middle of a paragraph.** Pictures and tables went
in at the same share of the way down the page's list of paragraphs as they
sit down the page. That assumes the paragraphs are spread evenly; a table
whose rows are also read as paragraphs below it is not, and the table landed
mid-paragraph, its caption after it. Where 80% of a page's blocks carry a
position, a table or picture now goes after the last block that STARTS above
it (`writer._by_y`, `QIRTAS_PLACE_BY_Y`) - starts, because a caption read
together with the header row below it ends inside the table. The tags route
has no positions and keeps the old way.

**The rest of the doubled table text** (`QIRTAS_TABLE_JOINED`), three causes:
- The page stores a cell's word broken over two lines (`ال` / `مطلوب`); alone
  at a line's end `ال` reads as a lam-alef stored backwards, and the cell said
  `لا مطلوب`. `reader._rejoin_articles`: where the page's paragraphs have
  `المطلوب` and never `مطلوب`, so does the cell. A real `لا يوجد` is left.
- A row read as a paragraph with the source line below it (`ممتازة ...
  المصدر :`): the leading words the table holds are cut off
  (`reader._trim_held`), by letters, so the formatting runs stay in step.
- The caption read together with the header row: the trailing words the
  first row holds are cut off (`reader._trim_header`).
A paragraph's word counts as the table's only when a cell has that whole
word. Also matching it inside the table's text with the spaces taken out
(for `ل مطلوب`) passed the quick set and failed the gate on the full run:
`z17931421` stores its spaces as `ۡ` and a cell read `المجموعةۡالضابطةۡم`,
so `المجموعةۡالضابطة` looked held, its only copy as printed was dropped,
and nothing lost fell to 97.9%. Taken out; `_rejoin_articles` covers the
broken word it was for.

**Spaces stored as U+200C** (`QIRTAS_ZWNJ`). `z21850164` stores a zero-width
non-joiner between every pair of words - 2,636 in 14 pages; `z22643426` 132.
Word draws it as nothing and the whole thesis came out glued
(`البعدالقيميوالروحي`). `reader._clean` now writes a space.
**The instrument hid it, then misread the fix** (the eighth measuring bug):
`harness/loss.py` counted U+200C as a space, but `compare.WORD` and
`compare.ALLWS` did not, so words in order fell 91% -> 4% the moment the
converter wrote spaces. Fixed there, it still read 76%: the original's side
was repaired with the joiners in, and the repair of words stored backwards
(`يف` for في) needs whole words, so the reference kept `يف` while ours,
correctly, said في. `compare.text_of` now reads U+200C as a space always.
Scored both ways on the fixed instrument: `z21850164` words in order 76.2 ->
97.1%, right page 62.3 -> 87.2%; `z22643426` right page 90.0 -> 91.7%;
nothing lost 100% both ways.

Quick set (`2026-09-27-quick-look-span3` against `-look-tables`; `z21850164`
also moved by the instrument): right page 53.9 -> 67.1%; words in order
88.6 -> 90.5%; pages 1.036x -> 1.000x; nothing lost 100% on every file (was
99.3% worst); page-check wrong words 9.3% unchanged. `z3387756` 20 -> 15
pages, right page 32.0 -> 78.7%; `z20973693` 21 -> 15, 69.6 -> 90.1%;
`z21850164` 22 -> 14, 22.8 -> 87.2%. No file worse. Looked at on
`z3387756` pages 4 and 6: the tables read as the original, caption above.
Still wrong:
- `z3387756` page 12: the 17-column table reads and is the right way round,
  but the table finder also finds five pieces of it as tables of their own,
  and they come out as small tables and loose lines under it.
- A stray `ا` in some header cells (the clip catching a letter beside it).
- `z21145041`'s cells stored backwards (`ارشؤم`), as before.

**Full run** (`2026-09-27-{thesis,regression}-part3d` against `part3b`):
nothing lost 100.0% on EVERY thesis - worst file 100.0%, the first time
(`z21145041` was 99.3%); pages 1.07x -> 1.00x; right page 58.6 -> 69.4%,
11 of 25 files better and none worse; words in order 92.9 -> 93.9%; page
check wrong words 8.4% and found 91.7% unchanged. Regression unchanged
(100%, 86.7%, wrong 2.2%). Largest: `z14714045` 16 -> 14 pages, right page
15.7 -> 94.6%; `z7456037` 29 -> 15, 14.3 -> 30.1%; `z18037898` 26 -> 13,
68.6 -> 80.6%; `z22828583` 22 -> 15, 12.4 -> 23.0%; `z21644412` 20 -> 15;
`z20306213` 17 -> 14. (`part3c`, the run before, failed the gate on
`z17931421` - see above.)
**One file reads worse, and is not:** `z21728839` words in order 97.8 ->
95.6%. With the flip off it is 98.5% - and its table mirrored. Looked at:
flipped, the columns sit as the original's. That PDF's own text reads the
table left to right, so words in order marks the right answer down. A
limit of the score for tables, not a fault; left as it is.

### Part 3: bold on the tags route, 2026-09-27

The two theses read through /ActualText (`z21145041`, `z22058810`) carried
no formatting. Each word there is a /Span with its own /ActualText and one
MCID, and the glyphs under that MCID are drawn in a font that says bold
(`SimplifiedArabic-Bold`, `TraditionalArabic-Bold`) though they spell the
word backwards. `reader._font_reader` parses each page's content stream once
and counts, per MCID, glyphs drawn in a bold / italic font (by name, weight,
or descriptor flags); `_walk` tags each /ActualText piece with that as a
`_Run`; `_rough_spans` builds spans per block. The text is repaired after
reading (lam-alef, the fix map, list markers) and the writer writes spans,
not text, so the spans are laid over the FINISHED text last thing in `read`
(`_fit_spans`: letters aligned, each word takes most of its letters'
formatting). Switch `QIRTAS_TAGS_FORMAT`.

**The bold measure was broken on these files** (the ninth instrument bug).
It matched words between the original and Word's render of ours, and the
original's words read backwards there (`هعماج`), so nothing could match:
6% and 15% before and after alike. Compared by letters in any order: bold
kept `z21145041` 76 -> 91 of 150, `z22058810` 28 -> 64 of 79 (quick run
`tagsfmt` against `thesis-part3d`). Bold where the original has none
21 -> 53 and 27 -> 72: looked at, the first is `z21145041`'s table text
written again under the table (its cells stored backwards, so the copy is
not recognised) now bold like the header it copies; the rest is words split
or glued differently in the two renders. Text scores identical on all 10
quick-set files, nothing lost 100%.

Seen on the way, not from this: `z22058810` page 2's shaded verse is read as
a table with backwards cells, and the verse written again garbled below it
- the same fault as `z21145041`'s cells.

### Part 3: italic drawn as a slant; headers keep their formatting, 2026-09-27

**The slant.** Word has no italic of most Arabic fonts and fakes one: the
ordinary font under a text matrix leaning 0.33 (`1 0 0.3333 1 x y Tm`). No
font says italic, so every reading saw none. 9 theses do it (`z18634114`
299 times, `z18441713` 177); 4 of them are in the dev set, 5 held out.
`reader._slant_starts` walks the content stream (q/Q/cm, BT, Tm, Td) and
notes where each text show starts when text matrix x CTM leans 0.15-0.6 of
its height; `_slanted_boxes` finds those shows in MuPDF's `get_texttrace()`
by the first letter's origin (within 0.6pt) and takes their boxes;
`_mark_slant` sets the italic flag on every dict span more than half inside
them - before `_rich_block`, so geometry and labels both see it. Switch
`QIRTAS_SKEW`. `z18634114` (held out) was looked at to see how Word draws
it; no score was taken on it.

**Headers and footers were always written plain.** `z22643426`'s italic
chapter line lost its slant on all nine pages. `writer._furniture_run` now
gives each piece what most of its letters were (`_note_style`). Switch
`QIRTAS_FURNITURE_STYLE`.

**Measured** as Word draws ours, both sides read the same way (an italic
font, or `_mark_slant`), words compared by their letters, the original read
through `glyphs.repaired` - without it `z18441713`'s own text (`جدوؿ` for
جدول) matched nothing and every italic word counted as both missing and
extra. Italic words of the original shown italic, on the two dev theses that
have Arabic italic: 16 -> 78 of 162 with the slant, 114 with headers too.
Italic where the original has none 0 -> 31: nearly all `z22643426`'s header
words, which the original's broken text spells differently (`ملتغريات`),
and Word repeating the lifted header on 11 pages where the original prints
it on 9 - lifting's behaviour, not new. The check undercounts: `z18441713`'s
"رسالة دكتوراه غير منشورة" is italic in our file and slanted in Word's
render, but shares a span with upright text there. Bold kept 78 -> 81%
(headers).

**Full run** `2026-09-27-{thesis,regression}-part3f` against `part3d`:
nothing lost 100.0% on every file; words in order 93.9% and page check
(found 91.7%, wrong 8.4%) unchanged; regression unchanged. Right page 69.4
-> 68.8% is one file: `z17931421` came out 24 pages in that run - converted
again alone, with the header switch on and off, it is 17 as before. A
one-off from Word in the run, not the change.

### Part 3: table cells shaded as in the original, 2026-09-27

Counted first: shaded boxes holding text on 15 of the 25 dev theses - 273
inside tables (banded rows, coloured header rows, a coloured first column)
on 10 theses, 48 behind ordinary text, several of those running-header
bands. Tables first. Every table cell came out white.

`reader._cell_fills` takes, for each cell box, the last fill drawn under at
least 60% of it (white clears; a fill darker than 0.45 lightness is left
out - it carries white text, which we write black). It runs BEFORE the thin
columns are dropped: on a table drawn with double rules a cell can start in
the 5pt sliver, and its box went with the sliver - `z17931421`'s green first
column came out white until `_drop_thin_columns` moved the shading with the
cell as it moves the text. `writer._shade` writes w:shd on the cell, through
the same right-to-left flip as the spans. Switch `QIRTAS_TABLE_FILL`.

**Measured** by looking: `z21145041`'s blue bands, `z17931421`'s grey header
and green first column, `z21850164`'s blue header and grey first column,
`z21644412`'s grey section rows all as in the original. A count of shaded
boxes in Word's render against the original was tried and is not usable:
it read `z21145041` as 0 though the render shows the bands (Word's shading
box does not contain the word boxes), and the original's as 0 on
`z21644412`, which has them. Full run `2026-09-27-{thesis,regression}-part3g`
(2 Word jobs - the PC went down twice under 3): nothing lost 100.0% on every
file, every score unchanged; `z17931421` back to 17 pages, confirming the
24 in `part3f` was the run, not the change.

Seen on the way, older faults: `z17931421` page 6's widest table runs off
the page's left edge by one column, and its text is written again below it
in small type (its spaces are stored as `ۡ`, so the words do not match the
table's) - likely most of why it is 17 pages for 14; `z21644412` page 12's
table is found with many narrow empty columns.

### Part 3: bands behind ordinary text; italic only where the PDF says so, 2026-09-28

**Bands.** Looked at first: `z14065750` a dedication in a grey outlined
box; `z20782957` a one-column table the finder does not see (rules only
across), its heading rows yellow and green; `z7456037` a running header
white on a black band; `z20973693` a grey header band. All plain in ours.
`reader._band_fills` gives a positioned paragraph, heading or list item
outside every table the colour behind 60% of it. Word draws a shaded
paragraph a line at a time - one strip per line, the outline as hairline
strips (1pt wide) down both sides - so strips of one colour are added up,
and an outline is hairlines at both edges of the whole band (or a stroked
fill). On a band the text keeps its own colour where it is not black
(`Block.ink`). `writer._band` writes w:pBdr (outline) and w:shd, in body
paragraphs and in lifted headers and footers; `_ink` colours the runs. Not
on the tags route (no positions). Switch `QIRTAS_BAND`. Looked at on the
four: all as the original; ours stretches the dedication box to the text
column where the original's is narrower, and `z7456037`'s white-on-black
header is smaller and not bold.

**Italic, corrected.** MuPDF marks a span italic when the font FILE says
so. `z20973693`'s AGA-Aladdin and Sultan Medium, `z22643426`'s AF_Taif,
`z18047321`'s Sultan, `z15446639`'s Mudir claim it, the PDF gives them
italic angle 0 and no italic flag, and they are drawn upright - looked at:
`z22643426`'s header is a heavy upright face. Writing headers with their
formatting (the day before) copied that false italic onto every page, and
the note above calling `z22643426`'s header "italic chapter line" was
wrong. `_pdf_italic_fonts` reads the PDF's own font description (name,
/ItalicAngle, /Flags bit 7); `_mark_slant` takes the flag off a span whose
font it does not call italic (names matched exactly, or by prefix only when
MuPDF cut them to 24 letters - "Helvetica" is a prefix of
"Helvetica-Oblique"). Switch `QIRTAS_TRUE_ITALIC`.

The italic check reads both sides through `_mark_slant`, so it was fooled
the same way; re-measured (the 9 slant theses in the dev set plus the 3 with
such fonts): the original's real italic words 92; kept 0 before any italic
work, 62 the day before and now; italic where the original has none 111
before, **238 the day before, 1 now**. The "16 -> 114 of 162" above counted
false italic as real.

**Full run** `2026-09-27-{thesis,regression}-part3h-2` against `part3g`:
nothing lost 100.0% on every file; words in order 93.9%, page check (found
91.7%, wrong 8.4%) and regression unchanged; right page 69.3 -> 69.4%. The
first attempt (`part3h-STOPPED`) was stopped: `convert/reader.py` was
edited while it ran.

### Part 3: headers laid out like the original - the line under, the two parts, 2026-09-28

**The line under the header**, on 7 of the 25 dev theses, was dropped.
`reader._header_rule` takes each page's wide (40% of the width) thin
(under 4.5pt) horizontal lines in the top 15%, keeps the pattern repeated
on half the pages, and makes it a border: one line single, two within 6pt
double / thinThickSmallGap / thickThinSmallGap by their thicknesses, two
groups apart a top and a bottom border (`z20973693`'s double lines above
and below its band). Colour and width kept (`z20585114`'s orange). A page
with a tall vertical line is framed all round and left out (`z3387756`'s
top line is the frame's). `writer._header_rules` puts it on Word's header
paragraphs (both headers where odd and even differ), or on an empty one if
the header has no text; the front pages' own section keeps none. Found on
exactly the 7: `z17804101`, `z18037898`, `z18048055`, `z20585114`,
`z20973693`, `z21850164`, `z22643426`. A 3pt line was first missed (a limit
of 3pt): `z22643426` is thin over thick. Switch `QIRTAS_HEADER_RULE`.

**Two parts at the edges.** A chapter at one edge and its title at the
other came out one centred line (`z22643426`, `z7456037`, `z20585114`) -
authors push the parts apart with spaces or a tab, which cleaning makes one
space - and on `z22643426` the wrong way round. `reader._header_parts`: for
a one-line block in the top or bottom 15%, the page's words inside it are
clustered by gaps of 30pt; with 2 or 3 clusters, the block's OWN words are
cut into runs matching each cluster's characters in any order (the hidden
text spells them garbled - `ملتغريات` - and in the wrong order), right to
left. Nothing is taken from the page. Only lifted headers and footers use
`Block.parts`; body lines near the edges get them too and ignore them.
`writer._draw_parts` sets an end tab stop at the text width (and a centre
one for three parts) and writes the parts tab-separated from the line's
start. Two traps: Word's positional tab (w:ptab) wrapped the second part
onto its own line in a right-to-left header; and Word's Header style brings
stops of its own (centre 4680, right 9360), so the tab went to the centre
one - cleared per paragraph. Switch `QIRTAS_HEADER_PARTS`.

Looked at on `z22643426`, `z7456037`, `z20585114`, `z18037898`,
`z20973693`: lines and parts as in the original. Header text is still
larger and less bold than the original on `z7456037` and `z20973693`.

**Full run** `2026-09-27-{thesis,regression}-part3i` against `part3h-2`:
nothing lost 100.0% on every file; every score unchanged (right page 69.35
-> 69.33%, two files by 0.003).

### Part 3: footnotes as the original sets them, 2026-09-28

Looked at side by side on the theses with real Word notes (`z18037898`,
`z14065750`, `z18048055`, `z21850164`, `z17804101`, `z3387756`). The notes
were not centred, as noted earlier from memory; three other things were
wrong:

- **The line above them** sat at the left, 2 inches long, on every thesis.
  Most originals draw it at the right (Word's own line, in a right-to-left
  separator); `z18037898` and `z18048055` draw it 288pt long; `z14065750`
  at the left. `reader._note_look` takes, on each page with notes, the thin
  line within 4 note-sizes above the first note (not the full-width one:
  that is Word's line for a note carried over from the page before), and
  keeps the commonest (length, side, width, colour). `footnotes._rule`
  writes a 2-inch one as Word's own separator, set right to left for the
  right side; any other length as the bottom edge of an empty paragraph cut
  short from its far end. **Trap:** Word ignores the separator notes in
  footnotes.xml unless settings.xml points at them (`w:footnotePr` with
  `w:footnote w:id="0"/"1"`) - the first try changed the file and not the
  page (`footnotes._add_settings`).
- **Line height.** Notes took the document default (1.15 of the font's own
  height), which in Traditional Arabic is far taller than the original:
  `z18037898`'s notes 15.6pt apart, ours near 21. Now the distance measured
  between the notes' lines on the original pages (`Doc.note_pitch`), set
  exact.
- **Bold words inside a note** were lost. When a page's notes are labelled
  as one piece, `_split_notes` cut the text and gave each note one style;
  it now cuts the formatting with it letter by letter (`_char_fmts`,
  `_word_spans`, split out of the tags route's `_fit_spans`), and the
  writer passes a note's pieces to footnotes.xml (`writer._note_pieces`)
  only where they spell exactly the note's text. Bold on the notes of
  `z17804101`, `z18037898`, `z18048055`, `z22828583`: none -> the book or
  sura name, as the original. Switch `QIRTAS_NOTE_LOOK`.

**Found on the way, a reader fault in body text too:** a word drawn in two
pieces of different formatting is put back together, and the whole second
piece went with it: `z17804101` draws "الدرام" bold and "ا، القاهرة، الهيئة
... ص44" plain, and all of it came out bold. Now only the word joins; the
rest keeps its own formatting (`_rich_block`, switch `QIRTAS_GLUE_FORMAT`).

**Left:** note numbers are Word's raised digits where the originals type
"(1)" or "(١)" small - parked with page numbers (FLAGS 31). Notes an author
numbers "1 ... 2 ... 3" in one paragraph stay one note (`z17804101`
page 5). A note's second paragraph joins its first (`z18048055`'s "انظر:
الجزائري").

**Full run** `2026-09-28-{thesis,regression}-part3k` against `part3i`:
nothing lost 100.0% on every file; every score unchanged (right page
69.33 -> 69.34%). Bold as Word draws it, all 25 theses: kept 80% as
before; bold where the original has none 889 -> 869 words (the glue fix;
`part3j` was the notes alone). Looked at on the six theses above.

### Part 3: the logo between two headers; a foot number read first, 2026-09-28

**The logo.** `z21850164`'s title page has its logo between the French and
Arabic headers; ours put it above them. A picture is placed after the text
that starts above it (`_by_y`), and none does, so the logo went first; side
by side then took it as the start of the French run, and the row failed
(the French and Arabic run overlapped the logo). `writer._pics_beside`,
after `_beside`: a picture sharing a run with text it sits clear of and
level with becomes a run of its own; a picture just before or after a row,
level with it and clear of every run, joins it; the runs are put in order
across the page. Found on that one page of the 25 dev theses. Switch
`QIRTAS_PIC_BESIDE`.

**A number at the foot, written at the top.** A page's number the header
and footer lifting does not take - a front page's letter (أ, ب, ج), the
last pages of a cut whose numbers jump (80, then 13) - is often read
before the text, and was written as the page's first line. On 58 pages of
24 of the 25 dev theses. `writer._foot_last`: a paragraph of 6 letters or
fewer, lower on the page than all the rest, goes last. Switch
`QIRTAS_FOOT_LAST`.

**Left, on the same page:** the header cells are narrower than the
original's - its headers reach into the page margins, the table stops at
them - so the Arabic ministry line wraps onto three lines; the title
page's lines are spaced wider than the original's.

**Full run** `2026-09-28-{thesis,regression}-part3l` against `part3k`:
nothing lost 100.0% on every file; right page 69.34 -> 69.64% (the foot
numbers); every other score unchanged. Looked at on `z21850164` page 1
and `z20585114` page 2.

### Brackets where the page draws them, 2026-09-28

**Moaz: "the brackets are always in the wrong place."** Measured, he was
right: a new instrument, `harness.brackets`, found 35% of the theses'
brackets out of place (1,530 of 2,365 right, 64.7%) - more than if we
had kept the PDF's stored order (69.0%). The worst was every reference
list in the APA style: `ابن كثير، إسماعيل. (1999). تفسير` came out
`( ابن كثير، إسماعيل. 1999 .) تفسير`.

**The instrument** reads each printed line as drawn - the extractor's
pieces on one baseline joined, read right to left by position, a number or
English run left to right - keys each bracket by the word before and after
it, and counts the keys our Word file holds. It shares no rules with the
converter. Arabic words are compared by length (spelling repairs change
their letters), English words and numbers exactly. Checked by reading its
misses: it misreads English citations with their own brackets
(`Sari (2023)`), sometimes matches a line to the wrong paragraph, and files
stored backwards or with broken fonts score low whatever we do.

**Why they moved.** Word stores the bracket, full stop and space between an
Arabic run and a number at the Arabic run's far end, as drawn: the reference
above is stored `( .ابن كثير، إسماعيل1999` then ` .)تفسير`. The punctuation
reordering (`order.py`, PLAN "Punctuation where it is drawn") moved only
marks, never brackets, and the guard added on 23 Sept (`_Whole`, after
`معين (Benchmark` broke the gate) turned it off on every tagged line
mixing Arabic with numbers or English - which is where references are.

**The fix** (`order._order_drawn`, switch `QIRTAS_DRAWN_BRACKETS`): an Arabic
line holding a bracket is read as drawn. Each Arabic word, and each number
or English run, stays as stored; the pieces between are placed by position,
right to left, with a number or English run and what lies between its parts
(`et al., 2020`, `I(2)` with its closing bracket) read left to right.
Because position decides, a reading that cuts the line into pieces puts
each bracket where one reading it whole does - so the `_Whole` guard is no
longer needed for these lines (the Benchmark test now checks both readings
agree). Also:
- A line of only brackets, stops and spaces (` .)` in `( 40 .)`) is read
  right to left on an Arabic page; one with a number in it (`(2018)`
  after Riley) is read as stored.
- **Brackets stored as the shape drawn.** Some fonts - Times New Roman in
  an Arabic line most often - store the turned-round shape: `(62)` stored
  `)62(`, which Word then draws `)62(` (`z7456037`, `z3387756`,
  `z21644412`). Read in order such a bracket gives itself away: `)` with a
  space before it and a word after opens. `_drawn_shapes` turns a line's
  brackets round where one says so and none says otherwise. It asks the
  whole printed line, not the extractor's piece: `جدول رقم )` + `29` +
  `( :` are three pieces and none alone can tell (`_Whole.turns`, keyed by
  where each bracket is drawn, so every reading turns the same ones).
- Only on a piece read right to left, and not in the labels reading on a
  piece with no word: there each bracket can be a piece of its own, already
  in the order Word wrote it (`(` `Maina,` ... `)`, `z20306213`), and
  turning it gave `)Maina ... (`.
- A vowel mark stored after a bracket goes to the letter before it
  (أنموذجاً); a line where a small hamza sits on a bracket is left alone -
  that is `z15446639`'s broken font writing its digits as marks.
- Any non-Arabic letter or digit counts as left to right here, so a
  formula's math letters and Greek (`(𝚫𝒚∕𝚫𝒙)`, `λ1`) are not reversed.

Two tries that failed on the way, both measured: a vote per font over the
whole document for brackets with nothing to say (one Times bracket turned
`z20305872`'s title `(Validation)` the wrong way, and `z3387756`'s Times
font stores some brackets turned and others not); and applying the whole
line's answer to an English piece read left to right (`(Gobira, 2023;19)`
turned round).

**The gate caught it once** (full run `brackets`): nothing lost 99.9%,
`z21145041` 97.0%. Our text for that file was the same with the rule on
or off; what changed was the reference, which is read through the same
`get_text`. Two sentences, both in lines the file stores backwards:
- A line with a stray letter drawn far from its word, and words drawn
  left to right: read by position, its Arabic words changed places. Now
  **Arabic words never change places** - where reading by position would
  move one, the line is left as stored. It cost no bracket anywhere
  (78.6% either way).
- `ةسياقم(ELISA)`: the page prints the bracket against the word, the space
  at the line's end, and the new reading follows it; the gate turns a
  backwards word round to look for it in ours, and turned ELISA round with
  it. **Instrument fix** (`loss._turn_round`): in a word mixing Arabic and
  English only the Arabic is turned. It can only excuse a backwards
  sentence whose words we have; `test_loss_gate` passes, and the old and
  new gate give the same answer on all 25 theses judged against the old
  reference.
A per-page vote for "this page is stored backwards" was tried first and
found nothing: that file mixes both kinds of line on every page.

**Found by looking, not by the instrument** (it leaves out note marks):
the rendered `z18048055` page 9 had its footnotes right and a stray `)`
after every note number in the body - `العليم ¹ ).`. Two causes, both a
mark or bracket taken into the raised note number `(1)`, so the number was
no longer read whole:
- A line where nothing moves was still rebuilt, and the rebuild puts a
  mark into the span before it. Now a line is left exactly as it was
  unless something moves or turns (`_turn`).
- A moved mark joins the span before it only at the same size (`_alike`):
  not the raised number's.
And in the labels reading a line with no letters is read right to left only
if it is one span (` .)` of `( 40 .)`); `)` + ` ،` after a note number are
two, already in Word's order. A second check, paragraphs with unmatched
brackets in our Word files, now goes with the instrument: 102 before the
change, 89 after (`z14065750` 19 -> 3); the few new ones are broken-font
files and pieces cut apart.

**Left:** in the labels reading a bracket that is a line on its own cannot
say whether its font stored the shape - `)` `59` `(` (`z7456037`, turned
the wrong way) looks exactly like `(` `Maina,` ... `)` (as meant). A URL
between two bracket pieces, `(www.globalreporting.org(` (`z18441713`; it
was `)...(` before). And the instrument undercounts files whose letters the
real pipeline repairs (FLAGS 23): their words no longer match the PDF's in
length, so the full run's Word files score 70.8% against 78.6% for the
reader alone - the brackets are the same (read by eye on `z15446639`,
`z17366480`, `z20782957`).

**Full run** `2026-09-28-{thesis,regression}-brackets3` against `part3l`:
nothing lost 100.0% on every file; right page 69.64 -> 70.2% (`z18048055`
78.6 -> 81.7%, `z14065750` 90.1 -> 92.8%, `z18037898`, `z20305872` up;
`z15446639` 30.0 -> 27.9%); words in order 93.9 -> 94.0%; page truth
wrong 8.4 -> 8.3%; the two chapters: right page 86.7 -> 87.3%, the rest
unchanged. Brackets in the Word files 57.4 -> 70.8% (the instrument's
undercount above). Looked at: `z18048055` page 9, `z18037898` page 13.

**Reader and writer only** (`out/work/brk-{off,on}`, 25 dev theses):
brackets right 64.7 -> 78.6%. Reference lists nearly all right now:
`z18048055` 52.7 -> 97.3%, `z18037898` 51.6 -> 96.7%, `z21850164` 78.6 ->
100%, `z20748757` 69.0 -> 97.6%. Lower: `z20305872` 91.7 -> 88.9%
(read by eye, every change there is right - the instrument misreads it),
`z22058810` 8.3 -> 5.6% (stored backwards, TASKS). Left: the files stored
backwards; `z21644412` and `z3387756` (47%, 68%), mostly the instrument's
English citations and formulas split into many pieces.

### English in the theses' Arabic lines, and numbers read backwards, 2026-09-28

Two of the text list, asked for by Moaz ahead of the tables.

**English and numbers the tags route dropped (FLAGS 29).** The two theses
read by the tags route (`z22058810`, `z21145041`) give every Arabic word a
Span label carrying its text, and leave English words, numbers and the
spaces between them as bare pieces of the page (an MCID straight under the
paragraph) with no label text. The route read label text only, so all of it
was dropped - 747 of `z22058810`'s 5,058 English words and numbers were
there, 242 of `z21145041`'s 2,310 - and the backfill put the English back as
a line of its own after the paragraph (COVID19 at its end), the numbers not
at all: every note number in the body read "()". Now a bare piece under no
label with text is read from the letters drawn in it (`reader._drawn_reader`,
`QIRTAS_TAGS_DRAWN`): by the font's ToUnicode table, or for a simple font
without one by its Windows encoding, which is how Word writes English. Only
pieces with no Arabic are taken - these files draw their Arabic backwards -
and spaces, which are pieces of their own between English words
("Biomarkers", " ", "as"). A drawn piece touching a word is set apart from it
(`_join_parts`): the contents page's labels have no line ends and its page
numbers ran into the entries ("المقدمة71.1 الخلفية"). Only on a file whose
labels carry Arabic: one with none keeps its words in the glyphs, and the
English read this way would make the tags route - chosen first on a tie -
look as complete as the others. Now 3,623 and 2,239 are there, in place.

**Notes with no measured line height.** `z22058810` then ran a page long:
its notes, now real notes with their numbers and web addresses, took Word's
default line height, about twice the size in Simplified Arabic. The tags
route has no positions, so `_note_look` measures nothing there. Where
nothing was measured the notes now take the body's line height scaled to
their size (`writer._note_pitch`). Back to 14 pages.

**A number's digits as drawn** (`order._digits_drawn`,
`QIRTAS_DIGIT_ORDER`). The extractor reads Arabic-Indic digits as Arabic and
turns them round with the letters. `z18441713`'s font gives its digits the
wrong codes; the font repair gives them back as ٠-٩, and then ٣١٠ read
٠١٣ and was written so. Seven theses store such digits, and nearly every
number in them was backwards - years above all (6691 for 1966, 9102 for
2019; `z15446639`, `z18441713`, `z18615445`, `z18842416`, `z21850164`,
`z22058810`, and `z20782957`'s licence "4.0"). Digits stored one after
another, each drawn left of the one before, are turned back; a decimal
separator between digits goes with them, a dash does not (`٣-٢` is two
numbers). The checker reads through the same `order.get_text`, so the
reference turned with us. Where the structure reading does not see a mixed
line whole (`_Whole.keeps`), only the digits are turned - every reading
turns them alike.

**Full run** `2026-09-28-{thesis,regression}-engdig2` against `brackets3`:
nothing lost 100.0% on every file; right page 70.2 -> 70.3%; words in order
94.0 -> 94.2%; page truth wrong 8.3 -> 7.9% (`z15446639` 7.9 -> 3.9%,
`z18441713` 12.9 -> 10.0%, `z21145041` 13.3 -> 10.7%); الفصل الثاني right
page 81.7 -> 83.1%. Lower: `z21145041` right page 36.2 -> 33.5%, 17 pages
for 14 (15 before) - 288 English words and numbers back, set as loose,
justified English lines at the body's line height (its reference list takes
four pages for two), and right page reads that file's backwards hidden text
anyway. Looked at: `z18441713` page 6 (٣١٠, ٣٢٧, ٢٧ as printed),
`z22058810` pages 3 and 12.

**Left:** Word draws "COVID19." with the full stop on the left of the word,
not after 19 (an English word ending a right-to-left sentence); `z21145041`
page 11 writes one paragraph a second time backwards (there before this
change); a web address on `z22058810` reads out of order - the page itself
prints it so.

**The English set as drawn** (Moaz, the same day: the loose English first).
The English the tags route now reads had no size, font or line height of its
own - that route has no positions - so it was set at the Arabic body's
(Simplified Arabic 13pt, 27pt apart) and justified: `z21145041`'s reference
list, Calibri 12pt 14.6pt apart and ragged at the right, took four pages for
two, its long web addresses spreading every line's words across the page.
Each drawn piece now keeps where and how it is drawn (`_Drawn.marks`: page,
left and right edge from the font's widths - a simple font's /Widths or a
CID font's /W - baseline, size, font). A paragraph mostly read that way
(`_drawn_look`, `QIRTAS_DRAWN_LOOK`) takes the size and font most of its
letters are drawn in (`Block.latin_font`, used for its English runs only),
its own line height from its baselines (`Block.line_pitch`), and bold or
italic from the font's name ("Abstract" had come out plain). Justified or
not is asked of the document's column (`_drawn_align`): lines short of the
right edge that 90% of lines reach, in over a third of a paragraph's lines
but its last, mean ragged (`Block.align` "start"); a two-line entry's own
longest line says nothing. First the widths of Calibri, a CID font, were
missing, and Arial - 67 letters on the page against 2,936 - was taken for
the references' font.

Full run `2026-09-28-{thesis,regression}-englook` against `engdig2`: only
`z21145041` moved - 17 -> 15 pages, its references two pages as printed;
the page over is page 11's backwards copy. Nothing lost 100.0%, everything
else unchanged. Looked at: `z21145041` page 13, `z22058810` page 13 (the
abstract in Times New Roman, justified, as printed). Left: the abstract's
heading is not centred (no positions to tell), web addresses are not links.

### Backwards second copies from the backfill, 2026-09-28

Moaz's pick after the English layout. The backfill puts back what the chosen
reading missed and skips a paragraph whose Arabic words are 80% ours
already, either way round (FLAGS 29). The other readings of `z21145041` and
`z22058810` store paragraphs backwards, and backwards storage does more than
turn words round: the tanween's alef lands at the other end (مراصا for
صارماً), a letter of the next word is taken in or one left behind (تراطإ
for إطار, يدصر for رصدياً), two words run together (نامضلتانايبلا). Asked
by the exact word, `z21145041`'s page-11 paragraph found 37 of its 47 words
and was written again backwards - seven paragraphs there, four on
`z22058810`. Now a paragraph that reads backwards - more of its words ours
only turned round than only as they stand - is asked loosely
(`QIRTAS_BACKFILL_LOOSE`): the same letters in another order, a letter off
either end or an alef on, or two words run together. Loose for all, it
skipped `z21145041`'s Arabic title, missing from the chosen reading, whose
words the body uses too; a paragraph the right way round is asked strictly,
as before. Ignoring vowel marks as well was tried, to catch a verse on
`z22058810` page 2: it let two other paragraphs back in; left.

**The gate, then.** Without its backwards copy `z21145041` read 98.5%: two
sentences the reference stores backwards, with the same distortions, had
been matched by our backwards copy, and the gate's excuse for them failed -
the page was asked for the turned word exactly (the OCR reads إطار, not
اطارت), and (غلم/درتليسي)لوبلا turned whole put its three words in the wrong
order. Asking the page with the stray letter off, and turning a word cut by
marks piece by piece, excused them - and a paragraph cut out of ours on
purpose was excused too: the backwards branch only asked whether each word
was somewhere in ours, and a thesis's common words are everywhere. So an
excuse there now also needs the sentence's words, each either way round,
together in ours (`loss._together`: 80% within twice the sentence's length).
Turning the sentence whole was tried first: the reference turns some lines
and not others (وقد أفيد بأن مساحة تحت منحنى التشغيل لقبلتسملل), 93.3%.
Word fragments of three letters (الب, غال) filled the places looked at before
the right one - only four letters or more; splitting a glued word at any
point matched three-letter pieces inside anything - only where the reference
has marks between them. Checked on every thesis's Word file against the
gate before: the same on all but `z21145041` (98.5 -> 100%); the cut-out
paragraph is caught (98.5%, 97.0% with two).

**Full run** `2026-09-28-{thesis,regression}-bwdup` (the converter as
committed; scored by the gate before its change - `z21145041` read 98.5%
there, 100% re-scored): page truth wrong 7.9 -> 7.2% (`z22058810` 19.3 ->
2.2%); `z21145041` words 2,924 -> 2,711 (the original 2,688) and pages 1-11
end where the original's do - the page over starts at page 12's results
table. Right page 70.3 -> 70.0%, words in order 94.2 -> 94.0%: both read the
two files' backwards hidden text, which our backwards copies had matched
(`z21145041` 33.6 -> 28.7%, `z22058810` 57.4 -> 54.6%). Left: the verse on
`z22058810` page 2.

### Tables: written twice, cells backwards, stray letters, off the page, 2026-09-28

Moaz: the table faults next. Started from `z17931421` page 6, 17 pages for
14: its widest table ran off the page's left edge, and its text was written
again below it in small type. Four causes, and each turned up on other
files too.

**A space stored as a vowel mark.** The file's Sakkal Majalla calls its
space glyph ۡ (U+06E1, a Quranic sukun): the installed font says the shape
is a space, and the file's own width for it is a space's. So every word
began with a mark Word drew, and the table's rows read as paragraphs
(`ۡضابطة 17.600 ...`) matched none of its cells. The font repair now makes
such a glyph a space (`glyphs.diagnose`, `QIRTAS_SPACE_MARK`, repair version
8). A second ۡ, a real zero-width sukun shape, is drawn at the start of
words and cells, where Arabic never puts one: dropped wherever no letter or
mark comes before it (`arabic._ORPHAN_SUKUN`, `QIRTAS_ORPHAN_SUKUN`), in
`repair_lam_alef`, which the reader and the checker both run - so a verse's
`عَلَقۡ` keeps it.

**A cell's direction checked against text that moved the mark.** The clip
read `ۡضابطة`, the page's text `ضابطةۡ`; the probe failed and the table
finder's backwards `ةطباض` was written. The probe now asks without ۡ
(`QIRTAS_TABLE_MARK`). And where the page's own text is backwards too
(`z21145041`, read from its labels) the probe agreed with the backwards
cells: a cell whose Arabic words are in the chosen reading only turned round
is now turned, brackets mirrored and English and numbers kept as they read,
and its first letter - which backwards storage moves to the end (لمؤشرا) -
put back where that makes a word the thesis has (`_turn_cells`,
`QIRTAS_CELLS_TURN`).

**Stray letters at a cell's edge.** Two kinds: `z17931421` draws an
invisible ۡ with one to three alefs or a م, of no width, at a header word's
start (`الاختلافۡا`, `وحدة القياسۡم`); and the plain clip takes any letter
touching the box, so the first letter of the entry beside a number came into
both cells (`251ح` and `حممد`, `z18037898`; `ا ي جودة النموذج`, `z3387756`).
The letter-by-letter reading (rawdict) takes only the cell's own; the text is
still the plain clip's, which keeps English inside Arabic in order, and the
letters it has over the other come off its two ends (`_unseen`,
`_cell_ends`). Tried and dropped: judging a letter by whether its middle is
in the box - the article's alef is drawn at the cell's edge and الدلالة came
out لدلالة. Found by `z21644412` going 15 -> 20 pages: stripping crossed into
the next word, and ran twice, and `ا المتغير` lost the article's alef too; a
thin column then no longer read as a copy of its neighbour, stayed, and a
22-column table ran over seven pages. Now never past the first or last word,
and once.

**A table wider than the text column** (`writer._table_place`,
`QIRTAS_TABLE_PLACE`). Word sets a table from the column's start edge; the
548pt table, drawn from 21pt to 570pt, reached past the paper by a column.
Now indented by the original's own edge, kept 18pt inside the paper, and
scaled to the page only if wider than it.

A paragraph held by a table is also compared without ۡ and vowel marks
(`_unmarked`), both sides alike.

**Full run** `2026-09-28-{thesis,regression}-tables2` against `bwdup`:
nothing lost 100.0% on every file; right page 70.0 -> 70.7%; page truth
wrong 7.2 -> 7.0% (`z17931421` 15.7 -> 13.9%, `z3387756` 10.4 -> 8.2%,
`z17804101` 8.2 -> 7.4%); words in order 94.0%. `z17931421` 17 -> 15 pages
(words 2,824 -> 2,467, the original 2,335), `z21145041` 15 -> 14,
`z17804101` 16 -> 15. Lower: `z22058810` right page 54.6 -> 53.8% (its
backwards hidden text, as before). Looked at: `z17931421` page 6 - all ten
columns on the page, the header as printed, two of its eighteen rows still
written again below it (words the page draws with a space inside:
`ال رجلين`, read لا رجلين).

**Second batch, 2026-09-29.** *Tables that are not tables*
(`reader._ruled`, `QIRTAS_TABLE_RULES`): the finder builds grids from filled
boxes too, and white or tinted fills behind lines of text came out as
tables - `z22058810`'s footnotes (pages 11-12) and its shaded opening verse,
reference lists (`z18896740`, `z5227331`, `z15446639`), `z21644412`'s cover
title. A found table with no rule inside its box - a stroked line, or a fill
2pt thin or less, Word's way of drawing borders - is dropped and its text read
as text. Listed on all 25 theses first: every one so dropped was one of
these. *Pieces* (`_drop_pieces`, `QIRTAS_TABLE_PIECES`): a table inside
another's box on its page is a piece of it - `z3387756` page 12's big table
and five of its rows found again. *Rows written again*: a paragraph inside a
table's box also counts as held where each word of four letters or more is
in the table's letters with the spaces out (`_held_by`) - the clip breaks
words the page draws in pieces (`المع ا لم`); whole words only had been set
after this lost text on `z17931421` when ۡ was still in the text.

Full run `2026-09-29-{thesis,regression}-tables3` against `tables2`: nothing
lost 100.0%; right page 70.7 -> 71.3%; page truth wrong 7.0 -> 6.9%;
`z3387756` 15 -> 14 pages, right page 79.8 -> 93.2%; `z18047321` 16 -> 15.
Looked at: `z3387756` page 12 - one table, all its rows; thin sliver columns
of the double rules still hold single stray letters, and six rows are still
written again below it (note references inside them, cells read
differently). `z22058810` page 2: the verse is no longer a table - but the
backfill's backwards copy of it is still written under it (FLAGS 32).

### Verses: the order of labelled lines, the backwards copy, the brackets, 2026-09-29

Moaz: tables parked, "fix the flag 32 first... make sure to find any bugs
relating to verses since its the most important"; he had seen a verse's last
word or letters outside its bracket. Looking at `z22058810` page 2 found
three faults, not one, and a look across the theses two more.

*Lines labelled left to right* (`reader._turn_lines`,
`QIRTAS_TAGS_LINE_TURN`). Word labels most Arabic lines in reading order,
but some in the order they are drawn, left to right: the verse's second line
came as "كَ فِي عِبَادِكَ الصَّالِحِينَ" then "وَأَدْخِلْنِي بِرَحْمَتِ" -
برحمتك cut and its end set after the line - and page 27's header word for
word backwards. Each label's letters are now placed on the page (the marks
`_page_marks` reads for every numbered piece, split out of `_drawn_reader`),
and a row of pieces on one baseline whose Arabic pieces step rightwards more
often than leftwards is turned. By where each piece *starts*: the width read
for a run of marked letters runs long (the verse's first line ends at x=1115
on a 595pt page). A step counts at half the letters' size - a tanween's alef
is a piece of its own a few points right of its word (عشوائي, اً), and
counted, a right line turned and split it. Spaces keep their places between
pieces; a run of English or *digits* keeps its own order - counted as Arabic,
"٢٠٢٤." turned into ".٠٢٤٢"; a bracket on its own turns with the line -
stuck to its number it read "4()". Fixed on `z22058810`: the verse, headings
on pages 27, 100 and 123, four sentences whose last words had jumped to their
start, four notes' "(4)" and "(1)". On `z21145041` one formula (a Word
equation, left to right) now has its words in order but its unit brackets
facing the other way; left.

*The backwards copy* (FLAGS 32; `reader._drawn_there`,
`QIRTAS_BACKFILL_PLACE`). The labels' pieces are also recorded with where
they are drawn (`doc.drawn_at`: page -> x, baseline from the top, letters).
Before the backfill adds another reading's paragraph it asks what the labels
draw inside that paragraph's box: 90% of its letters there, and it is a
second reading of text we have - skipped, its English and numbers put back
as for a backwards paragraph. Letters alone, asked of the whole page, cannot
decide it: a paragraph from another page shares a median 85% of a page's
letters, up to 95% (the verse copy: 95%); neighbouring letter pairs either
way round, 0.68 for the verse against up to 0.85 by chance. The place settles
it, and a line the labels miss has nothing drawn in its place to match:
`z22058810` pages 163 and 165 begin with a line the labels lack, and it is
still put back. Stripping vowel marks before asking by words was tried again:
the verse still added, two paragraphs more; reverted. Gone from `z22058810`:
the verse copy and eight backwards lines (pages 21, 42, 49, 123, 133, 143,
168; `z21145041` page 17).

*A picture's description* (`writer._in_its_words`, `QIRTAS_ALT_PLACE`). The
tags route reads a /Figure's /Alt as text, and the Basmala picture above the
verse was written again under it, "بسم الله الرحمن الرحيم" - with it
"D:\download.png" on the title page and "---" twice on `z21145041`. Dropped
in the reader, the Basmala went above "الآية:": the labels' text has no place
on the page and a picture goes at its share of the way down, a guess the
description's line had been steadying. Now each picture on a page takes a
description's place, in order, and the description is not written.

*The brackets round a verse* (`order.VERSE`, `QIRTAS_VERSE_BRACKETS`) - the
fault Moaz saw. ﴿ and ﴾ sit among the display shapes (U+FD3E, U+FD3F), and
`order.ARABIC` took them for letters, so they stayed where Word stores them:
`z18037898` stores "﴿ :أكل ذبائحهم ... قال"; the colon was put back after
تعالى, the bracket was not, and the verse opened a line early. They are now
marks, each going after the word drawn on its right, as a colon does. The
zero-width non-joiner `z21850164` puts after every word now counts as between
a word and its mark ("تعالى:‌﴿" had read the bracket as kept from its word).
Lines with a bracket: `z18037898` 27 of 55 changed, `z18048055` 45 of 75,
`z21850164` 5 of 13, `z5227331` 2 of 3, `z21728839` 1 of 4; Moaz's chapters
none. About 40 of the 80 read before and after: each puts a bracket or a
colon where the page has it.

*The gate caught one* (`order._by_pieces`, `_Whole.cuts`,
`QIRTAS_PIECE_ORDER`). Full run `verses1`: `z21850164` 98.9%. Word labels a
note number apart from its line, so the labels reading sees "…رِضْوَانَه" and
"96" as two lines, and put the verse's bracket right; the checker reads one
line with a number in it, which is only reordered where both readings see it
whole (`_Whole.keeps`), and kept the stored "ا﴾ُللهََّ … رِضْوَانَه96". The
bracket as a letter had hidden this: neither side moved it. Such a line is now
read piece by piece, each piece as the labels cut it. That reaches beyond
verses: about 170 lines in 17 theses, nearly all a comma, colon or full stop
moving from a line's start to after its word before a number (،فضيل2022 ->
فضيل،2022) - as the labels reading already had them.

Full runs `2026-09-29-{thesis,regression}-verses2` against `tables3` (`verses3`,
with the picture placed in its description's slot, reads the same):
nothing lost 100.0% (worst file 100.0%); words in order 94.0 -> 94.4%;
right page 71.3 -> 71.2%; page truth wrong 6.9% unchanged. Right page falls
on `z22058810` alone (53.3 -> 49.4%): it reads that file's backwards hidden
text, which the removed backwards copies matched, as in "Backwards second
copies". Regression set unchanged.

*Found, not fixed - the verses' own letters.* `z18037898` sets its verses in
KFGQPC Uthmanic, which draws some letters joined into one shape and maps the
shape to its first letter only: ٱلۡيَوۡمَ is stored without its ي, ٱلۡحَقِّ
without its ح, ٱلَّذِينَ without its ذ. The font's own table agrees; there
are no labels with the spelling. Nothing in the PDF holds these letters.
`z18842416` sets its verses in QCF page fonts, where each shape is a whole
word and the stored text is private codes (ﱥﱴﱵ...); in Word they read only
where those fonts are installed. Five of the 37 cut theses use a Quran font.
FLAGS 33; repaired the same day, next section.

### Verses in Quran fonts, from the Quran text, 2026-09-29

Moaz's call on FLAGS 33: repair. `convert/quran.py`, with Tanzil's Uthmani
text in `convert/data/` (unchanged, as its terms require; credit in README).

*Why not repair the font's table.* `glyphs.py` repairs a wrong table in a copy
of the PDF that both sides read, and that was tried first: the shapes that
carry two letters (لن, للَّ) come out of PyMuPDF turned round, so writing them
backwards in the table gave ٱلنَّاس - and made PyMuPDF break those lines in
odd places. Dropped.

*How it works.* Every line's stretch in a Quran font (by font name) is lined
up with the Quran by its letters - vowel marks dropped, hamza seats and ى/ي,
ة/ه folded, the stretching stroke dropped - using three-letter pieces to find
the place and an edit alignment to pair letters (a pair turned round counts as
found). The run's words are grouped with the Quran words their letters landed
on, and each group - and two and three side by side - becomes {its letters:
the Quran's words}. Applied by `pdftext.apply_fixes` after the text map, so
the converter and the checker both get it (`Fixes.verses`, carried on the
map).

*Traps, each seen:*
- keyed on letters, not on text: the two sides do not hold a broken verse
  alike (ٱلنَّاس ُ / ٱنلَّاس ُ, عَدُوِي / عَدُو ِي). A key fires on whole
  words joined by spaces only, so a verse number or a bracket stops it and
  stays.
- never a key the thesis's own writing has, read as the checker reads the
  page (`order.get_text`) and as both sides hold it after the lam-alef repair:
  read from MuPDF's plain dict instead, إىل (stored إلى) was missed and
  became ٱلَّذِى, and هلم (لهم) became لَّهُمْ throughout the prose.
- a line can line up well as a whole with one group of it lined up anywhere:
  وَقَدْ كَفَرُوا۟ بِمَا came out وَقَدْ سَرِيعُ ٱلْحِسَابِ. Each group has to
  agree on its own (80% of its letters; one letter missing is the fault
  itself - وََكَنَ is وَكَانَ). One stray letter lined up with nothing is a
  mark stored as a letter (حِل ر for حِلٌّ) and does not count against it.
- read a line alone and with its neighbours, and keep every reading found: a
  line of three letters is not found alone, but the line before may end
  another verse, and read with it the first word landed wrong (وََّلَ).
- a word our reader cut in two: ٱَّلل ه is ٱللَّهِ already. A key is not used
  when the letter it adds is the lone letter after it (`z17366480`'s
  Basmala came out ٱللَّهِ ه).
- a key two readings disagree on is dropped: خَبِيرٌ and خَبِيرٌۢ are both
  Quran spellings.

Checked: every change on `z18037898` compared stretch by stretch with what was
stored (none below 67% of letters in common, the two lowest كُلُّ and فِى,
both right); our Word file and the checker hold the same 361 Quran-spelled
words; the pages rendered and read (Word's Traditional Arabic draws the Quran
text's small marks). `z18037898`: verse words stored right 50 of 386 -> 371 of
395 spelled as the Quran has them. Full run `2026-09-29-{thesis,regression}-
quran1` against `verses3`: nothing lost 100.0% (worst file 100.0%); words in
order 94.4% unchanged; right page 71.2 -> 71.3%; `z18037898`'s page truth
(OCR of the page image, which the stored text cannot flatter) wrong 10.3 ->
9.4%; regression set unchanged. Then two fixes (the cut word, every reading)
touching only the two repaired files, rerun alone (`quick-quran3`): nothing
lost 100%; `z17366480` order back to 98.1%, right page 90.6 -> 91.5%;
`z18037898` order 99.6 -> 99.8%, right page 83.0 -> 84.0%.

Left (FLAGS 33): `z17366480`'s Basmala, stored with its words backwards;
`z15446639`, whose Al Qalam font stores almost only the vowel marks; about a
dozen words on `z18037898`; QCF (`z18842416`, holdout), whose codes the Quran
text cannot name.

### The text list re-checked on the theses, 2026-09-29

TASKS' text list (glued words, words not on the page) was drawn up on the old
corpus. Every wrong word of `2026-09-29-thesis-quran1`'s page truth counted
and sorted, 560 in all (not the 15 a page `truth.json` keeps):

    not on the page      199   36%
    one letter off       173   31%
    piece of a word      106   19%
    glued to a number     40    7%
    word cut in two       36    6%
    two words glued        6    1%

Read by file and page, almost all of it is the OCR, not us: it misreads the
small bold of reference lists and table headings (التدريي for our
التدريبي, المحسونه for المحسوبة, لاهتصد), reads nothing on two section
divider pages where ours holds the heading, reads Quran spelling as plain
spelling, and splits ص1994 and قسنطينة 2 differently from how the page and
ours hold them. **Glued words are gone on the theses** (6; the old file was
`z20276275`). Real faults found:

- two title pages in display fonts not installed here, whose tables name
  the wrong letters: `z18047321` (Sultan, Hacen Tunisia: جامعةةةةةة,
  الدكتوز, غصة) and `z18441713` (PT Bold Heading: اطبر محبسب ... راش المبل).
  FLAGS 23's open half; Moaz decided 22 Sept to warn (Part 2, not built).
- words the PDF itself stores cut by a space the page does not draw (اخت
  بار, الا نطلاق, مخر جات) - on both sides, so the gate is fine; the page
  shows one word. A third test for `join_map` was tried: a space whose letters
  have no room (closer than 0.05 of the type size, overlap under 0.5), on
  pages where 97% of spaces have a real gap, judged against the line's own
  letter spacing (one line of `z18441713` draws its boxes overlapping inside
  words: "المؤشر المصري" would have joined). Of 284 such spaces on 199 of 414
  pages all but that line were words cut in two - but the existing tests
  already join nearly all, or the rule that every copy of a word must carry
  the evidence holds them back: 8 new words on 5 files. Reverted; not worth
  a change to the step both sides share.

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

0. **Right page read Word's own backwards ligatures (2026-09-22).** Our
   output is rendered to PDF by Word to be scored, and Word writes its
   ligatures backwards like the documents it made: our correct خلال reads
   back as خالل. The original's words were compared as stored, broken the
   same way, so it mostly cancelled - until the converter began spelling
   them right. Repairing only the original made right page FALL (z19851706
   0.824 -> 0.747); repairing both sides, as the gate always did, is right.
   Re-scored on identical output: small unseen files 30.6% -> 35.2%, theses
   68.2% -> 73.1%. Unrelated documents 3.5% -> 3.7%, so it is not a more
   generous scorer - words on the right page were being missed. **Every
   right page recorded under Word before this is understated and is not
   comparable.** `fit._spilled` still reads both sides unrepaired, which is
   consistent with itself.

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
