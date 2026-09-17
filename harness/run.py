#!/usr/bin/env python3
"""Diagnostic harness: run every extraction route against every PDF and report
which one actually recovers the text.

    python -m harness.run corpus/*.pdf [--json out/report.json] [--dump out/text]
"""
import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.probe import probe
from harness.routes import ROUTES, run_route
from harness.metrics import score, recovery

BOLD, DIM, RED, GRN, YEL, OFF = "\033[1m", "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[0m"


def analyse(path, dump_dir=None):
    rec = {"probe": probe(path), "routes": {}}
    for name in ROUTES:
        t0 = time.time()
        text, err = run_route(name, path)
        s = score(text)
        s["error"] = err
        s["seconds"] = round(time.time() - t0, 2)
        rec["routes"][name] = s
        if dump_dir and text.strip():
            d = Path(dump_dir) / Path(path).stem
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{name}.txt").write_text(text, encoding="utf-8")
    best = max((r["arabic"] for r in rec["routes"].values()), default=0)
    for r in rec["routes"].values():
        r["recovery"] = round(recovery(r, best), 4)
    rec["best_arabic"] = best
    return rec


def report(rec):
    p = rec["probe"]
    print(f"\n{BOLD}{p['file']}{OFF}")
    print(f"  {p['pages']}pp | {p['producer']} | lang={p['lang']} | "
          f"tagged={p['tagged']} marked={p['marked']}")
    if p["tagged"]:
        print(f"  tags={p['tag_total']:,} semantic={p['tag_semantic']} "
              f"actualtext={p['actualtext_elements']:,} headings={p['has_headings']}")
        top = sorted(p["tags"].items(), key=lambda kv: -kv[1])[:8]
        print(f"  {DIM}{', '.join(f'{k}×{v}' for k, v in top)}{OFF}")
    print(f"  fonts: {p['fonts_subset']} subset / {len(p['fonts'])} total")
    print(f"  {DIM}{'route':<24}{'arabic':>8}{'recov':>8}{'pres':>6}{'pua':>6}{'words':>8}{'sec':>6}{OFF}")
    for name, r in sorted(rec["routes"].items(), key=lambda kv: -kv[1]["arabic"]):
        if r["error"]:
            print(f"  {name:<24}{RED}{'FAIL':>8}{OFF}  {DIM}{r['error'][:52]}{OFF}")
            continue
        pct = r["recovery"]
        col = GRN if pct > 0.95 else (YEL if pct > 0.5 else RED)
        warn = f" {RED}⚠ corrupt{OFF}" if r["presentation_forms"] else ""
        print(f"  {name:<24}{r['arabic']:>8,}{col}{pct:>8.1%}{OFF}"
              f"{r['presentation_forms']:>6}{r['pua']:>6}{r['words']:>8,}{r['seconds']:>6.1f}{warn}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--json")
    ap.add_argument("--dump", help="write each route's text to this dir")
    a = ap.parse_args()

    out = []
    for f in a.pdfs:
        try:
            rec = analyse(f, a.dump)
        except Exception as e:
            print(f"{RED}{f}: {type(e).__name__}: {e}{OFF}")
            continue
        out.append(rec)
        report(rec)

    if out:
        print(f"\n{BOLD}── winner by file ──{OFF}")
        tally = {}
        for rec in out:
            ok = {k: v for k, v in rec["routes"].items() if not v["error"]}
            win = max(ok, key=lambda k: ok[k]["arabic"]) if ok else "—"
            tally[win] = tally.get(win, 0) + 1
            print(f"  {rec['probe']['file'][:44]:<46} {GRN}{win}{OFF} "
                  f"({rec['best_arabic']:,} arabic chars)")
        print(f"\n{BOLD}── route wins ──{OFF}")
        for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"  {k:<26} {v}/{len(out)}")

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n{DIM}json -> {a.json}{OFF}")


if __name__ == "__main__":
    main()
