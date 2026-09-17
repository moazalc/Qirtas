#!/usr/bin/env python3
"""Evaluate the converter against the corpus split.

Default is the tuning set. The holdout set exists to answer one question at the
end - does this generalise, or have I fitted the files I could see? - so
opening it during development destroys the only safeguard there is.

    python -m harness.eval --n 30            # tune on a sample
    python -m harness.eval --set regression  # the hard ActualText case
    python -m harness.eval --set holdout     # once, at the end
"""
import argparse, json, random, statistics, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.roundtrip import run_one
from harness.compare import text_of, text_of_docx
from harness.loss import coverage

BOLD, DIM, GRN, YEL, RED, OFF = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def files_for(which, split_path="out/split.json"):
    if which == "regression":
        return sorted(str(p) for p in Path("corpus").glob("*.pdf"))
    rows = json.loads(Path(split_path).read_text(encoding="utf-8"))
    return [r["file"] for r in rows if r["usable"] and r["set"] == which]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev", choices=["dev", "holdout", "regression"])
    ap.add_argument("--n", type=int, default=0, help="sample this many (0 = all)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--work", default="out/eval")
    ap.add_argument("--json")
    a = ap.parse_args()

    if a.set == "holdout":
        print(f"{YEL}opening the holdout set - only do this to check generalisation{OFF}")

    files = files_for(a.set)
    if a.n and a.n < len(files):
        random.Random(a.seed).shuffle(files)
        files = sorted(files[:a.n])

    rows, losses = [], []
    for i, f in enumerate(files, 1):
        try:
            r = run_one(f, a.work)
            cov, _ = coverage(text_of(f), text_of_docx(r["docx"]))
            r["kept"] = round(cov, 4)
            rows.append(r)
            losses.append(cov)
        except Exception as e:
            print(f"  {RED}FAIL{OFF} {Path(f).name}: {type(e).__name__}: {e}"[:130])
        if i % 10 == 0:
            print(f"{DIM}  ...{i}/{len(files)}{OFF}", flush=True)

    if not rows:
        return
    kept = statistics.mean(losses)
    worst = min(losses)
    txt = statistics.mean(r["text_score"] for r in rows)
    pg = statistics.mean(r["page_score"] for r in rows)
    infl = statistics.median(r["pages_out"] / max(1, r["pages_orig"]) for r in rows)

    print(f"\n{BOLD}{a.set} set — {len(rows)} files{OFF}")
    print(f"  nothing lost   {GRN if worst >= 0.999 else RED}{kept:>7.1%}{OFF}  "
          f"(worst file {GRN if worst >= 0.999 else RED}{worst:.1%}{OFF})")
    print(f"  words in order {txt:>7.1%}")
    print(f"  right page     {pg:>7.1%}   {DIM}(unrelated docs ~13%){OFF}")
    print(f"  page inflation {infl:>7.2f}x")

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
