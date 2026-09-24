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

from convert.order import _fix_text, _indices, order, units

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


def read(ln):
    seq = order(ln)
    if seq is None:
        return "".join(c for c, _, _ in ln)
    return "".join(" " if i is None else ln[i][0]
                   for i in _indices(units([c for c, _, _ in ln]), seq))


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
    check("a bracket between a word and its mark", order(ln), None)

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
        # one line with معين; the plain reading must not move its bracket
        # either, or the two disagree and the gate loses the sentence.
        import pymupdf
        from convert.glyphs import repaired
        from convert.order import get_text
        with pymupdf.open(repaired(str(tagged))) as d:
            text = get_text(d[8], "text")
        check("a line the labels split is left alone (Benchmark)",
              "معين (Benchmark" in text, False)

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
