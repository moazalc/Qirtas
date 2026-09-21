#!/usr/bin/env python3
"""The answer key: grade each FEATURE, not one mixed number.

    python -m harness.answerkey --set dev             # Word-made, tagged files
    python -m harness.answerkey corpus/wild/z20252151.pdf -v

Every other score compares our output with the PDF's text, so it can say
whether the words survived but never whether a footnote came out as a
footnote. Word, when it saves a PDF, usually writes down what each piece of
the page WAS - paragraph, heading, footnote, list item, table cell - and
leaves the running headers and page numbers outside those labels. That record
is an answer key made by the program that wrote the document.

For each labelled file:

  truth      what the labels say each run of words is
  ours       what our .docx made of the same words
  stripped   the same, converted from a copy with the labels REMOVED - the
             hard path (geometry), graded on a real file with a known answer

Text is compared LETTER by letter with spaces ignored, in overlapping runs,
so a paragraph we split or merged still matches. Words would not do: the
theses' labels cut words in half (الث + لاثة) in one place and run separate
words together without a space in another, and no rule can tell which. Each
letter is counted once as (what it was, what we made it), which gives a table
per feature:

  found      of the text the labels call a footnote, the share we made a
             footnote                                   (did we find them?)
  right      of the text we made a footnote, the share that really was one
                                                        (were we right to?)
  extra      text we wrote as that kind that the original never had
             (a table written twice, a chart's numbers spilled as text)

What this key can NOT judge, stated up front:

  - Spelling. Truth and ours read the glyphs with the same library, so a
    misspelling shared by both is invisible (FLAGS 22), and the converter
    repairs some, so each run of lam and alef is compared in sorted order
    (خالل and خلال match). Spelling is TASKS N3's job.
  - What the author meant. Word labels a heading only if the author used a
    heading STYLE. A title typed in bold is a paragraph to Word, so making it
    a heading counts against us here.
  - Pictures. They carry no words; counted, not graded.
"""
import argparse
import collections
import json
import re
import sys
import time
import unicodedata
import zipfile
from pathlib import Path

import pikepdf
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KINDS = ("heading", "paragraph", "list", "footnote", "table", "furniture")
MISSING = "missing"

# Structure labels -> kind. The innermost labelled block owns its words; the
# kind is decided by the whole chain above it, because a list inside a
# footnote is a footnote (TASKS N5: that is exactly the case we get wrong).
BLOCKY = {"P", "H", "H1", "H2", "H3", "H4", "H5", "H6", "Title", "LI", "LBody",
          "Lbl", "TD", "TH", "Caption", "TOCI", "Note", "Footnote", "Textbox"}


def kind_of(chain):
    """chain: the structure labels from the root down. -> one of KINDS."""
    s = set(chain)
    if s & {"Footnote", "Note", "FENote"}:
        return "footnote"
    if s & {"Table", "TD", "TH", "TR"}:
        return "table"
    if s & {"H", "H1", "H2", "H3", "H4", "H5", "H6", "Title"}:
        return "heading"
    if s & {"LI", "LBody", "Lbl"}:
        return "list"
    return "paragraph"     # P, Caption, TOC, Textbox and anything unnamed


# ------------------------------------------------------------ letters

HARAKAT = re.compile(r"[\u064B-\u065F\u0670\u0640]")
KEEP = re.compile(r"[^\u0621-\u064Aa-z0-9]+")
LAM_ALEF = re.compile(r"[\u0644\u0627]{2,}")
FOLD = str.maketrans("أإآٱىة٠١٢٣٤٥٦٧٨٩", "اااايه0123456789")


def letters(text):
    """The text as bare letters: no spaces, marks or punctuation, alef forms
    folded, and every run of lam and alef sorted, so خالل and خلال agree."""
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = KEEP.sub("", HARAKAT.sub("", t).translate(FOLD))
    return LAM_ALEF.sub(lambda m: "".join(sorted(m.group(0))), t)


# ------------------------------------------------------------ truth

def truth_from_glyphs(pdf):
    """Word's labels over the page's own text, via PyMuPDF.

    Text outside every label is page furniture: Word marks running headers,
    footers and page numbers as artifacts, not content.
    """
    out = []
    with pymupdf.open(pdf) as doc:
        for pno, page in enumerate(doc):
            d = page.get_text("dict", flags=pymupdf.TEXTFLAGS_DICT
                              | pymupdf.TEXT_COLLECT_STRUCTURE)
            units = collections.OrderedDict()

            def walk(node, chain, owner):
                for b in node.get("blocks", []):
                    if b["type"] == 2:
                        tag = b.get("std") or b.get("raw") or ""
                        own = (id(b), chain + [tag]) if tag in BLOCKY else owner
                        walk(b, chain + [tag], own)
                    elif b["type"] == 0:
                        t = " ".join(s["text"] for l in b["lines"]
                                     for s in l["spans"])
                        if not t.strip():
                            continue
                        if owner is None:
                            key, k = ("art", id(b)), "furniture"
                        else:
                            key, k = owner[0], kind_of(owner[1])
                        units.setdefault(key, [k, []])[1].append(t)

            walk(d, [], None)
            # A bare page number is left out: ours is a PAGE field, which
            # holds no text for anything to match against.
            out += [(k, " ".join(ts), pno) for k, ts in units.values()
                    if not (k == "furniture" and " ".join(ts).strip().isdigit())]
    return out


def truth_from_labels(pdf):
    """The labels' own /ActualText - for files like Moaz's theses, whose
    glyphs decode to nothing and whose words live only in the labels.

    The pieces are joined inside each labelled block. Word cuts them mid-word
    (الث + لاثة is الثلاثة) and also runs separate words together with no
    space, so the joined text has wrong spaces either way - harmless, because
    grading ignores spaces.
    """
    out = []
    with pikepdf.open(pdf) as p:
        if "/StructTreeRoot" not in p.Root:
            return out
        pages = {pg.obj.objgen: i for i, pg in enumerate(p.pages)}
        state = {"page": 0}

        def walk(node, chain, buf, depth=0):
            if depth > 80:
                return
            if isinstance(node, pikepdf.Array):
                for k in node:
                    walk(k, chain, buf, depth + 1)
                return
            if not isinstance(node, pikepdf.Dictionary):
                return
            tag = str(node.get("/S", ""))[1:]
            ref = node.get("/Pg")
            if ref is not None:
                state["page"] = pages.get(ref.objgen, state["page"])
            here = chain + ([tag] if tag else [])
            own = tag in BLOCKY
            if own:
                buf, page = [], state["page"]
            at = node.get("/ActualText")
            if at is not None and str(at).strip():
                buf.append(str(at))
            else:
                kids = node.get("/K")
                if kids is not None:
                    walk(kids, here, buf, depth + 1)
            if own and "".join(buf).strip():
                out.append((kind_of(here), "".join(buf), page))

        loose = []
        walk(p.Root.StructTreeRoot.get("/K"), [], loose)
        if "".join(loose).strip():
            out.append(("paragraph", "".join(loose), 0))
    return out


def truth(pdf):
    """Measure, don't predict: read both ways, keep whichever found more."""
    a, b = truth_from_glyphs(pdf), truth_from_labels(pdf)
    n = lambda units: sum(len(letters(t)) for _, t, _ in units)
    return (a, "glyphs") if n(a) >= n(b) else (b, "labels")


# ------------------------------------------------------------ ours

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _ptext(p):
    return "".join(t.text or "" for t in p.iter(W + "t"))


def ours(docx):
    """What our Word file made of each paragraph, in order.

    A list is a paragraph with Word numbering OR the hanging indent the writer
    uses for list items - ours are indented paragraphs, not real Word lists
    (reported separately as `real_lists`).
    """
    from lxml import etree
    out, real_lists = [], 0
    with zipfile.ZipFile(docx) as z:
        body = etree.fromstring(z.read("word/document.xml"))
        for p in body.iter(W + "p"):
            txt = _ptext(p)
            if not txt.strip():
                continue
            # Footnotes and text boxes are their own parts or nested; a
            # paragraph inside a text box is still body text here.
            anc = {a.tag for a in p.iterancestors()}
            ppr = p.find(W + "pPr")
            style = ppr.find(W + "pStyle") if ppr is not None else None
            sname = style.get(W + "val") if style is not None else ""
            ind = ppr.find(W + "ind") if ppr is not None else None
            if W + "tbl" in anc:
                k = "table"
            elif sname.lower().startswith(("heading", "title")):
                k = "heading"
            elif ppr is not None and ppr.find(W + "numPr") is not None:
                k, real_lists = "list", real_lists + 1
            elif ind is not None and ind.get(W + "hanging"):
                k = "list"
            else:
                k = "paragraph"
            out.append((k, txt))
        for name in z.namelist():
            kind = ("footnote" if name == "word/footnotes.xml" else
                    "furniture" if re.match(r"word/(header|footer)\d*\.xml$", name)
                    else None)
            if kind:
                for p in etree.fromstring(z.read(name)).iter(W + "p"):
                    if _ptext(p).strip():
                        out.append((kind, _ptext(p)))
    return out, real_lists


# ------------------------------------------------------------ grading

def _stream(units):
    """-> (letters, kind of each, (start, end, kind) of each unit)."""
    ws, ks, spans = [], [], []
    for u in units:
        k, t = u[0], u[1]
        w = letters(t)
        spans.append((len(ws), len(ws) + len(w), k))
        ws += w
        ks += [k] * len(w)
    return ws, ks, spans


def _match_cells(tw, tspans, ow, ospans, got, used):
    """Table cells, headers and footers first, matched whole, in any order.

    A right-to-left table may store its cells in either order and still draw
    them the same way round - `z20252151` stores 2022 first where the labels
    list 2009 first, and the rendered page shows both with 2009 on the right.
    In a stream, a row of one-word cells in the other order matches nothing,
    so the table scored 0% while a duplicate of its numbers written as loose
    text took the credit.

    Headers and footers are short and sit in their own part of the Word file,
    so a stream never runs across them the way the original's does. They are
    matched whole too, and may be reused: written once, printed on every page.
    """
    whole = ("table", "furniture")
    cells = collections.defaultdict(list)
    for a, b, k in ospans:
        if k in whole and b > a:
            cells[(k, tuple(ow[a:b]))].append(a)
    for a, b, k in tspans:
        if k not in whole or b <= a:
            continue
        pos = cells.get((k, tuple(tw[a:b])))
        if pos:
            j = pos[0] if k == "furniture" else pos.pop(0)
            used.update(range(j, j + (b - a)))
            for i in range(a, b):
                got[i] = k


def grade(truth_units, our_units, n=12):
    """-> confusion {truth kind: {our kind or 'missing': letters}}.

    Both sides become one stream of letters, and runs of twelve (two or three
    words) are matched across it. Matching unit by unit failed: the theses'
    labels hold their text in pieces too short to contain a run, and 2,709
    words of a file the gate calls complete came back "missing".

    Each matched run hands its letters the kinds we gave them. A run in
    our output is used once, so one sentence of ours cannot vouch for two in
    the original, and the next match is looked for just after the last one,
    so a repeated phrase lands in the right place. Headers and footers are
    the exception: written once, printed by Word on every page, as the
    original did.
    """
    tw, tk, tspans = _stream(truth_units)
    ow, ok, ospans = _stream(our_units)
    used = set()
    got = [None] * len(tw)
    _match_cells(tw, tspans, ow, ospans, got, used)
    at = collections.defaultdict(list)             # run -> our positions
    for j in range(len(ow) - n + 1):
        at[tuple(ow[j:j + n])].append(j)
    starts, hit = set(), set(used)
    last = -1
    for i in range(len(tw) - n + 1):
        if all(got[i + d] is not None for d in range(n)):
            continue
        # Runs overlap by design (i, i+1 match j, j+1), so a start is used
        # once; the words themselves may be shared with the neighbouring run.
        cands = [j for j in at.get(tuple(tw[i:i + n]), ())
                 if ok[j] == "furniture" or (j not in starts and j not in used)]
        if not cands:
            continue
        after = [j for j in cands if j > last]
        j = min(after) if after else cands[0]
        if ok[j] != "furniture":
            starts.add(j)
        last = j
        for d in range(n):
            if got[i + d] is None:
                got[i + d] = ok[j + d]
            hit.add(j + d)
    conf = {k: collections.Counter() for k in KINDS}
    for k, g in zip(tk, got):
        conf[k][g or MISSING] += 1
    # Words we wrote that the original never had, by the kind we gave them:
    # a table written twice, a chart's numbers spilled as text.
    conf["_extra"] = collections.Counter(
        ok[j] for j in range(len(ow)) if j not in hit and ok[j] != "furniture")
    return conf


def table(conf):
    """-> {kind: {truth, found, right, went}} from a confusion table."""
    made = collections.Counter()
    for k in KINDS:
        for o, n in conf[k].items():
            made[o] += n
    rows = {}
    for k in KINDS:
        tot = sum(conf[k].values())
        rows[k] = {
            "truth": tot,
            "found": round(conf[k][k] / tot, 4) if tot else None,
            "right": round(conf[k][k] / made[k], 4) if made[k] else None,
            "went": {o: n for o, n in conf[k].most_common() if o != k},
            "extra": conf.get("_extra", {}).get(k, 0),
        }
    return rows


def add(into, conf):
    for k in list(KINDS) + ["_extra"]:
        into.setdefault(k, collections.Counter()).update(conf.get(k, {}))


# ------------------------------------------------------------ files

def is_tagged(pdf):
    try:
        with pikepdf.open(pdf) as p:
            return "/StructTreeRoot" in p.Root
    except Exception:
        return False


def strip_labels(pdf, out):
    """A copy with every structure label removed: what the geometry route
    sees. /ActualText lives in the labels, so a file whose words exist only
    there comes out wordless - that is the truth about such a file, and why
    it is skipped rather than graded."""
    with pikepdf.open(pdf) as p:
        for key in ("/StructTreeRoot", "/MarkInfo"):
            if key in p.Root:
                del p.Root[key]
        for page in p.pages:
            if "/StructParents" in page.obj:
                del page.obj["/StructParents"]
        p.save(out)
    return out


def convert_one(pdf, docx):
    from convert.v1 import convert
    docx.parent.mkdir(parents=True, exist_ok=True)
    return convert(str(pdf), str(docx))


def files_for(which):
    from harness.eval import files_for as ff
    rows = {r["file"]: r for r in json.loads(
        Path("out/split.json").read_text(encoding="utf-8"))}
    fs = ff(which)
    if which == "regression":
        return fs
    return [f for f in fs if "Word" in rows.get(f, {}).get("family", "")]


def run(pdfs, work, max_pages=60, verbose=False):
    total = {"ours": {k: collections.Counter() for k in KINDS},
             "stripped": {k: collections.Counter() for k in KINDS}}
    per_file = []
    for pdf in pdfs:
        pdf = Path(pdf)
        rec = {"file": pdf.name}
        try:
            with pymupdf.open(pdf) as d:
                n = len(d)
            if n > max_pages:
                rec["skipped"] = f"{n} pages"
            elif not is_tagged(pdf):
                rec["skipped"] = "no labels"
            else:
                t0 = time.time()
                tru, how = truth(pdf)
                rec["truth_from"] = how
                rec["truth_letters"] = sum(len(letters(t)) for _, t, _ in tru)
                if rec["truth_letters"] < 250:
                    rec["skipped"] = "labels hold almost no words"
                else:
                    stem = pdf.stem[:40]
                    d1 = work / "docx" / f"{stem}.docx"
                    rec["route"] = convert_one(pdf, d1)
                    o, rec["real_lists"] = ours(d1)
                    c = grade(tru, o)
                    add(total["ours"], c)
                    rec["ours"] = table(c)
                    if how == "glyphs":
                        (work / "stripped").mkdir(parents=True, exist_ok=True)
                        sp = strip_labels(pdf, work / "stripped" / pdf.name)
                        d2 = work / "docx-stripped" / f"{stem}.docx"
                        rec["route_stripped"] = convert_one(sp, d2)
                        c2 = grade(tru, ours(d2)[0])
                        add(total["stripped"], c2)
                        rec["stripped"] = table(c2)
                    rec["secs"] = round(time.time() - t0, 1)
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        per_file.append(rec)
        if verbose:
            print(json.dumps(rec, ensure_ascii=False)[:400], flush=True)
    return per_file, {k: table(v) for k, v in total.items()}, total


def show(summary, graded, skipped):
    lines = [f"answer key - {graded} files graded, {skipped} skipped",
             "  found = share of the real ones we made that kind",
             "  right = share of what we made that kind that really was",
             "  extra = text we wrote as that kind that the original never had",
             ""]
    for side, label in (("ours", "as converted (labels kept)"),
                        ("stripped", "labels removed (the hard path)")):
        lines.append(f"{label}")
        lines.append(f"  {'':10} {'letters':>7} {'found':>7} {'right':>7} "
                     f"{'extra':>6}   where the rest went")
        for k in KINDS:
            r = summary[side][k]
            if not r["truth"] and r["right"] is None:
                continue
            pct = lambda v: "   -  " if v is None else f"{v * 100:6.1f}%"
            went = ", ".join(f"{o} {n}" for o, n in list(r["went"].items())[:3])
            lines.append(f"  {k:10} {r['truth']:7} {pct(r['found'])} "
                         f"{pct(r['right'])} {r['extra']:6}   {went}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="*")
    ap.add_argument("--set", choices=("dev", "regression"),
                    help="Word-made files of the tuning set, or the theses. "
                         "Never the holdout: it is paused.")
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--label", default="answerkey")
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    pdfs = a.pdfs or files_for(a.set or "dev")
    stamp = time.strftime("%Y-%m-%d")
    name = f"{stamp}-{a.set or 'files'}-{a.label}"
    work = Path("out/work/answerkey") / name
    per_file, summary, _ = run(pdfs, work, a.max_pages, a.v)
    graded = sum(1 for r in per_file if "ours" in r)
    text = show(summary, graded, len(per_file) - graded)
    print(text)
    outdir = Path("out/runs") / name
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "summary.txt").write_text(text, encoding="utf-8")
    (outdir / "results.json").write_text(json.dumps(
        {"summary": summary, "files": per_file}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"-> {outdir}")


if __name__ == "__main__":
    main()
