#!/usr/bin/env python3
"""Brackets where the page draws them.

    python -m harness.brackets [--set thesis] [--work out/work/eval-thesis] [--show N]

For every bracket on an Arabic line of the original, the line is read as
DRAWN - its pieces right to left by position, a number or English run left
to right - and the bracket is keyed by the word before it and the word after
it. The score is the share of those keys our Word file holds.

Independent of `convert.order` on purpose: it joins the extractor's pieces
back into printed lines and reads them by position alone, so it does not
share the converter's rules. Things it gets wrong, found by reading its
misses (PLAN "Brackets where the page draws them"):
  - English citations whose own brackets sit inside the run, `Sari (2023)`:
    it reads them as `)Sari (2023`. Some of every file's misses are these.
  - A missed line matched against the wrong paragraph when read out.
  - Files stored backwards (`z21145041`, `z22058810`) or with broken fonts
    score low whatever we do.
Arabic words are compared by length only, so a spelling repair (حممد ->
محمد) is not counted as a moved bracket; English words and numbers exactly.
Brackets round a bare 1-3 digit number (note marks) are left out: Word's own
note numbers replace them.
"""
import argparse, collections, random, re, sys, unicodedata, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

AR = re.compile(r"[ء-يٮ-ۓۺ-ۿﭐ-﷿ﹰ-ﻼ]")
LTR = re.compile(r"[A-Za-z0-9٠-٩۰-۹%À-ɏ]")
BR = set("()[]{}")
MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{"}
NOTE = re.compile(r"[0-9٠-٩]{1,3}")


def _items(chars):
    """[(c, x0, x1)] in stored order -> [(kind, text, x0, x1, chars)]: runs of
    Arabic letters (A), of other letters and digits (L), each other one (N)."""
    items = []
    for c, x0, x1 in chars:
        for ch in unicodedata.normalize("NFKC", c):
            if unicodedata.combining(ch) or ch in "ـٰ":
                continue
            kind = "A" if AR.match(ch) else "L" if LTR.match(ch) else "N"
            if items and kind in "AL" and items[-1][0] == kind:
                k, t, a, b, cs = items[-1]
                items[-1] = (k, t + ch, min(a, x0), max(b, x1), cs + [(ch, x0, x1)])
            else:
                items.append((kind, ch, x0, x1, [(ch, x0, x1)]))
    return items


def drawn(chars):
    """The line in reading order as drawn: [(kind, text)]."""
    items = sorted(_items(chars), key=lambda it: -(it[2] + it[3]) / 2)
    out, i = [], 0
    while i < len(items):
        if items[i][0] != "L":
            out.append(items[i][:2])
            i += 1
            continue
        last = i
        for k in range(i + 1, len(items)):
            if items[k][0] == "A":
                break
            if items[k][0] == "L":
                last = k
        for t in sorted(items[i:last + 1], key=lambda t: (t[2] + t[3]) / 2):
            if t[0] == "L":
                xs = sorted(t[4], key=lambda c: (c[1] + c[2]) / 2)
                out.append(("L", "".join(c[0] for c in xs)))
            else:
                out.append(t[:2])
        i = last + 1
    return out


def _unbalanced(toks):
    bad, depth = 0, {"(": 0, "[": 0}
    for _, t in toks:
        for o, c in (("(", ")"), ("[", "]")):
            if t == o:
                depth[o] += 1
            elif t == c:
                depth[o] -= 1
                if depth[o] < 0:
                    bad, depth[o] = bad + 1, 0
    return bad + sum(depth.values())


def unmirror(toks):
    """Some fonts store the shape drawn, not the bracket meant: read in order
    the line then has ) before (. Turned round where that balances better."""
    flip = [(k, MIRROR.get(t, t) if k == "N" else t) for k, t in toks]
    return flip if _unbalanced(flip) < _unbalanced(toks) else toks


def _sig(kind, text):
    if kind == "A":
        return "A%d" % len(text)
    if kind == "L":
        return "L:#" if text.isdigit() else "L:" + text.lower()
    return text


def keys(toks):
    """[(word before, bracket, word after)], None at a line's end."""
    words = [(k, t) for k, t in toks if k in "AL" or t in BR]
    out = []
    for i, (k, t) in enumerate(words):
        if t not in BR:
            continue
        if t == "(" and i + 2 < len(words) and NOTE.fullmatch(words[i + 1][1]) \
                and words[i + 2][1] == ")":
            continue
        if t == ")" and i >= 2 and NOTE.fullmatch(words[i - 1][1]) \
                and words[i - 2][1] == "(":
            continue
        p = words[i - 1] if i > 0 else None
        n = words[i + 1] if i + 1 < len(words) else None
        out.append((_sig(*p) if p else None, t, _sig(*n) if n else None))
    return out


def text_keys(text):
    return keys([it[:2] for it in _items([(c, 0, 0) for c in text])])


def ours_text(docx):
    """Every paragraph's text: body, notes, headers, footers."""
    paras = []
    with zipfile.ZipFile(docx) as z:
        for n in z.namelist():
            if not re.match(r"word/(document|footnotes|header\d*|footer\d*)\.xml", n):
                continue
            x = z.read(n).decode("utf-8")
            for p in re.findall(r"<w:p[ >].*?</w:p>", x, re.S):
                t = "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", p))
                paras.append(t.replace("&amp;", "&").replace("&lt;", "<")
                             .replace("&gt;", ">"))
    return paras


def page_lines(page):
    """(text, chars) for each printed Arabic line holding a bracket: the
    extractor's lines on one baseline joined."""
    rows = []
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            if ln["dir"][0] < 0.9:
                continue
            y0, y1 = ln["bbox"][1], ln["bbox"][3]
            chars = [(c["c"], c["bbox"][0], c["bbox"][2]) for s in ln["spans"]
                     for c in s["chars"] if s["size"] > 0]
            for r in rows:
                if min(r[1], y1) - max(r[0], y0) > 0.6 * min(r[1] - r[0], y1 - y0):
                    r[2].extend(chars)
                    r[0], r[1] = min(r[0], y0), max(r[1], y1)
                    break
            else:
                rows.append([y0, y1, chars])
    for _, _, chars in rows:
        txt = "".join(c for c, _, _ in chars)
        a = len(AR.findall(txt))
        if any(c in BR for c in txt) and a and len(re.findall(r"[A-Za-z]", txt)) <= a:
            yield txt, chars


def _take(pool, k):
    """Take one match for key `k` from `pool` (a Counter of whole keys); a
    key with a side missing matches any key agreeing on the side it has."""
    if k[0] is not None and k[2] is not None:
        if pool[k] > 0:
            pool[k] -= 1
            return True
        return False
    if k[0] is None and k[2] is None:
        return True
    for q, n in pool.items():
        if n > 0 and q[1] == k[1] and k[0] in (None, q[0]) and k[2] in (None, q[2]):
            pool[q] -= 1
            return True
    return False


def score(pdf, docx):
    """-> (brackets, found in ours, found in the PDF's stored order, misses
    [(page, key, line)])."""
    ours = collections.Counter()
    for para in ours_text(docx):
        ours.update(text_keys(para))
    truth, stored = [], collections.Counter()
    with pymupdf.open(pdf) as doc:
        for pno, page in enumerate(doc):
            for txt, chars in page_lines(page):
                truth += [(pno, k, txt) for k in keys(unmirror(drawn(chars)))]
                stored.update(text_keys(txt))
    # whole keys first, so a half key does not take a whole key's match
    truth.sort(key=lambda t: t[1][0] is None or t[1][2] is None)
    found = kept = 0
    misses = []
    for pno, k, txt in truth:
        if _take(ours, k):
            found += 1
        else:
            misses.append((pno, k, txt))
        kept += _take(stored, k)
    return len(truth), found, kept, misses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="thesis")
    ap.add_argument("--work", help="the eval folder holding docx/ (default: "
                    "out/work/eval-thesis, or eval-reg for --set regression)")
    ap.add_argument("--show", type=int, default=0, help="print N misses")
    a = ap.parse_args()
    from harness.eval import files_for
    work = Path(a.work or ("out/work/eval-reg" if a.set == "regression"
                           else "out/work/eval-thesis"))
    total = found = kept = 0
    misses = []
    for f in files_for(a.set):
        d = work / "docx" / (Path(f).stem + ".docx")
        if not d.exists():
            continue
        t, fo, ke, mi = score(f, d)
        total, found, kept = total + t, found + fo, kept + ke
        misses += [(Path(f).stem,) + m for m in mi]
        pct = lambda n: n / t * 100 if t else 100.0
        print(f"{Path(f).stem:<45} brackets {t:5d}  ours right {pct(fo):5.1f}%"
              f"  as stored {pct(ke):5.1f}%")
    if total:
        print(f"ALL brackets {total}  ours right {found / total * 100:.1f}%"
              f"  as stored {kept / total * 100:.1f}%")
    random.seed(1)
    for m in random.sample(misses, min(a.show, len(misses))):
        print(m[0], "page", m[1], m[2], "|", m[3][:110])


if __name__ == "__main__":
    main()
