# Qirtas — progress

Where the project stands, in plain language. **Updated after every task.**
Detail and reasoning live in `PLAN.md`; the to-do list in `TASKS.md`; open
risks in `FLAGS.md`.

## Where we are now

**Focus: text accuracy first** (Moaz, 22 Sept). The words in the Word file
must match the printed page before any work on looks.

| Measure | Now | When "text first" started (22 Sept) |
|---|---|---|
| Our words that are **not** on the printed page (48 test files) | **7.8%**‡ | 17.1% (old way of counting) |
| Same, on Moaz's theses - the measuring floor | 2.8%‡ | 3.5% (old way) |
| **How far above the floor we are** | **5.0 points** | 13.6 points (old way) |
| Words on the printed page that we have | **91.9%** | 87.2% |
| Nothing lost (the hard gate), test files | 99.8%, worst file 90.0%* | 100%* |
| Nothing lost, theses and hard files | 100% | 100% |
| Pages land on the right page (test files) | 65.4% | 60.0% |
| Pages land on the right page (theses) | 83.6% | 80.6% |

‡ The page check was counting numbers in running headers against us
(23 Sept, fixed). Counted the old way the same files give 11.8%, theses
3.5%. The "how far above the floor" row is the fair comparison.

Full run of 24 Sept (`2026-09-24-{dev,regression}-textfixes4`), with the
fixes for spaces inside words, split words and punctuation beside numbers:
against the run of 23 Sept evening, 36 of 48 files better, none worse;
theses unchanged.

\* The worst file (`z21763864`) draws its text as shapes and its hidden text
is misspelled throughout; the gate now asks the printed page when the hidden
text disagrees (confirmed by Moaz, 23 Sept).

"Not on the printed page" is measured by Windows reading the page image
(OCR). Even perfect text scores about 3.5% there, because OCR itself makes
mistakes — that is the realistic floor.

## What is left, biggest first

Of the remaining wrong words, about 2.8 points are the OCR misreading the
page (measured on the theses, whose text is right). The rest is ours. The
biggest piece of it was **spaces Word stored inside words** (`م رجعية`,
`للعلا قات`) - about 2 points. Most of it is now fixed by where the space is
drawn (see the timeline); a full run will say how much is left. Then, smaller:

1. ~~Punctuation next to numbers or English~~ — done 23 Sept (see the
   timeline).
2. **`امل` for `الم` in `z21763864`** — the file whose text is drawn as
   shapes; the others are fixed (see the timeline).
3. **Words not on the page at all** — to be looked at file by file.
4. **Numbers** — mostly the OCR misreading small numbers; check before fixing.
5. **Text drawn as shapes** (`z21763864`).
6. **Ask the user to install a missing font** before converting (Moaz's
   idea, 23 Sept) — in TASKS.
7. Then the looks: bold, centring, the coloured bands, tables, footnotes.

### Plan from here (agreed 23 Sept, rough estimates)

**Part 1: text, about 2 days** (started 23 Sept)
1. Full run on every test file - DONE 24 Sept (wrong words 9.3% -> 7.8%).
2. Punctuation next to numbers or English - DONE 23-24 Sept.
3. Numbers - CHECKED 23 Sept: nearly all the OCR misreading; no fix.
Next, in this order (agreed 24 Sept):
4. Brackets around English citations (`(Shegaze et al., 2020)` lands in
   the wrong place when a line wraps) and a stray `%`. Half a day.
5. Words glued together, the rest (part was fixed by 2). Half a day.
6. Words not on the page at all, file by file. Half a day.
7. One file comes out 24 pages against 23. A couple of hours.

Parked: `z21763864`, whose text is drawn as shapes.

**Part 2: missing-font feature, about 1 day**
8. Before converting, tell the user which fonts the PDF uses that are not
   installed, and which to install (Moaz's idea).
9. On Moaz's PC: DecoType Naskh Special and Muna still missing.

**Part 3: looks, about a week**
10. Bold, italics, text size (Moaz's thesis page: all bold in the original,
regular in ours; footnotes far too small). 11. Arabic-style digits and
commas where the original shows them (`(١)`, `٤٠`, `،`). 12. Centring,
alignment, list dashes. 13. Coloured bands and headers. 14. Tables that
look like the original. 15. Footnotes.

**Waiting on Moaz:** nothing - everything is pushed (24 Sept). Two fonts are
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
- **Why our shape check misses them**: mostly the letter before the space
  never joins (إ يجاد), or the page itself draws the word broken
  (الم ستخرجة). The shapes cannot fix what is left; a different idea is
  needed (see "What is left").
- **Spaces inside words, second fix**: where the letters' shapes say
  nothing, the place Word draws the space does - a fake space is drawn
  somewhere else on the line, a real one between the two words. On 11 short
  files: wrong words 7.2% -> 6.1%, 7 files better, none worse, nothing lost
  still 100%. About 500 words joined; one of them wrongly (في منحني).
- **Words cut between two pieces of text that touch** (`التأ هيلي`,
  `والخد مي`, found on the random page): joined when the letters either
  side of the cut touch - between two real words there is always a space's
  width. 75 more split words caught on the checked pages, none wrongly.
- **Punctuation and spaces next to numbers or English** (`وبأطوال30` for
  وبأطوال 30, `:المجلد07`): put where the page draws them. Three mistakes
  caught on the way and fixed before keeping it: brackets flipped, spaces
  between Arabic words moved, and English lines with an Arabic word read
  backwards (the "nothing lost" check caught that one).
- **List dashes and bullets shown as boxes**: they are typed in the Symbol
  or Wingdings font; now turned into real dashes and bullets. 96 in 5 test
  files.
- **Numbers checked**: of the numbers the page check disagrees with, most
  are the OCR misreading references and web addresses. Nothing to fix.
- On 11 short files these three: wrong words 6.1% -> **5.2%**, 7 files
  better, none worse, nothing lost 100%.
- **The full run caught a problem the short files could not**: on 7 longer
  files the "nothing lost" check fell (to 98.4-99.6%) at a bracket next to
  an English word or number. In PDFs that carry Word's hidden labels, Word
  labels each English word and number separately, so the converter and the
  checker saw those lines differently. Fixed: such a line is changed only
  where both see it whole. Those 8 files: nothing lost 100% again, and they
  kept their gains.
- **Full run, 24 Sept**: wrong words 9.3% -> **7.8%**, 36 files better,
  none worse; distance above the measuring floor 6.5 -> 5.0 points;
  nothing lost 100% on every file but the parked one.
- Tried and reverted: fixing letter order at the source (fought an
  existing repair); moving punctuation to where it is drawn (cost the
  gate on two files).
