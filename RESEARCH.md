# Qirtas — project overview for research write-up

A plain-language account of what this project does, how it is built, what was
discovered along the way, and where it might become a paper.

Written 2026-09-17. Numbers in the "Results" section come from the checker in
this repository; see "How to reproduce" at the end.

---

## 1. The problem

Someone writes a document in Arabic in Microsoft Word. They export it to PDF to
send it to someone. Later they lose the Word file and only have the PDF. Now
they want to edit it again.

Converting a PDF back into an editable Word file is a well-known task, and there
are many tools for it. **They all mangle Arabic.** That is the gap this project
addresses.

### Why Arabic specifically is hard

A PDF is not a document in the way a Word file is. A Word file says "this is a
paragraph, it reads right-to-left, it is set in 12pt Simplified Arabic." A PDF
says "draw this shape at x=412, y=680; draw this shape at x=395, y=680." It is
closer to a printout than to a document. Converting back means reconstructing
meaning that was thrown away when the PDF was made.

Arabic makes that reconstruction harder in three specific ways:

**1. Direction is not recorded.** Arabic reads right-to-left. A PDF only stores
where each shape sits on the page, not which direction the text flows. When you
build a Word file you must state the direction explicitly. If you do not, the
text can look correct in a viewer and then fall apart the moment someone edits
it — the cursor moves the wrong way, typing inserts in the wrong place, and
punctuation jumps to the wrong end of the line.

**2. Letters change shape, and PDFs often store the shape, not the letter.**
Arabic letters look different depending on their neighbours — the same letter
has an isolated, initial, medial and final form. Word knows the real letter and
picks the shape when it draws. A PDF frequently stores only the drawn shape. Pull
those out and you get a string that *looks* like Arabic but is not real text:
it cannot be searched, spell-checked, or edited. In Unicode terms these are
"presentation forms," and their presence is a reliable signal of corruption.

**3. Order can be reversed.** PDFs store shapes in the order they were painted.
For right-to-left text that order is often the reverse of the reading order.
Extract naively and `المستخدم` comes out as `مدختسملا`.

### What the existing tools actually do

These were tested, not assumed:

| Tool | Result |
|---|---|
| Adobe Acrobat | Does not support right-to-left PDF-to-Word export at all |
| `pdf2docx` | Right-to-left support marked won't-fix by its maintainers |
| `html-to-docx` | Silently strips every right-to-left marker — verified: zero occurrences of `w:bidi`, `w:rtl`, `bidiVisual` in its output |

So a paid tool, an open-source tool, and a library-level tool all fail, in three
different ways. The gap is real.

---

## 2. Is there any machine learning in this project?

**No. None at all.** There is no trained model, no neural network, no statistical
classifier, no embeddings, and no training data in the machine-learning sense.
The entire codebase was searched for every major ML library (`scikit-learn`,
`torch`, `tensorflow`, `keras`, `transformers`, `onnx`, `xgboost`, `lightgbm`)
and for the words `train`, `classifier`, `neural`, and `embedding`. Zero hits.

Every decision in the system is a hand-written rule, a measurement taken off the
page, or a comparison between two deterministic methods.

### Things that might look like machine learning but are not

This distinction matters, because several parts of the project *borrow the
vocabulary* of machine learning without using any of its machinery.

**`numpy` is in the dependency list.** It is used to count dark pixels in a
rendered page image — to measure how tall a line of text is and how far apart
lines sit. That is array arithmetic, not learning.

**"Measure, don't predict" route selection.** The system runs two different
text-extraction methods on every file and keeps whichever recovered more Arabic.
This is a competition between two fixed algorithms decided by counting
characters. There is no model and nothing is learned — the same file always
produces the same choice.

**Medians for margins and font size.** The reader takes the median of text-block
edges to find the page margins. That is descriptive statistics, the same
arithmetic a spreadsheet does. No inference, no fitted parameters.

**The feedback loop in `convert/fit.py`.** This is the part most likely to be
mistaken for learning, so it is worth being precise. The system converts the
file, renders the result, checks which pages overflowed, shrinks only those
pages slightly, and tries again — up to four rounds. This is closed-loop
correction, the same idea as a thermostat or Newton's method: measure the error,
correct, measure again. Crucially, **nothing persists between files.** Each
document is solved from scratch. No parameters carry over, so nothing is being
learned in any meaningful sense.

**Heading detection.** This sounds like classification, and in a machine-learning
system it would be. Here it is a hand-written cascade of three rules tried in
order (see §4).

**The dev/holdout split.** This is the one place where machine-learning
*methodology* genuinely appears — see §7. But it is the evaluation discipline
being borrowed, not the modelling.

### Why using no machine learning is a defensible position

This is worth arguing explicitly rather than treating as an omission:

1. **Much of the task is deterministic.** A PDF's hidden structure tree either
   contains a label saying "this is a heading" or it does not. Training a model
   to guess at a label that is already written down would be worse than reading it.

2. **There is no training data.** A supervised model would need pairs of
   (Arabic PDF, correct Word file). No such corpus exists. Building one would
   mean hand-authoring hundreds of documents, which is a larger project than
   this one.

3. **Every rule is explainable and debuggable.** When a file converts badly you
   can point at the specific line responsible and fix it. A model gives a wrong
   answer with no recourse and no way to fix one file without disturbing others.

4. **The observed failures were mechanical, not perceptual.** Wrong font metrics,
   a missing `w:tblGrid` element, page-break arithmetic being off by one line.
   None of these are pattern-recognition problems. They are bugs with correct
   answers.

### Where machine learning could legitimately help (future work)

- **Heading detection** is the weakest rule-based component. It currently falls
  back to a keyword list of Arabic section words (المبحث, الفصل, المطلب …), which
  will not generalise to documents that phrase their headings differently. A
  small classifier over features that are already being extracted — font size
  relative to body, boldness, line length, position, whether the line ends in a
  full stop — would likely generalise better and could be trained on the 44% of
  wild files that *do* carry real heading labels. That is a genuinely available
  training signal, which makes it the strongest candidate.
- **Reading order** for complex multi-column layouts.
- **Distinguishing a real table from merely aligned text.**
- **OCR** for scanned PDFs, which are currently entirely out of scope — the tool
  assumes digital-born PDFs that contain real text.

---

## 3. The central discovery

This is the project's first genuine research finding.

**The text in an Arabic PDF can live in either of two places, and which one works
varies file by file.**

1. **The visible glyphs** — the shapes actually painted on the page. This is
   where every extraction tool looks first.
2. **A hidden accessibility layer** — Word writes an invisible parallel copy of
   the document for screen readers, called the *tagged structure tree*. It marks
   regions as paragraph, heading, list item or footnote, and attaches
   `/ActualText` labels saying what a run of shapes actually means.

The measured split:

| Corpus | Glyph extraction works? |
|---|---|
| 6 thesis chapters (the original problem files) | **0–8% recovered.** The text is effectively not in the glyphs at all. It exists only in the hidden layer. |
| 88 Arabic PDFs from Zenodo (open-access academic) | **88/88 work.** None need the hidden layer. |

### Two hypotheses were tested and both failed

The obvious next question is: what predicts which kind of file you have? If you
could tell in advance, you would only need to run one method.

**Hypothesis 1 — it depends on the Word version.** Disproved. Word 2010 files in
the wild corpus extract fine, while Word 2016 and 2019 files sometimes carry
`ActualText` and sometimes do not.

**Hypothesis 2 — it depends on a font signature** (specifically: a font with no
`ToUnicode` mapping combined with WinAnsi or non-embedded encoding, which should
make glyphs undecodable). Disproved. 30 of 40 wild files carry exactly that
signature and still extract perfectly — because in those files the problematic
font is carrying Latin digits and page numbers, not the Arabic body text.

**Conclusion: do not predict which method works. Run both and measure.**

This is a small but real methodological result, and the two negative results are
part of it. It is the kind of finding that is useful to publish precisely because
the intuitive approaches fail.

---

## 4. How the system is built

    PDF  →  reader  →  description  →  writer  →  DOCX
                                          ↑
                              checker scores the result

Four parts, deliberately separated so each can be tested and improved alone. The
whole system is about 2,500 lines of Python.

### The description (`convert/model.py`, 64 lines)

The interface between the two halves, and deliberately the dumbest file in the
project. It knows nothing about PDFs and nothing about Word.

A document is an ordered list of **blocks**. A block is one thing on a page — a
paragraph, a heading, a list item, a footnote, an image, or a table — plus what
is known about it: its text, page number, font size, boldness, position on the
page, and for tables its rows and column widths.

Keeping this layer ignorant of both formats is what allows the reader and writer
to be worked on independently.

### The reader (`convert/reader.py`, ~700 lines — the largest component)

Works out what is in the PDF. It looks in two completely different ways, because
neither works everywhere.

**Route A — tags.** Walk the PDF's hidden structure tree. Labels like `/P`,
`/H1`, `/LI`, `/Footnote` say directly what each region is, and `/ActualText`
gives the real text. Exact where present, which is about 76% of files.

**Route B — geometry.** Ignore labels entirely. Look at where text sits on the
page and group it by position, using font size and boldness where those can be
read.

Both run on every file. Then:

**Choosing a winner.** Keep whichever recovered more Arabic — with one important
exception. If the tag route recovered at least 97% of what the geometry route
did, prefer the tags anyway. This rule exists because of a specific observed
failure: one file picked geometry by a margin of 0.6% and lost every footnote and
list item in the process. A rounding-error win on quantity was a real loss on
structure.

**Putting back what the winner missed.** Whatever the losing route found but the
winner did not gets added back in. This exists because preferring the tag route
once cost a 110-character Quranic verse that only the geometry route had found.
Losing text is treated as the one unacceptable failure, so rather than trading
structure against completeness, the system takes the structure from the winner
and restores the missing text from the loser. Restored text is placed on the page
it actually belongs to, so page alignment is not disturbed.

#### Notable problems solved inside the reader

Each of these is a documented failure followed by a fix. Collectively they are
probably the most useful part of the project for anyone building something
similar, and they make a good "lessons learned" section in a paper.

**Lines are not paragraphs.** The PDF hands back one entry per *line* as often as
per paragraph — 290 entries for an 11-page document. Emitting each as its own
Word paragraph forced a line break after every line, so pages held half the text
they should and page counts doubled. Fix: merge two entries when they sit
directly under one another at normal line spacing, share a font size and weight,
the upper one does not end like a finished sentence, and the lower one is not
much narrower (which would indicate the last line of a paragraph).

**Headings are found three ways, best first.** (1) The PDF's own heading labels,
where present. (2) Font size relative to the document's body size. (3) The shape
of the line — short, does not end in a full stop, and either starts with a known
Arabic section word (المبحث, الفصل, المطلب, المقدمة, الخاتمة …) or ends with a
colon. The third rule is needed because *none* of the six sample files use Word's
heading styles — their author simply made text bigger by hand — whereas 44% of
wild files do carry real heading labels.

**Margins and font size are measured, not assumed.** Guessing one-inch margins
and 12pt put the rebuilt pages visibly out of step with the originals. Both are
measurable, so they are measured. Margins come from the *median* of text-block
edges rather than the extremes, because page numbers and running headers sit
further out than the body and would drag the margins wrong. Font sizes are first
filtered to a believable 6–30pt range, because undecodable decorative glyphs
report sizes like 90pt.

**Measuring font size from ink when glyphs will not decode.** On the hardest
files the Arabic glyphs cannot be decoded at all, so the only text spans
reporting a size are Latin digits and decorative marks — which gave 18pt for 12pt
body text. The fix renders the page to a greyscale image, finds the horizontal
bands that contain ink, and measures two things: the height of an inked band
(which gives glyph size directly) and the distance between consecutive bands
(which gives line spacing). Ink does not care whether a glyph decodes. Measuring
the band height was necessary because spacing alone is ambiguous — it cannot
distinguish a large font from a generously spaced small one.

**Using the document's own font.** Setting everything in Arial made the text
noticeably wider than the original, because Arial's Arabic is wide while fonts
like Sakkal Majalla and Simplified Arabic are not. That stretched every page. The
reader now detects the document's actual Arabic font, stripping the six-letter
subset prefixes and style suffixes that PDFs add to font names.

**Ignoring Word's pixel litter.** One page carried 276 images, of which 275 were
2×2 pixels stretched into thin bars — an artefact of how Word exports. Filtering
on both the stored pixel size and the size actually drawn on the page leaves only
the real figures.

**Un-reversing table cells.** The table finder does not apply the same
logical-ordering step the main text extractor does, so Arabic cells come out
backwards. Writing that into a Word file would be actual corruption. The fix
takes a probe slice from the *middle* of the cell — the edges pick up stray
characters that break an exact match — and checks it against the page's correctly
ordered text, flipping the cell only if the reversed version is the one that
matches.

**Rendering vector drawings.** The molecular structures in one paper are not
images at all; they are vector line art. Nothing extracts them, so the cells came
out blank. Cells that contain no text but a significant amount of drawing are
rendered to an image and carried across. Only text-free cells qualify, so this
can never turn a text cell into a picture.

**Removing duplicated table text.** A table's words are also picked up as
ordinary page text. Without explicitly dropping them, the document says
everything twice.

### The writer (`convert/writer.py`, 518 lines)

The only part that knows about Word. All the right-to-left handling lives here.

Word needs **three separate things** set for Arabic to be genuinely correct, and
the tested tools each forget at least one:

1. `w:bidi` on the paragraph — sets paragraph direction.
2. `w:rtl` on the run — sets the direction of the actual text run.
3. `w:rFonts w:cs` and `w:szCs` — the *complex-script* font and the
   *complex-script font size*. In Word these are separate properties from the
   ordinary font and size. Miss them and Arabic silently renders in a fallback
   face at the wrong size, even though the direction is correct.

Tables additionally need `w:bidiVisual` so that column one sits on the right.

**Direction is a property of the content, not the document.** Everything used to
be forced right-to-left, which mirrored English tables and flipped Latin
paragraphs that were never right-to-left. Each block now has its direction
decided by counting right-to-left against left-to-right characters in its own
text. This matters for real Arabic academic documents, which routinely contain
English abstracts, Latin citations and bilingual tables.

**Other notable fixes:**

- *Column widths.* Setting cell widths alone did nothing — twice. Word ignores
  them unless the table *also* declares a fixed layout *and* carries a `w:tblGrid`
  element stating each column's width. Without both, columns are shared out
  evenly and long cells wrap one word per line, turning a compact table into a
  tall ladder.
- *Picture placement.* Stacking every picture at the foot of its page added
  height the original never had — on one chapter that pushed 25 pages out to 32.
  Text read from the tag tree carries no coordinates, but pictures do, so each
  picture is inserted at the same fraction down the page it originally occupied.
- *Page breaks.* Break *before* a paragraph rather than inserting an empty
  paragraph to push content down. The empty paragraph consumed a line on every
  page, and the accumulated overflow pushed pagination steadily out of step.
- *Running headers.* A decoration that sits outside the text column and recurs
  on at least half the pages is a running header, not content. Emitted as
  ordinary paragraphs, two such decorations stole 96pt from every page's 735pt
  of usable height. They are now grouped by content hash and written once into
  the Word header, where Word redraws them per page at no cost to the body.

### Footnotes (`convert/footnotes.py`, 121 lines)

python-docx cannot write footnotes, so the part is hand-built. Three things must
agree or Word rejects the file outright: `word/footnotes.xml`, an `Override` in
`[Content_Types].xml` declaring its type, and a relationship in
`word/_rels/document.xml.rels`. The archive is rebuilt beside the original and
moved over it only once complete, so a crash leaves a valid .docx rather than a
truncated one.

**Anchoring is the interesting part.** A footnote is only a footnote if it is
attached to the right place in the text, and nothing in the PDF states the
correspondence. The documents supply it themselves: the note carries its own
number (`1- انظر`) and the body carries the matching marker inline
(`ابن مجاهد(2)`). Matching the two anchors **373 of 399 notes (93.5%)**, with
references and notes matching exactly on every file. The remaining 26 have no
findable marker and are deliberately left as plain
paragraphs — a footnote attached to the wrong sentence is worse than one left
in the flow.

One default had to be overridden: both Word and LibreOffice number footnotes
continuously, so a thesis that restarts at 1 on every page had page 3's first
note renumbered 5. `w:numRestart eachPage` restores the original convention.

### The layout feedback loop (`convert/fit.py`, 66 lines)

A page break is placed before each original page's content. So if a page
overflows by a single line it becomes two pages — and because every subsequent
page inherits the error, page counts swelled by roughly half.

Every attempt to *predict* the correct size from the PDF failed, because Word and
LibreOffice shape and wrap Arabic differently than whatever renderer produced the
original.

So the system stops predicting: convert, render, detect which pages actually
spilled onto two pages, shrink only those pages by 6%, and repeat. Up to four
rounds, never shrinking below 70% of the measured size.

This is the second methodological idea worth writing up: **replacing predictive
layout estimation with closed-loop empirical correction.** It works because
rendering is cheap and the error is directly observable.

---

## 5. The checker — how do you grade this with no answer key?

This is the third and arguably most interesting contribution.

The hard problem: to score a PDF-to-Word converter you would normally compare
against the correct Word file. **But there is no correct Word file.** The entire
premise of the tool is that the user lost it. A conventional evaluation setup is
unavailable.

**The solution is a round trip.** Convert the PDF to Word, then render that Word
file back to PDF with LibreOffice, and compare the result against the original
PDF. If the reconstruction is faithful, re-printing it should closely resemble
where it started. The original PDF becomes its own reference.

Four separate scores are produced, because the system fails in ways that are
independent of each other and a single number would hide them.

**1. `text_score` — did the words survive, in the right order?**

Read directly from the Word file's XML, *never* through LibreOffice. This is
important: LibreOffice's PDF export reverses certain Arabic letter pairs
(لا becomes ال), so scoring a rendered PDF would measure LibreOffice's bug rather
than the converter's. Rendering is used only for the visual scores, where images
are compared and the bug does not matter.

The algorithm splits the original into sentences, locates each one inside the
output, and then finds the longest run of them that appears in *increasing*
order — a longest-increasing-subsequence computed by patience sorting, O(n log n).
Substring lookup tolerates damage around a sentence's edges; the ordering test is
what distinguishes text that *moved* from text that *stayed put*.

Two earlier attempts failed, which is instructive:
- *Character-level comparison* was quadratic. On a 72-page document it sat at 97%
  of one core for an hour without finishing.
- *Hashing whole sentences* was fast but brittle — a single changed character
  discarded an entire sentence, dragging genuinely good results down to 7%.

**2. `page_score` — did each page's content land on the matching page?**

Compared as word counts per page. This metric **replaced** an earlier ink-density
comparison, and the reason is the most important methodological lesson in the
project: the ink-density metric was validated against a negative control and
failed. The reconstruction scored 29% against its own original, while *unrelated*
Arabic documents averaged 28%. The metric had essentially no discriminating
power, because ink density only measures "there is a block of text here," which is
true of every text document ever written.

Words were chosen over characters for the same reason: any two Arabic texts share
the same alphabet, so unrelated documents scored 48% on characters. Words are
distinctive. Unrelated documents score about 13% on the word-based metric, which
gives the score a meaningful floor.

**3. `ink_score` — does the page still look the same?**

Compares ink density on a coarse 48×48 grid. Exact pixel overlap is unreachable
even when the layout is perfectly correct, because Word and LibreOffice break
Arabic lines at slightly different points, so a correct page can score near zero
on strict pixel comparison. The coarse grid asks the useful question instead: is
there text in roughly the same places, in roughly the same amounts?

**4. `structure_score` — were tables and images kept?**

Added because the text scores counted only words, so a chemistry page that lost
its table *and* both molecular diagrams still scored 86%. Nothing was watching
the non-text parts of the document.

### Validation of the checker itself

The checker was sanity-checked against controls, which is what makes the numbers
trustworthy:

| Test | text | ink |
|---|---|---|
| A PDF compared against itself | 1.00 | 1.00 |
| A PDF compared against an unrelated PDF | 0.02 | 0.07 |
| Unrelated documents, page score | — | ~13% |

### The loss gate (`harness/loss.py`)

A separate, stricter check with one question: **was any text dropped?** Order is
deliberately ignored — that is the page score's job. This asks only whether every
sentence of the original appears *somewhere* in the output.

It is treated as a hard gate: the command exits with an error if the worst file
falls below 99.9%. The project's stated rule is that nothing ships while a word
is being lost. Silently dropping a sentence is considered worse than laying a
page out badly, because a user can see bad layout and cannot see missing text.

---

## 6. A note on the two scores that are *not* about correctness

`ink_score` is low even on good output (see Results) and this is expected rather
than alarming. The rebuilt PDFs are rendered by LibreOffice, which lays out
Arabic differently from Word. Both visual scores should be read as progress
meters, not grades. The text score and the loss gate are the measures of
correctness.

---

## 7. Evaluation methodology

This is where machine-learning *practice* appears, despite there being no model.

**The corpus.** Two sets, deliberately different in character:
- 6 unpublished Arabic thesis chapters, 1 Arabic Canva poster, 1 Turkish
  LibreOffice document as a left-to-right control. These are the hard cases where
  the text lives only in the hidden layer. They are used as a regression set.
- ~225 open-access Arabic PDFs downloaded from Zenodo, reproducible with a script
  in the repository. These represent ordinary well-produced documents.

**A stated corpus caveat, which belongs in any paper:** Zenodo is academic
publishing and its documents may be better-produced than the ordinary office
documents this tool actually targets. The wild corpus probably makes the problem
look easier than it is in practice.

**Tuning set and holdout set.** Early on, tuning and judging on the same files
produced a three-fold gap between them — 65% against 23%. That was overfitting
rather than progress, and a holdout set is the only way to notice that from the
inside. So the wild corpus is split, with 40% held out and never opened during
development.

Two details make the split sound:
- Assignment is by a SHA-256 hash of the filename, so a file's assignment never
  drifts between runs and cannot be accidentally reshuffled into a favourable
  split.
- It is stratified by producer — Word 2010, Word 2016, LibreOffice, TeX, Canva,
  Adobe and so on — so both halves see the same spread of tools.

This is textbook train/test discipline applied to a rule-based system. For a
paper this is a good point to make explicitly: **the project adopts machine
learning's evaluation methodology while deliberately using none of its
modelling.** Hand-written rules can be overfitted to a development set just as
surely as a trained model can, and the same safeguard applies.

---

## 8. Results

### Round-trip scores

Measured on this machine with LibreOffice 26.2.5 and Arabic font substitutes
installed. `text` = words survived in order; `pages@` = words landed on the
matching page; `look` = coarse visual similarity.

**Small control files:**

| File | text | pages@ | look | pages | words |
|---|---|---|---|---|---|
| `ödev.pdf` (Turkish, LTR control) | 100.0% | 100.0% | 47.8% | 1 → 1 | 182 → 182 |
| `عن بعد.pdf` (short Arabic) | 100.0% | 91.7% | 0.0% | 1 → 1 | 13 → 13 |

The 0.0% look score on a file with 13 words is a measurement artefact of the
coarse grid on a nearly empty page, not a conversion failure — the text score and
word count are both perfect.

**Full regression set (the 6 thesis chapters — the hard `ActualText` cases):**

| File | text | pages@ | pages | pictures |
|---|---|---|---|---|
| `الفصل الثاني- انفرادات القراء` | 99.8% | 58.4% | 20 → 20 | 44/44 |
| `الفصل الرابع - مبحث أول` | 98.6% | 56.6% | 24 → 24 | 64/64 |
| `الفصل الخامس المبحث الثالث` | 97.3% | 48.4% | 18 → 19 | 48/48 |
| `الفصل الخامس المبحث الأول` | 97.8% | 46.8% | 25 → 26 | 66/66 |
| `الفصل الثالث قراءات انفرادات` | 96.5% | 40.6% | 25 → 26 | 71/71 |
| `مقدمة البحث` | 100.0% | 31.0% | 16 → 17 | 21/21 |

Weighted by words over all eight files: **text 98.3%, pages@ 49.0%**, with the
loss gate at 100.00% and zero missing characters throughout. Raw output in
`out/roundtrip.json`, regenerated by the command in §9.

### A caution about this table, which is itself a result

The previous run of this table reported text 87.8% and pages@ 16.9%. Both
numbers moved for reasons that have nothing to do with the converter, and the
distinction matters more than the figures:

- **text 88% → 98% is the scorer being fixed, not the converter improving.**
  The sentence matcher recorded only the *first* occurrence of each sentence, so
  a document that repeats a phrase could not score 100% against itself. These
  theses repeat constantly — formulaic citations, honorifics after every name.
- **pictures were counted by stored file, not by placement.** Word stores one
  copy of a picture drawn forty times, so apparent losses like 62 → 13 were
  measuring deduplication. Counting `<a:blip>` placements — and multiplying a
  header picture by the page count, since Word draws it on every page — gives
  315/315. One genuine loss hid behind this: a bare DCT JPEG with no APP0/JFIF
  segment, which python-docx refuses to identify and the writer silently
  dropped.
- **pages@ 17% → 49% is the converter improving**, and it is the only column
  whose algorithm was untouched by either fix, so it is the only like-for-like
  comparison available.

This is worth reporting in the paper. Two of the three headline columns moved
because the measuring instrument was wrong, in a project whose central
methodological claim *is* the measuring instrument. It is direct evidence for
the discipline §5 and §7 argue for — negative controls, and a scorer with its
own test suite — rather than an embarrassment to be smoothed over.

### The holdout, opened once (2026-09-19)

Everything above was measured on files available during development. The
holdout set answers the only question that matters about a rule-based system:
**rules overfit as readily as models do**, and hand-tuning eight files until
they look good is indistinguishable from progress when you only ever look at
those eight.

Split by a hash of the filename, stratified by producer, sealed from the start
and opened once at the end. Reported by document class, because a newspaper
front page in five columns at 6.4pt and a book page are different problems and
their average is true of neither:

    class                  n    words   median   right page   median   >=95%
    dev  document         78    92.0%    99.0%       24.3%     17.2%     73%
    holdout document      61    92.2%    99.1%       29.4%     21.4%     77%
    dev  periodical       24    38.2%    32.8%       12.4%     10.0%      8%
    holdout periodical     9    42.0%    32.6%        8.8%      1.2%     11%

**The unseen files score equal or better than the development files on every
document-class statistic** — mean, median, and the share of files above 95%.
The rules did not merely fit the files they were written against.

Three qualifications belong in any paper that quotes these numbers.

**The hard gate appeared to break, and the gate turned out to be the thing that
was broken.** Three holdout files scored below 100% on text retention: 95.83%,
99.19% and 99.80%. Opening the worst of them showed it had lost nothing
whatsoever — a French keyword list on its title page had two phrases swapped,
and `harness/loss.py`, which documented itself as ignoring order, was in fact
testing each sentence as a contiguous substring. With only 24 scoreable
sentences in that document, one false flag cost 4.17% and made it the
worst-scoring file in the corpus.

After the fix, one file is genuinely affected in any meaningful sense:
`z21312494.pdf` drops nine words — author names and affiliations — across about
ten of its 432 pages. The other real case is a two-character fragment.

**The file that looked worst had lost nothing; the file that looked best was
the only one dropping words.** This is the more interesting result than either
number, and it generalises beyond this project: an evaluation metric that
inverts the ranking of its own failures will send you to fix the wrong thing,
and no amount of staring at the aggregate reveals it. It was found by opening
the worst-scoring file and reading what it had supposedly lost.

Diagnosing it took three instruments, and the first two failed the same way —
both measured contiguity and called it presence. Fixed-size chunks straddle the
seam where order changed; sliding n-grams lose N-1 grams per seam, a third of
them on a 49-character sentence, so a pure reordering scored 69% and read as
partial loss. Only word-level presence, which has no length dependence and no
threshold, separated the cases.

**Periodicals score below chance.** At 8.8% on right-page placement they are
worse than the ~13% floor set by comparing two unrelated documents. This is a
genuine scope boundary, found by measurement rather than assumed.

**The first run silently dropped three files, and that is a methodological
finding in its own right.** They crashed on control characters XML cannot
represent; the harness caught the exception per file so one bad document could
not cost a whole run, and then printed a mean over the survivors without
mentioning the absence. The reported average was quietly conditioned on not
crashing. After the fix (`17d7a25`) the set runs 70 files with nothing dropped.

Both runs are kept and reported together rather than the better one being
quoted. Looking at a holdout twice is only dishonest if you *select* between
the results. On the 68 files common to both runs the fix changed nothing —
words 85.4% -> 85.4%, right page 26.5% -> 26.5% — which is the evidence that it
only ever touched characters that would otherwise have raised.

One file was excluded as unusable rather than repaired, and the reasoning is
the interesting part. `z22244578.pdf`'s fonts carry no usable ToUnicode map, so
extraction returns raw glyph indices and 117 of its 131 pages read as mojibake.
Stripping the illegal characters would have stopped the crash and let the file
into the corpus, where its nonsense would have been compared against an equally
nonsensical round-trip — very possibly scoring *well*, and raising the average
because a broken file had started to pass. The check that refuses it lives in
`harness/split.py` and judges the source document, not our output. It caught a
second file in the dev set that had never been run, which is the evidence it
detects a class rather than the one file that happened to crash.

### Baseline for comparison

The first version (`convert/v0.py`) dumps extracted text into a right-to-left
Word file with no structure at all. It exists specifically to be the baseline
every later version must beat:

    v0 baseline: average over 8 files — text 58.3%, ink 2.0%

Its known failures: every extracted line became its own paragraph, so page counts
exploded (20 pages became 201) and word counts inflated about 15% from split
fragments. No headings, bold, footnotes, tables or images.

Keeping this baseline in the repository and runnable is good practice and worth
mentioning in a paper — it makes every subsequent improvement measurable rather
than asserted.

---

## 9. How to reproduce

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Also required:
- **LibreOffice**, used only to render the produced `.docx` back to PDF for
  checking. The path is set as `SOFFICE` at the top of `harness/roundtrip.py`.
- **Arabic font substitutes.** These documents ask for Simplified Arabic,
  Traditional Arabic and Sakkal Majalla, which are Windows fonts. Without
  substitutes LibreOffice falls back to a wider face, text overflows, and the
  converter is blamed for a font problem. See `docs/fonts.md`. Installing them
  moved one file from 70% to 80% on the page score and fixed its page count
  exactly.

Commands:

    # convert one file
    .venv/bin/python -m convert.v1 input.pdf output.docx

    # score the converter against the hard regression set
    .venv/bin/python -m harness.roundtrip corpus/*.pdf --json out/roundtrip.json

    # the hard gate: did we drop any text?
    .venv/bin/python -m harness.loss corpus/*.pdf

    # the scorer's and converter's own tests - no framework, exit 1 on failure
    for t in text_score images headings inline footnotes pagination; do
        .venv/bin/python -m harness.test_$t || break
    done

    # evaluate on the wild corpus
    .venv/bin/python -m harness.split corpus/wild/*.pdf --write out/split.json
    .venv/bin/python -m harness.eval --n 30            # tuning set
    .venv/bin/python -m harness.eval --set holdout     # once, at the end

    # diagnostic: which extraction route works per file
    .venv/bin/python -m harness.run corpus/*.pdf --json out/report.json --dump out/text

    # structural survey of a corpus
    .venv/bin/python -m harness.survey corpus/wild/*.pdf --json out/survey.json

---

## 10. Framing this as a paper

### Candidate contributions

1. **A working right-to-left-correct PDF-to-DOCX pipeline.** The claim that no
   existing tool does this is verifiable and already verified against three
   tools at three different levels (commercial, open-source application,
   library). This is the practical contribution.

2. **Reference-free round-trip evaluation.** Scoring a document converter with no
   ground-truth target document, by rendering the output back to the input format
   and comparing. Validated with negative controls. This is the methodological
   contribution and is likely the most transferable — it applies to any
   format-conversion task where ground truth is unavailable, not just Arabic and
   not just PDF.

3. **The empirical finding that extraction route cannot be predicted from file
   metadata.** Two plausible hypotheses tested and disproved, with a measured
   0–8% versus 88/88 split between corpora. Supports a "run both and measure"
   design rule.

4. **Closed-loop layout correction** replacing predictive layout estimation.

### The negative results are a strength, not a gap

A paper drawn from this work can honestly report:
- Two disproved hypotheses about what predicts extraction difficulty (§3).
- One metric built, validated against a negative control, found to have no
  discriminating power, and discarded (ink density for page alignment, §5).
- Three failed text-scoring algorithms before one worked (§5).
- One documented instance of overfitting caught by a holdout set (§7).
- A sealed holdout opened once, reporting that the rules did generalise (§8) —
  and, in the same run, a guarantee that had held for the project's whole life
  breaking on unseen data.
- One instance of an evaluation harness quietly conditioning its own average on
  not crashing, and the reasoning for excluding an unreadable source document
  rather than letting a fix launder it into the corpus (§8).
- A fourth failed scoring algorithm, found late: the text-retention gate
  measured contiguity rather than presence, ranked its own failures backwards,
  and was caught only by opening the worst-scoring file and reading it (§8).

Work that reports what did not work is more credible, and in an engineering-
heavy paper these are often the most useful parts for other researchers.

### Honest limitations to state up front

- **Scanned PDFs are entirely out of scope.** The tool assumes digital-born PDFs
  containing real text. No OCR.
- **The wild corpus may be unrepresentative.** Zenodo is academic publishing;
  ordinary office documents are likely worse-produced.
- **The visual scores are rendered through LibreOffice**, which lays out Arabic
  differently from Word, so they are progress meters rather than grades.
- **Heading detection partly relies on an Arabic keyword list**, which will not
  generalise to documents that phrase headings differently.
- **The corpus is small** on the hard cases: six thesis chapters from a single
  author, which is one author's Word habits rather than a representative sample.
- **Inline bold and italic are implemented but effectively untested.** The
  writer emits one run per formatting span, but on six of the eight corpus files
  the PDF exposes almost no font information for Arabic glyphs — one page with
  1,305 Arabic characters yields 9 spans covering 4 of them. The feature is
  correct by unit test and inert in practice.
- **Page alignment is still under half.** 49% of words land on the matching
  page. Page *counts* are now near-exact, so what remains is line-break drift
  within correctly numbered pages — partly a genuine limitation, partly the
  renderer caveat above.
- **One file resists explanation.** `مقدمة البحث` moved only 26% → 31% where
  its siblings reached ~50%, with perfect text and picture scores. Reporting an
  undiagnosed outlier is better than quoting only the aggregate.
- **The "no text lost" gate is close to, but not, a guarantee.** One holdout
  file of 70 drops nine words from author-name and affiliation lines, and one
  drops a two-character fragment. It holds on all 102 development files. The
  claim was overstated for most of this project's life, and the first evidence
  against it was itself partly a measurement fault — which is the more useful
  cautionary detail.
- **Multi-column periodicals are out of the system's competence**, at 8.8%
  right-page placement against a ~13% chance floor. Detected but not handled.
- **`page_score` is not exactly reproducible.** The same 68 files run twice on
  identical code agreed on 66 and differed on two, by 0.07 and 0.54 points.
  LibreOffice rendering varies slightly between runs and the layout feedback
  loop reads its own rendered output, so a hairline difference can flip a
  shrink decision. Differences below about half a point are noise, which is
  finer than several comparisons quoted in this document.
