"""A second reading of the page, to decide what a broken font's shapes are.

FLAGS 25: every score checked us against the PDF's hidden text, and on about
a fifth of the wild Arabic files that text is wrong - `z21762915` prints 1315
and محمد, and its hidden text says 3133 and زلمد. `glyphs.py` repairs fonts
by what the installed copy of the font calls each shape, but it cannot tell
when to believe it:

  - digits were never changed, because Word shows a typed 2 as ٢ - so a 1
    stored as 3 stayed 3
  - a joined pair (محـ drawn as one shape) was changed only over junk,
    because the shaping rules can name one shape several ways - so مح
    stored as لز stayed لز
  - and where the embedded font is numbered differently from the installed
    one, the installed names are themselves nonsense (`z21762915`'s Times
    New Roman Bold: ئإ, ڡ) and were used anyway where they looked like junk

So for every shape where the file and the installed font disagree, the page
decides. A few pages are read by OCR; each word it reads is compared with the
same spot read two ways - with the file's names and with the installed font's.
Where one matches and the other does not, every disputed shape in that word
gets a vote. The text still comes from the PDF: OCR never writes a word, it
only picks between two names for a shape, so its own misreadings cannot reach
the document - they fail to match either way and vote for nothing.

A shape that never appears on a page read keeps the old rule, unless the font
as a whole has shown which side to believe.

Windows only for now (`ocr_windows.ps1`, Windows' own Arabic OCR). Where it
is missing, nothing changes.
"""
import collections
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert.arabic import repair_lam_alef
from convert.glyphs import (_ARABIC, _descendant, _key, _same, SYMBOL_FONTS,
                            diagnose, read_tounicode, reference,
                            write_tounicode)
from convert.pdftext import apply_fixes, fix_map

PS = Path(__file__).with_name("ocr_windows.ps1")
DPI = 200
PAGES = 4                 # pages read by OCR, those richest in disputed shapes
SLACK = 1.5               # points added round an OCR box
# A font whose disputed shapes the page settled mostly one way: its other
# disputed shapes go the same way. At least this many settled, this lopsided.
FONT_SETTLED = 5
FONT_LOPSIDED = 4

TASHKEEL = re.compile(r"[ً-ْٰـ]")
NOT_WORD = re.compile(r"[^\w]")
WEST = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789" * 2)


def _norm(t):
    """What OCR can see: no vowel marks, one alef, no punctuation."""
    t = TASHKEEL.sub("", t or "").translate(WEST)
    t = re.sub("[أإآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    return NOT_WORD.sub("", t)


def _disputes(doc, xref):
    """(stored table, installed names of the shapes in dispute, old table)
    for a font the installed copy can name, or None."""
    if doc.xref_get_key(xref, "Subtype")[1] != "/Type0" \
            or doc.xref_get_key(xref, "Encoding")[1] != "/Identity-H":
        return None
    kind, tu = doc.xref_get_key(xref, "ToUnicode")
    if kind != "xref":
        return None
    name = doc.xref_get_key(xref, "BaseFont")[1].lstrip("/")
    if _key(name) in SYMBOL_FONTS:
        return None
    desc = _descendant(doc, xref)
    if desc is None:
        return None
    c2g = doc.xref_get_key(desc, "CIDToGIDMap")
    if c2g[0] == "name" and c2g[1] != "/Identity" or c2g[0] not in ("null", "name"):
        return None
    ref = reference(name)
    if ref is None:
        return None
    text, _ = ref
    stored = read_tounicode(doc.xref_stream(int(tu.split()[0])))
    named = {c: text[c] for c in stored if c in text
             and (_ARABIC.search(text[c]) or text[c].isdigit())
             and not _same(stored[c], text[c])
             # a typed 2 shown as ٢ is the same number, not a dispute
             and not (stored[c].translate(WEST) == text[c].translate(WEST))}
    if not named:
        return None
    old, _ = diagnose(doc, xref)
    return stored, named, old or stored


def _ocr(pdf, pages, work):
    """{page: [(normalised word, Rect in points)]} read by Windows' OCR."""
    work.mkdir(parents=True, exist_ok=True)
    todo = []
    for p in pages:
        png = work / f"p{p}.png"
        if not png.with_suffix(".words.json").exists():
            pdf[p].get_pixmap(dpi=DPI).save(str(png))
            todo.append(str(png))
    if todo:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(PS), *todo], capture_output=True,
                       timeout=60 + 30 * len(todo))
    k = 72.0 / DPI
    out = {}
    for p in pages:
        f = work / f"p{p}.words.json"
        if not f.exists():
            continue
        rows = json.loads(f.read_text(encoding="utf-8-sig") or "[]")
        out[p] = [(_norm(r["t"]), pymupdf.Rect(r["x"] * k, r["y"] * k,
                                               (r["x"] + r["w"]) * k,
                                               (r["y"] + r["h"]) * k))
                  for r in rows if _norm(r["t"])]
    return out


def _reading(path):
    """page, Rect -> the words there as the converter would read them."""
    doc = pymupdf.open(path)
    try:
        fixes = fix_map(path)
    except Exception:
        fixes = {}
    cache = {}

    def read(page, rect):
        if page not in cache:
            cache[page] = doc[page].get_text("words")
        r = rect + (-SLACK, -SLACK, SLACK, SLACK)
        ws = [w for w in cache[page]
              if r.contains(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))]
        return _norm(apply_fixes(repair_lam_alef("".join(w[4] for w in ws)), fixes))
    return read


def settle(pdf_path, work=None):
    """The tables for fonts whose disputed shapes the page has settled.

    -> {xref: (table, report)}; {} where there is nothing to settle or no OCR,
    and glyphs.repair keeps its own rules for every font."""
    pdf_path = str(pdf_path)
    doc = pymupdf.open(pdf_path)
    fonts = {}
    for xref in sorted({f[0] for p in doc for f in p.get_fonts()}):
        got = _disputes(doc, xref)
        if got:
            fonts[xref] = got
    if not fonts or not PS.exists():
        return {}
    keys = {}
    for xref in fonts:
        keys.setdefault(_key(doc.xref_get_key(xref, "BaseFont")[1].lstrip("/")),
                        []).append(xref)

    # Where the disputed shapes are drawn: (page, key, gid, centre).
    drawn = collections.defaultdict(list)
    for i, page in enumerate(doc):
        for sp in page.get_texttrace():
            k = _key(sp["font"])
            if k not in keys:
                continue
            for ch in sp["chars"]:
                g = ch[1]
                if g < 0 or not any(g in fonts[x][1] for x in keys[k]):
                    continue
                b = ch[3]
                drawn[i].append((k, g, pymupdf.Point((b[0] + b[2]) / 2,
                                                     (b[1] + b[3]) / 2)))
    if not drawn:
        return {}
    pages = sorted(drawn, key=lambda i: -len(drawn[i]))[:PAGES]

    # The same document with every disputed shape given the installed name.
    work = Path(work or tempfile.mkdtemp(prefix="qirtas-witness-"))
    alt = work / "installed.pdf"
    for xref, (stored, named, _) in fonts.items():
        tu = int(doc.xref_get_key(xref, "ToUnicode")[1].split()[0])
        doc.update_stream(tu, write_tounicode({**stored, **named}))
    doc.save(str(alt), garbage=0)
    doc.close()

    orig = pymupdf.open(pdf_path)
    words = _ocr(orig, pages, work)
    as_stored, as_named = _reading(pdf_path), _reading(str(alt))
    votes = collections.defaultdict(lambda: [0, 0])      # (key, gid) -> [stored, named]
    for p, rows in words.items():
        for seen, rect in rows:
            r = rect + (-SLACK, -SLACK, SLACK, SLACK)
            here = {(k, g) for k, g, pt in drawn[p] if r.contains(pt)}
            if not here:
                continue
            a, b = as_stored(p, rect), as_named(p, rect)
            if a == b:
                continue
            if a == seen:
                for kg in here:
                    votes[kg][0] += 1
            elif b == seen:
                for kg in here:
                    votes[kg][1] += 1

    done = {}
    for xref, (stored, named, old) in fonts.items():
        k = _key(orig.xref_get_key(xref, "BaseFont")[1].lstrip("/"))
        s_won = sum(1 for g in named if votes[(k, g)][0] > votes[(k, g)][1])
        n_won = sum(1 for g in named if votes[(k, g)][1] > votes[(k, g)][0])
        if n_won >= FONT_SETTLED and n_won >= FONT_LOPSIDED * max(1, s_won):
            lean = "named"
        elif s_won >= FONT_SETTLED and s_won >= FONT_LOPSIDED * max(1, n_won):
            lean = "stored"
        else:
            lean = None
        table = dict(old)
        for g in named:
            s, n = votes[(k, g)]
            if n > s:
                table[g] = named[g]
            elif s > n:
                table[g] = stored[g]
            elif lean == "named":
                table[g] = named[g]
            elif lean == "stored":
                table[g] = stored[g]
        done[xref] = (table, f"{k}: page settled {s_won + n_won} of "
                             f"{len(named)} disputed shapes ({n_won} as the "
                             f"installed font names them), font leans "
                             f"{lean or 'neither way'}")
    return done


if __name__ == "__main__":
    for x, (_, why) in settle(sys.argv[1]).items():
        print(x, why)
