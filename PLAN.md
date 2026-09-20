# Qirtas - Arabic PDF back to Word: the plan

Last updated 2026-09-20.

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
