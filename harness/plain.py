#!/usr/bin/env python3
"""A test set of plain Arabic PDFs that we make ourselves, made by Word.

Moaz, 2026-10-22: the first usable version is for PDFs of pure Arabic text -
no tables, no pictures - and for those the converted pages should match the
original's. The theses cannot measure that: 36 of the 37 hold a table or a
picture somewhere. So we write the documents: Arabic Wikipedia text (public,
CC BY-SA), laid out by Word with varied fonts, sizes, spacing and margins,
saved as PDF. The Word file each PDF came from is kept beside it, so the
answer is known exactly, and nothing in the set is anyone's private work.

    python -m harness.plain fetch --n 80     # articles -> corpus/plain/source.json
    python -m harness.plain build --n 40     # Word -> corpus/plain/{docx,pdf}/
    python -m harness.eval --set plain       # convert them back and score

The same seed builds the same documents from the same source.json.
"""
import argparse
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HOME = Path("corpus/plain")
SOURCE = HOME / "source.json"
API = "https://ar.wikipedia.org/w/api.php?"
AGENT = {"User-Agent": "QirtasTestSet/0.1 (https://github.com/moazalc/Qirtas)"}

# Sections that are lists of links and references, not prose.
SKIP_SECTIONS = ("مراجع", "المراجع", "مصادر", "المصادر", "وصلات خارجية",
                 "انظر أيضا", "انظر أيضًا", "اقرأ أيضا", "ملاحظات", "هوامش",
                 "قراءات إضافية", "روابط خارجية", "معرض صور", "المراجع والمصادر")
LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
# Pure Arabic text, as Moaz set it: Arabic letters and marks, digits, and
# ordinary punctuation. A paragraph with anything else is left out.
ALLOWED = re.compile(r"^[؀-ۿݐ-ݿ0-9\s.,:;!?()«»\"'\-–—/%]+$")
MIN_WORDS = 12


def _get(**params):
    url = API + urllib.parse.urlencode({"format": "json", **params})
    req = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _blocks(extract):
    """Wikipedia's plain text -> [("h", text) | ("p", text)], prose only."""
    out, skipping = [], False
    for line in extract.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(=+)\s*(.*?)\s*=+$", line)
        if m:
            title = m.group(2)
            skipping = any(s in title for s in SKIP_SECTIONS)
            if not skipping and ALLOWED.match(title) and not LATIN.search(title):
                out.append(("h", title))
            continue
        if skipping or LATIN.search(line) or not ALLOWED.match(line):
            continue
        if len(line.split()) < MIN_WORDS:
            continue
        out.append(("p", re.sub(r"\s+", " ", line)))
    # A heading with no prose under it goes.
    return [b for i, b in enumerate(out)
            if b[0] == "p" or (i + 1 < len(out) and out[i + 1][0] == "p")]


def fetch(n, min_words=1500):
    """Long random articles until n have enough plain prose."""
    have = json.loads(SOURCE.read_text(encoding="utf-8")) if SOURCE.exists() else []
    seen = {a["title"] for a in have}
    while len(have) < n:
        batch = _get(action="query", list="random", rnnamespace=0, rnlimit=50)
        titles = [r["title"] for r in batch["query"]["random"] if r["title"] not in seen]
        info = _get(action="query", prop="info", titles="|".join(titles))
        long = [p["title"] for p in info["query"]["pages"].values()
                if p.get("length", 0) > 20000]
        for t in long:
            seen.add(t)
            d = _get(action="query", prop="extracts|revisions", rvprop="ids",
                     explaintext=1, exsectionformat="wiki", titles=t)
            page = next(iter(d["query"]["pages"].values()))
            blocks = _blocks(page.get("extract", ""))
            words = sum(len(b[1].split()) for b in blocks if b[0] == "p")
            if words < min_words:
                continue
            rev = page.get("revisions", [{}])[0].get("revid")
            have.append({"title": t, "revid": rev, "blocks": blocks})
            print(f"{len(have):3} {words:6} words", flush=True)
            _save(have)                   # each one, so a crash keeps what came
            if len(have) >= n:
                break
        time.sleep(0.5)
    return have


def _save(have):
    HOME.mkdir(parents=True, exist_ok=True)
    tmp = SOURCE.with_suffix(".tmp")
    tmp.write_text(json.dumps(have, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(SOURCE)


# ---------------------------------------------------------------- building

FONTS = ["Simplified Arabic", "Traditional Arabic", "Sakkal Majalla",
         "Arial", "Times New Roman"]
# Word's own values (spelled out: no makepy constants module needed).
STYLE_NORMAL, STYLE_H1, STYLE_H2 = -1, -2, -3
STYLE_FOOTNOTE_TEXT, STYLE_FOOTNOTE_REF = -30, -39
RTL = 0                                   # wdReadingOrderRtl
JUSTIFY, RIGHT, CENTER = 3, 2, 1
SINGLE, ONE_HALF, DOUBLE, MULTIPLE = 0, 1, 2, 5
A4, LETTER = 7, 2                         # wdPaperA4, wdPaperLetter
SAVE_DOCX = 16
WD_EXPORT_PDF = 17
CM = 72 / 2.54                           # points in a centimetre


def design(rng):
    """One document's look, drawn at random within what people really use."""
    size = rng.choice([12, 13, 14, 14, 16])
    return {
        "font": rng.choice(FONTS),
        "size": size,
        "heading_size": size + rng.choice([2, 4, 6]),
        "align": rng.choice([JUSTIFY, JUSTIFY, RIGHT]),
        "spacing": rng.choice([(SINGLE, 0), (MULTIPLE, 1.15), (ONE_HALF, 0), (DOUBLE, 0)]),
        "after": rng.choice([0, 6, 8, 12]),
        "indent_cm": rng.choice([0, 0, 0.5, 1.0]),
        "margin_cm": rng.choice([2.0, 2.5, 3.0]),
        "paper": rng.choice([A4, A4, LETTER]),
        "page_numbers": rng.random() < 0.7,
        "footnotes": rng.choice([0, 0, 2, 4]),
        "pages": rng.randint(3, 10),
    }


def _words_for(d):
    """Roughly how many words make `pages` pages in this look."""
    per_line = {12: 15, 13: 14, 14: 12, 16: 10}[d["size"]]
    lines = {SINGLE: 38, MULTIPLE: 33, ONE_HALF: 26, DOUBLE: 19}[d["spacing"][0]]
    lines *= {12: 1.1, 13: 1.05, 14: 1.0, 16: 0.85}[d["size"]]
    return int(d["pages"] * per_line * lines * 0.85)


def _text(article, d, rng):
    """Headings and paragraphs from the article, up to the look's length."""
    want, have, out = _words_for(d), 0, []
    for kind, text in article["blocks"]:
        out.append((kind, text))
        if kind == "p":
            have += len(text.split())
            if have >= want:
                break
    title = article["title"]
    if out and out[0][0] == "p" and ALLOWED.match(title) and not LATIN.search(title):
        out.insert(0, ("h", title))
    return out


def _style(st, d, size, bold=False):
    for f in (st.Font,):
        f.Name = d["font"]
        f.NameBi = d["font"]
        f.Size = size
        f.SizeBi = size
        f.Bold = bold
        f.BoldBi = bold
    p = st.ParagraphFormat
    p.ReadingOrder = RTL


def build_one(app, article, d, rng, docx, pdf):
    doc = app.Documents.Add()
    try:
        ps = doc.PageSetup
        ps.PaperSize = d["paper"]
        m = d["margin_cm"] * CM
        ps.TopMargin = ps.BottomMargin = ps.LeftMargin = ps.RightMargin = m

        normal = doc.Styles(STYLE_NORMAL)
        _style(normal, d, d["size"])
        pf = normal.ParagraphFormat
        pf.Alignment = d["align"]
        rule, mult = d["spacing"]
        pf.LineSpacingRule = rule
        if rule == MULTIPLE:
            pf.LineSpacing = 12 * mult
        pf.SpaceBefore = 0
        pf.SpaceAfter = d["after"]
        pf.FirstLineIndent = d["indent_cm"] * CM
        for which, size in ((STYLE_H1, d["heading_size"]), (STYLE_H2, d["size"] + 2)):
            h = doc.Styles(which)
            _style(h, d, size, bold=True)
            h.Font.Color = 0          # black, like a thesis, not Word's blue
            h.ParagraphFormat.Alignment = CENTER if which == STYLE_H1 else RIGHT
            h.ParagraphFormat.FirstLineIndent = 0
        for which in (STYLE_FOOTNOTE_TEXT, STYLE_FOOTNOTE_REF):
            f = doc.Styles(which).Font
            f.Name = f.NameBi = d["font"]
        doc.Styles(STYLE_FOOTNOTE_TEXT).Font.SizeBi = d["size"] - 2
        doc.Styles(STYLE_FOOTNOTE_TEXT).ParagraphFormat.ReadingOrder = RTL

        blocks = _text(article, d, rng)
        doc.Content.Text = "\r".join(t for _, t in blocks)
        first_heading = True
        for i, (kind, _) in enumerate(blocks, start=1):
            if kind == "h":
                doc.Paragraphs(i).Style = doc.Styles(STYLE_H1 if first_heading else STYLE_H2)
                first_heading = False

        # Footnotes at the ends of a few random paragraphs, their text taken
        # from a sentence elsewhere in the article.
        paras = [i for i, (k, _) in enumerate(blocks, start=1) if k == "p"]
        spare = [t for k, t in article["blocks"][len(blocks):] if k == "p"] or \
                [t for k, t in blocks if k == "p"]
        for i in sorted(rng.sample(paras, min(d["footnotes"], len(paras)))):
            r = doc.Paragraphs(i).Range
            r.MoveEnd(1, -1)                       # before the paragraph mark
            r.Collapse(0)
            note = " ".join(rng.choice(spare).split()[:rng.randint(8, 25)])
            doc.Footnotes.Add(Range=r, Text=note)

        if d["page_numbers"]:
            doc.Sections(1).Footers(1).PageNumbers.Add(PageNumberAlignment=CENTER,
                                                       FirstPage=True)
        doc.SaveAs2(str(docx.resolve()), SAVE_DOCX)
        doc.ExportAsFixedFormat(OutputFileName=str(pdf.resolve()),
                                ExportFormat=WD_EXPORT_PDF, OpenAfterExport=False)
        return doc.ComputeStatistics(2)            # wdStatisticPages
    finally:
        doc.Close(SaveChanges=0)


def build(n, seed=22):
    from harness.word import _word
    articles = json.loads(SOURCE.read_text(encoding="utf-8"))
    rng = random.Random(seed)
    for sub in ("docx", "pdf"):
        (HOME / sub).mkdir(parents=True, exist_ok=True)
    app = _word()
    made = []
    for k in range(n):
        article = articles[k % len(articles)]
        d = design(rng)
        name = f"plain{k + 1:03}"
        docx, pdf = HOME / "docx" / f"{name}.docx", HOME / "pdf" / f"{name}.pdf"
        pages = build_one(app, article, d, rng, docx, pdf)
        made.append({"file": f"{name}.pdf", "title": article["title"],
                     "revid": article["revid"], "pages": pages, **d})
        print(f"{name} {pages:2}pp {d['font']:<18} {d['size']}pt", flush=True)
    (HOME / "designs.json").write_text(json.dumps(made, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return made


def files():
    """The set, for harness.eval."""
    return sorted(str(p) for p in (HOME / "pdf").glob("plain*.pdf"))


# ---------------------------------------------------------------- scoring
#
# harness.eval reads both sides out of PDFs, and Word's PDFs store text with
# faults of their own: no space before a number (في20), a word cut at the
# line's end (المخ / تلفة), a lam-alef read backwards. On the theses that is
# all there is. Here the Word file each PDF came from is known, so the words
# are checked against it, and where each page's words went is checked with
# the marks and digits taken off - so spelling and placement are judged apart
# (2026-10-22).

# A page matches when this much of its words land on the same page of ours
# (harness.eval.PAGE_MATCH).
PAGE_MATCH = 0.98
MARKS = re.compile(r"[ً-ٰٟۖ-ۭ]")
TOKEN = re.compile(r"[ء-ي٠-٩۰-۹0-9ً-ٰٟ]+")
LETTERS = re.compile(r"[ء-ي]{4,}")


def _docx_words(path, parts=("word/document.xml", "word/footnotes.xml")):
    import unicodedata
    import zipfile
    with zipfile.ZipFile(path) as z:
        xml = "".join(z.read(p).decode("utf-8") for p in parts if p in z.namelist())
    # Paragraph ends are word breaks; runs inside a paragraph are not.
    xml = xml.replace("</w:p>", "<w:t> </w:t>")
    text = "".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml))
    return [unicodedata.normalize("NFC", w) for w in TOKEN.findall(text)]


def _page_letters(pdf):
    """Each page's words, letters only, read the way the converter reads:
    the repaired copy, through order.get_text, with the file's fix map. Read
    raw, Word's own faults - a lam-alef stored turned, a word cut at a line's
    end - failed pages on both sides, not always alike: 447 of 461 words
    missing from failing pages were on no page of ours (2026-10-22)."""
    import pymupdf
    from convert.arabic import repair_lam_alef
    from convert.glyphs import repaired
    from convert.order import get_text
    from convert.pdftext import apply_fixes, fix_map
    pdf = repaired(pdf)
    try:
        fixes = fix_map(pdf)
    except Exception:
        fixes = {}
    with pymupdf.open(pdf) as d:
        return [LETTERS.findall(MARKS.sub("", apply_fixes(repair_lam_alef(get_text(p)), fixes)))
                for p in d]


def score_run(run):
    """Exact words against the true Word file, and pages matching, per file."""
    import collections
    res = json.loads((Path(run) / "results.json").read_text(encoding="utf-8"))
    rows, all_pages = [], []
    for r in res["results"]:
        name = Path(r["file"]).stem
        truth = collections.Counter(_docx_words(HOME / "docx" / f"{name}.docx"))
        ours = collections.Counter(_docx_words(r["docx"]))
        right = sum((truth & ours).values()) / max(1, sum(truth.values()))
        wrong = sorted((truth - ours).elements())
        extra = [w for w in (ours - truth).elements() if not (w.isdigit() and len(w) <= 2)]
        a, b = _page_letters(r["path"]), _page_letters(r["rebuilt"])
        per = []
        for i, words in enumerate(a):
            ca, cb = collections.Counter(words), collections.Counter(b[i] if i < len(b) else [])
            per.append(sum((ca & cb).values()) / len(words) if words else 1.0)
        all_pages += per
        rows.append({"file": r["file"], "exact": right, "missing": wrong, "extra": extra,
                     "pages": per, "same_count": len(a) == len(b)})
    return rows, all_pages


# ---------------------------------------------------------------- looks
#
# Pages matching counts words; it cannot see a page number moved to the
# corner, text starting lower, or a document shrunk a size (FLAGS 36). This
# reads each page of the original PDF and of ours by the same rule and puts
# the three side by side (2026-10-22).

NUMBER = re.compile(r"^\s*[-–(]?\s*[0-9٠-٩]{1,4}\s*[-–)]?\s*$")


def _page_looks(pdf):
    """[{"number": x centre of the page number or None, "top": top of the
    first line of text, "size": the commonest text size}] per page."""
    import collections
    import pymupdf
    out = []
    with pymupdf.open(pdf) as d:
        for p in d:
            H, W = p.rect.height, p.rect.width
            number, low, tops, sizes = None, 0.0, [], collections.Counter()
            for b in p.get_text("rawdict")["blocks"]:
                for ln in b.get("lines", ()):
                    chars = [c for s in ln["spans"] for c in s["chars"]
                             if not c["c"].isspace()]
                    if not chars:
                        continue
                    text = "".join(c["c"] for c in chars)
                    y0 = min(c["bbox"][1] for c in chars)
                    if y0 > 0.88 * H and NUMBER.match(text):
                        # the lowest: a footnote's number sits above it
                        if number is None or y0 > low:
                            xs = [c["bbox"][0] for c in chars] + [c["bbox"][2] for c in chars]
                            number, low = (min(xs) + max(xs)) / 2, y0
                        continue
                    if y0 < 0.06 * H or y0 > 0.92 * H:
                        continue
                    tops.append(y0)
                    for s in ln["spans"]:
                        n = sum(1 for c in s["chars"] if not c["c"].isspace())
                        sizes[round(s["size"])] += n
            out.append({"number": number, "top": min(tops) if tops else None,
                        "size": sizes.most_common(1)[0][0] if sizes else None,
                        "width": W})
    return out


def looks_run(run):
    """Per file: page numbers off centre by more than 10pt, pages whose text
    starts more than 6pt away, and the text size, original against ours."""
    res = json.loads((Path(run) / "results.json").read_text(encoding="utf-8"))
    rows = []
    for r in res["results"]:
        a, b = _page_looks(r["path"]), _page_looks(r["rebuilt"])
        numbers = moved = tops = off = 0
        shifts = []
        for pa, pb in zip(a, b):
            if pa["number"] is not None:
                numbers += 1
                if pb["number"] is None or abs(pa["number"] - pb["number"]) > 10:
                    moved += 1
            if pa["top"] is not None and pb["top"] is not None:
                tops += 1
                shifts.append(pb["top"] - pa["top"])
                if abs(pb["top"] - pa["top"]) > 6:
                    off += 1
        size_a = collections_mode([p["size"] for p in a])
        size_b = collections_mode([p["size"] for p in b])
        rows.append({"file": r["file"], "numbers": numbers, "moved": moved,
                     "tops": tops, "off": off, "shifts": shifts,
                     "size": (size_a, size_b)})
    return rows


def collections_mode(xs):
    import collections
    xs = [x for x in xs if x is not None]
    return collections.Counter(xs).most_common(1)[0][0] if xs else None


def main():
    ap = argparse.ArgumentParser(prog="python -m harness.plain")
    ap.add_argument("what", choices=["fetch", "build", "score", "looks"])
    ap.add_argument("run", nargs="?", help="score: an out/runs folder of --set plain")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=22)
    ap.add_argument("--show", action="store_true", help="score: list each file's faults")
    a = ap.parse_args()
    if a.what == "fetch":
        fetch(a.n)
    elif a.what == "build":
        build(a.n, a.seed)
    elif a.what == "looks":
        rows = looks_run(a.run)
        if a.show:
            for r in rows:
                med = sorted(r["shifts"])[len(r["shifts"]) // 2] if r["shifts"] else 0
                print(f"{r['file']}  number moved {r['moved']}/{r['numbers']}  "
                      f"text start off {r['off']}/{r['tops']} (middle {med:+.1f}pt)  "
                      f"size {r['size'][0]} -> {r['size'][1]}")
        numbers = sum(r["numbers"] for r in rows)
        tops = sum(r["tops"] for r in rows)
        print(f"plain set looks, {len(rows)} files, the original's PDF against ours")
        print(f"  page numbers in place   {1 - sum(r['moved'] for r in rows) / max(1, numbers):7.1%}"
              f"   ({numbers} pages with one)")
        print(f"  text starts in place    {1 - sum(r['off'] for r in rows) / max(1, tops):7.1%}"
              f"   (within 6pt; {tops} pages)")
        print(f"  text size kept          "
              f"{sum(r['size'][0] == r['size'][1] for r in rows) / len(rows):7.1%}   of files")
    else:
        rows, pages = score_run(a.run)
        exact = sum(r["exact"] for r in rows) / len(rows)
        match = sum(p >= PAGE_MATCH for p in pages) / len(pages)
        whole = sum(r["same_count"] and all(p >= PAGE_MATCH for p in r["pages"])
                    for r in rows) / len(rows)
        if a.show:
            for r in rows:
                bad = [i + 1 for i, p in enumerate(r["pages"]) if p < PAGE_MATCH]
                print(f"{r['file']}  exact {r['exact']:.2%}  pages off {bad}")
                if r["missing"] or r["extra"]:
                    print(f"   missing {r['missing'][:8]}\n   extra   {r['extra'][:8]}")
        print(f"plain set, {len(rows)} files, against the true Word files")
        print(f"  words exactly right {exact:7.2%}")
        print(f"  pages matching      {match:7.2%}   (files with every page matching {whole:.1%})")


if __name__ == "__main__":
    main()
