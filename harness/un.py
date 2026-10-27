#!/usr/bin/env python3
"""A test set of real Arabic PDFs whose true Word file is known: UN documents.

Moaz, 2026-10-26: the corpus was lost with the old PC, and the numbers we had
were on files we made (the plain set) or tuned on (the theses). The UN
publishes every official document in Arabic as both a PDF and the Word file
it was printed from, at documents.un.org. Real documents, made in Word by
people who are not us, with the answer beside each one.

The first 11 tried (2026-10-26) all had broken hidden text - words stored
backwards, lam-alef swapped, stretched words stored as repeated letters - so
any score that reads the PDF's own text as the reference cannot judge them.
Score against the Word file instead.

    python -m harness.un pick --n 30        # random symbols -> corpus/un/
    python -m harness.un fetch              # restore exactly corpus/un/manifest.jsonl
    python -m harness.eval --set un --label <what>
    python -m harness.un score out/runs/<date>-un-<label> --show

Symbols are drawn at random from document families (resolutions, reports,
letters; New York and Geneva) with a fixed seed. `pick` appends; the manifest
is what makes the set reproducible, as with the Zenodo corpora.
"""
import argparse
import hashlib
import json
import random
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

HOME = Path("corpus/un")
MANIFEST = HOME / "manifest.jsonl"
ACCESS = "https://documents.un.org/api/symbol/access?"
AGENT = {"User-Agent": "QirtasTestSet/0.1 (https://github.com/moazalc/Qirtas)"}
MAX_PAGES = 30          # conversion takes minutes a file; keep the set runnable
HOLDOUT_SHARE = 0.4     # same share as harness/split.py

# (pattern, numbers to draw from). The year or session picks the decade's
# production; the number picks the document.
FAMILIES = [
    ("A/RES/{s}/{n}", range(75, 80), range(1, 300)),        # GA resolutions
    ("A/{s}/{n}", range(75, 80), range(1, 800)),            # GA reports, notes
    ("A/HRC/RES/{s}/{n}", range(48, 58), range(1, 40)),     # HRC resolutions (Geneva)
    ("A/HRC/{s}/{n}", range(48, 58), range(1, 70)),         # HRC reports (Geneva)
    ("S/{s}/{n}", range(2021, 2026), range(1, 900)),        # SC letters, reports
    ("E/{s}/{n}", range(2021, 2026), range(1, 90)),         # ECOSOC
]


def get(symbol, kind):
    """The document's bytes, or None when the UN has no such file."""
    url = ACCESS + urllib.parse.urlencode({"s": symbol, "l": "ar", "t": kind})
    req = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(req, timeout=120) as r:
        if "error" in r.geturl() or "html" in r.headers.get("Content-Type", ""):
            return None
        return r.read()


def name(symbol):
    return "un_" + symbol.replace("/", "_").replace("(", "").replace(")", "")


def holdout(file):
    return int(hashlib.sha256(file.encode()).hexdigest(), 16) % 1000 < HOLDOUT_SHARE * 1000


def save(symbol):
    """Download one pair. Returns the manifest row, or a reason it was refused."""
    import pymupdf
    pdf = get(symbol, "pdf")
    if not pdf:
        return "no Arabic PDF"
    doc = get(symbol, "docx")
    if not doc or not doc.startswith(b"PK"):
        return "no Word file"     # older ones are .doc (Word 97) - not readable as an answer
    d = pymupdf.open(stream=pdf, filetype="pdf")
    if len(d) > MAX_PAGES:
        return f"{len(d)} pages"
    stem = name(symbol)
    (HOME / f"{stem}.pdf").write_bytes(pdf)
    (HOME / f"{stem}.docx").write_bytes(doc)
    zipfile.ZipFile(HOME / f"{stem}.docx").testzip()
    return {"symbol": symbol, "file": f"{stem}.pdf", "answer": f"{stem}.docx",
            "pages": len(d), "producer": d.metadata.get("producer", ""),
            "holdout": holdout(f"{stem}.pdf")}


def pick(n, seed, delay):
    HOME.mkdir(parents=True, exist_ok=True)
    seen = set()
    if MANIFEST.exists():
        seen = {json.loads(l)["symbol"] for l in MANIFEST.open(encoding="utf-8") if l.strip()}
    rng = random.Random(seed)
    got = tries = 0
    with MANIFEST.open("a", encoding="utf-8") as mf:
        while got < n and tries < n * 20:
            tries += 1
            pattern, sessions, numbers = rng.choice(FAMILIES)
            symbol = pattern.format(s=rng.choice(sessions), n=rng.choice(numbers))
            if symbol in seen:
                continue
            seen.add(symbol)
            try:
                row = save(symbol)
            except Exception as e:
                row = f"failed: {e}"
            time.sleep(delay)
            if isinstance(row, str):
                print(f"  {symbol:<22} skipped: {row}")
                continue
            got += 1
            mf.write(json.dumps(row, ensure_ascii=False) + "\n")
            mf.flush()
            print(f"  [{got:>2}/{n}] {symbol:<22} {row['pages']:>3} pages"
                  f"{'  (held out)' if row['holdout'] else ''}")
    print(f"\n{got} pairs in {tries} tries -> {HOME}")


def fetch(delay):
    """Re-download exactly the documents in the manifest."""
    if not MANIFEST.exists():
        sys.exit(f"no manifest at {MANIFEST}")
    lost = []
    for row in (json.loads(l) for l in MANIFEST.open(encoding="utf-8") if l.strip()):
        if (HOME / row["file"]).exists() and (HOME / row["answer"]).exists():
            continue
        try:
            got = save(row["symbol"])
        except Exception as e:
            got = f"failed: {e}"
        if isinstance(got, str):
            lost.append((row["symbol"], got))
        print(f"  {row['symbol']:<22} {got if isinstance(got, str) else 'restored'}")
        time.sleep(delay)
    if lost:
        print(f"\n{len(lost)} could not be restored - the set is NOT the one on record:")
        for s, why in lost:
            print(f"  {s}: {why}")
        return 1


def rows(holdout=False):
    return [r for r in (json.loads(l) for l in MANIFEST.open(encoding="utf-8") if l.strip())
            if r["holdout"] == holdout]


def files(holdout=False):
    """The set, for harness.eval."""
    return sorted(str(HOME / r["file"]) for r in rows(holdout))


# ---------------------------------------------------------------- scoring
#
# Words: ours against the UN's Word file, as harness.plain does.
# Pages: the UN PDF's own text cannot be the reference - it is broken
# (FLAGS 37) - so the reference page is the UN's Word file laid out by Word
# HERE, read the way the converter reads, as ours is. Checked 2026-10-26 on
# the 13 to work on: Word here gives the UN's page count on 11; the two others
# run one page longer (A/HRC/56/13, A/HRC/48/40), and their pages are counted
# against Word's layout, not the UN's. Word's own PDF of the true file holds
# 84-91% of its words as text (the UN's 16-55%) - Word's export faults are
# why both sides are read through the converter's repairs.

TRUE_PDF = Path("out/un-true")


def true_pdf(answer):
    """The true Word file laid out by Word on this machine, made once."""
    pdf = TRUE_PDF / (Path(answer).stem + ".pdf")
    if not pdf.exists():
        from harness.word import docx_to_pdf
        docx_to_pdf(str(answer), str(TRUE_PDF))
    return pdf


def score_run(run):
    import collections
    from harness.plain import MARKS, _docx_words, _page_letters
    res = json.loads((Path(run) / "results.json").read_text(encoding="utf-8"))
    out, all_pages = [], []
    for r in res["results"]:
        answer = HOME / (Path(r["file"]).stem + ".docx")
        truth = collections.Counter(_docx_words(answer))
        ours = collections.Counter(_docx_words(r["docx"]))
        right = sum((truth & ours).values()) / max(1, sum(truth.values()))
        # Placement is judged apart from spelling: the stretch line is taken
        # off both sides, or every stretched word fails its page (2026-10-27:
        # pages matching read 2.7% with it left in).
        a, b = ([[w.replace("ـ", "") for w in page] for page in _page_letters(p)]
                for p in (str(true_pdf(answer)), r["rebuilt"]))
        # Word's own PDF of the true file glues and cuts words (ميثاقالأمم,
        # أسبو): pages then read 95-98% where every word had landed right.
        # Only words the true file holds are asked for.
        real = {MARKS.sub("", w).replace("ـ", "") for w in truth}
        a = [[w for w in page if w in real] for page in a]
        per = []
        for i, words in enumerate(a):
            ca, cb = collections.Counter(words), collections.Counter(b[i] if i < len(b) else [])
            per.append(sum((ca & cb).values()) / len(words) if words else 1.0)
        all_pages += per
        out.append({"file": r["file"], "exact": right, "pages": per,
                    "same_count": len(a) == len(b),
                    "missing": (truth - ours).most_common(8),
                    "extra": (ours - truth).most_common(8)})
        print(f"  {len(out):>2}/{len(res['results'])} {Path(r['file']).stem}", flush=True)
    return out, all_pages


def score(run, show):
    from harness.plain import PAGE_MATCH
    got, pages = score_run(run)
    if show:
        for r in got:
            bad = [i + 1 for i, p in enumerate(r["pages"]) if p < PAGE_MATCH]
            print(f"{Path(r['file']).stem:<28} exact {r['exact']:7.2%}  pages off {bad}")
            print(f"   missing {r['missing']}\n   extra   {r['extra']}")
    exact = sum(r["exact"] for r in got) / len(got)
    match = sum(p >= PAGE_MATCH for p in pages) / len(pages)
    whole = sum(r["same_count"] and all(p >= PAGE_MATCH for p in r["pages"])
                for r in got) / len(got)
    print(f"UN set, {len(got)} files, against the UN's own Word files")
    print(f"  words exactly right {exact:7.2%}   (worst file {min(r['exact'] for r in got):.2%})")
    print(f"  pages matching      {match:7.2%}   (files with every page matching {whole:.1%})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--delay", type=float, default=1.0)
    f = sub.add_parser("fetch")
    f.add_argument("--delay", type=float, default=1.0)
    s = sub.add_parser("score", help="an out/runs folder of --set un")
    s.add_argument("run")
    s.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.cmd == "score":
        return score(a.run, a.show)
    return pick(a.n, a.seed, a.delay) if a.cmd == "pick" else fetch(a.delay)


if __name__ == "__main__":
    sys.exit(main() or 0)
