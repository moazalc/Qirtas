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
| Pages land on the right page (test files) | 65.7% | 60.0% |
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
4. Brackets around English citations and a stray `%` - DONE 24 Sept.
5. Pictures drawn squashed (found behind the file that came out 24 pages
   against 23; 107 pictures in 23 files). A couple of hours.
6. Words glued together, the rest - nearly all one file. A couple of hours.
7. Words not on the page at all, file by file. Half a day.

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

### 24 Sept — citations, and what is left
- **Brackets around English citations**: the brackets themselves were fine;
  what went wrong was inside. Where a line broke in the middle of a
  citation, Word threw its `&` or comma to the wrong end of the line
  (`(Zumla, 2011 &`). English inside Arabic text is now written as its own
  left-to-right piece, and Word keeps it in order however the line breaks.
  Spaces around brackets now follow the printed page (`العالمي (Shegaze et
  al., 2020)`, not `العالمي( Shegaze et al., 2020 )`), and a `%` stored at
  the wrong end goes back beside its number (`15% من حالات`) - about 190
  of those across 20 test files.
- Read every text change this made on all 86 test files before measuring.
  Two faults caught and fixed first: on lines the PDF stores backwards,
  `في` became `يف`; and `لا يوجد` became `ال يوجد` in two files.
- **Full run**: nothing lost unchanged on every file; wrong words
  unchanged (the page check counts only Arabic words, so it cannot see
  brackets or `%`); right page 65.4% -> 65.7%, one file now exactly its
  own page count. Theses unchanged. Not committed yet.
- One leftover on the example page: `Tuberculosis(TB)` - the PDF stores
  that bracket in the wrong piece, and moving it risks losing words.
- **Needs Moaz** (FLAGS 27): the "right page" check reads our English
  glued to the Arabic word before it, which costs a little of that score
  for nothing. Changing the check means re-scoring every old number.
- **What is left, looked at while the full run ran**: "glued words" is
  nearly all one file that stores whole phrases with no spaces. The file
  that came out 24 pages against 23 is a photo the author squashed to fit,
  which we draw at its own shape, 41pt taller - and 107 pictures in 23 test
  files are like that, up to most of a page in one file. Both are next.
- **Fonts installed by Moaz**: DecoType Naskh Special, Boutros News H1,
  AF_Diwani, Arabic Transparent, AGA Arabesque, XB Niloofar, PT Bold
  Broken, Muna and Muna Black - all found by the converter under the names
  the PDFs use. One fix: a PDF calls Muna "MunaRegular" and the installed
  file calls itself "Muna"; now matched. Still missing: Muna Bold (1,000
  letters in `z20538636`). Scores from here on are not comparable with
  earlier ones - a fresh full run is the new starting point.
- **One page looked at** (`z20276275` page 12, which uses Boutros News H1):
  the fonts are right; the page is not. The table's columns come out in
  the wrong order with the question column squeezed thin, the table is
  written a second time as plain text below it, the stretched title
  (مجلة المؤتمرات العلمية الدولية) comes out as broken pieces, and the text
  below is too small with words glued. All already on the list (tables in
  Part 3, glued words next); the title is new.
- **Fresh full run with the new fonts** (the new starting point): nothing
  lost unchanged on every file; wrong words unchanged at 7.8%. Right page
  65.7% -> 65.1% on the test files, 83.6% -> 87.0% on the theses. One file
  got worse (`z21751977`, 20 pages against 18). I first blamed the new
  font; that was wrong - see the pictures entry below.
- **Pictures drawn squashed - fixed, full run still to do.** Authors often
  squeeze a picture to fit; we gave Word only its width, so it came out at
  its original shape, taller or shorter than on the page. 157 pictures in
  the test files, including a journal logo on every page. Now Word gets the
  height too, and six pictures turned on their side are copied off the page
  the right way round. On 11 picture-heavy files: nothing lost, right page
  62.0% -> 64.7%, one file now exactly its original 17 pages. One file got
  a page longer: two pictures that sit side by side in the original are
  written one above the other, and at their true size they no longer fit.
  That is a separate, older problem, for the looks part.
- **The file I blamed on a font was not a font problem.** `z21751977`'s
  Arabic body text is not letters at all but about 130 small pictures a
  page, like a partly scanned page. The converter drops tiny pictures, so
  the body never arrives. It should probably be refused like a scan - that
  needs your call (FLAGS 28).
- **New test corpus: Arabic theses made in Word** (your call). The old
  collection was mostly short journal articles and scans - 5 theses out of
  225. Now: every Arabic thesis on Zenodo (113 downloaded), of which 37 are
  made by Word with real text. The same 13-14 pages are taken from each
  every time: the opening pages, a run from the middle, a table page and the
  reference list. 25 to work on, 12 kept aside to check we did not tune to
  the 25, and two of your chapters kept as a quick check.
- **Runs are fast now**: a full run took 23 minutes instead of 3 hours; the
  check after each fix will take about 10.
- **Two problems caught while building it**: cutting pages left hidden text
  from the removed pages inside the file (one 14-page cut read back as most
  of the thesis) - fixed; and the page checker was comparing our pages with
  the wrong pages of the whole thesis - fixed before any number was kept.
- **Where the theses stand**: wrong words 10.1% (your chapters 2.2%), right
  page 61.1%, and output 14% longer than the original - some theses come
  out at double their pages. Nothing lost is 99.4%: five theses show words
  missing, and so far what is "missing" is the PDF's own hidden text stored
  backwards, not text we dropped. That is the first thing to settle.
- **The five theses that seemed to lose words - settled.** Most of the
  "lost" text was the PDF's own hidden copy being wrong (stored backwards,
  or with invisible characters between words); the checker now sees through
  that, but only where the page image confirms our text. Looking closely
  turned up four real faults of ours, all fixed:
  - Two theses were written with much of their text **twice, the second
    copy backwards** - no score had noticed. Gone now; their wrong words
    fell from 33% to 14% and from 28% to 20%.
  - Reference-list entries that look almost alike were **dropped** as
    "already there". Now put back.
  - The font repair **ran twice by accident**, and the accident was hiding
    that the first pass missed digits and the ending ـاً - and it broke
    الله. One pass now gets all three right.
  - English inside Arabic lines is **put back on its own line** where the
    reading drops it (COVID19 at a paragraph's end). Nothing is lost, but it
    reads wrong - next on the list.
- **Where it stands**: nothing lost 100% on the theses (one file 99.3%),
  wrong words 9.0% (was 10.1%), your chapters unchanged.

- **Part 2 done: the missing-font message.** There is now one command to
  convert a file: `python -m convert thesis.pdf`. Before converting it
  lists the fonts the PDF uses that this computer does not have, how much
  of the text is in each, and where to get it (Windows' Arabic fonts,
  Google Fonts, Office, the King Fahd Quran fonts ...). The person can
  install them and press Enter to check again, or carry on without them.
  A missing bold whose regular font is installed is only mentioned, since
  Word imitates it. Scans are still refused first.
- **Next: Part 3, looks** - bold, text size, Arabic-style digits, centring
  and list dashes first, starting from your thesis page 13.

- **Part 3 started - bold.** Every bold Arabic word in every file was coming
  out regular. Word keeps a separate "bold" setting for Arabic text, and we
  only ever set the one for English. Fixed, and footnotes now keep their
  bold and the size the original used. Measured as Word actually shows it:
  of the words bold in the original, 18% were bold in ours; now 78%. Left:
  two theses read a different way that carries no formatting, and some
  headings bold that should not be. (A first measurement of this gave a
  wrong 23% - my own counting fault, caught before anything was built on
  it.)

- **Headings and centring.** Headings now keep the original's bold instead
  of all being made bold, and titles and headings drawn in the middle of
  the page are centred (30 of 37 such lines now, was 11). Digits in the
  text already come out as the original shows them.
- **Seen on a title page, still to do:** the title comes out much smaller
  than the original and the page is bunched at the top; things side by side
  (two supervisors, two pictures) are stacked; a page number appears where
  the original has none.
- **Needs you:** footnote numbers and page numbers are made by Word, and
  Word shows them as ١ or 1 depending on each reader's own Word setting. To
  force (١) we would type them in as fixed text - but then they no longer
  renumber if the document is edited. Which do you prefer?

- **Text size fixed.** Every paragraph came out at the body size and every
  heading at a fixed step above it, so a 22pt thesis title came out at about
  14pt. Now each paragraph gets the size the original used, with its line
  spacing to match. Titles and chapter headings at the original's size: 36
  of 48 now, was 17 of 43.
- **Spacing on title pages - tried, not kept yet.** Putting back the gaps
  between the lines of a title page made pages run over, because our pages
  hold more than the original's: things side by side (the two supervisors)
  come out stacked. That is next: fix side by side, then the gaps fit.
- **Footnote and page numbers - parked.** You chose to leave them as they
  are for now (Word's automatic numbers, which show 1 or ١ depending on the
  reader's Word). Written down as FLAGS 31 so it is not forgotten.
- **Side by side fixed.** Two supervisors next to each other on a title
  page now come out next to each other (an invisible two-column table),
  each centred in its column. Seen on 7 of the 25 theses. Reference lists
  whose numbers sit in the margin ("47 -") had the number on a line of its
  own; it now leads its entry again. Scores did not change - this is how
  the page looks, not what is on it. It is also not why some theses come out
  twice as long; that cause is still to be found.
- **No page number on the title page.** Word puts the header and page
  number on every page, so title pages showed a number ("70") and the
  chapter's header, and so did the unnumbered pages after them. Pages the
  original leaves unnumbered at the front now have none, and numbering
  picks up at the right number on the first numbered page.
- **Rows of three or more across.** Tables drawn without borders, read one
  cell at a time, came out with the first cell beside the rest stacked in a
  column. Each cell now sits beside the next, as in the original.
- **Found while looking:** some tables come out as a tall ladder with too
  many columns, and their text is written a second time below them. That
  was there before; it belongs to the tables item still on the list.
- **Tables fixed in part - and some theses much shorter.** Tables drawn
  with double lines came out with a fake empty column between each pair of
  lines, so a 3-column table became a ladder one letter wide spread over
  several pages. And the table's text was written a second time below it.
  Both fixed: one thesis went from 34 pages to 20 (the original has 14),
  another from 27 to 22. Still to do on tables: the header row can come out
  squashed, and about half of the doubled text is still there.
- **Tables now read like the original - and the theses come out the right
  length.** Four things were wrong on every table page looked at:
  - Every Arabic table came out **mirrored** - the original's first column
    on the left. It had been like that all along; no score can see it,
    because the words are the same either way round.
  - A cell stretching across several columns was written into the first of
    them, often a sliver 5pt wide - the **header row one letter a line**.
    Such cells are now merged across their columns, as in the original.
  - The table was placed by guessing how far down the page it sat, and
    landed **in the middle of a paragraph**, with its title after it. It now
    goes after the last paragraph above it.
  - Most of the **table text still written twice** below the table is gone.
- **A thesis whose text came out glued together** (`z21850164`,
  "البعدالقيميوالروحي"): the PDF stores every space as an invisible
  character that Word shows as nothing. It now gets real spaces.
  **The scores had hidden this, and then misjudged the fix** - two of them
  did not treat that character as a space. That is the eighth bug found in
  the measuring tools rather than the converter. Fixed and re-checked both
  ways: that thesis's words in order 76% -> 97%.
- **A word lost on the way, and caught.** The first full run found one
  thesis losing a table heading (nothing lost 97.9%) - a rule for spotting
  doubled table text was too loose. Taken out, and the second full run is
  clean.
- **Full run**: nothing lost is now 100% on **every** thesis - the first
  time; one file had always shown 99.3%. Theses are now the original's
  length overall (they were 7% too long); right page 58.6% -> **69.4%**,
  11 theses better and none worse. One thesis went from 29 pages to 15 (the
  original has 14), another from 26 to 13 (exact). Your chapters unchanged.
  One thesis reads slightly worse on "words in order", and looking at it,
  ours is right: the PDF itself reads that table in the wrong direction.
- **Still to do on tables:** one very large table is also found in pieces,
  which come out as small extra tables under it; a stray letter "ا" in some
  table headings; one thesis's table cells stored backwards in the PDF.
- **Next:** bold and italic on the two theses read through the PDF's hidden
  labels, then italic drawn as slanted text.

### 27 Sept (later) — bold on the two theses read through hidden labels
- Two theses (`z21145041`, `z22058810`) are read from text hidden behind
  each word, which says nothing about bold. Their bold titles, headings and
  table headers came out plain. The letters drawn for each word are still in
  a bold or plain font, even though they spell the word backwards, so each
  word now takes its bold from its own letters.
- Bold words of the original shown bold: **76 -> 91 of 150** on one thesis,
  **28 -> 64 of 79** on the other. Nothing lost still 100%, and every other
  score unchanged.
- **The bold check had a fault** (the ninth in the measuring tools): on
  these two files the original's words read backwards, so it could never
  match them, and reported 6% and 15% whatever we did. It now compares
  words by their letters, whichever way round.
- **Some bold where the original has none** went up on one thesis. Looked at:
  it is the table's text written a second time under the table (an old
  fault - that thesis stores its table cells backwards). The copy is now bold
  like the table's own header. It goes when that fault is fixed.
- **Next:** italic that Word draws as slanted text (9 theses use it).

### 27 Sept (evening) — slanted italic, and headers keep their looks
- **Italic now shows.** Word has no italic for most Arabic fonts, so it
  fakes one by drawing the ordinary letters leaning over. No font says
  "italic", so we never saw it. We now spot the lean itself. Italic words of
  the original shown italic: **16 -> 114 of 162** on the two theses that have
  it (this includes the next point).
- **Running headers and footers were always written plain.** One thesis's
  italic chapter line at the top of nine pages came out upright. Headers
  and footers now keep the original's bold and italic.
- Nothing lost still 100% on every thesis; the other scores unchanged. One
  thesis came out 24 pages in the full run; converted again it is 17, as
  before - a one-off from Word during the run, not this change.
- **The italic check had to be fixed first**: one thesis's hidden text
  spells words with the wrong letters (جدوؿ for جدول), so nothing matched
  until the check read the repaired letters.
- **Found on the way (a text fault, not looks):** one thesis prints its
  numbers backwards in ours - ٣١٠ comes out ٠١٣. Added to the text list.
- **Next in Part 3:** coloured bands, how footnotes look, the logo between
  two headers; then the leftover table faults.

### 27 Sept (night) — coloured table cells
- Ten of the theses colour some table cells: striped rows, a grey or blue
  header row, a green first column. Ours were all white. Each cell now gets
  the colour drawn behind it in the original.
- Checked by looking at four theses' tables: the colours match. (A count
  was tried and could not tell shading apart reliably, so it was dropped.)
- Nothing lost 100% on every thesis; the other scores unchanged. The thesis
  that came out 24 pages last run is back to 17 - that was the run.
- Runs now use 2 copies of Word at once instead of 3; the PC went down
  twice during runs.
- **Found on the way:** one thesis's widest table runs off the page's edge
  and its text is written again below it - probably why that thesis is 17
  pages against 14. Another table comes out in many narrow empty columns.
  Both added to the table list.
- **Next:** coloured bands behind ordinary text and headers laid out like
  the original (two parts, a line under them), then how footnotes look.

### 28 Sept — coloured bands, and a correction on italic
- **Coloured bands behind text now show**: a dedication in a grey box with
  its border, yellow and green heading rows, a running header that is white
  text on a black band (the text stays white - black on black would vanish).
  Looked at on four theses: they match the original.
- **Correction: I was wrong about one header being italic.** Some decorative
  Arabic fonts say "italic" inside the font file but are drawn upright, and
  the PDF itself says upright. Yesterday's header change copied that false
  italic onto every page of three theses. Italic now counts only when the
  PDF itself says so, or the text is drawn slanted.
- Measured again, properly: real italic words kept 62 of 92, and italic
  where the original has none went from 238 (yesterday) to **1**. The
  "114 of 162" I gave you yesterday included false italic.
- Nothing lost 100% on every thesis; other scores unchanged.
- **Next:** headers laid out like the original (two parts, a line under
  them), then how footnotes look.

### 28 Sept (later) — headers laid out like the original
- **The line under the header** is back on the 7 theses that draw one -
  single, thin over thick, orange, or double lines above and below a band,
  as the original has it.
- **Headers in two parts** (the chapter at one edge, its title at the
  other) came out as one centred line - on one thesis the wrong way round.
  They now sit at the two edges, in the right order.
- Checked by looking at five theses. Nothing lost 100% on every thesis;
  other scores unchanged.
- **Still different:** on two theses the header text is bigger and less
  bold than the original.
- **Next:** how footnotes look (centred instead of starting from the right),
  then the logo between two headers, then the leftover table faults.

### 28 Sept (evening) — footnotes as the original sets them
- **Correction:** I said the footnotes came out centred. Looking at them
  side by side, they did not - they start from the right as they should.
  What was wrong was three other things, now fixed:
- **The short line above the notes** was always at the left and 2 inches
  long. It now sits where the original has it - on the right on most
  theses, on the left on one - and at the original's length.
- **The notes were spaced far apart** (about a third more than the
  original). They now use the original's own spacing, so they take the
  same room at the foot of the page.
- **Bold words inside a note** (a book's title, a sura's name) came out
  plain on four theses. They are bold again.
- **Found on the way:** where a word is split between two pieces of the
  PDF, the reader glued it back together but also made the rest of the
  line bold with it. Fixed in body text too: 20 fewer words wrongly bold.
- Nothing lost 100% on every thesis; other scores unchanged.
- **Still different:** note numbers are Word's small raised digits where
  the originals type "(1)" (parked with page numbers, your call on FLAGS
  31); on one thesis, three notes typed as one paragraph stay one note.
- **Next:** the logo between two headers, then the leftover table faults.

### 28 Sept (night) — the logo between two headers
- **The logo** on one thesis's title page sits between its French and
  Arabic headers; ours put it above them. It is now in its place between
  them.
- **Found on the way:** on 58 pages across 24 theses, a page number the
  program does not move into the footer (the letters أ ب ج on front
  pages, and numbers where the sample jumps) was written as the page's
  first line. It now comes last, where the original has it. Right page
  went up a little (69.3% -> 69.6%).
- Nothing lost 100% on every thesis; other scores unchanged.
- **Still different:** on that title page the two header columns are
  narrower than the original's, so the Arabic line wraps onto three lines.
  Seen on another thesis: a full-page picture with text printed over it
  comes out as picture, text, picture - noted for later.
- **Next:** the leftover table faults (pieces of one table found as
  separate small tables, a stray letter in header cells, cells stored
  backwards, a wide table off the page's edge, a table split into many
  narrow empty columns).

### 28 Sept (late) — brackets where the page prints them
- **Moaz saw brackets in the wrong place, and he was right.** A new check
  (it reads every bracket where the page prints it and looks for it in our
  Word file) found about a third of the theses' brackets misplaced - worse
  than simply keeping the PDF's own order. Worst of all were reference
  lists: "ابن كثير، إسماعيل. (1999). تفسير" came out
  "( ابن كثير، إسماعيل. 1999 .) تفسير".
- **Why:** the PDF stores the bracket, full stop and space next to a year
  at the far end of the Arabic words, and a safety rule from 23 Sept had
  switched our punctuation fixing off on exactly those lines.
- **Now** lines with brackets are read the way they are printed. Some
  fonts store a bracket's drawn shape, so "(62)" came out ")62(" - those
  are turned round too. Brackets in place went from 65% to 79% (reading
  only); reference lists are nearly all right (one thesis 53% -> 97%).
- **Two problems found and fixed on the way:** the "nothing lost" check
  dropped to 97% on one thesis stored backwards (a fault in the check,
  fixed, and Arabic words are now never moved); and looking at a page
  showed a stray ")" after the note numbers in the body text, which the
  bracket check could not see - fixed.
- Nothing lost 100% on every file; right page 69.6% -> 70.2%.
- **Still wrong:** theses stored backwards; English citations and
  formulas the PDF cuts into many pieces; one caption `)59(`.
- **Not FLAGS 27:** that flag is about how the "right page" score reads
  English next to Arabic, and is still open.
- **Next:** the leftover table faults.

### 28 Sept (evening) — English inside Arabic lines, and backwards numbers
- **Moaz asked for these two first.** Both are wrong words, not looks.
- **English and numbers were dropped on two theses** (`z22058810`,
  `z21145041`). Those files attach each Arabic word's text to a hidden label,
  but give English words and numbers no label. We read only the labels, so
  most of the English and numbers went missing - in one thesis 4,300 of
  5,000 - and some English was put back on a line of its own. Every note
  number in the body read "()".
- **Now** they are read from the letters on the page, in their place:
  "COVID19" is back inside its sentence, the note numbers and web
  addresses are back. Nothing Arabic is read this way.
- **Numbers were written backwards in seven theses, not just one** - years
  most of all (6691 for 1966, 9102 for 2019). The PDF reader treats Arabic
  digits (٠-٩) like Arabic letters and reads them right to left; a number
  always reads left to right. Fixed: ٣١٠ is ٣١٠ again.
- **Found on the way:** with their note numbers back, one thesis's
  footnotes spilled a page, because Word set their lines twice too far
  apart. Fixed.
- Nothing lost 100% on every file; wrong words (checked against the page
  image) 8.3% -> 7.9%; right page 70.2% -> 70.3%; your الفصل الثاني
  81.7% -> 83.1%.
- **Still wrong:** `z21145041` now comes out 17 pages for 14 - its English
  is back, but set loosely (big gaps, wide lines), so its reference list
  takes four pages for two. One paragraph there is also written a second
  time backwards (that was there before).
- **Then fixed, at Moaz's request:** the English is now set the way the
  page prints it - its own font (Calibri, Times New Roman), size, line
  spacing, and left-aligned where the original is not justified; "Abstract"
  bold again. The reference list is back to two pages; the file is 15 pages
  for 14 (the extra one is the backwards paragraph above). Nothing else
  changed; nothing lost 100%.
- **Still not done there:** that English's headings are not centred, and
  web addresses are plain text, not links.

### 28 Sept (night) — paragraphs written twice, backwards
- **Moaz asked for this next.** On the two theses above, some paragraphs
  came out twice: once right, then again with every word backwards. The
  step that fills in text one reading missed from another did not
  recognise them as already there, because backwards storage also moves
  letters around a little. It now does - but only for a paragraph that
  reads backwards; one the right way round (a missing title) is still put
  back.
- **The "nothing lost" check needed fixing too.** Once the backwards copies
  were gone it reported two sentences lost on one thesis - both are in our
  file; it was the check reading the PDF's own backwards text. While fixing
  it I tested it by deleting a paragraph on purpose: the check did not
  notice. That is fixed as well - it now also needs the sentence's words to
  be together in our file, not scattered. It catches the deleted paragraph,
  and reads the same as before on every other thesis.
- **Result:** wrong words (checked against the page image) 7.9% -> 7.2%;
  one thesis went from 19% wrong words to 2%. `z21145041` now has as many
  words as the original, and its first 11 pages end where the original's
  do.
- **Not improved on paper:** right page 70.3% -> 70.0%. That score compares
  against the PDF's hidden text, which on these two theses is itself
  backwards - our backwards copies were matching it.
- **Still wrong:** one Quran verse on `z22058810` page 2 is still written a
  second time backwards (now FLAGS 32, at Moaz's request); `z21145041` is
  still a page long, from its results table (a table fault).

### 28 Sept (night) — tables, first batch
- **Tables written twice, and a table off the page.** One thesis
  (`z17931421`) came out 17 pages for 14: its widest table ran off the
  page's left edge, and the table's text was written again underneath.
  The root cause: its font calls the space character a Quranic vowel mark,
  so every word started with a stray mark, and the table's text never
  matched the same text read as paragraphs. The font repair now reads it
  as a space. The wide table is now placed where the original has it,
  reaching into the margins but on the page. 15 pages now.
- **Table cells written backwards** on `z21145041` and in places on
  `z17931421` - now the right way round, checked against the text we
  already trust.
- **Stray letters in cells** - the "ا" at the end of header cells, and
  reference numbers like "251ح" (a letter from the entry next to it). Now
  taken off, only where the page shows they are not the cell's.
- **A mistake caught on the way:** one version of the stray-letter fix also
  took off real letters and made one thesis 5 pages longer. Found by the
  full run, fixed, checked again.
- Right page 70.0% -> 70.7%; wrong words 7.2% -> 7.0%; nothing lost 100%.
  `z21145041` now exactly 14 pages.

### 29 Sept — tables, second batch
- **Things that were not tables** came out as tables: footnotes, a shaded
  Quran verse, reference lists, a cover title. What they had in common:
  shading behind the text but no lines at all. A real table has borders,
  so a "table" with no line of any kind inside it is now read as text.
  Checked on every thesis first: everything this drops was one of these.
- **Pieces of one table found as tables of their own** (`z3387756`: one
  big table plus five of its rows again) - pieces inside a bigger table
  are now left out. That thesis is now exactly 14 pages, and its right
  page went from 80% to 93%.
- Right page 70.7% -> 71.3%; wrong words 7.0% -> 6.9%; nothing lost 100%.
- **Still wrong:** the verse on `z22058810` is no longer a table, but its
  backwards second copy is still written under it (FLAGS 32, still open);
  some thin table columns still hold single stray letters; a few table rows
  still written again below their table.
- **Tables left:** the `z21644412` table with many empty narrow columns,
  and the small leftovers above.
- **Next:** that table, then the smaller leftovers - or the text list, if
  Moaz prefers.

### 29 Sept — verses
Moaz parked the tables ("they will take a really long time") and asked for
the verse flag first, and for any other verse bugs - "the most important".
- **The verse written twice (FLAGS 32) - fixed.** `z22058810`'s opening
  verse came out once right and once backwards underneath. The step that
  fills in missing text now checks what is already written at the same spot
  on the page; the verse is there, so the backwards copy is not added. Eight
  other backwards lines on the same two theses went with it. A line that
  really is missing (two on `z22058810`) is still put back.
- **The verse's second line was scrambled.** "برحمتك" came out split, with
  its last letter after the end of the line. Word stores some lines in the
  order they are drawn, left to right, instead of the order they are read.
  Such lines are now turned back. The same fix repaired a heading printed
  word for word backwards, two more headings, four sentences whose last
  words had jumped to their start, and four footnote numbers.
- **The Basmala picture was also written out as text** under itself. Now the
  picture sits where its description was, and the description is not
  written. Same for two stray "---" lines and a "D:\download.png" on a
  title page.
- **Verse brackets out of place - the fault Moaz saw.** The Quran brackets
  ﴿ ﴾ were being treated as letters, so they stayed wherever Word happened
  to store them: a verse would open a line too early ("وأباح الإسلام ﴿ أكل
  ذبائحهم ... قال تعالى: ٱلۡيَوۡمَ") or close a line too late. They are now
  placed like a colon or full stop, next to the word the page shows them
  beside. About 80 verse lines changed across five theses; the 40 or so I
  read all move a bracket to where the page has it. Moaz's own chapters were already
  right and are unchanged.
- **A catch on the way:** the missing-text check (the gate) dropped one
  thesis to 98.9% after the bracket fix. Nothing was really lost - our text
  had become right and the checker's copy of the original was still wrong in
  a line with a note number. The checker now reads such lines the same way;
  gate back at 100%. This also moves about 170 commas and colons in
  reference lists to after their word, as they are printed.
- Words in order 94.0% -> 94.4%; nothing lost 100% on every file; right
  page 71.3% -> 71.2% (only `z22058810`, whose score reads its PDF's
  backwards hidden text - the removed copies had matched it).
- **Found, not fixed (FLAGS 33, needs Moaz):** five theses set verses in a
  special Quran font. In one, some letters are simply not in the PDF's text
  (ٱلۡيَوۡمَ stored without its ي); in another, the text is private codes
  that only read with that exact font installed. The reliable repair is to
  match each verse against the Quran text and write that - which means
  shipping the Quran text with the converter.
- **Next:** Moaz's call on FLAGS 33; otherwise back to the text list (words
  run together, words not on the page, bracket leftovers).

### 29 Sept — verses in Quran fonts, repaired from the Quran text

Moaz's call: do the repair. Pushed the verse work first.

- **What was wrong.** Some theses set their verses in a special Quran font
  (the King Fahd Complex's). That font draws some letter pairs as one shape
  and the PDF records only the first letter, so ٱلَّذِينَ was stored without
  its ذ, ٱللَّهِ without its ه, ٱلۡيَوۡمَ without its ي. Other shapes came out
  with their two letters swapped (ٱنلَّاس). Nothing in the file holds the
  missing letters.
- **The repair.** The converter now carries the Quran's text (from the
  Tanzil project, the standard free copy, used unchanged and credited). Each
  line set in a Quran font is matched against it letter by letter, and its
  words are written the way the Quran text spells them. The checker does the
  same, so a repaired verse is not counted as lost.
- **Result.** On `z18037898`, the thesis with the most verses: before, 50 of
  its 386 verse words were stored right; now 371 of 395 are spelled exactly
  as the Quran has them. `z17366480`'s verse is repaired too. Nothing lost
  100% on every file. The independent check that reads the page image with
  OCR agrees: wrong words on `z18037898` 10.3% -> 9.4%. Right page up a
  little on both files.
- **Caught on the way:** a first version also changed ordinary words in the
  thesis's own writing (إلى became ٱلَّذِى); one matched a stretch of verse
  to the wrong verse; one left a stray letter where our reader had split a
  word. All three fixed and tested; every change on `z18037898` was checked
  against what was there before, and the pages were rendered and read.
- **Not repaired:** one Basmala stored with its words backwards; one thesis
  whose Quran font stores almost only the vowel marks (no letters to match);
  about a dozen words on `z18037898`; and the QCF fonts, where each word is a
  private code the Quran text cannot name (that thesis is in the paused
  held-back set).
- **Next:** Moaz's call on pushing; then back to the text list (words run
  together, words not on the page, bracket leftovers).

### 29 Sept — the text list, re-checked on the theses

- Pushed the Quran repair.
- The text list (words run together, words not on the page) was made on
  the old test files. On the 25 theses I counted every word our Word file
  has that the page picture does not show: 560. Read one by one, nearly all
  are the page-reading tool (OCR) misreading small bold text, reference
  lists and Quran spelling - our text is right there. Words run together:
  6 in all, so that item is done on the theses.
- **Real faults left:** two title pages in fancy fonts that are not
  installed here (`z18047321`, `z18441713`) come out as gibberish. You
  decided on 22 Sept that the converter should warn the user to install the
  font and convert again - that warning is not built yet. And some words the
  PDF itself stores with a space in the middle (اخت بار); I tried a fix, it
  would repair only 8 more words, so I left it out.
- **Next:** the missing-font warning (it covers the most visible text fault
  left), unless Moaz prefers tables or looks.

### 29 Sept — warning when a missing font makes the text come out wrong

- Pushed the text-list findings.
- **What it does now.** Before converting, the converter already listed the
  fonts this computer lacks. Now it also checks, for each missing Arabic
  font, whether its text will actually come out wrong: Windows' own
  text-reading (OCR) looks at the pages where the font is used and compares
  what it sees with what the PDF stores. Where they disagree, the font is
  named first: "The text set in these fonts will come out WRONG", with a
  sample of how it reads and on which pages, and "install them and convert
  again". The same note is repeated after converting, where it is seen.
  Fonts that are missing but read fine are only listed, as before.
- **Checked on the test files:** it flags 8 fonts on 5 files - every one I
  looked at really is gibberish (the two title pages from before, and three
  more) - and none that reads right. Decorative fonts the OCR cannot read
  (a calligraphic Basmala) are not flagged: their words are checked against
  the rest of the document and the Quran text too.
- **Not caught:** a font with fewer than 10 words (one Quran font), and
  nothing is judged on a computer without Windows' Arabic OCR - there it
  falls back to the plain list. The line between wrong and fine is narrow
  on two fonts (50% against 57% of words readable).
- **Next:** Moaz's call - tables (parked), looks (Part 3), or the Quran
  leftovers.

### 30 Sept — the looks leftovers (items 10-19)

- Pushed the missing-font warning.
- **Done**, each checked on its own page:
  - **Headers** at the right size (they were set by an icon's size), the
    icon itself shows (it was an empty box), and a full-width header starts
    at the right instead of the middle.
  - **Footnotes:** notes numbered "1 ... 2 ... 3" in one paragraph are now
    separate notes; a note's second paragraph stays a paragraph; and a
    verse number inside a note ("(9)") is no longer cut off as a note of its
    own - found while looking.
  - **Title page side cells** reach into the margins like the original, so
    the ministry line wraps less.
  - **A full-page picture with text over it** (`z20585114`) now sits behind
    the text, as in the original, instead of taking a page of its own - that
    file went from 25% to 86% of pages landing right.
  - **Footer:** the right page numbers on every page (it printed "1"
    everywhere), with the double line and the box round the number.
  - **English:** a centred English heading is centred; web addresses are
    clickable links. The full stop after "COVID19" was already fixed.
  - **Brackets** turned the wrong way round a number or web address
    - ")59(" - now print "(59)", as the page does (tested in Word).
  - **Journal line numbers** (417, 418 ... in the margin) no longer end up
    inside sentences; Word numbers the lines itself instead.
  - **A grid of pictures** no longer has its captions written twice.
  - Pictures side by side were already fixed by earlier work.
- **Scores:** nothing lost 100% on every file; pages landing right 71.3% ->
  73.7%; everything else unchanged.
- **Not fixed:** headers set in fonts not installed look lighter and can
  wrap (the missing-font message names them); gaps above paragraphs stay
  off (they push pages over) except on pages with a background picture;
  some brackets in citations cut into pieces; links inside footnotes.
- **Something uncomfortable:** one of my first versions dropped 93 words
  of a reference list, and the "nothing lost" check still said 100%. It
  only checks sentences of 40+ characters, and reference entries are all
  short pieces. I caught it by comparing the words directly and fixed the
  change, but the check itself is blind there (FLAGS 34).
- **Next:** fix that blind spot in the "nothing lost" check before more
  changes, then Moaz's call - tables (parked), the Quran leftovers, or the
  numbers warning.

### 30 Sept — the "nothing lost" check now sees short text

- Pushed the looks leftovers.
- **The blind spot, fixed.** The check only looked at sentences of 40+
  characters, so reference lists, title pages and contents lines were
  never checked. Now short pieces are checked too, joined into stretches.
  Tested on purpose: taking 7 reference entries (100 words) out of a thesis
  now shows as a loss (99.4%); before, it said 100%.
- **It found a real loss straight away:** one thesis's title page
  (`z21145041`) was missing the student's name, "under the supervision
  of", the academic year and the degree line. Our converter reads each
  file several ways and fills gaps from the others, but the gap-filling
  also ignored short text. Fixed: the title page is back.
- **Also found and fixed:** one word misspelled when the PDF stores it in
  two pieces (الانحلال came out الانحالل).
- **Things it cannot see, still:** numbers inside short text (note numbers
  make them unreliable), and text the PDF's hidden text does not contain
  at all. My first version of the title-page fix dropped a Quran verse
  from another thesis, and the check could not see that either - the
  verse is only in the PDF's labels. I caught it by comparing the Word
  files word by word, which I now do for every change that can drop text.
- **Scores:** nothing lost 100% on every file under the stricter check;
  everything else the same or slightly better.
- **Next:** Moaz's call - tables (parked), the Quran leftovers, or the
  numbers warning.

### 1 Oct — the numbers warning

- Pushed the "nothing lost" fix.
- **What it is about.** Some PDFs show one number on the page and store a
  different one underneath - the page says 1951, the stored text says 1901.
  The Word file is made from what is stored, so it says 1901, and none of
  our scores can notice. You decided in September: convert anyway, and tell
  the person which pages.
- **Built.** After converting, it now says, for example:
  "page 7: 1992 (stored as 2991)". Up to ten pages are spelled out, the
  rest listed. Nothing in the Word file changes.
- **Better than the old check.** The old one could only say "this file is
  suspect". The new one reads, for each digit on the page, what is stored
  and what is actually drawn, so it can say the exact number the page shows.
- **How often:** 18 of 338 files, four of them theses - one thesis on 146
  of its 195 pages ("74.4%" stored as "47.7"). I cropped about 45 of the
  flagged numbers from the pages and looked: every one was what the check
  said. Your own chapters: nothing flagged.
- **What went wrong on the way:** the first try flagged 69 files, mostly
  nonsense - two fonts with the same name, and it read the digits with the
  wrong one. Now it only judges a font when there is no doubt which one it
  is.
- **What it cannot do yet:** fix the numbers. It knows what the page
  shows, but changing numbers silently needs its own independent check
  first. It also cannot check fonts that are not inside the PDF.
- **Next:** your call - tables (parked), the Quran leftovers, or actually
  correcting these numbers.
- **Correction, same day, from the page you asked for.** Converting a whole
  thesis page showed the warning was checking the wrong thing. Our letter
  repair had already put some of the numbers right (74.4% was correct in
  the Word file), so the warning named numbers that were fine - and missed
  six that were wrong (416 written as 614, 94.5% as 1645%), because two
  fonts on the page share the name Times New Roman. Now it checks the
  copy the converter actually reads, works out which of the two fonts drew
  each number, and reads decimal points too (one thesis stores 0.05 as
  0005, 1,210 times). On your page it names exactly the six. Across the
  corpus: 14 of 338 files, three of them theses. I looked at about 30 of
  the flagged numbers after the change: all right.

### 1 Oct — the wrong numbers, corrected

- **What it does.** Where the PDF shows one number and stores another, the
  Word file now gets the number the page shows. It uses the same evidence
  as the warning: the font itself says which digit each shape is.
- **Your page 7:** all 15 numbers now match the page - 416, 411, 200, 189,
  94.5%, 100% were wrong before.
- **Checked independently, as we said it must be:** Windows' text
  recognition read the changed numbers straight off the page images, in
  every file the fix touches (20 files). It agreed with the new numbers
  434 times and the old ones once - and that one, when I looked, was the
  recognition misreading. A dozen other odd cases, looked at: the new
  number right every time.
- **Nothing lost:** still 100%; the other scores the same, one thesis
  slightly better. Word for word, the fix changes only numbers (and one
  web address ending, a little closer to the page than before).
- **The warning:** on the 14 files it used to name, it now has nothing
  left to say. It stays switched on for files we have not seen.
- **Your own chapters:** no change - Arabic-style digits (٢ for a typed 2)
  are left alone.
- **Still wrong on that page:** brackets come out as ص, and a few words
  are cut short. Those are separate faults.
- **Next:** check the 12 held-out theses, then tables. And please back up
  the corpus folder (five minutes, FLAGS 5).

### 1 Oct — the 12 held-out theses

- **Backup:** you copied the corpus out of the VM. Done.
- **The held-out check.** These are the 12 theses I have never tuned on -
  the honest test of whether our work holds up on new files. It does, and
  better than on the files I worked on: words in order 97.4% (vs 94.4%),
  words on the right page 85.1% (vs 73.8%). No sign that I was just
  fitting the files I could see.
- **It caught two lost words**, which our "nothing lost" check can only
  find on files it is run on:
  - الركوع came out as "الرك عو" - a small piece of the word, labelled on
    its own in the PDF, was read backwards. Fixed.
  - ولله came out as "وهلل" - the PDF stores the word backwards; we turn
    such words round, but missed it with و stuck in front. Fixed.
  - The fix for the first one also brought back a title-page line that
    was missing in another thesis ("الأستاذ الدكتور"), though in pieces.
  - My first version of that fix broke a table's "لا" (No) and wrote its
    header twice; I caught it comparing the words with the fix on and off,
    and fixed it before it went anywhere.
- **Nothing lost on the held-out set:** 99.9%. What is left is one thesis
  whose own title text is garbled in the PDF (ours is right) and the
  Quran-font codes we already knew about. The 25 working theses and your
  chapters: unchanged, 100%.
- **Not looked into yet:** one held-out thesis reads 48% wrong on the
  page check, another spills from 13 pages to 15.
- **Next:** your call - tables (you parked them), or those two files.

### 22 Oct — plain Arabic text, measured exactly

- **Why:** you set the first usable version as "pure Arabic text, no
  tables or pictures, pages the same - 99%". Only 1 of the 37 theses has
  no table or picture, so they could not measure it.
- **What I made:** a test set of our own. 40 Arabic documents written by
  Word from public Arabic Wikipedia text, with different fonts, sizes,
  spacing, footnotes and page numbers, saved as PDF. Because we have the
  Word file each one came from, the answer is known exactly - nobody's
  private work in it, and it can be shared when the project goes public.
- **Where we stand on it now:**
  - pages matching: **99.6%** (39 of 40 files, every page the same);
  - words exactly right: **99.35%**;
  - nothing lost: 100%.
- **What it found** that our old scores could not see (they compared PDF
  with PDF, and Word's PDF makes the same mistakes on both sides):
  numbers glued to the word before them (عام2015), short words turned
  backwards (يب for بي, مث for ثم), a vowel mark doubled, and words split
  by a piece of a letter that the PDF calls a space (الروس ي). All four
  fixed; your theses and chapters scored exactly as before.
- **Left:** a vowel mark at the end of a line jumping to the next line's
  word, some split words, and Hijri years (1427هـ came out 1427 هـ) - the
  one page that still does not match.
- **Next:** the check that refuses PDFs with tables or pictures (so the
  app only takes what it can do), then the small window and installer.
- **Pushed** to GitHub the same day.
- **Example, and an honest catch:** the picture I showed you (plain009
  page 4) has the same words on the page, but it does not look the same:
  the page number moved from the middle to the corner (that happens in
  every file), the text starts a little lower, and this one file came out
  one size smaller. Our "pages matching" number only checks the words,
  so it missed this. Written down as FLAGS 36.
- **Next:** your call - the refusal check for tables and pictures first,
  or making the pages look the same first (page numbers, top margin).


### 22 Oct (later) — items 2, 3 and 5 done; item 1 cancelled

- **Item 1 cancelled** (your call): files with tables, pictures or columns
  are converted as well as it can, not turned away. Scans are still
  refused.
- **Item 3, the plain set's leftover text faults.** Word sometimes stores a
  space or a vowel mark away from where it draws it - a line's last
  tanween at the start of the line, with a space left inside the word
  where it belonged (س مح for سُمح). They now go back where the page draws
  them. Hijri years come out "1427هـ/ 2006م" (4 of 5 in the file that has
  them).
  - words exactly right: 99.35% -> **99.71%**;
  - pages matching: 99.6% -> **100%**;
  - nothing lost: 100%.
- **Item 5, pages that look the same.** I built a check for what "pages
  matching" could not see: where the page number sits, where the text
  starts, the text size. Then fixed what it found:
  - page numbers in the right place: 6.5% -> **97%** of pages (our left
    margin was measured wrong, so the middle of the page was off);
  - text starting where the original's does: 36% -> **93%** of pages
    (Word puts the extra line space above the text in our files, below it
    in yours - the converter now measures the gap and moves the text up);
  - plain009 no longer comes out a size smaller (we added a first-line
    indent the original did not have; the indent is now measured).
- **Item 2, the window and the installer.** A small window: choose a PDF,
  press Convert, the Word file appears beside it, with the same warnings
  as before as pop-ups, in Arabic with English underneath. And one
  installer, `installer\Output\Qirtas-Setup.exe` (44MB), which warns if
  Word is missing. I tested that the installed program converts a file
  exactly as the code does; I have not tried installing it on another
  computer - worth you trying.
- **Your theses:** nothing lost still 100% on every file. The other scores
  barely moved (right page 73.8 -> 74.1%).
- **Honest catches:** a few new small faults on two theses (a number
  joined to the letter before it, ج٣٨ for ج ٣٨; a doubled vowel mark), and
  الثالثة coming out لاثلاثة in three plain files. Listed in TASKS.
- **Waiting on you:** item 4 - ten or twenty real plain PDFs from people.
  Send them, or tell me I may download public ones.
- **Pushed** to GitHub the same day.
