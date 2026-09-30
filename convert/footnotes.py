"""Real Word footnotes and endnotes.

python-docx cannot write either, so the part is built by hand and dropped
into the saved .docx. Three things have to agree or Word refuses the file:

  word/footnotes.xml (endnotes.xml)  the notes themselves
  [Content_Types].xml                an Override declaring that part's type
  word/_rels/document.xml.rels       a relationship pointing at it

The body only ever refers to a note by its w:id, never by relationship id, so
the rId chosen here does not have to match anything.

An endnote is a footnote collected at the end of the document instead of the
foot of its page. The machinery is the same; only the names differ.
"""
import os
import posixpath
import re
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NOTE_CT = ("application/vnd.openxmlformats-officedocument"
           ".wordprocessingml.{note}s+xml")
FOOTNOTE_CT = NOTE_CT.format(note="footnote")
FOOTNOTE_REL = REL_NS + "/footnotes"
KINDS = ("footnote", "endnote")

# Word reserves the first two notes for the rules it draws above them, so real
# notes start at 2.
FIRST_ID = 2

# A reference the reader found as a small raised number ("شاتليه¹³") rather
# than typed "(13)". Wrapped in private-use characters so it cannot be taken
# for a "(13)" the author typed, and so that one left without a note can be
# written back as the raised digits it was, not as "(13)".
MARK_OPEN, MARK_CLOSE = "", ""
RAISED = re.compile(MARK_OPEN + r"(\d{1,3})" + MARK_CLOSE)
# Where a note's own second paragraph starts (reader._rich_block): written
# as a new paragraph of the note, and as a space anywhere else.
NOTE_PARA = ""

# "1- انظر" and "(1) انظر" are both used, sometimes in the same thesis.
NUMBER = re.compile(r"^\s*[\(\[]?\s*(\d{1,3})\s*[\)\]]?\s*[-–—.]?\s*")
# The matching marker in the body: as the typesetter left it, "ابن مجاهد(2)",
# or raised and found by the reader.
MARKER = re.compile(r"(?:[\(\[]\s*(\d{1,3})\s*[\)\]]|"
                    + MARK_OPEN + r"(\d{1,3})" + MARK_CLOSE + ")")


# A note number as a plain number: ١٢ and 12 are the same note. The writer
# shows digits as the original did (N5a), in the body by the Arabic around
# them - so a reference and its note can come out in different forms.
WESTERN = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789" * 2)


def marker_numbers(text):
    """Every note number referred to in this text, in order."""
    return [(a or b).translate(WESTERN) for a, b in MARKER.findall(text or "")]


def split_number(text):
    """-> (number, rest). number is None when the note is not numbered."""
    m = NUMBER.match(text or "")
    if not m:
        return None, (text or "").strip()
    return m.group(1).translate(WESTERN), (text or "")[m.end():].strip()


# English inside an Arabic paragraph is written as a left-to-right run of its
# own - from its first Latin letter to its last letter or digit, with what
# lies between (`Lawn & Zumla, 2011`) and a full stop that ends it (`et al.`).
# Written into the paragraph's one right-to-left run, Word draws it right
# while it stays on one line, but where a line wraps inside it Word takes the
# `&`, comma or full stop that begins or ends a line for Arabic, and moves it
# to the far end: `(Zumla, 2011 &` for `(& Zumla, 2011` (`z20252507` page 3;
# PLAN "Citations where a line wraps"). The brackets around it stay in the
# Arabic run, as an author's own Word types them, and Word draws them
# mirrored as before. A number alone stays in the Arabic run.
# QIRTAS_LTR_RUNS=0 turns this off, to measure against.
LTR_ON = os.environ.get("QIRTAS_LTR_RUNS", "1") != "0"
_ARABIC = r"\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF"
LTR_STRETCH = re.compile(
    r"[A-Za-z\u00C0-\u024F](?:[^" + _ARABIC + r"]*[A-Za-z\u00C0-\u024F0-9])?"
    r"\.?")
PAIRS = {"(": ")", "[": "]"}


def directional(text, rtl=True):
    """-> [(piece, rtl)]: `text` cut where English starts and ends inside a
    right-to-left paragraph. A left-to-right paragraph is one piece."""
    if not rtl or not LTR_ON or not text:
        return [(text, rtl)]
    out, at = [], 0
    for m in LTR_STRETCH.finditer(text):
        end = m.end()
        # `Tuberculosis (TB)`: a bracket opened inside is closed inside.
        for o, c in PAIRS.items():
            if text.count(o, m.start(), end) > text.count(c, m.start(), end) \
                    and text[end:end + 1] == c:
                end += 1
        if m.start() > at:
            out.append((text[at:m.start()], True))
        out.append((text[m.start():end], False))
        at = end
    if at < len(text):
        out.append((text[at:], True))
    return out


def _sep(kind, tag, wid, note="footnote", bidi=""):
    return (f'<w:{note} w:type="{kind}" w:id="{wid}">'
            f'<w:p><w:pPr>{bidi}<w:spacing w:after="0" w:line="240" '
            f'w:lineRule="auto"/></w:pPr><w:r><w:{tag}/></w:r></w:p>'
            f'</w:{note}>')


# Word's own line above the notes is this long; one the original drew at
# another length is drawn as the bottom edge of an empty paragraph cut to it.
WORD_RULE = 144.0


def _rule(rule, width, note="footnote"):
    """The separator for `rule` = (length pt, side, eighths, colour), or
    Word's own at the right side."""
    length, side, eighths, colour = rule
    bidi = "<w:bidi/>" if side == "right" else ""
    if abs(length - WORD_RULE) <= 4 or not width or length >= width:
        return _sep("separator", "separator", 0, note, bidi)
    # w:right is the paragraph's END side both ways round, so it shortens
    # the line from the far end and it keeps its start at `side`.
    end = round((width - length) * 20)
    return (f'<w:{note} w:type="separator" w:id="0"><w:p><w:pPr>{bidi}'
            f'<w:pBdr><w:bottom w:val="single" w:sz="{eighths}" w:space="0" '
            f'w:color="{colour}"/></w:pBdr>'
            f'<w:spacing w:after="0" w:line="120" w:lineRule="exact"/>'
            f'<w:ind w:right="{end}"/></w:pPr></w:p></w:{note}>')


def _rpr(font, size_pt, rtl, superscript=False, bold=False, italic=False):
    half = max(2, int(round(size_pt * 2)))
    out = [f'<w:rFonts w:ascii="{escape(font)}" w:hAnsi="{escape(font)}" '
           f'w:cs="{escape(font)}"/>',
           # Both ways, as the writer's runs: Arabic follows w:bCs and w:iCs.
           '<w:b/><w:bCs/>' if bold else '',
           '<w:i/><w:iCs/>' if italic else '',
           f'<w:sz w:val="{half}"/><w:szCs w:val="{half}"/>']
    if superscript:
        out.append('<w:vertAlign w:val="superscript"/>')
    if rtl:
        out.append('<w:rtl/>')
    return "<w:rPr>" + "".join(out) + "</w:rPr>"


def build_xml(notes, font="Arial", size_pt=9.0, rtl=True, note="footnote",
              pitch=0.0, rule=None, width=0.0):
    """notes is [(id, text)] or [(id, text, bold, italic)], where text may
    instead be [(text, bold, italic)] pieces. -> the complete footnotes.xml
    document, or endnotes.xml with note="endnote". pitch: the notes' distance
    between lines in points; rule: the line above them as the reader
    measured it (model.note_rule), within a text `width` of points."""
    assert note in KINDS
    bidi = "<w:bidi/>" if rtl else ""
    # rule None: as before, Word's line at the left. () : nothing measured,
    # so Word's line at the side the notes start from.
    side = bidi if rule is not None else ""
    first = _rule(rule, width, note) if rule else \
        _sep("separator", "separator", 0, note, side)
    parts = [first,
             _sep("continuationSeparator", "continuationSeparator", 1, note,
                  side)]
    line = (f' w:line="{round(pitch * 20)}" w:lineRule="exact"'
            if pitch else "")
    for wid, text, *style in notes:
        bold, italic = (list(style) + [False, False])[:2]
        pieces = text if isinstance(text, list) else [(text, bold, italic)]
        pieces = [(" " + pieces[0][0],) + tuple(pieces[0][1:])] + pieces[1:]
        ppr = f'<w:pPr>{bidi}<w:spacing w:after="0"{line}/></w:pPr>'
        body = "".join(
            (f'</w:p><w:p>{ppr}' if t == NOTE_PARA else
             f'<w:r>{_rpr(font, size_pt, r, bold=b, italic=i)}'
             f'<w:t xml:space="preserve">{escape(t)}</w:t></w:r>')
            for piece, b, i in pieces
            for bit in re.split(r"\s*(" + NOTE_PARA + r")\s*", piece) if bit
            for t, r in ([(bit, rtl)] if bit == NOTE_PARA
                         else directional(bit, rtl)))
        parts.append(
            f'<w:{note} w:id="{wid}">'
            f'<w:p>{ppr}'
            f'<w:r>{_rpr(font, size_pt, rtl, superscript=True)}'
            f'<w:{note}Ref/></w:r>'
            + body +
            f'</w:p></w:{note}>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:{note}s xmlns:w="{W}">' + "".join(parts) + f'</w:{note}s>')


def _add_override(ctypes, note="footnote"):
    if f"{note}s+xml" in ctypes:
        return ctypes
    tag = (f'<Override PartName="/word/{note}s.xml" '
           f'ContentType="{NOTE_CT.format(note=note)}"/>')
    return ctypes.replace("</Types>", tag + "</Types>")


def _add_rel(rels, note="footnote"):
    if f"{note}s.xml" in rels:
        return rels
    used = {int(n) for n in re.findall(r'Id="rId(\d+)"', rels)}
    rid = max(used, default=0) + 1
    tag = (f'<Relationship Id="rId{rid}" Type="{REL_NS}/{note}s" '
           f'Target="{note}s.xml"/>')
    return rels.replace("</Relationships>", tag + "</Relationships>")


def _add_settings(settings, note="footnote"):
    """Point the document at our separators. Without this Word ignores the
    separator notes in footnotes.xml and draws its own line - at the left, 2
    inches long, whatever the original had."""
    if f"<w:{note}Pr>" in settings:
        return settings
    tag = (f'<w:{note}Pr><w:{note} w:id="0"/><w:{note} w:id="1"/>'
           f'</w:{note}Pr>')
    # Schema order: after the typography settings, before w:compat.
    for before in ("<w:compat", "<w:docVars", "<w:rsids", "</w:settings>"):
        if before in settings:
            return settings.replace(before, tag + before, 1)
    return settings


def install(docx_path, xml, note="footnote"):
    """Write footnotes.xml (or endnotes.xml) into an existing .docx and
    declare it.

    A zip entry cannot be edited in place, so the archive is rebuilt beside the
    original and moved over it only once it is complete - a crash halfway
    through leaves the original .docx intact rather than a truncated one.
    """
    src = Path(docx_path)
    part = f"word/{note}s.xml"
    tmp = src.with_suffix(f".{note}s.tmp")
    with zipfile.ZipFile(src) as zin, \
            zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == part:
                continue                      # ours replaces any existing one
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = _add_override(data.decode("utf-8"), note).encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                data = _add_rel(data.decode("utf-8"), note).encode("utf-8")
            elif item.filename == "word/settings.xml":
                data = _add_settings(data.decode("utf-8"), note).encode("utf-8")
            zout.writestr(item, data)
        zout.writestr(part, xml.encode("utf-8"))
    shutil.move(str(tmp), str(src))
