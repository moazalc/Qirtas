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
from dataclasses import dataclass
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
        n0, ar0 = seen.get(key, (0, 0, False))[:2]
        seen[key] = (n0 + n, ar0 + ar, only_style)
    out = []
    for (family, style), (n, ar, only_style) in seen.items():
        if n < MIN_CHARS:
            continue
        k = glyphs._key(family.replace(" ", ""))
        where = WHERE.get(k) or next(
            (v for p, v in WHERE_PREFIX.items()
             if k.startswith(p) and (p != "ae" or family.startswith("ae "))), ELSEWHERE)
        out.append(Missing(family, style, n, ar >= n / 2, only_style, where))
    # What costs most first: a whole missing face before a missing style.
    out.sort(key=lambda m: (m.only_style, -m.chars))
    return out


def message(found):
    """What to tell the person, in plain words. "" when nothing is missing."""
    if not found:
        return ""
    lines = ["This PDF uses fonts that are not installed on this computer:", ""]
    lines += [f"  - {m.line()}" for m in found]
    lines += ["",
              "The conversion works without them - Word puts another font in "
              "their place - but that font is wider or narrower, so lines "
              "break in other places and pages can run over. With the fonts "
              "installed, the Word file comes out closer to the PDF."]
    return "\n".join(lines)


def rescan():
    """Forget what was installed, after the person has installed fonts."""
    glyphs._INDEX = None
    glyphs._MAPS.clear()
    glyphs._FAMILIES.clear()
    glyphs._FORMS.clear()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p)
        print(message(missing(p)) or "  every font it uses is installed")
