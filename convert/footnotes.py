"""Real Word footnotes.

python-docx cannot write footnotes, so the part is built by hand and dropped
into the saved .docx. Three things have to agree or Word refuses the file:

  word/footnotes.xml                 the notes themselves
  [Content_Types].xml                an Override declaring that part's type
  word/_rels/document.xml.rels       a relationship pointing at it

The body only ever refers to a note by its w:id, never by relationship id, so
the rId chosen here does not have to match anything.
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
FOOTNOTE_CT = ("application/vnd.openxmlformats-officedocument"
               ".wordprocessingml.footnotes+xml")
FOOTNOTE_REL = REL_NS + "/footnotes"

# Word reserves the first two notes for the rules it draws above them, so real
# notes start at 2.
FIRST_ID = 2

# "1- انظر" and "(1) انظر" are both used, sometimes in the same thesis.
NUMBER = re.compile(r"^\s*[\(\[]?\s*(\d{1,3})\s*[\)\]]?\s*[-–—.]?\s*")
# The matching marker in the body, as the typesetter left it: "ابن مجاهد(2)".
MARKER = re.compile(r"[\(\[]\s*(\d{1,3})\s*[\)\]]")


def split_number(text):
    """-> (number, rest). number is None when the note is not numbered."""
    m = NUMBER.match(text or "")
    if not m:
        return None, (text or "").strip()
    return m.group(1), (text or "")[m.end():].strip()


def _sep(kind, tag, wid):
    return (f'<w:footnote w:type="{kind}" w:id="{wid}">'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" '
            f'w:lineRule="auto"/></w:pPr><w:r><w:{tag}/></w:r></w:p>'
            f'</w:footnote>')


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


def build_xml(notes, font="Arial", size_pt=9.0, rtl=True):
    """notes is [(id, text)]. -> the complete footnotes.xml document."""
    parts = [_sep("separator", "separator", 0),
             _sep("continuationSeparator", "continuationSeparator", 1)]
    bidi = "<w:bidi/>" if rtl else ""
    for wid, text in notes:
        parts.append(
            f'<w:footnote w:id="{wid}">'
            f'<w:p><w:pPr>{bidi}<w:spacing w:after="0"/></w:pPr>'
            f'<w:r>{_rpr(font, size_pt, rtl, superscript=True)}'
            f'<w:footnoteRef/></w:r>'
            f'<w:r>{_rpr(font, size_pt, rtl)}'
            f'<w:t xml:space="preserve"> {escape(text)}</w:t></w:r>'
            f'</w:p></w:footnote>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:footnotes xmlns:w="{W}">' + "".join(parts) + '</w:footnotes>')


def _add_override(ctypes):
    if "footnotes+xml" in ctypes:
        return ctypes
    tag = (f'<Override PartName="/word/footnotes.xml" '
           f'ContentType="{FOOTNOTE_CT}"/>')
    return ctypes.replace("</Types>", tag + "</Types>")


def _add_rel(rels):
    if "footnotes.xml" in rels:
        return rels
    used = {int(n) for n in re.findall(r'Id="rId(\d+)"', rels)}
    rid = max(used, default=0) + 1
    tag = (f'<Relationship Id="rId{rid}" Type="{FOOTNOTE_REL}" '
           f'Target="footnotes.xml"/>')
    return rels.replace("</Relationships>", tag + "</Relationships>")


def install(docx_path, xml):
    """Write footnotes.xml into an existing .docx and declare it.

    A zip entry cannot be edited in place, so the archive is rebuilt beside the
    original and moved over it only once it is complete - a crash halfway
    through leaves the original .docx intact rather than a truncated one.
    """
    src = Path(docx_path)
    tmp = src.with_suffix(".footnotes.tmp")
    with zipfile.ZipFile(src) as zin, \
            zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "word/footnotes.xml":
                continue                      # ours replaces any existing one
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = _add_override(data.decode("utf-8")).encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                data = _add_rel(data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)
        zout.writestr("word/footnotes.xml", xml.encode("utf-8"))
    shutil.move(str(tmp), str(src))
