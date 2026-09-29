#!/usr/bin/env python3
"""Tests for punctuation put back where the page draws it (convert/order.py).

    python -m harness.test_order

Each case is a line as the extractor hands it over: (character, left, right)
in its order, positions in points. In a right-to-left line a word's letters
run leftwards; a mark drawn on a word's left comes after it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from convert.order import (MIRROR, _by_pieces, _fix_text, _indices, _turned,
                           order, units)

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<56} got {got!r}")
    if not ok:
        print(f"        want {want!r}")
        FAILED.append(name)


def line(*words, start=400.0, w=5.0, gap=4.0):
    """Lay out words right to left: each (text, None) is a word, (mark, x)
    places a mark at x. -> [(c, x0, x1)] in the order given."""
    out, x = [], start
    for text, at in words:
        if at is not None:
            out += [(c, at, at + 2) for c in text]
            continue
        for c in text:
            if c == " ":
                out.append((c, x - gap, x))
                x -= gap
            else:
                out.append((c, x - w, x))
                x -= w
    return out


def read(ln, arabic_page=None):
    seq = order(ln, arabic_page)
    if seq is None:
        return "".join(c for c, _, _ in ln)
    us = units([c for c, _, _ in ln])
    turned = _turned(us, seq)
    return "".join(" " if i is None else MIRROR[ln[i][0]] if i in turned
                   else ln[i][0] for i in _indices(us, seq))


def main():
    print("a mark stored before the word it is drawn after")
    # ،عشر: the comma drawn on the left of عشر (x 373 against ر at 378)
    ln = [(" ", 366, 370), ("،", 371, 375), ("ع", 391, 396), ("ش", 382, 391),
          ("ر", 377, 382)]
    check("،عشر reads عشر،", read(ln).strip(), "عشر،")

    # ا،جلزائر: stored inside the word, drawn after the next word
    ln = line(("ا", None)) + [("،", 300, 302)] + line(
        ("جلزائر خالل", None), start=395)
    check("a comma inside a word goes to the word it is drawn beside",
          read(ln), "اجلزائر خالل،")

    # the full stop ending a line, stored at its start
    ln = [(".", 300, 302)] + line(("بين الجزائريين", None))
    check("a line-final full stop stored first goes last", read(ln),
          "بين الجزائريين.")

    # بإدارة،الرصف: nothing but the comma parted the words
    ln = line(("بإدارة", None)) + [("،", 300, 302)] + line(("الرصف", None),
                                                          start=365)
    check("a mark that parted two words leaves a space", read(ln),
          "بإدارة الرصف،")
    ln = line(("اله", None)) + [(".", 300, 302)] + line(("امل", None),
                                                       start=385)
    check("inside one word it leaves none (اهل.امل)", read(ln), "الهامل.")

    print("\nleft alone")
    ln = line(("بين الجزائريين", None)) + [(".", 300, 302)]
    check("a mark already after its word", order(ln), None)
    ln = line(("والتنمية", None)) + [(")", 355, 358), ("،", 350, 352)]
    check("a bracket between a word and its mark", read(ln), "والتنمية)،")

    print("\nlines with numbers or Latin")
    ln = [(".", 300, 302)] + line(("العدد 5", None))
    check("a mark after the number", read(ln), "العدد 5.")
    ln = [(".", 300, 302)] + line(("أو أكثر%", None))
    check("... after a percent sign", read(ln), "أو أكثر%.")
    ln = [(".", 300, 302)] + line(("DVB-S بين القمرين", None))
    check("... after the word beyond the Latin", read(ln),
          "DVB-S بين القمرين.")
    # An English line with an Arabic word in it runs left to right
    # (z22179435's abstract): the gate lost text when it was reordered.
    ln = [(".", 300, 302)] + line(("the word قلب was mapped", None))
    check("an English line with an Arabic word is left alone", order(ln),
          None)
    # Word lays numbers left to right: وبأطوال 30 is stored " وبأطوال30",
    # the space drawn between the word and the number (z19799524).
    word = line(("وبأطوال", None))
    ln = [(" ", 361, 365)] + word + [("3", 350, 355), ("0", 355, 360)]
    check("a space stored at the line's end goes before the number",
          read(ln), "وبأطوال 30")
    ln = [(":", 361, 364)] + word + [("0", 350, 355), ("7", 355, 360)]
    check("so does a mark (المجلد: 07)", read(ln), "وبأطوال:07")
    ln = [(c, x0, x1) for c, x0, x1 in line(("الفرنسي ", None))] + [
        ("(", 356, 360), ("T", 340, 345), ("G", 345, 350), ("V", 350, 355),
        (")", 336, 340)]
    check("brackets beside Latin stay (TGV)", read(ln), "الفرنسي (TGV)")
    # (Evershed, at a line's end: the comma is drawn at the Latin run's
    # right end, between it and الوقت - still the run's (z21760107).
    ln = line(("الوقت", None)) + [("(", 371, 374)] + [
        (c, 330 + 5 * i, 335 + 5 * i) for i, c in enumerate("Evershed")] + [
        (",", 370, 372)]
    check("a comma at a Latin run's end stays (Evershed,)", read(ln),
          "الوقت(Evershed,")
    # 15% من حالات: the 15 is the piece before; this one stores the % last
    # and draws it at its right end, against the 15 (z20252507).
    ln = line(("  من حالات", None)) + [("%", 401, 406)]
    check("a % drawn at the line's right end starts it", read(ln),
          "%  من حالات")
    ln = line(("أكثر من حالات%", None))
    check("a % drawn at the left stays last", read(ln), "أكثر من حالات%")
    ln = [("1", 380, 385), ("5", 385, 390)] + line(
        (" من حالات", None), start=380) + [("%", 391, 396)]
    check("... and so does one beside a number of its own line", order(ln),
          None)
    ln = line(("سبق", None)) + [(" ", 330, 334)] + line(
        ("قدم", None), start=384) + [("V", 340, 345), ("a", 345, 350)]
    check("a space between two Arabic words stays", read(ln), "سبق قدمVa")
    # the theses: text laid over a drawing, every character at one point
    ln = [(c, 310, 310) for c in "معرفة المقصود من القراءات الشواذ."]
    check("a line whose characters have no place of their own", order(ln),
          None)
    # a line stored in drawing order: letters run rightwards
    ln = [(".", 300, 302)] + [(c, 310 + 5 * i, 315 + 5 * i)
                              for i, c in enumerate("فدهلا")]
    check("a line stored backwards as a whole", order(ln), None)

    print("\nbrackets where the page draws them")
    # A reference, `z18048055`: "إسماعيل. (1999). تفسير" is stored
    # `( .إسماعيل1999` and ` .)تفسير` - the bracket, full stop and space at
    # the Arabic run's far end, as drawn.
    words = line(("ابن كثير، إسماعيل", None), start=484)
    left = min(x0 for _, x0, _ in words)
    ln = [("(", left - 10, left - 6), (" ", left - 6, left - 3),
          (".", left - 3, left)] + words + [
        (d, left - 32 + 5 * i, left - 27 + 5 * i) for i, d in enumerate("1999")]
    check("the bracket before the year", read(ln), "ابن كثير، إسماعيل. (1999")
    ln = [(" ", 363, 366), (".", 366, 369), (")", 369, 372)] + line(
        ("تفسير", None), start=360)
    check("the bracket after it", read(ln), "). تفسير")
    ln = [(" ", 363, 366), (".", 366, 369), (")", 369, 372)]
    check("a line of its own, on an Arabic page", read(ln, lambda: True), "). ")
    check("... left alone on an English one", read(ln, lambda: False), " .)")
    ln = [("(", 300, 304)] + [(d, 304 + 5 * i, 309 + 5 * i)
                              for i, d in enumerate("2018")] + [(")", 324, 328)]
    check("a year of its own is read as stored (Riley (2018))",
          read(ln, lambda: True), "(2018)")
    # `z7456037`: the font stores the shape drawn, `)62(`
    words = line(("جدول رقم", None), start=480)
    left = min(x0 for _, x0, _ in words)
    ln = words + [(" ", left - 4, left), (")", left - 8, left - 4),
                  ("6", left - 18, left - 13), ("2", left - 13, left - 8),
                  ("(", left - 22, left - 18), (" ", left - 26, left - 22),
                  (":", left - 29, left - 26)]
    check("brackets stored as drawn are turned round", read(ln),
          "جدول رقم (62) :")
    # `z3387756`: I(2), its closing bracket drawn with it
    words = line(("ومتغير آخر", None), start=200)
    ln = [(" ", 118, 122)] + words + [("I", 100, 104), ("(", 104, 108),
                                      ("2", 108, 113), (")", 113, 117)]
    check("a bracket inside an English run stays in it", read(ln),
          "ومتغير آخر I(2)")

    print("\na number's digits as drawn")
    # `z18441713`: ٣١٠ drawn left to right, read back ٠١٣ by the extractor
    ln = [("٠", 515, 522), ("١", 507, 514), ("٣", 500, 507), (" ", 495, 499)]
    check("Arabic-Indic digits turned back", read(ln), "٣١٠ ")
    words = line(("بنشر", None), start=340)
    ln = [("٧", 364, 371), ("٢", 357, 364), ("٣", 349, 356)] + words
    check("in a line with words", read(ln)[:3], "٣٢٧")
    ln = [("٥", 520, 526), ("٫", 516, 519), ("٣", 510, 516)]
    check("a decimal separator goes with them", read(ln), "٣٫٥")
    # the section number ٣-٢ is two numbers: left as stored
    ln = [("٣", 515, 522), ("-", 505, 512), ("٢", 497, 504)]
    check("a dash parts two numbers", read(ln), "٣-٢")
    ln = [("٣", 500, 507), ("١", 507, 514), ("٠", 515, 522)]
    check("stored as drawn: left alone", order(ln), None)

    print("\nthe brackets round a verse")
    # z18037898: "﴿ :أكل ... قال تعالى" stored, the bracket and colon drawn
    # on the left of تعالى, the verse's first word further left.
    ln = [("﴿", 300, 304), (":", 305, 307)] + line(("أكل قال تعالى", None)) \
        + [(" ", 290, 296)] + line(("ٱليوم", None), start=290)
    check("an opening bracket stored first goes before the verse",
          read(ln), "أكل قال تعالى:﴿ ٱليوم")
    ln = [("﴾", 300, 304)] + line(("رحيم غفور", None))
    check("a closing bracket stored first goes after the last word",
          read(ln), "رحيم غفور﴾")
    ln = line(("تعالى", None)) + [(":", 372, 374), ("‌", 372, 372),
                                  ("﴿", 367, 371)] + line(("وأما", None), start=366)
    check("in place past a zero-width joiner: left alone",
          read(ln), "تعالى:‌﴿وأما")
    # z21850164: the labels cut the note number 96 off the verse's line, and
    # read the verse alone; read whole, the line has a number in it.
    ln = [("﴾", 300, 304)] + line(("رحيم غفور", None)) \
        + [("9", 290, 294), ("6", 294, 298)]
    seq = _by_pieces(ln, [10, 2])
    us = units([c for c, _, _ in ln])
    check("a line the labels cut in two, read piece by piece",
          seq and "".join(ln[i][0] for i in _indices(us, seq)), "رحيم غفور﴾96")
    check("... not where the pieces do not cover it", _by_pieces(ln, [5, 2]),
          None)

    print("\nvowel marks")
    # ،ًمبكرا: the tanween stored after the comma is the word's
    ln = [("،", 300, 302), ("ً", 300, 302)] + line(("مبكرا", None))
    check("a tanween stored after a moved comma stays on the word",
          read(ln), "مبكراً،")

    print("\nthe plain text gets the same order")
    ln = [("،", 371, 375), ("ع", 391, 396), ("ش", 382, 391), ("ر", 377, 382)]
    seq = order(ln)
    orders = {"،عشر": [(seq, 4)]}
    check("a plain line with a vowel mark the detailed one lacks",
          _fix_text("x\n،عشَر\ny", {k: list(v) for k, v in orders.items()}),
          "x\nعشَر،\ny")
    # The detailed reading ends the line at ،عشر; the plain one runs on.
    ln = [("،", 360, 364), ("ع", 391, 396), ("ش", 382, 391), ("ر", 377, 382),
          ("ي", 372, 377), ("ن", 367, 372)]
    orders = {"،عشرين": [(order(ln), 6)]}
    check("a line the plain text runs on into the next",
          _fix_text("،عشرين ومع", orders), "عشرين، ومع")

    real = Path("corpus/wild/z21762915.pdf")
    if real.exists():
        print("\na real page (z21762915 page 1)")
        import pymupdf
        from convert.glyphs import repaired
        from convert.order import get_text
        with pymupdf.open(repaired(str(real))) as d:
            text = get_text(d[0], "text")
            words = "".join(s["text"] for b in get_text(d[0], "dict")["blocks"]
                            for l in b.get("lines", ()) for s in l["spans"])
        check("عشر، in the plain text", "عشر،" in text, True)
        check("،عشر gone", "،عشر" in text, False)
        check("no comma inside اجلزائر", "ا،جلزائر" in text, False)
        check("the reader's view agrees", "عشر،" in words, True)

    tagged = Path("corpus/wild/z20252126.pdf")
    if tagged.exists():
        # Word labels Benchmark apart, so the tagged reader never sees it on
        # one line with معين. Both readings must put its bracket in one
        # place, or they disagree and the gate loses the sentence
        # (2026-09-23): read as drawn, both put it after معين.
        import pymupdf
        from convert.glyphs import repaired
        from convert.order import get_text
        with pymupdf.open(repaired(str(tagged))) as d:
            text = get_text(d[8], "text")
            flags = pymupdf.TEXTFLAGS_DICT | pymupdf.TEXT_COLLECT_STRUCTURE
            labels = []

            def walk(node):
                for b in node.get("blocks", ()):
                    for ln in b.get("lines", ()):
                        labels.append("".join(s["text"] for s in ln["spans"]))
                    walk(b)
            walk(get_text(d[8], "dict", flags=flags))
        check("read whole: the bracket after معين (Benchmark)",
              "معين (Benchmark" in text, True)
        check("read by labels: the same",
              any(t.rstrip().endswith("معين (") for t in labels), True)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
