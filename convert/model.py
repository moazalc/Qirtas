"""The description: what the reader found, before any Word file exists.

Deliberately small. A block is one thing on the page — a paragraph, a heading,
a list item, a footnote. The writer turns these into Word; nothing here knows
anything about Word or about PDFs.
"""
from dataclasses import dataclass, field
from typing import List

PARAGRAPH = "paragraph"
HEADING = "heading"
LIST_ITEM = "list_item"
FOOTNOTE = "footnote"
IMAGE = "image"
TABLE = "table"


@dataclass
class Block:
    kind: str
    text: str
    page: int = 0
    level: int = 0            # heading depth, 1-6
    size: float = 0.0         # font size in points, 0 if unknown
    # The size most of its letters are set at. `size` is the largest, which
    # suits finding headings and would enlarge a paragraph for one big letter.
    text_size: float = 0.0
    bold: bool = False         # whole-block boldness, kept for joining and headings
    # (text, bold, italic) per run of like-formatted text. Empty when the route
    # could not read formatting, in which case the writer falls back to `bold`.
    spans: List[tuple] = field(default_factory=list)
    y: float = 0.0       # top edge on the page, 0 if unknown
    y1: float = 0.0      # bottom edge
    x0: float = 0.0
    x1: float = 0.0
    image: str = ""      # path to the extracted picture, for image blocks
    # Stable identity of the picture in the SOURCE pdf, independent of the file
    # we wrote out. Running-header detection groups by this: a decoration drawn
    # on forty pages is one PDF object drawn forty times, but the bytes we
    # extract for it need not be identical page to page - and stopped being so
    # once masked images started being rendered off the page.
    origin: str = ""
    # The picture was photographed off the page and page TEXT sits inside it,
    # so the photo carries that one page's words - a boxed page number is the
    # case that found it. Such a picture must never be drawn once and repeated
    # as a running header or footer: it would stamp page 1's number on all.
    over_text: bool = False
    # The whole first page was photographed as one picture (a title-page
    # collage). The writer keeps Word's header and footer off that page, since
    # the photo already shows everything the original printed there.
    collage: bool = False
    # Every word of this block came from a picture's /Alt description in the
    # structure tree, none from /ActualText or the page. It describes a picture
    # rather than being text the document printed - often Word's automatic
    # "Logo Description automatically generated with medium confidence".
    from_alt: bool = False
    rows: List[List[str]] = field(default_factory=list)   # for table blocks
    col_widths: List[float] = field(default_factory=list)  # points, per column
    cell_boxes: List[List[tuple]] = field(default_factory=list)   # cell rects
    cell_images: dict = field(default_factory=dict)               # (row,col) -> path

    def __bool__(self):
        return bool(self.text.strip()) or bool(self.image) or bool(self.rows)


@dataclass
class Doc:
    blocks: List[Block] = field(default_factory=list)
    page_width: float = 595.0
    page_height: float = 842.0
    pages: int = 0
    source_route: str = ""
    margin_left: float = 72.0
    margin_right: float = 72.0
    margin_top: float = 72.0
    margin_bottom: float = 72.0
    body_size: float = 12.0
    font: str = ""       # the document's own Arabic font, if we can tell
    # "arabic" or "persian" when the pages show typed digits in that form
    digits: str = ""
    line_spacing: float = 1.15
    line_pitch: float = 0.0     # measured distance between lines, in points
    # (path, reason) for every picture the writer could not place. Filled by
    # write(); a silent drop is how one lost picture went unnoticed for weeks.
    dropped_images: List[tuple] = field(default_factory=list)

    def add(self, block: Block):
        if block:
            self.blocks.append(block)

    def counts(self):
        out = {}
        for b in self.blocks:
            out[b.kind] = out.get(b.kind, 0) + 1
        return out
