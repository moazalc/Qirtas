#!/usr/bin/env python3
"""A spelling check that does not read the PDF the way we do (TASKS N3).

    python -m harness.spelling --set dev              # our latest eval output
    python -m harness.spelling corpus/wild/z21761968.pdf --docx out/x.docx -v

Every other score compares our Word file with text PyMuPDF extracted from the
PDF - the same library the converter reads with. A word it misspells is
misspelled on both sides and cancels out, so the checker cannot see it
(FLAGS 22). This one asks a second program: Microsoft Word, which has opened
PDFs itself since 2013 ("PDF Reflow"), and reads the glyphs its own way.

Word's reading is NOT a reference to copy. It puts text in floating boxes,
splits words, and has its own mistakes (رأس -> أرس). So nothing here depends
on its ORDER. It is used only as a vocabulary: the set of words Word saw in
this same file. Each Arabic word we wrote is then one of:

  confirmed      Word saw this exact word in the file.
  lam-alef       Word did not, but it did see the word with a stored "ال"
                 read as "لا" (خالل -> خلال). The lam-alef ligature's
                 letters were stored backwards and we copied them.
  display form   written with Arabic presentation-form glyphs (ﻤ ﺔ): looks
                 right, cannot be searched or spell-checked.
  backwards      Word saw the word spelled in reverse (FLAGS 1).
  unconfirmed    none of the above: a rare word, one Word split or misread,
                 or a fault this check has no rule for. Not proven wrong.

The first four are named faults with evidence from a second reader. The
unconfirmed share is the check's blind spot, and is reported, not hidden.

The same count is taken of the checker's own reference (`compare.text_of`), so
we see whether a fault is ours or already in what we are scored against.

Files Word turns into pictures (the theses, whose text exists only in their
labels, and backwards-stored files) give Word almost no words: they are listed
as "no second opinion", never scored as 0% or 100%. They are checked instead
against a lexicon: every word Word read in the other files. That is enough to
tell a backwards file from a readable one, not enough to call its rarer words
right, so their unconfirmed share runs high and is reported apart.

Windows and Word only. Word's reading is cached in out/work/wordread/.
"""
import argparse
import collections
import contextlib
import html
import json
import re
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CACHE = Path("out/work/wordread")
KINDS = ("confirmed", "lam-alef", "display form", "backwards", "unconfirmed")
FAULTS = KINDS[1:4]

MARKS = re.compile("[\u064b-\u065f\u0670\u0640]")     # harakat, dagger alef, tatweel
# An Arabic word: base letters, or presentation forms, not mixed with Latin.
TOKEN = re.compile("[\u0621-\u064a\u0671-\u06d3\u064b-\u065f\u0670\u0640"
                   "\ufb50-\ufdff\ufe70-\ufefc]+")
DISPLAY = re.compile("[\ufb50-\ufdff\ufe70-\ufefc]")
# A stored "alef, lam" that may have been the ligature "lam, alef". The
# hamza-carrying alefs form the same ligature (لأ لإ لآ).
PAIR = re.compile("[\u0627\u0623\u0625\u0622]\u0644")
MAX_PAIRS = 4          # 2**4 spellings tried per word at most
# Word needs enough of the file as text for its silence about a word to mean
# anything. Below this many words it drew the file as pictures.
MIN_WORDS = 200
COMMON = 50            # "the commonest words", for short backwards words
STALE_SECS = 3600      # an output this much older than the newest is stale
WORD_KEY = r"Software\Microsoft\Office\16.0\Word\Options"


def tokens(text):
    """Arabic words, marks and tatweel removed. One letter is not a word."""
    out = []
    for t in TOKEN.findall(text or ""):
        t = MARKS.sub("", t)
        if len(t) > 1:
            out.append(t)
    return out


def xml_text(xml):
    """Every w:t, paragraphs and text boxes alike. Order is not used."""
    # Runs of one paragraph are joined without a space: Word splits a word
    # across runs wherever its formatting changes.
    return html.unescape("\n".join(
        "".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", p))
        for p in xml.split("</w:p>")))


def docx_text(docx):
    """All the text in a .docx: body, text boxes, notes, headers, footers."""
    out = []
    with zipfile.ZipFile(docx) as z:
        for n in z.namelist():
            if re.match(r"word/(document|footnotes|endnotes|header\d*|footer\d*)"
                        r"\.xml$", n):
                out.append(xml_text(z.read(n).decode("utf-8", "replace")))
    return "\n".join(out)


def lam_alef_forms(w):
    """Spellings of w with some stored 'alef, lam' pairs read as 'lam, alef'."""
    spots = [m.start() for m in PAIR.finditer(w)][:MAX_PAIRS]
    for mask in range(1, 2 ** len(spots)):
        s = list(w)
        for k, i in enumerate(spots):
            if mask >> k & 1:
                s[i], s[i + 1] = s[i + 1], s[i]
        yield "".join(s)


def classify(word, vocab, common=()):
    """vocab: words the second reader saw. common: its most frequent ones."""
    if word in vocab:
        return "confirmed"
    if DISPLAY.search(word):
        return "display form"
    # The Allah ligature fails the same way lam-alef does, with no "alef, lam"
    # pair to swap: stored "هللا", printed "الله".
    if word.replace("هللا", "الله") in vocab \
            or any(f in vocab for f in lam_alef_forms(word)):
        return "lam-alef"
    # Reversed, it is a word - but so is many a fragment of three letters
    # ("الإ" read backwards is "إلا"). Short words count only when the
    # reversal is among the commonest words of all ("يف" for "في").
    back = word[::-1]
    if back != word and (len(word) >= 4 and back in vocab or back in common):
        return "backwards"
    return "unconfirmed"


def check(words, vocab, examples=0, common=()):
    """-> (Counter of kind -> word count, {kind: [(word, count)]})"""
    counts = collections.Counter(words)
    by_kind, seen = collections.Counter(), collections.defaultdict(list)
    for w, n in counts.items():
        k = classify(w, vocab, common)
        by_kind[k] += n
        seen[k].append((w, n))
    ex = {k: sorted(v, key=lambda x: -x[1])[:examples] for k, v in seen.items()}
    return by_kind, ex


@contextlib.contextmanager
def _no_pdf_prompt():
    """Word asks before converting a PDF, in a dialog nobody can see when it
    runs hidden, and waits forever. DisplayAlerts does not reach it; this
    Word option does. Set for the run, and put back exactly as found."""
    import winreg
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, WORD_KEY)
    try:
        old = winreg.QueryValueEx(key, "DisableConvertPdfWarning")
    except FileNotFoundError:
        old = None
    winreg.SetValueEx(key, "DisableConvertPdfWarning", 0, winreg.REG_DWORD, 1)
    try:
        yield
    finally:
        if old is None:
            winreg.DeleteValue(key, "DisableConvertPdfWarning")
        else:
            winreg.SetValueEx(key, "DisableConvertPdfWarning", 0, old[1], old[0])
        winreg.CloseKey(key)


def word_reading(pdf, cache=CACHE):
    """Word's own .docx of this PDF, made once and cached. Needs _no_pdf_prompt."""
    from harness.word import _word
    pdf = Path(pdf).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    out = (cache / (pdf.stem + ".docx")).resolve()
    if out.exists():
        return out
    app = _word()
    d = app.Documents.Open(str(pdf), ConfirmConversions=False, ReadOnly=True,
                           AddToRecentFiles=False, Visible=False)
    try:
        d.SaveAs2(str(out), FileFormat=16)          # wdFormatDocumentDefault
    finally:
        d.Close(SaveChanges=0)
    return out


def reversed_share(words):
    """Share of a reading that is some more frequent word spelled backwards.

    Word reads some files partly backwards itself: on z21508463 it wrote
    "يف" 77 times beside "في". Such words must not vouch for ours."""
    n = sum(words.values())
    back = sum(k for w, k in words.items() if _reversal(w, words))
    return back / n if n else 0.0


def _reversal(w, words):
    return len(w) > 2 and w[::-1] != w and words.get(w[::-1], 0) > words[w]


def vouching(words):
    """The words of a reading that may confirm ours: its reversals removed."""
    return collections.Counter({w: k for w, k in words.items()
                                if not _reversal(w, words)})


_LEXICON = {}


def lexicon(cache=CACHE):
    """Every word Word read in the cached files it could read, with counts.

    The fallback for a file Word drew as pictures - whose own reading is under
    MIN_WORDS and so is not in here. Weaker than Word's reading of the file
    itself: a rare word of this file will be missing. But still not ours:
    nothing in it came through PyMuPDF."""
    key = str(cache)
    if key not in _LEXICON:
        words = collections.Counter()
        for d in sorted(Path(cache).glob("*.docx")):
            ws = collections.Counter(tokens(docx_text(d)))
            # 2026-09-21: 0.0-0.6% on twelve readings, 3.0% on z21508463.
            if sum(ws.values()) >= MIN_WORDS and reversed_share(ws) <= 0.01:
                words.update(ws)
        _LEXICON[key] = vouching(words)
    return _LEXICON[key]


def score_file(pdf, docx, examples=0):
    from harness.compare import text_of
    t = time.time()
    word_words = tokens(docx_text(word_reading(pdf)))
    r = {"file": Path(pdf).name, "word_words": len(word_words)}
    if len(word_words) >= MIN_WORDS:
        vocab, r["opinion"] = vouching(collections.Counter(word_words)), "word"
    else:
        vocab, r["opinion"] = lexicon(), "lexicon"
        # The lexicon grows with the cache, so these rows are comparable only
        # between runs over the same cached readings. Recorded for that.
        r["lexicon_words"] = len(vocab)
        if len(vocab) < 1000:
            r["skip"] = "no second opinion: Word read %d words" % len(word_words)
            return r
    common = {w for w, _ in vocab.most_common(COMMON)}
    for side, text in (("ours", docx_text(docx)), ("reference", text_of(pdf))):
        kinds, ex = check(tokens(text), vocab, examples, common)
        r[side] = dict(kinds)
        if examples:
            r[side + "_examples"] = ex
    r["secs"] = round(time.time() - t, 1)
    return r


def share(c, k):
    n = sum(c.values())
    return 100.0 * c.get(k, 0) / n if n else 0.0


def show(results):
    lines = ["%-16s %-7s %7s  " % ("file", "checked", "words") + "  ".join(
        "%12s" % k for k in KINDS)]
    total = collections.defaultdict(collections.Counter)
    scored = [r for r in results if "ours" in r]
    for r in sorted(scored, key=lambda r: r["opinion"], reverse=True):
        c = collections.Counter(r["ours"])
        total[("ours", r["opinion"])].update(c)
        total[("reference", r["opinion"])].update(r["reference"])
        lines.append("%-16s %-7s %7d  " % (r["file"][:16], r["opinion"],
                                           sum(c.values())) + "  ".join(
            "%11.1f%%" % share(c, k) for k in KINDS))
    for r in results:
        if "ours" not in r:
            lines.append("%-16s   %s" % (r["file"][:16], r.get("skip") or r.get("error")))
    for op, what in (("word", "against Word's reading of the same file"),
                     ("lexicon", "against the lexicon only (Word drew them as pictures)")):
        n = sum(1 for r in scored if r["opinion"] == op)
        if not n:
            continue
        lines += ["", "%d files %s:" % (n, what)]
        for side in ("ours", "reference"):
            c = total[(side, op)]
            lines.append("  %-22s %7d  " % (side, sum(c.values())) + "  ".join(
                "%11.1f%%" % share(c, k) for k in KINDS))
    bad = [r for r in scored if sum(r["ours"].get(k, 0) for k in FAULTS)
           > 0.01 * sum(r["ours"].values())]
    lines += ["", "%d of %d files have more than 1%% of their words in a named "
              "fault." % (len(bad), len(scored))]
    return "\n".join(lines)


def files_for_set(which):
    from harness.eval import files_for
    return files_for(which)


def newest_eval(which):
    """The most recent eval record of this set - not an answer key or a
    spelling record, which share the out/runs naming."""
    runs = [d for d in Path("out/runs").glob(f"*-{which}-*")
            if (d / "results.json").exists()
            and "-answerkey-" not in d.name and "-spelling" not in d.name]
    runs = [d for d in runs if "results" in json.loads(
        (d / "results.json").read_text(encoding="utf-8"))]
    if not runs:
        sys.exit(f"no eval run of {which} in out/runs - run harness.eval first")
    # By the record's date: runs do not store the time they were taken, and
    # these folders have been renamed and rewritten since. Only the file list
    # is used, and the staleness check above guards the .docx themselves.
    return max(runs, key=lambda d: (d / "results.json").stat().st_mtime)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdfs", nargs="*")
    ap.add_argument("--set", choices=("dev", "regression"),
                    help="Never the holdout: it is paused.")
    ap.add_argument("--docx", help="our .docx, for a single pdf")
    ap.add_argument("--run", help="an eval run folder: check the files it "
                    "converted (default: the newest eval run of --set)")
    ap.add_argument("--label", default="spelling")
    ap.add_argument("-v", action="store_true", help="show example words")
    a = ap.parse_args()
    ours = {}
    if a.pdfs:
        pdfs = [Path(p) for p in a.pdfs]
        if a.docx:
            ours[pdfs[0].name] = Path(a.docx)
    else:
        # The files one eval run converted, and its .docx of each - never
        # whatever happens to sit in the work folder. Two left there by an
        # earlier run, with the old lam-alef repair on, got into a baseline
        # once and halved its lam-alef count.
        run = Path(a.run) if a.run else newest_eval(a.set or "dev")
        rows = json.loads((run / "results.json").read_text(encoding="utf-8"))["results"]
        for r in rows:
            if r.get("docx") and Path(r["docx"]).exists():
                ours[r["file"]] = Path(r["docx"])
        # Every eval writes into the same folder, so a run's .docx may have
        # been overwritten since - or be left over from before it. Outputs
        # much older than the rest were not made by the latest conversion.
        if ours:
            newest = max(d.stat().st_mtime for d in ours.values())
            stale = sorted(n for n, d in ours.items()
                           if d.stat().st_mtime < newest - STALE_SECS)
            for n in stale:
                print(f"  left out, stale .docx: {n}")
                del ours[n]
        files = {Path(f).name: Path(f) for f in files_for_set(a.set or "dev")}
        pdfs = [files[n] for n in sorted(ours) if n in files]
        print(f"checking {len(pdfs)} files converted by {run}")

    results = []
    with _no_pdf_prompt():
        for pdf in pdfs:
            docx = ours.get(pdf.name)
            if not docx or not docx.exists():
                results.append({"file": pdf.name, "error": "no .docx of ours at %s" % docx})
                continue
            try:
                r = score_file(pdf, docx, examples=8 if a.v else 0)
            except Exception as e:
                r = {"file": pdf.name, "error": "%s: %s" % (type(e).__name__, e)}
            results.append(r)
            print(json.dumps({k: v for k, v in r.items() if not k.endswith("examples")},
                             ensure_ascii=False), flush=True)
            if a.v:
                for s in ("ours", "reference"):
                    for k, ws in r.get(s + "_examples", {}).items():
                        if k != "confirmed":
                            print("   %-9s %-12s %s" % (s, k, " ".join(
                                "%s(%d)" % x for x in ws)))
    text = show(results)
    print()
    print(text)
    stamp = time.strftime("%Y-%m-%d")
    name, n = f"{stamp}-{a.set or 'files'}-{a.label}", 2
    while (Path("out/runs") / name).exists():
        name, n = f"{stamp}-{a.set or 'files'}-{a.label}-{n}", n + 1
    outdir = Path("out/runs") / name
    outdir.mkdir(parents=True)
    (outdir / "summary.txt").write_text(text, encoding="utf-8")
    (outdir / "results.json").write_text(json.dumps(results, ensure_ascii=False,
                                                    indent=1), encoding="utf-8")
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
