#!/usr/bin/env python3
"""Does this PDF DISPLAY the numbers it STORES?

    python -m harness.digits --set dev --json out/runs/digits.json
    python -m harness.digits corpus/wild/z21358439.pdf -v

`z21358439.pdf` page 8 shows the 1951 Geneva Convention and its 1967 protocol.
Its text layer stores **1901** and **1922**. Also `المادة 3` as `المادة1`, and
`10 دجنبر 1948` as `14 دجنبر 1900`.

We copy the text layer faithfully, so the Word file carries the wrong dates -
and the scorer compares our 1901 against the source's 1901 and calls it 100%.
**No measurement here can see a fault that both sides share.** It is the same
blindness as the visual-order problem and worse in one respect: reversed text
is obviously broken to a reader, while a wrong date looks perfectly fine and
may be legally meaningful.

## How it is detected, without rendering anything

A PDF draws GLYPHS; the font's ToUnicode table claims what those glyphs mean.
When the table lies the two disagree and normal extraction cannot tell.

The embedded font carries its OWN opinion, in its cmap. Ask both.
`z21358439`'s `Traditional Arabic` says:

    ToUnicode      glyph 20 -> "1"   glyph 21 -> "2"   glyph 28 -> "9"
                   glyph 50 -> "0"
    the font       "1" -> glyph 20   "2" -> glyph 21   "9" -> glyph 28
                   "0" -> glyph 19,  and glyph 50 is no digit at all

Three entries agree and one does not. **That partial disagreement is the
signal.** A subsetter that renumbered every glyph would break ALL of them, so
"all mismatched" proves nothing; a table where most entries line up and one
does not cannot be explained that way. Glyph 50 is what the page draws as a
5 - which is how 1951 comes out as 1901.

Two earlier attempts were wrong and are recorded so nobody repeats them:

- **"Two glyphs claiming the same digit."** Sound in principle, but it came
  from a sloppy read of the CMap that paired hex tokens across entry
  boundaries. The properly parsed table is one to one.
- **"Digit glyphs should ascend with glyph id."** They do not, and need not:
  subsetters assign ids in order of first use, so a scattered run (20, 21, 28,
  50) is perfectly ordinary. This flagged healthy files.
- **Checking every font, not just Identity-H ones.** In a simple font the code
  is the CHARACTER code - 48 is "0" because that is ASCII - so comparing it to
  a glyph id disagrees on principle. This flagged most of the corpus.

## This finds CANDIDATES. Confirming one means looking at it.

All seven candidates in the 102-file dev set were checked by rendering a
number and reading it:

    z21358439   page shows 1951   text stores 1901   WRONG
    z19799068   page shows 2014   text stores 4102   WRONG
    z19799524   page shows 2014   text stores 4102   WRONG
    z21490618   page shows 2019   text stores 2112   WRONG
    z19773087   page shows 1989   text stores 1989   right, in the sample seen
    z20276145   page shows 3059   text stores 3059   right, in the sample seen
    z21813345   page shows 2020   text stores 2020   right, in the sample seen

So **4 of 102 files (3.9%) carry numbers that are verifiably wrong.**

Two cautions, and the second matters more than the first:

1. The test cannot see a table that is wrong in EVERY digit, or a font with no
   usable cmap. It under-counts.
2. **A single sample cannot clear a file.** `z21358439` prints 2026 correctly
   on page 1 and 1951-as-1901 on page 8. The three files above are "right
   where it was looked at", not "right".

Note also that two of the four are a different fault wearing the same mask:
2014 stored as 4102 is the digit run REVERSED, not mis-identified - the
visual-order problem of `FLAGS.md` 1, reaching the numbers.

## What it deliberately does not do

It does not correct anything. What to do about a file whose numbers cannot be
trusted - convert with a warning, or refuse - is a decision, and Moaz's to
make. This exists to put a number on how often it happens.
"""
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

BOLD, DIM, GRN, YEL, RED, OFF = ("\033[1m", "\033[2m", "\033[32m",
                                 "\033[33m", "\033[31m", "\033[0m")

PAIR = re.compile(r"<([0-9A-Fa-f]{2,8})>\s*<([0-9A-Fa-f]{4,})>")
RANGE = re.compile(r"<([0-9A-Fa-f]{2,8})>\s*<([0-9A-Fa-f]{2,8})>\s*<([0-9A-Fa-f]{4,})>")
DIGIT = range(0x30, 0x3A)


def _digit_map(doc, tu_xref):
    """{glyph code: digit character} for every entry that claims to be a digit."""
    try:
        cm = doc.xref_stream(tu_xref).decode("latin-1", "replace")
    except Exception:
        return {}
    out = {}
    for chunk in re.findall(r"beginbfchar(.*?)endbfchar", cm, re.S):
        for code, uni in PAIR.findall(chunk):
            u = int(uni[:4], 16)
            if u in DIGIT:
                out[int(code, 16)] = chr(u)
    for chunk in re.findall(r"beginbfrange(.*?)endbfrange", cm, re.S):
        for lo, hi, uni in RANGE.findall(chunk):
            u0 = int(uni[:4], 16)
            for k in range(int(lo, 16), int(hi, 16) + 1):
                u = u0 + (k - int(lo, 16))
                if u in DIGIT:
                    out[k] = chr(u)
    return out


def scan(path):
    """-> verdict for one file."""
    try:
        d = pymupdf.open(path)
    except Exception as e:
        return {"file": str(path), "error": f"{type(e).__name__}: {e}"}
    bad, weak, notes = False, False, []
    with d:
        seen = set()
        for page in d:
            try:
                fonts = page.get_fonts(full=True)
            except Exception:
                continue
            for f in fonts:
                xref = f[0]
                if xref in seen:
                    continue
                seen.add(xref)
                obj = d.xref_object(xref, compressed=True).replace("\n", " ")
                m = re.search(r"/ToUnicode (\d+) 0 R", obj)
                if not m:
                    continue
                # ONLY Identity-H. There the code in the content stream IS the
                # glyph number, which is what makes the comparison below mean
                # anything. In a simple font the code is the CHARACTER code -
                # 48 is "0" because it is ASCII - so comparing it against a
                # glyph id flags every healthy file in the corpus. The first
                # run of this tool did exactly that.
                if "/Identity-H" not in obj:
                    continue
                dm = _digit_map(d, int(m.group(1)))
                if len(dm) < 3:
                    continue           # too few to judge
                try:
                    _n, _e, _t, buf = d.extract_font(xref)
                    fnt = pymupdf.Font(fontbuffer=buf) if buf else None
                except Exception:
                    fnt = None
                if fnt is None:
                    continue           # no embedded font to cross-examine
                name = re.search(r"/BaseFont/([^/ >]+)", obj)
                name = name.group(1) if name else f"xref{xref}"
                agree, differ = [], []
                for code, claimed in sorted(dm.items()):
                    try:
                        g = fnt.has_glyph(ord(claimed))
                    except Exception:
                        continue
                    if not g:
                        continue       # font has no such digit; says nothing
                    (agree if g == code else differ).append((code, claimed, g))
                # Only a digit with NO correct route is proof of anything.
                #
                # A healthy file often carries spare entries: `z20397518` maps
                # glyphs 19-28 to 0-9 correctly AND has extra entries at 48-50
                # also claiming "0", "1", "2". Those spares disagree with the
                # cmap but nothing is broken, because the digit can still come
                # from the entry that is right - and rendering the page
                # confirmed it prints 2026 and stores 2026.
                #
                # `z21358439` is different: "0" is reachable ONLY through the
                # entry that disagrees. Every "0" it extracts must come from a
                # glyph the font says is not a "0" - and the page prints 1951
                # where the text says 1901.
                right = {c for _, c, _ in agree}
                only_wrong = [(code, c, g) for code, c, g in differ
                              if c not in right]
                if agree and only_wrong:
                    bad = True
                    for code, claimed, g in only_wrong[:3]:
                        notes.append(
                            f"{name}: {claimed!r} can ONLY come from glyph {code}, "
                            f"which the font says is not {claimed!r} "
                            f"(it puts {claimed!r} at glyph {g})")
                elif differ and not agree:
                    weak = True
                    notes.append(f"{name}: every digit disagrees with the font's "
                                 f"cmap - renumbered subset, or wholly wrong")
    return {"file": str(path), "untrustworthy": bad, "suspect": weak,
            "notes": notes}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--set", dest="which",
                    choices=["dev", "holdout", "regression"])
    ap.add_argument("--json")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    files = list(a.files)
    if a.which:
        from harness.eval import files_for
        files = files_for(a.which)
    if not files:
        ap.error("give some files or --set")

    rows = []
    for n, f in enumerate(files, 1):
        rows.append(scan(f))
        if n % 25 == 0:
            print(f"{DIM}  ...{n}/{len(files)}{OFF}", flush=True)

    ok = [r for r in rows if not r.get("error")]
    bad = [r for r in ok if r["untrustworthy"]]
    weak = [r for r in ok if r["suspect"] and not r["untrustworthy"]]

    print(f"\n{BOLD}{len(ok)} files scanned{OFF}")
    print(f"  {RED}candidates{OFF}                  {len(bad):4d}"
          f"   ({len(bad)/max(1,len(ok)):.1%})   a digit contradicts the font")
    print(f"  {YEL}cannot be cross-examined{OFF}    {len(weak):4d}"
          f"   ({len(weak)/max(1,len(ok)):.1%})   every digit differs: unprovable")
    print(f"  {GRN}no sign of trouble{OFF}          {len(ok)-len(bad)-len(weak):4d}")
    print(f"\n{DIM}  CANDIDATES, not verdicts. On the dev set 4 of 7 were real"
          f" when rendered and read;{OFF}")
    print(f"{DIM}  and a file that looks right in one place can still be wrong"
          f" elsewhere - see the docstring.{OFF}")
    for r in (bad + weak)[:15] if a.verbose else bad[:8]:
        print(f"\n  {Path(r['file']).name}")
        for note in r["notes"][:3]:
            print(f"      {note}")
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        print(f"\n{DIM}recorded in {a.json}{OFF}")


if __name__ == "__main__":
    main()
