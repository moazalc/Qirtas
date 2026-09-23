#!/usr/bin/env python3
"""The loss check: did we drop anything?

The only question here is whether text went missing. Order is deliberately
ignored - that is the look score's job. This is the hard gate: nothing ships
while a word is being lost.

    python -m harness.loss corpus/*.pdf
"""
import argparse, collections, difflib, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.compare import text_of, text_of_docx
from convert.v1 import convert

WS = re.compile(r"\s+")
TASHKEEL = re.compile(r"[ً-ْٰـ]")
BOLD, DIM, GRN, YEL, RED, OFF = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def norm(t, marks=True):
    t = WS.sub("", t or "")
    return t if marks else TASHKEEL.sub("", t)


SENT_SPLIT = re.compile(r"[.؟!؛:\n]+|،")
MIN_SENT = 40


def sentences(t):
    """Split into sentences, normalised so spacing differences don't matter."""
    return [s for s in (norm(x) for x in SENT_SPLIT.split(t or ""))
            if len(s) >= MIN_SENT]


def sentence_pairs(t):
    """(normalised, as written) per sentence. The raw form keeps the spaces,
    which is the only place word boundaries still exist after norm()."""
    out = []
    for piece in SENT_SPLIT.split(t or ""):
        n = norm(piece)
        if len(n) >= MIN_SENT:
            out.append((n, piece))
    return out


MIN_WORD = 3


def words_survive(raw, b, marks=True):
    """Is every substantial word of this sentence somewhere in the output?

    This is what "order is deliberately ignored" has to mean in practice. A
    sentence found as one contiguous run is present; a sentence whose words all
    survive but changed places is ALSO present, because the gate's question is
    whether text was dropped, not where it ended up. Putting it anywhere else
    is the page score's business.

    Words under three characters are skipped. They turn up by coincidence far
    too easily to be evidence in either direction, and requiring them would
    reintroduce the false alarms this exists to remove.
    """
    words = [w for w in (norm(x, marks) for x in raw.split())
             if len(w) >= MIN_WORD]
    if not words:
        return False
    return all(w in b for w in words)


def coverage(orig, out, marks=True):
    """Is every sentence of the original present somewhere in our output?

    Sentences, not characters or fixed-size chunks. Characters were too lenient
    (a dropped sentence shares its letters with the rest of the text). Fixed
    chunks were too harsh: a chunk straddling a point where order differs - a
    page number moving, say - is reported missing though both halves are there.
    A sentence is a real unit that reordering keeps intact.

    A sentence not found whole is retried with 8% trimmed off each end, so a
    page number glued onto its start does not condemn it.
    """
    b = norm(out, marks)
    pairs = sentence_pairs(orig)
    if not pairs:
        return 1.0, []
    gone = []
    for s, raw in pairs:
        if s in b:
            continue
        pad = max(2, len(s) * 8 // 100)
        if s[pad:-pad] in b:
            continue
        # Not found as one run. Before calling it lost, check whether its words
        # are simply somewhere else - see words_survive(). Three holdout files
        # were being reported as losing text when between them they had lost a
        # two-character fragment.
        if words_survive(raw, b, marks):
            continue
        gone.append(s)
    return 1 - len(gone) / len(pairs), gone


# A flagged sentence is judged by the page only where the OCR plainly read
# that part of it: at least this share of the sentence's other words.
PAGE_READ = 0.5


def judge(pdf, out, marks=True):
    """Nothing lost, with the original's page as the tie-breaker (FLAGS 25).

    The reference is the PDF's hidden text, and where that text is wrong a
    sentence we wrote right reads as lost: `z21763864` has الٕ with no alef
    where the page shows الإ, and fell to 81.5% the day we stopped writing a
    misspelled second copy that matched it. So each sentence coverage()
    flags is taken to its page, read by OCR, and the words it says we lack
    are looked for there. If the page shows any of them, the loss is real.
    If it shows none - while plainly reading the rest of the sentence - the
    reference was wrong there: the sentence is excused, and listed.

    -> (kept, kept before the page was asked, [excused sentence])
    """
    import hashlib
    import pymupdf
    from convert.witness import _norm, _ocr
    from harness.compare import text_of
    pages = text_of(pdf, pages=True)
    orig = "\n".join(pages)
    cov, gone = coverage(orig, out, marks)
    if not gone:
        return cov, cov, []
    pairs = sentence_pairs(orig)
    raw_of = dict(pairs)
    by_page = [norm(t, marks) for t in pages]
    with open(pdf, "rb") as f:
        key = hashlib.sha1(f.read()).hexdigest()[:16]
    doc = pymupdf.open(pdf)
    ours = {_norm(w) for w in out.split()}
    excused = []
    for s in gone:
        page = next((i for i, t in enumerate(by_page) if s[5:45] in t), None)
        if page is None:
            continue
        seen = _ocr(doc, [page], Path("out/work/truth/cache") / key).get(page)
        if not seen:
            continue
        shown = {w for w, _ in seen}
        joined = "".join(w for w, _ in seen)
        words = [w for w in (_norm(x) for x in raw_of.get(s, "").split())
                 if len(w) >= MIN_WORD]
        lacking = [w for w in words if w not in ours]
        present = [w for w in words if w in ours]
        if not lacking or not present:
            continue
        read = sum(1 for w in present if w in shown or w in joined)
        if read < PAGE_READ * len(present):
            continue                  # the OCR did not read this part well
        if any(w in shown or w in joined for w in lacking):
            continue                  # the page shows what we lack: a loss
        excused.append(s)
    kept = 1 - (len(gone) - len(excused)) / max(1, len(pairs))
    return kept, cov, excused


def missing_chunks(orig, out, marks=True, limit=8):
    """The actual runs of text that were dropped, so we can see WHAT is gone."""
    a, b = norm(orig, marks), norm(out, marks)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    gone = [a[i1:i2] for tag, i1, i2, _, _ in sm.get_opcodes()
            if tag in ("delete", "replace") and i2 - i1 >= 4]
    gone.sort(key=len, reverse=True)
    return gone[:limit], sum(len(g) for g in gone)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--work", default="out/work/loss")
    ap.add_argument("--show", type=int, default=3, help="missing chunks to print per file")
    a = ap.parse_args()

    worst = 1.0
    print(f"{DIM}{'file':<42}{'kept':>8}{'missing chars':>15}{OFF}")
    for pdf in a.pdfs:
        docx = Path(a.work) / (Path(pdf).stem[:40] + ".docx")
        try:
            convert(pdf, docx)
            orig, out = text_of(pdf), text_of_docx(docx)
        except Exception as e:
            print(f"{Path(pdf).name[:40]:<42} {RED}FAILED{OFF} {e}"[:140])
            continue
        cov, gone = coverage(orig, out)
        lost = sum(len(g) for g in gone)
        worst = min(worst, cov)
        col = GRN if cov >= 0.999 else (YEL if cov >= 0.99 else RED)
        print(f"{Path(pdf).name[:40]:<42}{col}{cov:>8.2%}{OFF}{lost:>15,}")
        for c in gone[:a.show]:
            print(f"    {DIM}missing:{OFF} {c[:78]}")

    print(f"\n{BOLD}worst file: {GRN if worst>=0.999 else RED}{worst:.2%}{OFF}")
    sys.exit(0 if worst >= 0.999 else 1)


if __name__ == "__main__":
    main()
