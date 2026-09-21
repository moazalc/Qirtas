#!/usr/bin/env python3
"""Record the environment a score was measured in.

A score is only comparable to another score taken the same way. The corpus was
already caught drifting - re-running the fetcher returned whatever Zenodo held
that day, so every recorded number quietly described a different collection.

The rendering environment drifts the same way and is easier to miss. Rendering
is done by real Microsoft Word only (LibreOffice was removed 2026-09-21). If
the Arabic faces a document asks for are not installed, Word substitutes its
own, usually wider, so text overflows and the converter is blamed.

    python -m harness.env
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FACES = ["Simplified Arabic", "Traditional Arabic", "Sakkal Majalla",
         "AGA Arabesque", "Arabic Transparent"]

# The three that carry BODY text in this corpus. The other two are decorative
# and third-party: no file has yet needed one, and neither ships with Windows
# or Office, so their absence is a note rather than a warning.
BODY_FACES = {"Simplified Arabic", "Traditional Arabic", "Sakkal Majalla"}


def _installed_windows(face):
    """Is this face installed for Word? -> the registered name, or None.

    Read from the registry. An older check shelled out to fc-match, which does
    not exist on Windows, and read its failure as success - reporting a
    machine with NO Arabic fonts at all as correctly set up. A check that
    cannot run must say so, not pass.
    """
    try:
        import winreg
    except ImportError:
        return None
    for root, path in (
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
    ):
        try:
            with winreg.OpenKey(root, path) as k:
                for i in range(winreg.QueryInfoKey(k)[1]):
                    name = winreg.EnumValue(k, i)[0]
                    if name.lower().startswith(face.lower()):
                        return name
        except OSError:
            continue
    return None


def fingerprint():
    from harness.word import available
    from convert.pdftext import enabled

    ok, detail = available()
    fonts = {f: (_installed_windows(f) or "NOT INSTALLED") for f in FACES}
    return {
        "renderer": "word",
        "renderer_version": detail if ok else f"UNAVAILABLE ({detail})",
        "platform": sys.platform,
        "fonts": fonts,
        "body_fonts_installed": all(fonts[f] != "NOT INSTALLED" for f in BODY_FACES),
        # A switch, not the environment - but a run that cannot say which way
        # it was set cannot be compared to anything. QIRTAS_ARABIC_FIX.
        "arabic_fix": enabled(),
    }


def describe(fp=None):
    fp = fp or fingerprint()
    lines = [f"  renderer     Word  {fp['renderer_version']}",
             f"  arabic fix   {'on' if fp.get('arabic_fix', True) else 'OFF (QIRTAS_ARABIC_FIX)'}"]
    for face, got in fp["fonts"].items():
        lines.append(f"  {face:<20} -> {got}")

    missing = [f for f, v in fp["fonts"].items() if v == "NOT INSTALLED"]
    # Only the three the corpus actually asks for are worth warning about.
    # AGA Arabesque and Arabic Transparent ship with neither Windows nor
    # Office, so reporting them on every run is crying wolf - and a warning
    # that is always on is a warning nobody reads.
    matters = [f for f in missing if f in BODY_FACES]
    if matters:
        lines += [
            f"  WARNING: {', '.join(matters)} not installed. Word picks its own",
            "           face instead, usually wider, so text overflows and the",
            "           converter takes the blame. FLAGS.md 6.",
        ]
    elif missing:
        lines.append(f"  note: {', '.join(missing)} absent; neither ships with "
                     "Windows or Office, and no corpus file has needed one.")
    return "\n".join(lines)


if __name__ == "__main__":
    fp = fingerprint()
    print(describe(fp))
    print()
    print(json.dumps(fp, indent=2))
