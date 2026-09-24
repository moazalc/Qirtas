# Qirtas

Converting Arabic PDFs back into editable Word files.

## The problem, and why it is worth solving

People export a Word document to PDF, lose the Word file, and later need to
edit it. Converters mangle Arabic, and **Adobe Acrobat does not support
right-to-left PDF→Word export at all** — so buying the expensive tool does not
help either. The target user is an ordinary person, not a developer.

**Getting Arabic text *out* of a PDF is already a solved problem.** That was
measured across 105 real files: plain PyMuPDF extraction recovers clean,
correctly ordered Arabic every time. Do not rebuild it.

**The gap is writing a correct right-to-left `.docx`.** Every open-source tool
stops at Markdown; `pdf2docx` marked RTL won't-fix; `html-to-docx` silently
strips every RTL marker. That last mile is the project.

## Shape of the code

    PDF → reader → description → writer → DOCX
                                    ↑
                          harness scores the result

- `convert/reader.py` — works out what is in the PDF. Two strategies: the PDF's
  own hidden structure labels, and geometry. Runs both, keeps whichever
  recovered more. **Measure, don't predict** — two theories about which
  strategy a file needs were tested and both were wrong.
- `convert/model.py` — a plain ordered description. Knows nothing about PDF or
  Word.
- `convert/writer.py` — the only part that knows Word. All right-to-left
  handling lives here.
- `convert/fit.py` — converts, renders, sees which pages actually spilled,
  shrinks those, repeats.
- `harness/` — scoring. More than half the work has been here.

## How to work in this repo

**Write findings into the right file. Do not create new ones.**

| What | Goes in |
|---|---|
| Design, history, why something was done, measurement traps | `PLAN.md` |
| Work to be done, in priority order | `TASKS.md` |
| Open risks, things needing a decision, things that could make the work wrong | `FLAGS.md` |
| Where the project stands, the timeline, what is finished - plain language, updated after every task (Moaz, 2026-09-23) | `PROGRESS.md` |

`README.md` is setup and commands. `RESEARCH.md` is what was established about
the problem space — read it before investigating anything; do not redo it.

Start a fresh session by reading `TASKS.md`, then `FLAGS.md`.

## The three scores are not interchangeable

    nothing lost   did any text go missing? Order ignored by design. THE GATE.
    words in order did the wording survive in sequence?
    right page     did each page's words land on the matching page?
                   Unrelated documents score ~13%, so that is the floor.

Read the structure score (tables and pictures kept) alongside `right page` — on
its own it is blind to non-text content.

## Rules that were learned the hard way

**Nothing lost is a hard gate.** No change ships while a word is being dropped.
It held at 100% across the old dev and regression sets. On the thesis corpus
(since 2026-09-24) it reads 99.4%: five theses, where the PDF's own hidden text
looks at fault — `FLAGS.md` 29. Settle that before trusting the gate there.

**When a number moves, check the instrument first.** Seven bugs so far have
been in the measuring tools, not the converter. Three times a reported
improvement was not real. Examples: LibreOffice reverses Arabic letter pairs
when rendering; Word stores `&` escaped so every ampersand read as lost text;
the "looks right" score could not distinguish our output from an unrelated
Arabic document.

**Verify on files you did not tune on.** Tuning on the 8 thesis files produced
64.7% there against 22.7% on unseen ones. The corpus is split; a holdout exists
for this reason. It is currently paused at Moaz's request.

**A score is only comparable to one taken the same way.** Both the corpus and
the rendering environment have been caught drifting. Run `python -m harness.env`
before trusting any number.

**Word is the only renderer.** Since 2026-09-21, at Moaz's call. LibreOffice
has been removed; do not bring it back as a default or a fallback. Scores taken
under it are not comparable to Word ones.

**Render a page and look at it.** The largest known correctness problem in this
project — a third of the corpus producing unreadable output while scoring 99% —
was found by looking, not by any metric.

## Talking to Moaz

Plain language, no jargon. Explain a term the first time or do not use it.
Lead with what is happening and why it matters, not with data. Always say
plainly what comes next.

Be straight about what does not work. He has twice caught real methodological
problems — overfitting to his own files, and forcing right-to-left onto English
content. Surface the uncomfortable finding rather than the clean number.

## Things not to do

- Do not rebuild Arabic text extraction. It works.
- Do not route through HTML. It discards the right-to-left information, which
  is the one thing already correct.
- Do not restore the corpus with a fresh `--n 120` search. Use
  `--from-manifest`. A different file set silently invalidates every recorded
  number.
- Do not commit `corpus/` or `out/`. The thesis PDFs are someone else's
  unpublished work; `out/` holds files past GitHub's 100MB limit.
- Do not handle scanned PDFs. Out of scope — detect and refuse.
