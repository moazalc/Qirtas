# Qirtas — progress

Where the project stands, in plain language. **Updated after every task.**
Detail and reasoning live in `PLAN.md`; the to-do list in `TASKS.md`; open
risks in `FLAGS.md`.

## Where we are now

**Focus: text accuracy first** (Moaz, 22 Sept). The words in the Word file
must match the printed page before any work on looks.

| Measure | Now | When "text first" started (22 Sept) |
|---|---|---|
| Our words that are **not** on the printed page (48 test files) | **9.3%**‡ | 17.1% (old way of counting) |
| Same, on Moaz's theses - the measuring floor | 2.8%‡ | 3.5% (old way) |
| **How far above the floor we are** | **6.5 points** | 13.6 points (old way) |
| Words on the printed page that we have | **90.7%** | 87.2% |
| Nothing lost (the hard gate), test files | 99.8%, worst file 89.7%* | 100%* |
| Nothing lost, theses and hard files | 100% | 100% |
| Pages land on the right page (test files) | 64.6% | 60.0% |
| Pages land on the right page (theses) | 83.5% | 80.6% |

‡ The page check was counting numbers in running headers against us
(23 Sept, fixed). Counted the old way the same files give 11.8%, theses
3.5%. The "how far above the floor" row is the fair comparison.

Full run of 23 Sept evening (`2026-09-23-{dev,regression}-newbase`), the
first with Moaz's fonts installed: 22 files better than the run before
today's fixes, none worse.

\* The worst file (`z21763864`) draws its text as shapes and its hidden text
is misspelled throughout; the gate now asks the printed page when the hidden
text disagrees (confirmed by Moaz, 23 Sept).

"Not on the printed page" is measured by Windows reading the page image
(OCR). Even perfect text scores about 3.5% there, because OCR itself makes
mistakes — that is the realistic floor.

## What is left, biggest first

Of the remaining wrong words, about 2.8 points are the OCR misreading the
page (measured on the theses, whose text is right). The rest is ours. The
biggest piece of it: **spaces Word stored inside words** (`م رجعية`,
`للعلا قات`) where our shape check finds no evidence - about 2 points.
Then, smaller:

1. **Punctuation next to numbers or English** (`الإ8 ،براهيمي`) — the
   Arabic-only lines are fixed (see the timeline); these are not yet.
2. **`امل` for `الم` in `z21763864`** — the file whose text is drawn as
   shapes; the others are fixed (see the timeline).
3. **Words not on the page at all** — to be looked at file by file.
4. **Numbers** — mostly the OCR misreading small numbers; check before fixing.
5. **Text drawn as shapes** (`z21763864`).
6. **Ask the user to install a missing font** before converting (Moaz's
   idea, 23 Sept) — in TASKS.
7. Then the looks: bold, centring, the coloured bands, tables, footnotes.

**Waiting on Moaz:** nothing to push. Two fonts are
still missing: **DecoType Naskh Special** (the plain DecoType Naskh installed
is a different font) and **Muna**. 

Arabic fonts the test files use that this PC does not have, most text first:
Adobe Arabic (`z20538636`), Boutros News H1 (`z20276275`), Arslan Wessam B
(`z22051439`), AF Diwani (`z21764254`, `z21764410`), DecoType Naskh
(`z21751977`), Muna (`z20538636`), Almarai (`z20538636`), AGA Arabesque
(3 theses, a few signs), Arabic Transparent (`z21763864`), and a handful
with under 60 letters each. Not installable: `GlyphLessFont` (text laid over
a scan by an OCR program) and `F1`-`F9` (fonts whose names were removed).

## Timeline

### Up to 20 Sept — setting up
- Test files collected and fixed in place, so every score is measured on
  the same set. Scoring tools built.
- Project notes set up (`TASKS`, `FLAGS`, `PLAN`).
- Lists: bullets and numbered items recognised.

### 21 Sept — Word as the only renderer, reading structure
- LibreOffice dropped (it reversed Arabic letter pairs). Word only.
- Title pages, boxed page numbers, thesis page numbers.
- Word's hidden structure labels read (headings, lists, footnotes).
- Footnotes and endnotes as Word prints them.
- Spelling check against Word's own reading of the PDF.

### 22 Sept — broken Arabic inside the PDF
- لا stored backwards: repaired, on by default.
- Other letter pairs stored backwards (في, التي, المجتمع) repaired.
- Scanned PDFs refused.
- Arabic display shapes turned back into plain letters.
- Fonts that name the wrong letters read by the shape of each letter;
  warning when a font is not installed (Moaz's call).
- 49 random pages reviewed with Moaz; faults sorted by cause.
- Body font by the letters it draws; honorific signs kept; digits as shown.
- Headers, footers and page numbers moved out of the body into Word's real
  header and footer.
- Moaz: the text is not accurate enough on PDFs from the wild — **text
  first**.

### 23 Sept — text accuracy
- **The page as the reference**: Windows OCR reads the printed page and we
  score against what is actually printed, not the PDF's hidden text.
- **OCR fixes broken fonts**: where a font's hidden text lies (3133 for
  1315, زلمد for محمد), OCR'd words vote on the right letter.
  `z21762915`: 54% wrong words → 12%.
- **No second copy**: a bug wrote parts of documents twice (3,482 words on
  one file). Fixed.
- **The gate asks the page** when the hidden text is misspelled.
  Confirmed by Moaz.
- **Words cut between two pieces** joined back. 12 files better, 0 worse.
- **Missing article title** on page 1: it was thrown away as a duplicate
  of the header band. Fixed; 4 more files got text back.
- **Spaces inside words** (`الوطن ية`): joined when the letter beside the
  space is drawn in its joined shape. 24 files better, 0 worse.
- **Letters in the wrong order** (`بني` for بين): fixed where the word is
  ambiguous alone, by keying the fix with the word beside it. 6 files
  better, 0 worse.
- **Footer printed twice**: fixed.
- Pushed everything to GitHub. Listed the Arabic fonts missing on this PC;
  Moaz installed most of them. Three were still not recognised because the
  PDF names them differently (cut short, or by family name) - fixed. On 7
  short files the fonts changed nothing; the files that need them are longer.
- **Broke down the remaining wrong words** by cause (see "What is left").
- **Stretched words** (`شبببببكات` for شبكات): Word's justification stroke
  was stored as a letter, and in one file spaces as ا. Fixed: `z20397518`
  54% wrong words → 8%, `z20276145` 18% → 7%. It also exposed a fault in
  the gate's page check, fixed and re-checked on every file.
- **Backwards words in tables** (`بعوتسي` for يستوعب): the PDF had them
  right; our table reader fell back to a backwards copy whenever a cell had
  more than one line. Fixed: 300 cells across the test files now read
  forward. Wrong words: `z22639353` 9.9% → 5.0%, `z21013208` 21.8% → 17.9%,
  two more files a little better, none worse; nothing lost still 100%.
- Pushed everything to GitHub.
- **Punctuation in the wrong place** (`،عشر`, `ا،جلزائر`, `اهل.امل`) —
  third attempt, kept. The earlier two fixed the text after it was read,
  and the converter and the checker disagreed. Now every place that reads
  a page's text goes through one function that puts each comma and full
  stop after the word it is drawn beside. Checked on all 1,033 test pages
  that it changes nothing else. On 9 files: nothing lost 100%, wrong
  words down on 4 (`z21762915` 8.2% → 7.1%), none worse, theses
  unchanged. Not yet: marks beside numbers or English words.
- **Full run with everything so far**: wrong words 14.1% → **11.9%**
  (better than the 12.9% estimate), 22 files better, none worse; theses
  unchanged; nothing lost unchanged.
- **`امل` written for `الم`** (`املهاجرين`, `املحددات`): the running header
  in a bigger font hid the evidence, so the fix was dropped for the whole
  file; and words split by a space were joined back in the stored order.
  Both fixed. `z21095413` wrong words 9.8% → 6.4%, two more files a little
  better, none worse, nothing lost 100%.
- **Fixed the page check itself**: it counted the numbers in running
  headers (volume, year, page range) against us on every page. Recounted:
  9.3% wrong, and the theses' floor 2.8%. Nothing in the Word files
  changed - only the counting.
- **New breakdown**: the biggest remaining cause is spaces stored inside
  words in the PDF itself (380 of 400 word pieces).
- Tried and reverted: fixing letter order at the source (fought an
  existing repair); moving punctuation to where it is drawn (cost the
  gate on two files).
