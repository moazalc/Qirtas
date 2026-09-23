#!/usr/bin/env python3
"""Recover the words of a PDF whose font says the wrong letters (FLAGS 23).

A PDF keeps two things for every letter: the SHAPE drawn on the page, by its
number in the font (the glyph id), and a table saying which character each
shape is, which is what copying, searching and every text reader use. Some
files carry a wrong table. The page looks right and reads as gibberish:
z20375390 prints يعد السرطان مشكلة صحية كبيرة and stores
يعد السررررررشكلة صحرررررررة - its table has the stretching stroke Word uses to
justify a line down as ر, and a quarter of its letters as spaces.

The shapes are still right. When the font is one installed here - these
files ask for Simplified Arabic, Traditional Arabic, Sakkal Majalla - its own
tables say which letter each shape number is: the character map for the
plain letters, and the shaping rules (GSUB) for the beginning, middle and end
forms and the joined pairs such as لا. Word keeps the original shape numbers
when it embeds part of a font, so the installed font's numbers are the
file's numbers. That is checked, not assumed: the widths the PDF records for
each shape have to match the installed font's before anything is changed.

The repair writes a corrected table into a copy of the PDF, and the
converter AND the checker both read that copy. Repairing only our side would
make every recovered word count as lost against the gibberish original.
"""
import hashlib
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

# A font is repaired only when this share of its shapes have the installed
# font's width, which is what shows the shape numbers are the same font's.
SAME_WIDTHS = 0.9
# The widest shape with no letter of its own that is read as a stretching
# stroke, in 1/1000 em: Times New Roman's and Arial's are 125.
KASHIDA = 150
# Letters stored as a letter of another shape before a font counts as
# scrambled rather than merely missing some.
SCRAMBLED = 3
TATWEEL = "\u0640"
ALEF = chr(0x0627)
HAMZA_ALEFS = {chr(0x0622), chr(0x0623), chr(0x0625)}
_BASIC = re.compile(r"[ء-ي]")
_LETTER_OR_MARK = re.compile("[" + chr(0x0621) + "-" + chr(0x0652) + "]")
_ARABIC = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")

# Fonts of religious signs drawn as one shape each, whose table names the
# shape by a private code that means nothing outside the font: the reader
# gets a box, Word a Latin letter. Named by looking at each shape
# (Moaz's theses, 2026-09-22). Each is named by ONE character: named by the
# three words it stands for, the line holding it came out backwards in
# PyMuPDF (الفصل الثالث page 20) and the gate fell to 97.9%.
SYMBOL_FONTS = {
    "agaarabesque": {chr(0xF072): chr(0xFDFA),      # ﷺ
                     chr(0xF074): chr(0xFD47)},     # رضي الله عنه
}
# Signs no font here draws (U+FD47 is Unicode 14): written out, by the writer
# and by the checker alike.
SPELLED = {chr(0xFD47): "رضي الله عنه"}


def spell_out(text):
    for sign, words in SPELLED.items():
        if sign in (text or ""):
            text = text.replace(sign, words)
    return text


# Bumped when the repair changes, so the cached copies are made again.
REPAIR_VERSION = "5"

_INDEX = None
_MAPS = {}


def _font_dirs():
    windir = os.environ.get("WINDIR", r"C:\Windows")
    local = os.environ.get("LOCALAPPDATA", "")
    return [Path(windir) / "Fonts",
            Path(local) / "Microsoft" / "Windows" / "Fonts"]


def _key(name):
    """PostScript name without the subset tag: BCDKEE+SimplifiedArabic-Bold.
    Also without Monotype's MT/PSMT, which some writers keep and some drop:
    "Arial" and "ArialMT", "Times New Roman,Bold" and "TimesNewRomanPS-BoldMT".
    """
    name = name.split("+", 1)[-1]
    k = re.sub(r"[^a-z0-9]", "", name.lower())
    k = re.sub(r"mt$", "", k)
    return re.sub(r"ps(?=(bold|italic|bolditalic)?$)", "", k)


def _index():
    """Installed fonts by PostScript name. Read once per process.

    Also by family name, for a regular face only: some writers name the
    font by its family, "(A) Arslan Wessam B" for AArslanWessamB-AArslan...
    A family name never takes a key a PostScript name holds."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    from fontTools.ttLib import TTFont
    _INDEX, family = {}, {}
    for d in _font_dirs():
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.suffix.lower() not in (".ttf", ".otf"):
                continue
            try:
                with TTFont(str(f), lazy=True) as t:
                    n = t["name"]
                    ps, fam, style = (n.getDebugName(6), n.getDebugName(1),
                                      n.getDebugName(2))
            except Exception:
                continue
            if ps:
                _INDEX.setdefault(_key(ps), str(f))
            if fam and (style or "").lower() == "regular":
                family.setdefault(_key(fam), str(f))
    for k, f in family.items():
        _INDEX.setdefault(k, f)
    return _INDEX


def _path(name):
    """The installed font file for a PDF's name of it, or None.

    Word cuts a long PostScript name at 24 characters -
    AF_Diwani-NormalTraditio - so a name of that length that begins exactly
    one installed font's is that font."""
    k = _key(name)
    index = _index()
    if k in index:
        return index[k]
    if len(name.split("+", 1)[-1]) >= 24:
        found = {f for key, f in index.items() if key.startswith(k)}
        if len(found) == 1:
            return found.pop()
    return None


# The PDF standard's built-in fonts, by the Windows font Word would use.
_BUILT_IN = {"timesroman": "Times New Roman", "times": "Times New Roman",
             "helvetica": "Arial", "courier": "Courier New"}
_FAMILIES = {}


def family(name):
    """The name Word knows an installed font by, for a PDF's name of it:
    TimesNewRomanPSMT -> Times New Roman, SakkalMajalla -> Sakkal Majalla.
    Word looks fonts up by that name; given the PDF's own it finds nothing
    and substitutes. A font not installed keeps the name it came with."""
    k = _key(name)
    if k in _BUILT_IN:
        return _BUILT_IN[k]
    path = _path(name)
    if path is None:
        return name
    if path not in _FAMILIES:
        from fontTools.ttLib import TTFont
        try:
            with TTFont(path, lazy=True) as t:
                n = t["name"]
                _FAMILIES[path] = n.getDebugName(16) or n.getDebugName(1) or name
        except Exception:
            _FAMILIES[path] = name
    return _FAMILIES[path]


def reference(name):
    """(glyph id -> text, glyph id -> advance in 1/1000 em) for an installed
    font, or None when it is not installed."""
    path = _path(name)
    if path is None:
        return None
    if path in _MAPS:
        return _MAPS[path]
    from fontTools.ttLib import TTFont
    with TTFont(path, lazy=True) as t:
        order = t.getGlyphOrder()
        gid = {g: i for i, g in enumerate(order)}
        seen = {}
        for cp, g in (t.getBestCmap() or {}).items():
            seen.setdefault(gid[g], set()).add(_plain(chr(cp)))
        _shaping(t, gid, seen)
        text = {g: _best(c) for g, c in seen.items()}
        upem = t["head"].unitsPerEm
        widths = {gid[g]: a * 1000.0 / upem
                  for g, (a, _) in t["hmtx"].metrics.items()}
    _MAPS[path] = (text, widths)
    return _MAPS[path]


FORMS = ("init", "medi", "fina", "isol")
_FORMS = {}


def forms(name):
    """glyph id -> {"init", "medi", "fina", "isol"}: the forms of its letter
    a shape is drawn for, in an installed font; None when it is not installed.

    As the font's own shaping features say: the shape an `init` or `medi` rule
    produces joins the letter after it, `medi` or `fina` the letter before. A
    shape can serve several forms - Arial draws ب the same at the start and
    in the middle of a word - so all of them are kept, and only a shape whose
    every form joins is evidence of a join. A shape reached from one of them
    by a later rule - a contextual alternate - keeps its forms. A shape no
    such rule produces is absent: the cmap's own shape, or a ligature.
    """
    path = _path(name)
    if path is None:
        return None
    if path in _FORMS:
        return _FORMS[path]
    from fontTools.ttLib import TTFont
    out = {}
    with TTFont(path, lazy=True) as t:
        gid = {g: i for i, g in enumerate(t.getGlyphOrder())}
        table = t["GSUB"].table if "GSUB" in t else None
        if table is not None and table.FeatureList and table.LookupList:
            tags = {}
            for rec in table.FeatureList.FeatureRecord:
                for i in rec.Feature.LookupListIndex:
                    tags.setdefault(i, set()).add(rec.FeatureTag)
            single = {}
            for i, lookup in enumerate(table.LookupList.Lookup):
                for st in lookup.SubTable:
                    kind = lookup.LookupType
                    if kind == 7:
                        kind, st = st.ExtSubTable.LookupType, st.ExtSubTable
                    if kind == 1:
                        single.setdefault(i, []).extend(st.mapping.items())
            for i, pairs in single.items():
                for tag in sorted(tags.get(i, set()) & set(FORMS)):
                    for _, b in pairs:
                        out.setdefault(gid[b], set()).add(tag)
            for _ in range(3):
                for i, pairs in single.items():
                    if tags.get(i, set()) & set(FORMS):
                        continue
                    for a, b in pairs:
                        if gid[a] in out:
                            out.setdefault(gid[b], set()).update(out[gid[a]])
    _FORMS[path] = out
    return out


def _rank(s):
    """Which of several names for one shape a writer most likely typed.
    Arabic letters and marks first; then Persian and Urdu letters that share a
    shape with them (ی with ي, ھ with ه); then single-character symbols such as
    ﷲ, which Word does not type for الله."""
    worst = 0
    for ch in s:
        o = ord(ch)
        if 0x0621 <= o <= 0x0652 or o < 0x0600 or 0x0660 <= o <= 0x0669:
            continue
        worst = max(worst, 2 if o >= 0xFB50 else 1)
    return worst, len(s) == 0, s


def _best(names):
    return min(names, key=_rank)


# Single signs for words Word users type letter by letter.
SIGNS = {chr(0xFDF2): "".join(map(chr, (0x0627, 0x0644, 0x0644, 0x0647))),
         chr(0xFDF4): "".join(map(chr, (0x0645, 0x062D, 0x0645, 0x062F)))}

# Letters that share a base shape and differ only in their dots or hamza.
_SKELETON = {}
for _group in ((0x0628, 0x062A, 0x062B, 0x0646, 0x064A, 0x0649, 0x0626),
               (0x062C, 0x062D, 0x062E), (0x062F, 0x0630), (0x0631, 0x0632),
               (0x0633, 0x0634), (0x0635, 0x0636), (0x0637, 0x0638),
               (0x0639, 0x063A), (0x0641, 0x0642), (0x0647, 0x0629),
               (0x0627, 0x0623, 0x0625, 0x0622), (0x0648, 0x0624)):
    for _o in _group:
        _SKELETON[chr(_o)] = _group[0]


def _plain(text):
    return "".join(map(_letter, text))


def _letter(ch):
    """A display form as its letter; the honorifics (FDF0-FDFF) and the Quran
    brackets stay as typed. Except the signs for Allah and Muhammad: Word
    users type the letters, and a font draws them as one shape."""
    if ch in SIGNS:
        return SIGNS[ch]
    if 0xFDF0 <= ord(ch) <= 0xFDFF or ord(ch) in (0xFD3E, 0xFD3F):
        return ch
    # The isolated forms of the vowel marks fold to a space and the mark.
    return unicodedata.normalize("NFKC", ch).lstrip(" ") or ch


def _shaping(t, gid, seen):
    """Name the shapes only the shaping rules reach: letter forms, joined
    pairs. Repeated until nothing new is learned, since one rule's output is
    the next one's input. A shape both reaches from a letter and is given a
    name directly keeps every name; _best chooses."""
    if "GSUB" not in t:
        return
    lookups = t["GSUB"].table.LookupList
    if lookups is None:
        return
    subs = []
    for lookup in lookups.Lookup:
        for st in lookup.SubTable:
            kind = lookup.LookupType
            if kind == 7:                    # extension: the real table inside
                kind, st = st.ExtSubTable.LookupType, st.ExtSubTable
            subs.append((kind, st))

    named = set(seen)

    def add(g, name):
        names = seen.setdefault(g, set())
        if name in names:
            return False
        names.add(name)
        return True

    for _ in range(6):
        grew = False
        for kind, st in subs:
            if kind == 1:
                pairs = [(a, [b]) for a, b in st.mapping.items()]
            elif kind == 2:
                # One shape split into several (إ as ا and a hamza below):
                # no piece is the whole letter, so none takes its name.
                pairs = [(a, bs) for a, bs in st.mapping.items()
                         if len(bs) == 1]
            elif kind == 3:
                pairs = list(st.alternates.items())
            elif kind == 4:
                for first, ligs in st.ligatures.items():
                    for lig in ligs:
                        parts = [gid[p] for p in [first] + list(lig.Component)]
                        # A shape the character map already names keeps
                        # that name: the rules can reach it by odd routes.
                        if gid[lig.LigGlyph] in named:
                            continue
                        if all(p in seen for p in parts):
                            grew |= add(gid[lig.LigGlyph],
                                        "".join(_best(seen[p]) for p in parts))
                continue
            else:
                continue
            for a, bs in pairs:
                if gid[a] in seen:
                    for b in bs:
                        grew |= add(gid[b], _best(seen[gid[a]]))
        if not grew:
            break


# -- reading and writing the PDF's own table --------------------------------

_BFCHAR = re.compile(r"beginbfchar(.*?)endbfchar", re.S)
_BFRANGE = re.compile(r"beginbfrange(.*?)endbfrange", re.S)
_HEX = re.compile(r"<([0-9A-Fa-f]*)>")


def _utf16(h):
    b = bytes.fromhex(h)
    return b.decode("utf-16-be", errors="replace")


def read_tounicode(stream):
    """code -> text from a ToUnicode CMap."""
    s = stream.decode("latin-1")
    out = {}
    for body in _BFCHAR.findall(s):
        hx = _HEX.findall(body)
        for a, b in zip(hx[0::2], hx[1::2]):
            out[int(a, 16)] = _utf16(b)
    for body in _BFRANGE.findall(s):
        for line in body.strip().splitlines():
            m = re.match(r"\s*<(\w+)>\s*<(\w+)>\s*(.*)", line)
            if not m:
                continue
            lo, hi, rest = int(m.group(1), 16), int(m.group(2), 16), m.group(3)
            if rest.strip().startswith("["):
                for k, h in enumerate(_HEX.findall(rest)):
                    out[lo + k] = _utf16(h)
            else:
                h = _HEX.findall(rest)[0]
                base = int(h, 16)
                for k in range(hi - lo + 1):
                    out[lo + k] = _utf16(f"{base + k:0{len(h)}X}")
    return out


def write_tounicode(table):
    lines = ["/CIDInit /ProcSet findresource begin", "12 dict begin",
             "begincmap", "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS)"
             " /Supplement 0 >> def", "/CMapName /Adobe-Identity-UCS def",
             "/CMapType 2 def", "1 begincodespacerange", "<0000> <FFFF>",
             "endcodespacerange"]
    items = sorted(table.items())
    for k in range(0, len(items), 100):
        chunk = items[k:k + 100]
        lines.append(f"{len(chunk)} beginbfchar")
        for code, text in chunk:
            lines.append(f"<{code:04X}> <{text.encode('utf-16-be').hex().upper()}>")
        lines.append("endbfchar")
    lines += ["endcmap", "CMapName currentdict /CMap defineresource pop",
              "end", "end"]
    return "\n".join(lines).encode("latin-1")


def _descendant(doc, xref):
    """The CIDFont under a composite font, or None."""
    kind, desc = doc.xref_get_key(xref, "DescendantFonts")
    if kind == "xref":              # the array itself is a separate object
        desc = doc.xref_object(int(desc.split()[0]))
    m = re.search(r"(\d+) 0 R", desc)
    return int(m.group(1)) if m else None


DIGIT_SETS = {"arabic": 0x0660, "persian": 0x06F0}


def shown_digits(pdf_path):
    """Which digits the pages SHOW: "arabic" (٠١٢), "persian" (۰۱۲) or "".

    Word stores a typed 121 as 121 and, with its numbers set to Hindi or
    Context, draws ١٢١ - so the text says one thing and the page another,
    and our file showed 121 where Moaz's theses show ١٢١ (N4). The font
    embedded in the PDF knows which shape it drew: in those theses the
    shape stored as 5 is the embedded Arial's `uni0665`. Only fonts whose
    codes are shape numbers can be asked, which is what Word embeds for
    Arabic text.
    """
    from fontTools.ttLib import TTFont
    import io
    count = {"": 0, **{k: 0 for k in DIGIT_SETS}}
    with pymupdf.open(pdf_path) as doc:
        fonts = {f[0] for p in doc for f in p.get_fonts()}
        for xref in sorted(fonts):
            try:
                if doc.xref_get_key(xref, "Subtype")[1] != "/Type0" or \
                        doc.xref_get_key(xref, "Encoding")[1] != "/Identity-H":
                    continue
                kind, tu = doc.xref_get_key(xref, "ToUnicode")
                desc = _descendant(doc, xref)
                if kind != "xref" or desc is None:
                    continue
                c2g = doc.xref_get_key(desc, "CIDToGIDMap")
                if c2g[0] == "xref" or c2g[0] == "name" and c2g[1] != "/Identity":
                    continue
                fd = doc.xref_get_key(desc, "FontDescriptor")
                ff = doc.xref_get_key(int(fd[1].split()[0]), "FontFile2")
                if ff[0] != "xref":
                    continue
                digits = {c: t for c, t in read_tounicode(
                    doc.xref_stream(int(tu.split()[0]))).items()
                    if len(t) == 1 and "0" <= t <= "9"}
                if not digits:
                    continue
                with TTFont(io.BytesIO(doc.xref_stream(int(ff[1].split()[0]))),
                            lazy=True) as t:
                    order = t.getGlyphOrder()
                    # A shape can stand for several characters: Arial draws
                    # Arabic ٤ and Persian ۴ alike only for some digits.
                    back = {}
                    for u, g in (t.getBestCmap() or {}).items():
                        back.setdefault(g, set()).add(u)
            except Exception:
                continue
            for gid, typed in digits.items():
                if gid >= len(order):
                    continue
                g = order[gid]
                us = set(back.get(g, ()))
                if re.fullmatch(r"uni[0-9A-F]{4}", g):
                    us.add(int(g[3:], 16))
                if ord(typed) in us:
                    count[""] += 1
                    continue
                for kind, zero in DIGIT_SETS.items():
                    if zero + int(typed) in us:
                        count[kind] += 1
                        break
    best = max(count, key=count.get)
    return best if count[best] else ""


def _widths(doc, descendant):
    """cid -> width from a CIDFont's /W array."""
    out = {}
    kind, w = doc.xref_get_key(descendant, "W")
    if kind == "xref":
        w = doc.xref_object(int(w.split()[0]))
    elif kind != "array":
        return out
    toks = re.findall(r"\[|\]|[-\d.]+", w)
    i = 0
    while i < len(toks):
        if toks[i] in "[]":
            i += 1
            continue
        first = int(float(toks[i]))
        if i + 1 < len(toks) and toks[i + 1] == "[":
            j = i + 2
            while toks[j] != "]":
                out[first + j - i - 2] = float(toks[j])
                j += 1
            i = j + 1
        elif i + 2 < len(toks):
            last, width = int(float(toks[i + 1])), float(toks[i + 2])
            for c in range(first, last + 1):
                out[c] = width
            i += 3
        else:
            break
    return out


def _same(a, b):
    """Stored and true text agree, allowing for how either was spelled."""
    fold = lambda s: _plain(s).replace(TATWEEL, "")
    a, b = fold(a), fold(b)
    if a == b or sorted(a) == sorted(b):
        return True
    # A font that draws the hamza as a mark of its own draws أ إ آ with the
    # plain alef shape, and the letter stored for it is the whole one.
    return b == ALEF and a in HAMZA_ALEFS


def diagnose(doc, xref):
    """For one font: (repair table or None, why)."""
    if doc.xref_get_key(xref, "Subtype")[1] != "/Type0":
        return None, "not a composite font"
    if doc.xref_get_key(xref, "Encoding")[1] != "/Identity-H":
        return None, "codes are not shape numbers"
    kind, tu = doc.xref_get_key(xref, "ToUnicode")
    if kind != "xref":
        return None, "no table"
    name = doc.xref_get_key(xref, "BaseFont")[1].lstrip("/")
    if _key(name) in SYMBOL_FONTS:
        stored = read_tounicode(doc.xref_stream(int(tu.split()[0])))
        signs = SYMBOL_FONTS[_key(name)]
        fixes = {c: signs[t] for c, t in stored.items() if t in signs}
        if not fixes:
            return None, "fine"
        return {**stored, **fixes}, f"{name}: {len(fixes)} signs named"
    desc = _descendant(doc, xref)
    if desc is None:
        return None, "no descendant font"
    c2g = doc.xref_get_key(desc, "CIDToGIDMap")
    if c2g[0] not in ("null", "name") or c2g[0] == "name" and c2g[1] != "/Identity":
        return None, "codes are renumbered"
    ref = reference(name)
    if ref is None:
        return None, f"{name} not installed"
    text, advance = ref
    stored = read_tounicode(doc.xref_stream(int(tu.split()[0])))
    # A scrambled font stores letters as other letters of a different shape:
    # م as س, و as ك. One that does not is right apart from its blanks and
    # junk, and there a stored letter is not second-guessed on its dots.
    scrambled = sum(1 for c in stored if c in text
                    and len(stored[c]) == 1 and _BASIC.match(stored[c])
                    and len(text[c]) == 1 and _BASIC.match(text[c])
                    and _SKELETON.get(stored[c]) != _SKELETON.get(text[c]))
    scrambled = scrambled >= SCRAMBLED
    fixes = {c: text[c] for c in stored
             if c in text and _ARABIC.search(text[c])
             and not _same(stored[c], text[c])
             and _trust(stored[c], text[c], scrambled)}
    # Two a font can say plainly are not letters, stored as one all the same
    # (z20397518, z20276145): the stretching stroke Word adds to justify a
    # line - no letter of its own, an eighth of an em - stored as the letter
    # it followed, so شبكات reads شبببببكات; and a space stored as ا.
    for c, s in stored.items():
        if len(s) == 1 and _BASIC.match(s):
            if c not in text and advance.get(c, KASHIDA + 1) <= KASHIDA:
                fixes[c] = TATWEEL
            elif text.get(c) == " ":
                fixes[c] = " "
    if not fixes:
        return None, "fine"
    widths = _widths(doc, desc)
    both = [c for c in stored if c in widths and c in advance]
    same = [c for c in both if abs(widths[c] - advance[c]) <= 2]
    if not both or len(same) < SAME_WIDTHS * len(both):
        return None, f"{name}: shapes are not the installed font's "                      f"({len(same)}/{len(both)} widths agree)"
    # The stretching stroke Word draws to justify a line stays one: an empty
    # entry makes readers fall back to the code's Latin-1 letter (») instead.
    # The checker ignores it, and in Word it stretches the word as the page did.
    return {**stored, **fixes}, f"{name}: {len(fixes)} shapes stored wrong"


def _trust(stored, true, scrambled=False):
    """Replace what the file says with what the shape is? Only where the
    shape's name is certain, or what the file says is plainly not it.

    A single letter's shape is named by the font's own character map and
    form rules, which do not go wrong. A joined pair's name comes from the
    shaping rules, which can reach one shape by several routes - so it
    replaces only a stored value that is plainly junk: a space, a Latin or
    control character, a stray digit or mark. Digits the file stores are kept:
    Word displays a typed 2 as ٢ without changing what was typed."""
    if any(ch.isdigit() for ch in stored) and all(ch.isdigit() for ch in true):
        return False
    # Punctuation likewise: a typed ; is displayed as the Arabic one.
    if stored.strip() and all(ord(ch) < 0x80 and not ch.isalnum()
                              for ch in stored) and not _BASIC.search(true):
        return False
    # Junk: a blank, or anything that is not an Arabic letter or vowel mark -
    # Latin, controls, a digit inside a letter (ت١). A letter with its vowel
    # mark is NOT junk: fonts draw تِ as one shape, and the name the shaping
    # rules give such a shape can be wrong (تن).
    junk = not stored.strip() or any(not _LETTER_OR_MARK.match(ch)
                                     for ch in stored)
    if any(0x0653 <= ord(ch) <= 0x0655 for ch in true):
        # a hamza or madda drawn as a mark of its own: the letter it sits on
        # is stored whole already, and inserting it lands before the letter
        return False
    if len(true) != 1 or not _BASIC.match(true):
        # joined pairs, vowel marks: only over junk
        return junk
    # Some fonts draw the dots as marks of their own over a dotless base, so
    # the base shape of في can be named ڜ or ى. Where the stored letter has
    # the same base shape as the name, the stored letter is the better guess.
    if not scrambled and len(stored) == 1 \
            and _SKELETON.get(stored) == _SKELETON.get(true, true):
        return False
    return True


def repair(pdf_path, out_path):
    """Write a copy with every broken font's table corrected.
    Returns [(font, why)] for the fonts repaired; [] writes nothing."""
    done = []
    # Where the page itself can be read, it settles the shapes the file and
    # the installed font disagree on (convert/witness.py, FLAGS 25).
    try:
        from convert.witness import settle
        settled = settle(pdf_path)
    except Exception:
        settled = {}
    with pymupdf.open(pdf_path) as doc:
        fonts = {f[0] for p in doc for f in p.get_fonts()}
        for xref in sorted(fonts):
            table, why = settled[xref] if xref in settled                 else diagnose(doc, xref)
            if table is None:
                continue
            tu = int(doc.xref_get_key(xref, "ToUnicode")[1].split()[0])
            doc.update_stream(tu, write_tounicode(table))
            done.append((xref, why))
        if done:
            doc.save(str(out_path), garbage=0)
    return done


def repaired(pdf_path):
    """The PDF to read: a repaired copy when a font's table is wrong,
    otherwise the file itself. Cached by content, so the converter and the
    checker read the same copy."""
    pdf_path = str(pdf_path)
    h = hashlib.sha1(REPAIR_VERSION.encode())
    # A repair reads the installed fonts: one installed since changes it.
    h.update("|".join(sorted(_index())).encode())
    with open(pdf_path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    cache = Path(tempfile.gettempdir()) / "qirtas-glyphs"
    cache.mkdir(exist_ok=True)
    out = cache / f"{h.hexdigest()[:16]}.pdf"
    none = cache / f"{h.hexdigest()[:16]}.none"
    if out.exists():
        return str(out)
    if none.exists():
        return pdf_path
    try:
        fixed = repair(pdf_path, out)
    except Exception:
        # A file this cannot open or save is read as it is, which is what
        # happened before this existed.
        fixed = []
    if fixed:
        return str(out)
    none.touch()
    return pdf_path


def main():
    for p in sys.argv[1:]:
        with pymupdf.open(p) as doc:
            fonts = {f[0] for pg in doc for f in pg.get_fonts()}
            for x in sorted(fonts):
                table, why = diagnose(doc, x)
                print(f"{Path(p).name:<20} {x:>5}  "
                      f"{'REPAIR' if table else '      '}  {why}")


if __name__ == "__main__":
    main()
