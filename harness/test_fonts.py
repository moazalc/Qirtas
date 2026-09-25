#!/usr/bin/env python3
"""Tests for the missing-font check (convert/fonts.py, Part 2).

    python -m harness.test_fonts

Before converting, the person is told which of the PDF's fonts this computer
lacks and where to get them, and may install them and check again. The PDFs
here are made on the spot: a line of text whose font is then renamed, so the
file asks for a font by whatever name the test needs.
"""
import builtins
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf

from convert import fonts

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<52} got {got!r}")
    if not ok:
        print(f"        want {want!r}")
        FAILED.append(name)


def _pdf_asking_for(tmp, font_name, text="A line of text in a font by that name."):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontname="helv")
    for x in range(1, doc.xref_length()):
        if doc.xref_get_key(x, "Type")[1] == "/Font":
            doc.xref_set_key(x, "BaseFont", f"/{font_name}")
    path = tmp / f"{font_name.replace('+', '_')}.pdf"
    doc.save(path)
    doc.close()
    return path


def main():
    tmp = Path("out/tests/fonts")
    tmp.mkdir(parents=True, exist_ok=True)

    print("names as a person would type them")
    check("subset tag and style", fonts._readable("ABCDEE+BoutrosNewsH1-Bold"),
          ("Boutros News H1", "Bold"))
    check("Monotype's MT", fonts._readable("TimesNewRomanPSMT"), ("Times New Roman", ""))
    check("Regular is no style", fonts._readable("MunaRegular"), ("Muna", ""))

    print("\na font no computer has is named, with the plain advice")
    found = fonts.missing(_pdf_asking_for(tmp, "ABCDEE+QirtasNoSuchFont-Bold"))
    check("one font missing", [(m.name, m.style) for m in found],
          [("Qirtas No Such Font", "Bold")])
    check("... not only a style", found and found[0].only_style, False)
    check("... where to get it", found and found[0].where, fonts.ELSEWHERE)
    check("... and the message names it", "Qirtas No Such Font Bold" in fonts.message(found), True)

    print("\na font Windows has in a collection file is not called missing")
    # Cambria Math lives in cambria.ttc, which the converter's own index does
    # not read; asked alone, it called Cambria Math missing on every computer.
    if "cambriamath" in fonts._windows():
        check("Cambria Math", fonts.missing(_pdf_asking_for(tmp, "CambriaMath")), [])
    else:
        print("  skip  Cambria Math is not installed here")

    print("\na name Word cut at 24 characters is matched by its start")
    if "timesnewromanbolditalic" in fonts._windows():
        check("Times New Roman PS-Bold Ital",
              fonts._installed("TimesNewRomanPS-BoldItal", fonts._windows()), True)
    check("KFGQPC Quran fonts: where", fonts.missing(
        _pdf_asking_for(tmp, "KFGQPCUthmanicScriptHafsQirtasTest"))[0].where,
        fonts.WHERE_PREFIX["kfgqpc"])

    print("\nnothing missing, nothing said")
    check("Arial", fonts.message(fonts.missing(_pdf_asking_for(tmp, "ArialMT"))), "")

    print("\nthe person installs, presses Enter, and it looks again")
    from convert import __main__ as cli
    answers = iter(["", "go"])
    asked, looked = [], []
    real_input, real_missing, real_rescan = builtins.input, fonts.missing, fonts.rescan
    builtins.input = lambda prompt="": asked.append(prompt) or next(answers)
    fonts.missing = lambda pdf: looked.append(pdf) or real_missing(pdf)
    fonts.rescan = lambda: looked.append("rescan")
    try:
        cli._ask_fonts(_pdf_asking_for(tmp, "QirtasNoSuchFont"), wait=True)
    finally:
        builtins.input, fonts.missing, fonts.rescan = real_input, real_missing, real_rescan
    check("asked twice: Enter, then go", len(asked), 2)
    check("looked again after Enter", [x for x in looked if x == "rescan"], ["rescan"])

    print(f"\n{len(FAILED)} failed" if FAILED else "\nall passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
