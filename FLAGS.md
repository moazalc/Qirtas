# Qirtas — open flags

Things that need a decision, or that could quietly make the work wrong. Not
tasks (see `TASKS.md`) and not history (see `PLAN.md`).

Each entry says what it is, why it matters, and what would close it.

---

## 1. A third of the corpus produces unreadable output, and the score says 99%

**Status: needs Moaz's decision. Largest known correctness problem.**

Some Arabic PDFs — typically LaTeX output — store their character stream
already reversed. The page displays perfectly; the text underneath runs
backwards. We reproduce it faithfully, Word applies right-to-left a second
time, and the result is unreadable.

**The scorer is structurally blind to it.** Our reversed output is compared
against the same reversed source, so they agree.

    z21889411.pdf    text 99.9%, pages 130 -> 130
                     called the best pagination result in the project
                     not one word of its output is readable

    56 of 172 corpus files (32.6%) are stored this way
    7 of 20 such holdout files score >=95% text, two exactly 100%

Detection is cheap and already prototyped: count common function words against
their reversals; the two cases separate by an order of magnitude.

**The decision is not technical.** Reorder the text and risk mangling documents
that are partly correct, or refuse such files the way `z22244578.pdf` is
refused. Either changes what Qirtas promises.

*Does not affect Moaz's 8 files* — they are the other kind.

**Closes when:** Moaz chooses reorder or refuse, and the scorer can tell the
two cases apart.

---

## 2. "Nothing lost 100%" has a known exception, parked in the holdout

**Status: true as stated, but easy to over-read.**

The gate reports 100% across the dev set and Moaz's 8 files. The one file with
verified real loss — `z21312494.pdf`, nine words of author names and
affiliations across ten of its 432 pages, scoring 99.80% — is in the **holdout
set**, which is paused at Moaz's request.

So the headline is a claim about what we measure, while a known loss sits in
what we don't. Say "100% on the dev and regression sets", not "100%".

**Closes when:** the nine words are recovered, or the holdout is unpaused and
the number is restated to include it.

---

## 3. Scores are not comparable between machines

**Status: instrumented, older numbers still suspect.**

The office machine scores **61.4%** on the regression set where `PLAN.md`
records **49%** for the same code. Almost certainly the Arabic font
substitutions — installed at the office, probably not at home. Without them
everything falls back to Noto Sans Arabic, which is wider, so text overflows
and the converter takes the blame.

Every eval run now prints its environment, warns when substitutions are
missing, and stores the fingerprint with the results. **Numbers recorded before
that carry no environment and cannot be compared to new ones.**

This is the same failure as the corpus drift — the thing being measured moved,
and nothing said so.

**Closes when:** the recorded baselines are re-measured on a known environment,
or explicitly marked as environment-unknown.

---

## 4. The only path back to the corpus has never been run

**Status: untested, single point of failure.**

`--from-manifest` re-downloads the 225 Zenodo records exactly. It has been
verified to parse and its CLI works. **It has never been run end-to-end against
Zenodo.**

It is now the only thing standing between a fresh checkout and 567MB of corpus,
and it should be tested *while the real corpus still exists to compare
against* — not at the moment it is needed.

**Closes when:** it is run on a machine that already has the corpus, and the
restored set matches.

---

## 5. `corpus/*.pdf` cannot be recovered by anything

**Status: needs a manual backup.**

Moaz's 8 thesis chapters, 37MB. Not in the repo — they are someone else's
unpublished work. No command restores them. They are the regression set;
without them there is no measuring the thing this project was built for.

**Closes when:** they are backed up somewhere Moaz controls.

---

## 6. We may be shrinking text to fix overflow that does not exist

**Status: unverifiable without Word. Could be actively harming output.**

`convert/fit.py` detects page overflow by rendering through LibreOffice, which
lacks the fonts these documents ask for and substitutes wider ones. Real Word
on Windows has those fonts.

So we may be reducing font sizes to fix spill that only exists in the measuring
tool — making the document worse for the user to make a number better.

**Closes when:** one regression run is rendered in real Word on Windows and the
overflow is confirmed or dismissed. Moaz has Windows and macOS with Word.

---

## 7. "Right page" is blind to tables and images

**Status: mitigated, not solved.**

A chemistry page that lost its table and both molecular diagrams scored **86%**,
because the score counts words and the words survived.

The structure score now counts tables and pictures, so the blindness is
*visible* — but only if read alongside. `right page` on its own still says
nothing about whether a page kept its non-text content.

**Closes when:** the structure counts are folded into the headline, or the
headline is never quoted alone.

---

## 8. Periodicals are detected, then averaged in anyway

**Status: produces a number true of neither class.**

`harness/doctype.py` tells periodicals from ordinary documents. The score then
averages both into one mean.

    ordinary documents   words 92.2%, right page 29.4%   n=61
    periodicals          words 42.0%, right page  8.8%   n=9

Periodicals score **below the ~13% chance floor** on right page. Mixing them in
drags the mean and hides both.

**Closes when:** multi-column layout is handled, or periodicals are put out of
scope in writing and excluded from the headline.

---

## 9. `fit.py` cannot rescue a picture-only page

**Status: known limitation, worked around.**

`_spilled()` matches output pages to original pages by shared words, and skips
originals that have none. A page of nothing but pictures is invisible to the
correction loop, so its fill factor has to be right on the first pass — which
is why `IMAGE_PAGE_FILL` is measured (0.95 spilled, 0.88 fitted) rather than
chosen.

**Closes when:** `_spilled()` can match pages by something other than words.

---

## 10. `مقدمة البحث` is an undiagnosed outlier

**Status: open, low urgency.**

26% → 31% where its siblings reached ~50%. Its text and picture scores are both
perfect, so whatever is wrong is positional. No hypothesis yet.

**Closes when:** the cause is found, or it is shown to be the same line-break
drift affecting everything else.
