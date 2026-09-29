#!/usr/bin/env python3
"""Which fonts does this PDF use that this computer does not have?

Asked before converting (Moaz, 2026-09-23). Word lays out every page with the
fonts installed here, and several repairs read the installed font to put a
wrong letter right (glyphs.py). A missing font does not stop the conversion -
Word puts another in its place - but the other face is wider or narrower, so
lines break elsewhere and pages spill, and a broken letter table cannot be
repaired against a font that is not there. So: name them, say where each can
be had, and let the person install them first if they want.

"Installed" is what the converter finds (glyphs._path: by the PDF's own
name, the family name, or the name Word cut at 24 characters) OR what
Windows lists as installed - which is what Word uses. The converter's index
reads single font files only, and Cambria Math lives in a collection
(cambria.ttc) on every Windows computer; asked alone, the index called it
missing.

    python -m convert.fonts some.pdf
"""
import collections
import re
import sys
import hashlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert import glyphs

ARABIC = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFC]")
# Less text than this in a font is a stray mark or a space: not worth asking.
MIN_CHARS = 20
# Names that are not fonts anyone can install: text an OCR program laid over
# a scan, and fonts whose names the PDF maker removed (F1, F2 ...).
NAMELESS = re.compile(r"^(GlyphLessFont|F\d+|T3Font_\d+|Type3)$", re.I)
STYLE = re.compile(r"[-,]?(Bold|Italic|BoldItalic|BoldOblique|Oblique|Regular|"
                   r"Black|Light|Medium|Semibold|SemiBold)$")

# Where to get a font, for the ones a person meets in Arabic documents. Kept
# to what is certain; anything else gets the plain advice at the bottom.
WINDOWS_ARABIC = ("Windows: Settings > Apps > Optional features > Add a feature > "
                  "\"Arabic Supplemental Fonts\"")
WHERE = {
    **{k: WINDOWS_ARABIC for k in (
        "simplifiedarabic", "traditionalarabic", "sakkalmajalla",
        "arabictypesetting", "aldhabi", "andalus", "urdutypesetting",
        "microsoftuighur", "simplifiedarabicfixed")},
    **{k: "free from Google Fonts: fonts.google.com" for k in (
        "amiri", "cairo", "tajawal", "almarai", "notonaskharabic",
        "notokufiarabic", "notosansarabic", "lateef", "scheherazadenew",
        "reemkufi", "harmattan", "markazitext", "elmessiri", "changa",
        "lalezar", "mada", "readexpro", "ibmplexsansarabic", "vazirmatn",
        "arefruqaa", "katibeh", "rakkas", "mirza", "jomhuria")},
    **{k: "comes with Microsoft Office" for k in (
        "calibri", "cambria", "candara", "constantia", "corbel",
        "consolas", "garamond", "bookantiqua", "centurygothic")},
    **{k: "comes with Adobe's apps (Acrobat, Photoshop ...)" for k in (
        "adobearabic", "myriadpro", "minionpro")},
    "aptos": "comes with Microsoft 365 (Office's newer default font)",
}
# By the start of the name: families with many members.
WHERE_PREFIX = {
    "kfgqpc": "free from the King Fahd Quran Printing Complex (qurancomplex.gov.sa)",
    "ae": "free from the Arabeyes project (the \"ae\" Arabic fonts)",
}
ELSEWHERE = ("search its name online, or ask the person who made the PDF "
             "for it")


@dataclass
class Missing:
    name: str          # as a person would type it: Boutros News H1
    style: str         # "", "Bold", ...
    chars: int         # how much of the text is in it
    arabic: bool       # mostly Arabic letters
    only_style: bool   # the family is installed, this style is not
    where: str
    # The PDF's own names for it (ABCDEE+PTBoldHeading ...).
    names: tuple = ()
    # Set by `judge`: True when the text in it reads wrong - the PDF names
    # the wrong letters and only the font can put them right; False when it
    # reads right; None when it could not be told.
    wrong: object = None
    samples: list = field(default_factory=list)   # words as they come out
    pages: list = field(default_factory=list)     # 1-based, where it is used

    def line(self):
        what = f"{self.name}{' ' + self.style if self.style else ''}"
        size = f"{self.chars:,} characters" + (" of Arabic" if self.arabic else "")
        if self.only_style:
            return (f"{what} - {size}. {self.name} is installed but not its "
                    f"{self.style.lower()} style; Word will imitate it.")
        return f"{what} - {size}. Where: {self.where}."


def _bare(name):
    """The PDF's name without its subset tag: ABCDEE+Calibri,Bold -> Calibri,Bold."""
    return name.split("+", 1)[-1]


def _readable(name):
    """BoutrosNewsH1-Bold -> ("Boutros News H1", "Bold")."""
    base = _bare(name)
    m = STYLE.search(base)
    style = m.group(1) if m else ""
    base = base[:m.start()] if m else base
    base = re.sub(r"(PS)?MT$", "", base)
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z])(?=[A-Z][a-z])", " ",
                    base.replace("_", " ")).strip()
    return spaced, ("" if style == "Regular" else style)


def usage(pdf_path):
    """{PDF font name: (characters, Arabic characters)} over every page."""
    count = collections.Counter()
    arabic = collections.Counter()
    with pymupdf.open(str(pdf_path)) as doc:
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if text:
                            count[span["font"]] += len(text)
                            arabic[span["font"]] += len(ARABIC.findall(text))
    return {f: (n, arabic[f]) for f, n in count.items()}


def _windows():
    """Font names Windows lists as installed, for this user and for all:
    "Cambria & Cambria Math (TrueType)" -> cambria, cambriamath."""
    names = set()
    try:
        import winreg
    except ImportError:
        return names
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
        except OSError:
            continue
        i = 0
        while True:
            try:
                entry = winreg.EnumValue(key, i)[0]
            except OSError:
                break
            i += 1
            entry = re.sub(r"\s*\(.*\)$", "", entry)
            for one in entry.split("&"):
                names.add(glyphs._key(one.strip()))
    return names


def _cut_key(name):
    """A name Word cut at 24 characters, keyed so it can be matched by its
    start: TimesNewRomanPS-BoldItal -> timesnewromanboldital."""
    return glyphs._key(name).replace("psbold", "bold").replace("psital", "ital")


def _installed(name, windows):
    if glyphs._path(name) is not None or glyphs._key(name) in windows:
        return True
    # Word cuts a long name at 24 characters (glyphs._path does the same for
    # its own index): Times New Roman PS-Bold Ital is Times New Roman Bold
    # Italic, which Windows has.
    if len(_bare(name)) >= 24:
        k = _cut_key(name)
        return any(w.startswith(k) for w in windows)
    return False


def missing(pdf_path):
    """[Missing], most text first. Empty when everything is installed."""
    seen = {}
    windows = _windows()
    for font, (n, ar) in usage(pdf_path).items():
        name = _bare(font)
        if NAMELESS.match(name) or glyphs._key(name) in glyphs._BUILT_IN:
            continue
        if _installed(name, windows):
            continue
        family, style = _readable(font)
        # The family is here and only this style is not: Word draws a bold
        # of its own from the regular face (Muna Bold, z20538636).
        base = STYLE.sub("", name)
        only_style = bool(style) and _installed(base, windows)
        key = (family, style)
        n0, ar0, _, names = seen.get(key, (0, 0, False, ()))
        seen[key] = (n0 + n, ar0 + ar, only_style, names + (font,))
    out = []
    for (family, style), (n, ar, only_style, names) in seen.items():
        if n < MIN_CHARS:
            continue
        k = glyphs._key(family.replace(" ", ""))
        where = WHERE.get(k) or next(
            (v for p, v in WHERE_PREFIX.items()
             if k.startswith(p) and (p != "ae" or family.startswith("ae "))), ELSEWHERE)
        out.append(Missing(family, style, n, ar >= n / 2, only_style, where,
                           names))
    # What costs most first: a whole missing face before a missing style.
    out.sort(key=lambda m: (m.only_style, -m.chars))
    return out


# Does a missing font's text read right? (FLAGS 23, Moaz 2026-09-22: warn
# only where the text looks wrong.) Without the font nothing in the file says
# which letters its shapes are, so the page is asked: Windows' OCR reads the
# pages where the font is used most, and each of its words (after the
# repairs every text gets) counts as right where the OCR reads it there, or
# the document has it in a font that is installed, or the Quran has it - a
# calligraphic font the OCR cannot read (the Thuluth of a Basmala) is still
# right. On the 36 theses and the old corpus's files under 30 pages
# (2026-09-29), fonts looked at and found broken read 0.00-0.50 right
# (Sultan, Hacen Tunisia, PT Bold Heading, Thick Naskh, Generator Black);
# fonts that read right 0.57 and up, most 0.8 and up. The narrow side: the
# 0.50 is Hacen Tunisia on z18047321, the 0.57 Cadillac Sans Arabic on
# z19740548, whose words are right and the OCR misses.
RIGHT = 0.55
MIN_WORDS = 10
OCR_PAGES = 2
_LETTERS = re.compile("[\u0621-\u064A]")


def judge(pdf_path, found):
    """Set `wrong`, `samples` and `pages` on each missing Arabic font.
    Leaves `wrong` None where Windows' OCR is not there or reads nothing."""
    todo = [m for m in found if m.arabic and not m.only_style]
    if not todo:
        return found
    from convert.arabic import repair_lam_alef
    from convert.glyphs import repaired, spell_out
    from convert.pdftext import apply_fixes, fix_map
    from convert.quran import _quran
    from convert.witness import _norm, _ocr
    path = repaired(str(pdf_path))
    try:
        fixes = fix_map(path)
    except Exception:
        fixes = {}
    windows = _windows()

    def reads(text):
        """As the Word file will have it: the repairs every text gets."""
        return spell_out(apply_fixes(repair_lam_alef(" " + text + " "), fixes))

    def words(text):
        return [w for w in (_norm(x) for x in reads(text).split())
                if len(_LETTERS.findall(w)) >= 3]

    # font -> [(page, box, its words for comparing, its words as they read)]
    spans = collections.defaultdict(list)
    elsewhere = collections.Counter()
    with pymupdf.open(path) as doc:
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        ws = words(span["text"])
                        if not ws:
                            continue
                        if _installed(_bare(span["font"]), windows):
                            elsewhere.update(ws)
                        else:
                            spans[span["font"]].append(
                                (page.number, pymupdf.Rect(span["bbox"]), ws,
                                 reads(span["text"]).split()))
        with open(str(pdf_path), "rb") as f:
            key = hashlib.sha1(f.read()).hexdigest()[:16]
        work = Path(tempfile.gettempdir()) / "qirtas-fontcheck" / key
        quran = {_norm(w) for w in _quran()[0]}
        for m in todo:
            mine = [s for n in m.names for s in spans.get(n, ())]
            count = collections.Counter()
            for p, _, ws, _ in mine:
                count[p] += len(ws)
            m.pages = sorted(p + 1 for p in count)
            if sum(count.values()) < MIN_WORDS:
                continue
            pages = [p for p, _ in count.most_common(OCR_PAGES)]
            try:
                seen = _ocr(doc, pages, work)
            except Exception:
                seen = {}
            if not any(seen.get(p) for p in pages):
                continue
            right = total = 0
            for p, rect, ws, shown in mine:
                if p not in seen:
                    continue
                near = {w for w, r in seen[p] if r.intersects(rect + (-2, -2, 2, 2))}
                for w in ws:
                    total += 1
                    right += w in near or w in elsewhere or w in quran
                if len(m.samples) < 6:
                    m.samples += shown[:6 - len(m.samples)]
            if total >= MIN_WORDS:
                m.wrong = right / total < RIGHT
    return found


def message(found):
    """What to tell the person, in plain words. "" when nothing is missing."""
    if not found:
        return ""
    broken = [m for m in found if m.wrong]
    rest = [m for m in found if not m.wrong]
    lines = []
    if broken:
        lines += ["The text set in these fonts will come out WRONG in the Word "
                  "file - the PDF does not say which letters their shapes are, "
                  "and only the font itself can:", ""]
        for m in broken:
            lines.append(f"  - {m.line()}")
            lines.append(f"    It reads like this{_pages(m.pages)}: "
                         f"{' '.join(m.samples)}")
        lines += ["", "Install them and convert again to get that text right.", ""]
    if rest:
        lines += ["This PDF also uses fonts that are not installed on this computer:"
                  if broken else
                  "This PDF uses fonts that are not installed on this computer:", ""]
        lines += [f"  - {m.line()}" for m in rest]
        lines += ["",
                  "The conversion works without them - Word puts another font in "
                  "their place - but that font is wider or narrower, so lines "
                  "break in other places and pages can run over. With the fonts "
                  "installed, the Word file comes out closer to the PDF."]
    return "\n".join(lines)


def _pages(pages):
    """Where a font's text is: " (page 1)", " (pages 1, 3 and 4)"."""
    if not pages:
        return ""
    if len(pages) == 1:
        return f" (page {pages[0]})"
    shown = [str(p) for p in pages[:6]]
    more = " ..." if len(pages) > 6 else ""
    return f" (pages {', '.join(shown[:-1])} and {shown[-1]}{more})"


def rescan():
    """Forget what was installed, after the person has installed fonts."""
    glyphs._INDEX = None
    glyphs._MAPS.clear()
    glyphs._FAMILIES.clear()
    glyphs._FORMS.clear()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p)
        print(message(judge(p, missing(p))) or "  every font it uses is installed")
