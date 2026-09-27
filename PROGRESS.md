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
