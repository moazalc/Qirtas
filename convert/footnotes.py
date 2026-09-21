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

# "1- انظر" and "(1) انظر" are both used, sometimes in the same thesis.
NUMBER = re.compile(r"^\s*[\(\[]?\s*(\d{1,3})\s*[\)\]]?\s*[-–—.]?\s*")
# The matching marker in the body: as the typesetter left it, "ابن مجاهد(2)",
# or raised and found by the reader.
MARKER = re.compile(r"(?:[\(\[]\s*(\d{1,3})\s*[\)\]]|"
                    + MARK_OPEN + r"(\d{1,3})" + MARK_CLOSE + ")")


def marker_numbers(text):
    """Every note number referred to in this text, in order."""
    return [a or b for a, b in MARKER.findall(text or "")]


def split_number(text):
    """-> (number, rest). number is None when the note is not numbered."""
    m = NUMBER.match(text or "")
    if not m:
        return None, (text or "").strip()
    return m.group(1), (text or "")[m.end():].strip()


def _sep(kind, tag, wid, note="footnote"):
    return (f'<w:{note} w:type="{kind}" w:id="{wid}">'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" '
            f'w:lineRule="auto"/></w:pPr><w:r><w:{tag}/></w:r></w:p>'
            f'</w:{note}>')


def _rpr(font, size_pt, rtl, superscript=False):
    half = max(2, int(round(size_pt * 2)))
    out = [f'<w:rFonts w:ascii="{escape(font)}" w:hAnsi="{escape(font)}" '
           f'w:cs="{escape(font)}"/>',
           f'<w:sz w:val="{half}"/><w:szCs w:val="{half}"/>']
    if superscript:
        out.append('<w:vertAlign w:val="superscript"/>')
    if rtl:
        out.append('<w:rtl/>')
    return "<w:rPr>" + "".join(out) + "</w:rPr>"


def build_xml(notes, font="Arial", size_pt=9.0, rtl=True, note="footnote"):
    """notes is [(id, text)]. -> the complete footnotes.xml document, or
    endnotes.xml with note="endnote"."""
    assert note in KINDS
    parts = [_sep("separator", "separator", 0, note),
             _sep("continuationSeparator", "continuationSeparator", 1, note)]
    bidi = "<w:bidi/>" if rtl else ""
    for wid, text in notes:
        parts.append(
            f'<w:{note} w:id="{wid}">'
            f'<w:p><w:pPr>{bidi}<w:spacing w:after="0"/></w:pPr>'
            f'<w:r>{_rpr(font, size_pt, rtl, superscript=True)}'
            f'<w:{note}Ref/></w:r>'
            f'<w:r>{_rpr(font, size_pt, rtl)}'
            f'<w:t xml:space="preserve"> {escape(text)}</w:t></w:r>'
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
            zout.writestr(item, data)
        zout.writestr(part, xml.encode("utf-8"))
    shutil.move(str(tmp), str(src))
