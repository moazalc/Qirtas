"""Every way we know of to get text out of a PDF.

Each route is a function (path) -> str, registered in ROUTES. A route that
raises returns "" and is reported as failed rather than crashing the run.
"""
import io, re, subprocess, shutil
from pathlib import Path

QALAM_PY = Path("/home/my-pc/.venvs/qalam/bin/python")
ROUTES = {}


def route(name):
    def deco(fn):
        ROUTES[name] = fn
        return fn
    return deco


# ---------- PyMuPDF: same library, different internal paths ----------

@route("pymupdf.text")
def _pm_text(p):
    import pymupdf
    with pymupdf.open(p) as d:
        return "\n".join(pg.get_text("text") for pg in d)


@route("pymupdf.blocks")
def _pm_blocks(p):
    import pymupdf
    out = []
    with pymupdf.open(p) as d:
        for pg in d:
            out += [b[4] for b in pg.get_text("blocks")]
    return "\n".join(out)


@route("pymupdf.dict")           # glyph-level
def _pm_dict(p):
    import pymupdf
    out = []
    with pymupdf.open(p) as d:
        for pg in d:
            for b in pg.get_text("dict")["blocks"]:
                if b["type"] != 0:
                    continue
                for l in b["lines"]:
                    out += [s["text"] for s in l["spans"]]
    return "\n".join(out)


@route("pymupdf.xhtml")          # glyph-level
def _pm_xhtml(p):
    import pymupdf
    with pymupdf.open(p) as d:
        html = "".join(pg.get_text("xhtml") for pg in d)
    return re.sub(r"<[^>]+>", " ", html)


# ---------- other libraries ----------

@route("pdfminer.six")
def _pdfminer(p):
    from pdfminer.high_level import extract_text
    return extract_text(p)


@route("pypdf")
def _pypdf(p):
    from pypdf import PdfReader
    return "\n".join((pg.extract_text() or "") for pg in PdfReader(p).pages)


@route("poppler.pdftotext")
def _poppler(p):
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext not installed")
    return subprocess.run(["pdftotext", "-enc", "UTF-8", str(p), "-"],
                          capture_output=True, text=True, timeout=120).stdout


@route("poppler.layout")
def _poppler_layout(p):
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext not installed")
    return subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(p), "-"],
                          capture_output=True, text=True, timeout=120).stdout


@route("qalam")
def _qalam(p):
    if not QALAM_PY.exists():
        raise RuntimeError("qalam venv not found")
    code = "import qalam,sys; sys.stdout.write(qalam.Document(sys.argv[1]).text or '')"
    r = subprocess.run([str(QALAM_PY), "-c", code, str(p)],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return r.stdout


# ---------- our own: read the accessibility layer ----------

def _walk_struct(node, acc, depth=0):
    import pikepdf
    if depth > 80:
        return
    if isinstance(node, pikepdf.Array):
        for k in node:
            _walk_struct(k, acc, depth + 1)
        return
    if not isinstance(node, pikepdf.Dictionary):
        return
    at = node.get("/ActualText")
    if at is not None:
        acc.append(str(at))
    else:
        alt = node.get("/Alt")
        if alt is not None:
            acc.append(str(alt))
    kids = node.get("/K")
    if kids is not None:
        _walk_struct(kids, acc, depth + 1)


@route("structtree.actualtext")
def _structtree(p):
    import pikepdf
    with pikepdf.open(p) as pdf:
        root = pdf.Root
        if "/StructTreeRoot" not in root:
            raise RuntimeError("not tagged")
        acc = []
        _walk_struct(root["/StructTreeRoot"].get("/K"), acc)
    return "".join(acc)


def run_route(name, path):
    """-> (text, error_or_None)"""
    try:
        return ROUTES[name](str(path)) or "", None
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"[:160]
