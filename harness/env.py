#!/usr/bin/env python3
"""Record the environment a score was measured in.

A score is only comparable to another score taken the same way. The corpus was
already caught drifting - re-running the fetcher returned whatever Zenodo held
that day, so every recorded number quietly described a different collection.

The rendering environment drifts the same way and is easier to miss. This
machine resolves Simplified Arabic to Amiri; a machine without the substitution
rules falls back to Noto Sans Arabic, which is wider, so text overflows and the
converter is blamed. The office regression run scores 61.4% where the plan
records 49% for the same code - almost certainly this, not a change in the
converter.

    python -m harness.env
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FACES = ["Simplified Arabic", "Traditional Arabic", "Sakkal Majalla",
         "AGA Arabesque", "Arabic Transparent"]

# The three that carry BODY text in this corpus. The other two are decorative
# and third-party: no file has yet needed one, and neither ships with Windows
# or Office, so their absence is a note rather than a warning.
BODY_FACES = {"Simplified Arabic", "Traditional Arabic", "Sakkal Majalla"}


def _fc_match(face):
    try:
        out = subprocess.run(["fc-match", face], capture_output=True,
                             text=True, timeout=20).stdout
        return out.split(":")[0].strip() or "?"
    except Exception:
        return "?"


def _installed_windows(face):
    """Is this face installed for Word? -> the registered name, or None.

    fc-match does not exist on Windows, and the old code read its failure ("?")
    as "not Noto, so the substitutions are fine" - which reported a machine
    with NO Arabic fonts at all as correctly set up. A check that cannot run
    must say so, not pass.
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
    from harness.roundtrip import SOFFICE, _renderer

    renderer = _renderer()
    windows = sys.platform == "win32"

    if renderer == "word":
        from harness.word import available
        ok, detail = available()
        ver, path = (detail if ok else f"UNAVAILABLE ({detail})"), "COM"
    else:
        try:
            ver = subprocess.run([SOFFICE, "--version"], capture_output=True,
                                 text=True, timeout=60).stdout.strip().split("\n")[0]
        except Exception:
            ver = "missing"
        path = SOFFICE

    if windows:
        fonts = {f: (_installed_windows(f) or "NOT INSTALLED") for f in FACES}
        # Windows has no fontconfig, so there is no way to map a missing face
        # onto a substitute without admin rights. Either the document's own
        # font is there or the renderer picks something of its own width.
        applied = None
    else:
        fonts = {f: _fc_match(f) for f in FACES}
        applied = all(not v.lower().startswith("noto") for v in fonts.values())

    return {
        "renderer": renderer,
        "renderer_version": ver,
        "renderer_path": path,
        "platform": sys.platform,
        "fonts": fonts,
        "substitutions_applied": applied,
    }


def describe(fp=None):
    fp = fp or fingerprint()
    label = "Word" if fp["renderer"] == "word" else "LibreOffice"
    lines = [f"  renderer     {label}  {fp['renderer_version']}",
             f"               {fp['renderer_path']}"]
    for face, got in fp["fonts"].items():
        lines.append(f"  {face:<20} -> {got}")

    missing = [f for f, v in fp["fonts"].items()
               if v in ("NOT INSTALLED", "?") or v.lower().startswith("noto")]
    # Only the three the corpus actually asks for are worth warning about.
    # AGA Arabesque and Arabic Transparent ship with neither Windows nor
    # Office, so reporting them on every run is crying wolf - and a warning
    # that is always on is a warning nobody reads.
    matters = [f for f in missing if f in BODY_FACES]
    if fp["substitutions_applied"] is None and matters:
        lines += [
            f"  WARNING: {', '.join(matters)} not installed. Windows has no",
            "           fontconfig, so there is no way to map the name onto a",
            "           substitute without admin rights - the renderer picks its",
            "           own face, which is usually wider, so text overflows and",
            "           the converter takes the blame. FLAGS.md 6.",
        ]
    elif fp["substitutions_applied"] is None and missing:
        lines.append(f"  note: {', '.join(missing)} absent; neither ships with "
                     "Windows or Office, and no corpus file has needed one.")
    elif fp["substitutions_applied"] is False:
        lines += [
            "  WARNING: Arabic faces fall back to Noto, which is wider than the",
            "           fonts these documents ask for. Text will overflow and the",
            "           scores will not be comparable. See docs/fonts.md.",
        ]
    return "\n".join(lines)


if __name__ == "__main__":
    fp = fingerprint()
    print(describe(fp))
    print()
    print(json.dumps(fp, indent=2))
