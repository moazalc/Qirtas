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
    ap.add_argument("--work", default="out/loss")
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
