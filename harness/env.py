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


def _fc_match(face):
    try:
        out = subprocess.run(["fc-match", face], capture_output=True,
                             text=True, timeout=20).stdout
        return out.split(":")[0].strip() or "?"
    except Exception:
        return "?"


def fingerprint():
    from harness.roundtrip import SOFFICE
    try:
        ver = subprocess.run([SOFFICE, "--version"], capture_output=True,
                             text=True, timeout=60).stdout.strip().split("\n")[0]
    except Exception:
        ver = "missing"
    return {
        "soffice_path": SOFFICE,
        "soffice_version": ver,
        "fonts": {f: _fc_match(f) for f in FACES},
        "substitutions_applied": all(
            not _fc_match(f).lower().startswith("noto") for f in FACES),
    }


def describe(fp=None):
    fp = fp or fingerprint()
    lines = [f"  LibreOffice  {fp['soffice_version']}",
             f"               {fp['soffice_path']}"]
    for face, got in fp["fonts"].items():
        lines.append(f"  {face:<20} -> {got}")
    if not fp["substitutions_applied"]:
        lines.append("  WARNING: Arabic faces fall back to Noto, which is wider than the")
        lines.append("           fonts these documents ask for. Text will overflow and the")
        lines.append("           scores will not be comparable. See docs/fonts.md.")
    return "\n".join(lines)


if __name__ == "__main__":
    fp = fingerprint()
    print(describe(fp))
    print()
    print(json.dumps(fp, indent=2))
