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
    sents = sentences(orig)
    if not sents:
        return 1.0, []
    gone = []
    for s in sents:
        if s in b:
            continue
        pad = max(2, len(s) * 8 // 100)
        if s[pad:-pad] in b:
            continue
        gone.append(s)
    return 1 - len(gone) / len(sents), gone


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
