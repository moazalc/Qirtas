#!/usr/bin/env python3
"""Does our Word file say what the original's page SHOWS? (FLAGS 25)

Every other score compares us with the PDF's hidden text, and where that text
is wrong - `z21762915` stores 3133 under a printed 1315 - both sides agree on
the wrong word and the score says 100%. This one compares with what Windows'
OCR reads from a picture of the page, which shares nothing with the hidden
text.

For a few pages of each file, page by page (the writer breaks the page before
each original page, so our page N holds what we took from its page N):

    found   of the words OCR reads on the page, the share on our page
    wrong   of the words on our page, the share OCR does not read there:
            misspellings, wrong numbers, text written twice

Arabic words of three letters or more, and numbers. The OCR reads English and
Turkish poorly, so Latin words are not counted either way. Numbers are
compared as runs of digits, since the two sides cut them differently (OCR
reads 1831 where we have 18 31). Running headers and footers are left out on
both sides - words read at the top or bottom of more than one page read:
Moaz's header is a picture, in ours as in the original, and the page score
measures where furniture went. (Leaving out every word inside a picture
left out all of the theses: each of their words IS a picture, labelled with
its text.) OCR makes its own mistakes: on Moaz's theses, whose text is known right, it is
the floor - read every number against theirs.

    python -m harness.truth out/runs/2026-09-22-dev-some-label
"""
import argparse, hashlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert.witness import _ocr, _norm, TASHKEEL
from harness.compare import text_of_docx

CACHE = Path("out/work/truth/cache")
WORD = re.compile(r"[ء-ي0-9]+")
EDGE = 0.15              # top and bottom share of a page: header, footer
LETTERS = re.compile(r"[ء-ي]")


def words(text):
    """Vowel marks off first: a mark inside a word would cut it in two."""
    return [w for w in (_norm(x) for x in
                        WORD.findall(TASHKEEL.sub("", text or "")))
            if len(w) >= 3 and LETTERS.match(w)]


def digits(text):
    return "".join(re.findall(r"[0-9]", _norm(text or "")))


def _numbers_match(runs, other):
    """Runs of digits found in the other side's digits, in any cut."""
    return sum(1 for r in runs if r in other)


def sample(n):
    """First, middle and next-to-last page: a title page, a body page, and
    one near the end where the references are."""
    return sorted({0, n // 2, max(0, n - 2)})


def score(pdf, docx):
    with open(pdf, "rb") as f:
        key = hashlib.sha1(f.read()).hexdigest()[:16]
    doc = pymupdf.open(pdf)
    pages = sample(len(doc))
    seen = _ocr(doc, pages, CACHE / key)
    ours = text_of_docx(docx, pages=True)
    edge = {}
    for p in seen:
        H = doc[p].rect.height
        for w, r in seen[p]:
            if r.y1 < EDGE * H or r.y0 > (1 - EDGE) * H:
                edge.setdefault(w, set()).add(p)
    furniture = {w for w, on in edge.items() if len(on) >= 2}
    found = total = wrong = written = 0
    per = []
    for p in pages:
        if p not in seen or p >= len(ours):
            continue
        shown = [(w, r) for w, r in seen[p] if w not in furniture]
        page = [w for w, _ in shown if WORD.fullmatch(w) and len(w) >= 3
                and LETTERS.match(w)]
        mine = [w for w in words(ours[p]) if w not in furniture]
        a, b = set(page), set(mine)
        f = sum(1 for w in page if w in b)
        x = sum(1 for w in mine if w not in a)
        # numbers: each side's runs of digits looked for in the other's
        o_runs = [w for w, _ in shown if w.isdigit()]
        m_all, o_all = digits(ours[p]), "".join(o_runs)
        m_runs = re.findall(r"[0-9]+", ours[p].translate(
            str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        f += _numbers_match(o_runs, m_all)
        x += len(m_runs) - _numbers_match(m_runs, o_all)
        page += o_runs
        mine += m_runs
        found, total, wrong, written = found + f, total + len(page), \
            wrong + x, written + len(mine)
        per.append(dict(page=p, ocr=len(page), ours=len(mine), found=f,
                        wrong=x, missing=[w for w in page if w not in b][:15],
                        extra=[w for w in mine if w not in a][:15]))
    return dict(found=round(found / max(1, total), 3),
                wrong=round(wrong / max(1, written), 3),
                ocr_words=total, our_words=written, pages=per)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", help="an out/runs/ directory")
    a = ap.parse_args()
    run = Path(a.run)
    data = json.loads((run / "results.json").read_text(encoding="utf-8"))
    base = "corpus" if data["set"] == "regression" else "corpus/wild"
    rows = []
    for r in data["results"]:
        pdf = Path(base) / r["file"]
        if not pdf.exists():        # a quick run mixes the two folders
            pdf = next(Path("corpus").rglob(r["file"]), pdf)
        try:
            s = score(str(pdf), r["docx"])
        except Exception as e:
            print(f"{r['file'][:32]:<34} FAILED {e}")
            continue
        s["file"] = r["file"]
        rows.append(s)
        if s["ocr_words"]:
            print(f"{r['file'][:32]:<34} found {s['found']:6.1%}   "
                  f"wrong {s['wrong']:6.1%}   ({s['ocr_words']} words read)")
    arabic = [r for r in rows if r["ocr_words"] >= 50]
    if arabic:
        f = sum(r["found"] for r in arabic) / len(arabic)
        w = sum(r["wrong"] for r in arabic) / len(arabic)
        print(f"\n{len(arabic)} files with Arabic to read: found {f:.1%}, "
              f"wrong {w:.1%}")
    (run / "truth.json").write_text(json.dumps(rows, ensure_ascii=False,
                                               indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
