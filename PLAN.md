# Arabic PDF → Word: the plan

Last updated 2026-09-17.

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

    on 14 unseen files pulled from the wild: no text lost 100%,
    words 97.9%, right page 23%

**No text lost is the hard gate** and it holds on all 22 files. "Right page"
means words landing on the matching page; unrelated documents score ~13%, so it
is measured against that floor, not against zero.

## What works now

- correct right-to-left Arabic, correct letters, correct word order
- lines joined into real paragraphs
- headings found and styled (from heading labels, font size, or line shape)
- footnotes moved to the foot of the page under a rule
- page size, margins, font size and line spacing measured off the original
- the document's own Arabic font carried through, not a substitute
- page breaks aligned to the original's pages

## Work list (rewritten 2026-09-17 after seeing wild output)

**Blocking - nothing can be measured honestly until these are done**

1. DONE. The check now locates each sentence of the original in the output and
   measures the longest run that stayed in order - O(n log n). A 418,000
   character document scores in 0.14s where the character comparison held a
   core at 97% for an hour. Validated: identical 100%, unrelated 0%, same text
   shuffled 0.6%.  Was: O(n-squared) on characters. It pinned a core at
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
   STILL WRONG: image counts are inconsistent across files - 33/33, 7/7 and 5/5
   on some, but 62->13, 53->3, 11->0 and 6->0 on others. Works sometimes; the
   failures are not yet diagnosed.
   A chart's axis labels are still picked up as a table.

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

8. Bold and italic inside a paragraph (only whole-block boldness is carried).
9. Heading detection over-fires on any short line ending in a colon.
10. Real Word footnotes. Ours are ordinary paragraphs at the foot of the page;
    Word cannot renumber them. Needs hand-built footnotes.xml.

**Last**

11. Open the holdout set once, to find out whether any of this generalised.

## Known unfinished## Known unfinished

- **Pagination on ordinary files.** Our 8 files land 65% of words on the right
  page; unseen files manage 23%, with pages inflating about 1.5x. A page that
  overflows even slightly becomes two, and the error repeats on every page.
- **Tables and images** are not handled at all (steps 7 and 8).
- **Real Word footnotes.** Ours are ordinary paragraphs at the foot of the page,
  not footnote objects Word can renumber. python-docx cannot write them without
  hand-building footnotes.xml.
- **Bold and italic inside a paragraph.** Only whole-block boldness is carried.
- **Heading detection over-fires** on lines ending in a colon.

## Measurement caveats, learned the hard way

Every one of these made the numbers lie before it was found:

1. **LibreOffice reverses Arabic letter pairs** (لا -> ال) when exporting our
   .docx to PDF. Text is now read from the .docx directly and never rendered.
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
