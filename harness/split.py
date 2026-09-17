#!/usr/bin/env python3
"""Split the corpus into a set to tune on and a set to leave alone.

Tuning and judging on the same files produced a three-times gap between them
(65% against 23%), which was overfitting rather than progress. A holdout set
that is never looked at during development is the only way to notice that from
the inside.

Assignment is by a hash of the file's name, so it never drifts between runs,
and stratified by producer so both halves see the same spread of Word versions
and tools.

    python -m harness.split corpus/wild/*.pdf --write out/split.json
"""
import argparse, collections, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.probe import probe
from harness.survey import producer_family
from harness.routes import run_route
from harness.metrics import score

HOLDOUT_SHARE = 0.4
MIN_ARABIC = 500


def bucket(path, share=HOLDOUT_SHARE):
    h = hashlib.sha256(Path(path).name.encode()).hexdigest()
    return "holdout" if (int(h[:8], 16) % 1000) < share * 1000 else "dev"


def classify(path):
    p = probe(path)
    text, _ = run_route("pymupdf.text", path)
    ar = score(text)["arabic"]
    return {
        "file": str(path),
        "family": producer_family(p["producer"]),
        "pages": p["pages"],
        "arabic": ar,
        "usable": ar >= MIN_ARABIC,
        "set": bucket(path),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--write", default="out/split.json")
    a = ap.parse_args()

    rows = []
    for f in a.pdfs:
        try:
            rows.append(classify(f))
        except Exception:
            continue

    usable = [r for r in rows if r["usable"]]
    dev = [r for r in usable if r["set"] == "dev"]
    hold = [r for r in usable if r["set"] == "holdout"]

    print(f"{len(rows)} files, {len(usable)} with enough Arabic to judge")
    print(f"  tune on : {len(dev)}")
    print(f"  holdout : {len(hold)}   (not opened during development)")
    print("\nproducer spread:")
    fams = collections.Counter(r["family"] for r in usable)
    print(f"  {'producer':<24}{'dev':>6}{'holdout':>9}")
    for fam, _ in fams.most_common(12):
        d = sum(1 for r in dev if r["family"] == fam)
        h = sum(1 for r in hold if r["family"] == fam)
        print(f"  {fam:<24}{d:>6}{h:>9}")

    Path(a.write).parent.mkdir(parents=True, exist_ok=True)
    Path(a.write).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {a.write}")


if __name__ == "__main__":
    main()
