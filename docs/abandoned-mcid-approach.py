"""Find the font, size and position behind each piece of tagged text.

The hidden labels tell us *what* something is ("a paragraph"); they say nothing
about how it looks. That lives in the page's drawing instructions, tied together
by a marked-content id (MCID) that appears in both places.

This walks the drawing instructions and builds: mcid -> {size, bold, x, y}.
With that, a label and its appearance can finally be matched up.
"""
import collections
import pikepdf

BOLD_HINTS = ("bold", "black", "heavy", "semib", "demib")


def _font_table(page):
    """name in the drawing instructions -> (is_bold, base font name)"""
    out = {}
    fonts = (page.get("/Resources", {}) or {}).get("/Font", {}) or {}
    for name, fo in fonts.items():
        try:
            base = str(fo.get("/BaseFont", ""))
            flags = 0
            if str(fo.get("/Subtype")) == "/Type0":
                fd = fo["/DescendantFonts"][0].get("/FontDescriptor", {}) or {}
            else:
                fd = fo.get("/FontDescriptor", {}) or {}
            flags = int(fd.get("/Flags", 0) or 0)
            weight = int(fd.get("/StemV", 0) or 0)
            bold = (any(h in base.lower() for h in BOLD_HINTS)
                    or bool(flags & (1 << 18))          # ForceBold
                    or weight >= 120)
            out[str(name)] = (bold, base)
        except Exception:
            out[str(name)] = (False, "")
    return out


def scan_page(page):
    """-> {mcid: {"size": float, "bold": bool, "x": float, "y": float}}"""
    fonts = _font_table(page)
    info = {}
    stack = []                      # open marked-content ids
    size, bold = 0.0, False
    x = y = 0.0
    try:
        ops = pikepdf.parse_content_stream(page)
    except Exception:
        return info

    for operands, operator in ops:
        op = str(operator)
        try:
            if op in ("BDC", "DP") and len(operands) >= 2:
                props = operands[1]
                mcid = None
                if isinstance(props, pikepdf.Dictionary) and "/MCID" in props:
                    mcid = int(props["/MCID"])
                stack.append(mcid)
            elif op == "EMC":
                if stack:
                    stack.pop()
            elif op == "BMC":
                stack.append(None)
            elif op == "Tf" and len(operands) >= 2:
                bold, _ = fonts.get(str(operands[0]), (False, ""))
                size = float(operands[1])
            elif op in ("Tm", "cm") and len(operands) >= 6:
                x, y = float(operands[4]), float(operands[5])
                if op == "Tm":
                    scale = abs(float(operands[3])) or 1.0
                    eff = size * scale
                    _stamp(info, stack, eff, bold, x, y)
            elif op == "Td" and len(operands) >= 2:
                x += float(operands[0]); y += float(operands[1])
            elif op in ("Tj", "TJ", "'", '"'):
                _stamp(info, stack, size, bold, x, y)
        except Exception:
            continue
    return info


def _stamp(info, stack, size, bold, x, y):
    for mcid in stack:
        if mcid is None:
            continue
        rec = info.get(mcid)
        if rec is None:
            info[mcid] = {"size": size, "bold": bold, "x": x, "y": y}
        else:
            rec["size"] = max(rec["size"], size)
            rec["bold"] = rec["bold"] or bold


def scan(pdf):
    """-> {page_index: {mcid: {...}}}"""
    return {i: scan_page(pg) for i, pg in enumerate(pdf.pages)}
