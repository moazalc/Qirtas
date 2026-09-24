#!/usr/bin/env python3
"""The thesis corpus: which theses count, and the pages of each we convert.

Replaced the Zenodo mix on 2026-09-24 (Moaz): half of that was 8-page journal
articles, a fifth scans, and 5 of 225 files theses. The project is about one
person - someone who wrote a thesis in Word, exported it to PDF and lost the
Word file - so the corpus is that: Arabic theses, made by Word, with real text.

    python -m harness.fetch_corpus --theses --n 200 --out corpus/theses
    python -m harness.theses --pick      # which theses count, and why not
    python -m harness.theses --cut       # the fixed pages of each, and the split

A thesis runs to 100-300 pages; converting all of it through Word is what made
a full run take three hours. Each thesis is cut to the same pages every time:
its first pages (title, front matter), a run of body pages from a third of the
way in, the first table page after that, and the start of its reference list.
The cut is a pure function of the file, so it never drifts between runs.

Files written, all under corpus/theses/:
    picked.json   every thesis downloaded, whether it counts, and why not
    cuts.json     the pages taken from each, and dev or holdout
    cuts/*.pdf    the cut files - what the converter is run on (not committed)
"""
import argparse, hashlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert.scan import scanned
from harness.split import control_share

ROOT = Path("corpus/theses")
MIN_PAGES = 30           # shorter is an article or a chapter, not a thesis
MIN_ARABIC = 0.6         # share of letters that are Arabic
MIN_CHARS = 500          # a body page of a thesis carries far more
MAX_CONTROL = 0.02       # harness.split: more is a broken font, not text
TILE_PT = 60             # a picture this small, many to a page, is text as tiles
TILES = 20               # z21751977: ~130 a page (FLAGS 28)
SAMPLE = 10
HOLDOUT_SHARE = 0.4

FRONT = 3                # title page and what follows it
BODY = 8                 # a run of ordinary pages
BODY_AT = 0.35           # starting this far in, past the front matter
REFS = 2
REF_HEAD = re.compile(r"(قائمة\s+)?(المصادر|المراجع)(\s+و\s*(المراجع|المصادر))?")
ARAB = re.compile("[\u0600-\u06FF]")


def _sample(n):
    return sorted({round(i * (n - 1) / max(1, SAMPLE - 1)) for i in range(min(n, SAMPLE))})


def judge(path):
    """-> (counts?, why not, facts). Every check is on the file alone."""
    with pymupdf.open(path) as d:
        md = d.metadata or {}
        made = f"{md.get('creator', '')} | {md.get('producer', '')}"
        n = d.page_count
        idx = _sample(n)
        text = [d[i].get_text() for i in idx]
        tiles = sum(1 for i in idx
                    if sum(1 for im in d[i].get_image_info()
                           if pymupdf.Rect(im["bbox"]).width < TILE_PT
                           and pymupdf.Rect(im["bbox"]).height < TILE_PT) >= TILES)
    body = "".join(text)
    letters = [c for c in body if c.isalpha()]
    arabic = sum(1 for c in letters if ARAB.match(c)) / max(1, len(letters))
    chars = sorted(len(t.strip()) for t in text)[len(text) // 2]
    facts = dict(pages=n, made=made[:80], arabic=round(arabic, 2), chars=chars,
                 tiles=tiles)
    if "word" not in made.lower():
        return False, "not made by Word", facts
    if n < MIN_PAGES:
        return False, f"{n} pages - not a thesis", facts
    scan, detail = scanned(str(path))
    if scan:
        return False, f"a scan ({detail})", facts
    if tiles >= len(idx) / 3:
        return False, "text drawn as picture tiles", facts
    if control_share(body) > MAX_CONTROL:
        return False, "broken font: text is control characters", facts
    if arabic < MIN_ARABIC:
        return False, f"{arabic:.0%} Arabic", facts
    if chars < MIN_CHARS:
        return False, f"{chars} characters a page", facts
    return True, "", facts


def pages_for(path):
    """The pages taken from a thesis, 0-based, in order. A function of the
    file alone."""
    with pymupdf.open(path) as d:
        n = d.page_count
        take = list(range(min(FRONT, n)))
        start = max(FRONT, round(n * BODY_AT))
        take += range(start, min(n, start + BODY))
        # The first page after the body run with a ruled table on it.
        for i in range(start + BODY, min(n, start + BODY + 40)):
            try:
                if d[i].find_tables().tables:
                    take.append(i)
                    break
            except Exception:
                break
        # The reference list: the last page in the final third headed by it.
        refs = None
        for i in range(n - 1, round(n * 0.66), -1):
            head = d[i].get_text()[:200]
            if REF_HEAD.search(head):
                refs = i
        if refs is None:
            refs = max(0, n - REFS - 1)
        take += range(refs, min(n, refs + REFS))
    return sorted(set(take))


def _prune(path):
    """Cut the label tree to the kept pages as well.

    Taking pages out leaves the PDF's hidden labels whole, still pointing at
    the pages that went. The tags route walks every label, so a 14-page cut of
    z22058810 read back 41,746 words - most of the thesis - and the dead pages
    were kept alive inside the file (310MB for 500 pages). A label goes when
    the page it sits on (its /Pg, or its parent's) is not kept.
    """
    import pikepdf
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        root = pdf.Root.get("/StructTreeRoot")
        if root is None:
            return
        keep = {p.objgen for p in pdf.pages}

        def prune(node, pg):
            if isinstance(node, pikepdf.Array):
                kids = [k for k in (prune(x, pg) for x in node) if k is not None]
                return pikepdf.Array(kids) if kids else None
            if isinstance(node, pikepdf.Dictionary):
                ref = node.get("/Pg")
                if ref is not None:
                    pg = ref.objgen
                kids = node.get("/K")
                if node.get("/Type") in ("/MCR", "/OBJR") or kids is None:
                    return node if pg in keep else None
                kids = prune(kids, pg)
                if kids is None:
                    return None
                node.K = kids
                return node
            # A bare marked-content number: on the page its label sits on.
            return node if pg in keep else None

        root.K = prune(root.get("/K"), None) or pikepdf.Array()
        # The page -> labels index keeps every dead label alive; rebuild it
        # with the kept pages' entries only.
        if "/ParentTree" in root:
            old = pikepdf.NumberTree(root.ParentTree)
            nums = []
            wanted = sorted({int(p.obj["/StructParents"]) for p in pdf.pages
                             if "/StructParents" in p.obj})
            for k in wanted:
                if k in old:
                    nums += [k, old[k]]
            root.ParentTree = pdf.make_indirect(pikepdf.Dictionary(Nums=pikepdf.Array(nums)))
        pdf.save(path)


def _set(name):
    """dev or holdout, by a hash of the name - never drifts."""
    h = int(hashlib.sha1(name.encode()).hexdigest(), 16) % 1000
    return "holdout" if h < HOLDOUT_SHARE * 1000 else "dev"


def pick():
    rows = []
    for f in sorted(ROOT.glob("z*.pdf")):
        try:
            ok, why, facts = judge(f)
        except Exception as e:
            ok, why, facts = False, f"unreadable: {type(e).__name__}", {}
        rows.append(dict(file=f.name, counts=ok, why=why, **facts))
        print(f"  {f.name:16} {'yes' if ok else 'no ':3}  {why or ''}")
    (ROOT / "picked.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    good = sum(r["counts"] for r in rows)
    print(f"\n{good} of {len(rows)} theses count")


def cut():
    rows = json.loads((ROOT / "picked.json").read_text(encoding="utf-8"))
    out = ROOT / "cuts"
    out.mkdir(exist_ok=True)
    cuts = []
    for r in rows:
        if not r["counts"]:
            continue
        src = ROOT / r["file"]
        take = pages_for(src)
        with pymupdf.open(src) as d:
            d.select(take)
            # garbage=3 (merge duplicate objects) ran for minutes on some
            # theses; dropping what nothing points to is enough.
            d.save(out / r["file"], garbage=1, deflate=True)
        _prune(out / r["file"])
        cuts.append(dict(file=r["file"], pages=take, set=_set(r["file"])))
        print(f"  {r['file']:16} {len(take):3} pages  {cuts[-1]['set']}")
    (ROOT / "cuts.json").write_text(json.dumps(cuts, indent=1), encoding="utf-8")
    dev = sum(c["set"] == "dev" for c in cuts)
    print(f"\n{len(cuts)} cut: {dev} dev, {len(cuts) - dev} holdout")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", action="store_true")
    ap.add_argument("--cut", action="store_true")
    a = ap.parse_args()
    if a.pick:
        pick()
    if a.cut:
        cut()


if __name__ == "__main__":
    sys.exit(main() or 0)
