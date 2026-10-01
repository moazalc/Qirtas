"""Numbers the PDF draws as one thing and stores as another (FLAGS 13).

    python -m convert.digits some.pdf

`z21358439.pdf` page 8 shows the 1951 Geneva Convention and its 1967
protocol; its stored text says 1901 and 1922. We copy the stored text, so the
Word file says 1901 - and every score agrees with it, because the scorer reads
the same stored text. Decided 2026-09-21 (Moaz): convert, and warn which pages.

## How it knows

For every character the PDF draws, PyMuPDF's text trace gives both the
character the PDF CLAIMS (its ToUnicode table) and the GLYPH it actually draws.
The embedded font has its own table, character -> glyph. Ask it which digit
that glyph is:

    stored "0", drawn glyph 24     the font: "0" is glyph 19, glyph 24 is "5"

So the page shows a 5 where the text says 0. Only a glyph the font itself
names as a DIFFERENT digit counts; a glyph it names as nothing proves nothing.

A font whose table was renumbered by a subsetter disagrees about every digit
for no fault of the PDF, so a font counts only if, somewhere in the file, at
least one of its digits agrees (the partial disagreement `harness/digits.py`
found first, judged here per character drawn rather than per table entry).

Only fonts that are embedded, and on a page where every font sharing that name
agrees about its digits: a span names its font but not which one.

A number stored turned round (2014 as 4102, FLAGS 1) is found too where the
PDF pairs its stored characters with the glyphs in drawing order - the trace
then shows stored "4" on a glyph that is a 2. The reader turns some of those
back (`z22245438`'s "02"), so the message states what the PDF stores and
shows, and asks to check, rather than claiming what the Word file says.

Looked at on 2026-10-01: 18 of 338 corpus files, four of them theses; about 45
numbers cropped from the pages, every one showing what this said it shows.
Not seen: a font with no usable table, or one not embedded.

It does not correct anything. The check knows what the page draws, but a
silent rewrite of numbers needs its own independent check first (FLAGS 13,
the spelling repair's lesson, FLAGS 20 and 22).
"""
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

ON = os.environ.get("QIRTAS_DIGITS_WARN", "1") != "0"
DIGITS = "0123456789"
SHOWN = 3          # numbers quoted per page in the message
PAGES = 10         # pages quoted; the rest only listed


@dataclass
class Wrong:
    page: int                     # 1-based
    stored: str                   # the number as the text says it
    drawn: str                    # the number as the page shows it
    box: tuple = ()               # where on the page


@dataclass
class Fonts:
    """Each embedded font's own digit table, by the name spans carry."""
    tables: dict = field(default_factory=dict)    # xref -> (own name, {digit: gid})

    def load(self, doc, page):
        """-> {name: digit table} for the names on this page that can be
        judged: every font of that name is embedded and they agree on which
        glyph each digit is. A span names its font but not which one, and
        `z20026356` draws its year in a system Times that shares the name of
        an embedded one. `z21358439` has two embedded Traditional Arabics,
        with the same digits - fine - and `z21490618` subsets that each carry
        some of the digits, agreeing where they overlap.

        A span carries the name inside the font where there is one ("ArialMT"),
        which need not be the one the PDF lists ("Arial Regular"): both count."""
        names = defaultdict(list)
        for xref, *_rest in page.get_fonts(full=True):
            listed = _rest[2].split("+", 1)[-1]
            if xref not in self.tables:
                self.tables[xref] = self._table(doc, xref)
            own, table = self.tables[xref]
            for name in {listed, own} - {""}:
                names[name].append(table)
        return {n: m for n, ts in names.items() if (m := _merge(ts))}

    @staticmethod
    def _table(doc, xref):
        try:
            buf = doc.extract_font(xref)[3]
            font = pymupdf.Font(fontbuffer=buf) if buf else None
        except Exception:
            return "", {}
        table = {}
        if font is not None:
            for d in DIGITS:
                try:
                    g = font.has_glyph(ord(d))
                except Exception:
                    g = 0
                if g:
                    table[d] = g
        return (_own_name(buf) if table else ""), table


def _own_name(buf):
    """The PostScript name inside the font, which is what a span carries."""
    import io
    from fontTools.ttLib import TTFont
    try:
        name = TTFont(io.BytesIO(buf), lazy=True)["name"].getDebugName(6)
    except Exception:
        return ""
    return (name or "").split("+", 1)[-1]


def _merge(tables):
    """One digit table from several fonts of one name, or {} if any is
    missing or two disagree about a digit or a glyph."""
    if not all(tables):
        return {}
    out = {}
    for t in tables:
        for d, g in t.items():
            if out.get(d, g) != g:
                return {}
            out[d] = g
    return out if len(set(out.values())) == len(out) else {}


def _read(gid, table):
    """Which digit one drawn glyph is, by the font: None if no digit."""
    return next((d for d, g in table.items() if g == gid), None)


def scan(path):
    """-> [Wrong], one per number the page draws differently from the text."""
    try:
        doc = pymupdf.open(path)
    except Exception:
        return []
    fonts = Fonts()
    found = []               # (page, name, [(stored, drawn or None, box)])
    agree = defaultdict(int)
    with doc:
        for page in doc:
            judged = fonts.load(doc, page)
            for span in page.get_texttrace():
                name = span.get("font", "")
                table = judged.get(name)
                if not table:
                    continue
                run = []
                for c in span["chars"]:
                    ch = chr(c[0]) if c[0] >= 0 else ""
                    if ch in DIGITS and ch:
                        drawn = _read(c[1], table)
                        if drawn == ch:
                            agree[name] += 1
                        run.append((ch, drawn, c[3]))
                    elif run:
                        found.append((page.number + 1, name, run))
                        run = []
                if run:
                    found.append((page.number + 1, name, run))
    out = []
    for pno, name, run in found:
        if not agree[name]:
            continue                   # renumbered subset: proves nothing
        if not any(d is not None and d != s for s, d, _b in run):
            continue
        box = pymupdf.Rect(run[0][2])
        for *_sd, b in run:
            box |= pymupdf.Rect(b)
        out.append(Wrong(pno, "".join(s for s, _d, _b in run),
                         "".join(d if d is not None else s for s, d, _b in run),
                         tuple(box)))
    return out


def message(wrong):
    """The note printed after converting: which pages, and what they show."""
    if not wrong:
        return ""
    pages = defaultdict(list)
    for w in wrong:
        if (w.stored, w.drawn) not in pages[w.page]:
            pages[w.page].append((w.stored, w.drawn))
    lines = [f"Check the numbers on {_count(len(pages))} against the PDF. The "
             f"PDF stores them differently from how its pages show them, and "
             f"the Word file is made from what is stored:"]
    for p in sorted(pages)[:PAGES]:
        seen = pages[p][:SHOWN]
        more = " ..." if len(pages[p]) > SHOWN else ""
        shown = ", ".join(f"{d} (stored as {s})" for s, d in seen)
        lines.append(f"  page {p}: {shown}{more}")
    if len(pages) > PAGES:
        rest = sorted(pages)[PAGES:]
        lines.append(f"  and {len(rest)} more page{'s' if len(rest) > 1 else ''}: "
                     f"{', '.join(str(p) for p in rest)}")
    return "\n".join(lines)


def _count(n):
    return "1 page" if n == 1 else f"{n} pages"


def main():
    for f in sys.argv[1:]:
        w = scan(f)
        print(f"{Path(f).name}: {len(w)} number(s)")
        if w:
            print(message(w))


if __name__ == "__main__":
    main()
