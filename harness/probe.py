"""Structural facts about a PDF: who made it, is it tagged, what tags, what fonts."""
import collections, re
import pikepdf, pymupdf

SEMANTIC = {"/H", "/H1", "/H2", "/H3", "/H4", "/H5", "/H6",
            "/Table", "/TR", "/TD", "/TH", "/L", "/LI", "/LBody", "/Footnote"}
SUBSET_RE = re.compile(r"^[A-Z]{6}\+")


def _walk(node, counter, actual, depth=0):
    if depth > 80:
        return
    if isinstance(node, pikepdf.Array):
        for k in node:
            _walk(k, counter, actual, depth + 1)
        return
    if not isinstance(node, pikepdf.Dictionary):
        return
    s = node.get("/S")
    if s is not None:
        counter[str(s)] += 1
    if node.get("/ActualText") is not None:
        actual[0] += 1
    k = node.get("/K")
    if k is not None:
        _walk(k, counter, actual, depth + 1)


def probe(path) -> dict:
    info = {"file": str(path).split("/")[-1]}
    with pikepdf.open(path) as pdf:
        di = pdf.docinfo or {}
        info["producer"] = str(di.get("/Producer", "—"))
        info["creator"] = str(di.get("/Creator", "—"))
        info["pages"] = len(pdf.pages)
        root = pdf.Root
        info["lang"] = str(root.get("/Lang", "—"))
        info["marked"] = bool(root.get("/MarkInfo", {}).get("/Marked", False)) \
            if "/MarkInfo" in root else False
        tags, actual = collections.Counter(), [0]
        info["tagged"] = "/StructTreeRoot" in root
        if info["tagged"]:
            _walk(root["/StructTreeRoot"].get("/K"), tags, actual)
        info["tags"] = dict(tags)
        info["tag_total"] = sum(tags.values())
        info["tag_semantic"] = sum(v for k, v in tags.items() if k in SEMANTIC)
        info["actualtext_elements"] = actual[0]
        info["has_headings"] = any(k.startswith("/H") and k != "/Hn" for k in tags)

    fonts, embedded = set(), set()
    with pymupdf.open(path) as d:
        for i, pg in enumerate(d):
            for f in pg.get_fonts(full=True):
                fonts.add(f[3])
                if f[1]:                     # ext present => embedded
                    embedded.add(f[3])
            if i >= 19:
                break
    info["fonts"] = sorted(fonts)
    info["fonts_embedded"] = len(embedded)
    info["fonts_subset"] = sum(1 for f in fonts if SUBSET_RE.match(f))
    return info
