#!/usr/bin/env python3
"""Compare two holdout runs, and split each by document class.

    python -m harness.report_holdout out/holdout.json out/holdout_postfix.json

Two runs exist because the first one crashed on three files and the fix changed
which files are in the corpus at all. Looking at a holdout twice is only a
problem if you SELECT between the results, so both are printed side by side and
the difference in sample size is stated rather than smoothed over.

Split by class because the headline mean describes no actual file: a newspaper
front page in five columns at 6.4pt and an ordinary book page are different
problems, and averaging them produces a number true of neither.
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.doctype import is_periodical


def load(path):
    """Read an eval result file.

    Older runs wrote a bare list of results; newer ones wrap it as
    {"env": ..., "set": ..., "results": [...]} so a score carries the
    environment it was measured in. Accept both, so results recorded before
    that change still compare.
    """
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("results", [])
    return data


def classify(rows):
    out = {"document": [], "periodical": []}
    for r in rows:
        src = Path("corpus/wild") / r["file"]
        key = "periodical" if (src.exists() and is_periodical(str(src))) else "document"
        out[key].append(r)
    return out


def describe(rows):
    if not rows:
        return None
    text = [r["text_score"] for r in rows]
    page = [r["page_score"] for r in rows]
    kept = [r.get("kept", 1.0) for r in rows]
    infl = [r["pages_out"] / max(1, r["pages_orig"]) for r in rows]
    return {
        "n": len(rows),
        "text": statistics.mean(text),
        "text_med": statistics.median(text),
        "page": statistics.mean(page),
        "page_med": statistics.median(page),
        "infl": statistics.median(infl),
        "kept": statistics.mean(kept),
        "worst": min(kept),
        "ge95": sum(1 for t in text if t >= 0.95) / len(text),
    }


def show(label, rows):
    classes = classify(rows)
    print(f"\n{label} — {len(rows)} files scored")
    print(f"  {'class':<12}{'n':>4}{'text':>8}{'med':>8}{'page':>8}{'med':>7}"
          f"{'infl':>7}{'>=95%':>8}{'worst kept':>12}")
    for name in ("document", "periodical"):
        d = describe(classes[name])
        if not d:
            continue
        print(f"  {name:<12}{d['n']:>4}{d['text']:>8.1%}{d['text_med']:>8.1%}"
              f"{d['page']:>8.1%}{d['page_med']:>7.1%}{d['infl']:>7.2f}x"
              f"{d['ge95']:>8.0%}{d['worst']:>12.2%}")
    # The hard gate: nothing may be lost. Name every file that broke it.
    broke = sorted((r for r in rows if r.get("kept", 1.0) < 0.999),
                   key=lambda r: r["kept"])
    if broke:
        print(f"  hard gate broken by {len(broke)} file(s):")
        for r in broke:
            print(f"    {r['file']:<24} kept {r['kept']:.2%}  "
                  f"{r['pages_orig']} -> {r['pages_out']} pages")
    else:
        print("  hard gate held on every file")


def main():
    args = sys.argv[1:] or ["out/holdout.json", "out/holdout_postfix.json"]
    runs = [(p, load(p)) for p in args]
    for path, rows in runs:
        if rows is None:
            print(f"\n{path} — not written yet")
            continue
        show(path, rows)

    present = [(p, r) for p, r in runs if r]
    if len(present) == 2:
        a, b = present[0][1], present[1][1]
        fa, fb = {r["file"] for r in a}, {r["file"] for r in b}
        common = fa & fb
        # Only meaningful for two runs of the SAME set. Given dev and holdout
        # the overlap is empty and the "difference" is just the split itself,
        # which is not a result and should not be printed as one.
        if not common:
            print(f"\nthese two runs share no files - different sets, so there "
                  f"is nothing to compare like for like")
            return
        only_b, only_a = sorted(fb - fa), sorted(fa - fb)
        print(f"\nfiles in the second run only: {only_b or 'none'}")
        print(f"files in the first run only:  {only_a or 'none'}")
        da = describe([r for r in a if r["file"] in common])
        db = describe([r for r in b if r["file"] in common])
        print(f"\non the {len(common)} files BOTH runs scored — the honest "
              f"like-for-like:")
        print(f"  text {da['text']:.1%} -> {db['text']:.1%}   "
              f"right page {da['page']:.1%} -> {db['page']:.1%}")


if __name__ == "__main__":
    main()
