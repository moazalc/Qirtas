#!/usr/bin/env python3
"""Evaluate the converter against the corpus split.

Default is the tuning set. The holdout set exists to answer one question at the
end - does this generalise, or have I fitted the files I could see? - so
opening it during development destroys the only safeguard there is.

    python -m harness.eval --n 30            # tune on a sample
    python -m harness.eval --set regression  # the hard ActualText case
    python -m harness.eval --set holdout     # once, at the end
"""
import argparse, datetime, json, random, statistics, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.roundtrip import run_one
from harness.compare import text_of, text_of_docx
from convert.scan import Refused
from harness.loss import coverage
from harness.env import fingerprint, describe

BOLD, DIM, GRN, YEL, RED, OFF = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def files_for(which, split_path="out/split.json"):
    if which == "regression":
        return sorted(str(p) for p in Path("corpus").glob("*.pdf"))
    rows = json.loads(Path(split_path).read_text(encoding="utf-8"))
    return [r["file"] for r in rows if r["usable"] and r["set"] == which]


def _pages_of(path):
    try:
        import pymupdf
        with pymupdf.open(path) as d:
            return len(d)
    except Exception:
        return 0


def score_one(args):
    """One file, start to finish. Top level so it can be sent to a worker."""
    f, work = args
    r = run_one(f, work)
    cov, _ = coverage(text_of(f), text_of_docx(r["docx"]))
    r["kept"] = round(cov, 4)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev", choices=["dev", "holdout", "regression"])
    ap.add_argument("--n", type=int, default=0, help="sample this many (0 = all)")
    ap.add_argument("--max-pages", type=int, default=60,
                    help="skip files longer than this (0 = no limit)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--work", default="out/work/eval")
    ap.add_argument("--jobs", type=int, default=6,
                    help="files in parallel; 1 to run serially")
    ap.add_argument("--json", help="extra copy of the results at this exact path")
    ap.add_argument("--label", default="",
                    help="what this run was testing, e.g. 'after-backfill-fix'")
    a = ap.parse_args()

    if a.set == "holdout":
        print(f"{YEL}opening the holdout set - only do this to check generalisation{OFF}")

    env = fingerprint()
    print(f"{DIM}environment{OFF}")
    print(describe(env))
    if not env["renderer_version"].startswith("Word"):
        sys.exit(f"Word is unusable: {env['renderer_version']}")
    if not env["body_fonts_installed"]:
        print(f"{YEL}  scores from this machine are not comparable to ones taken with"
              f" the documents' own fonts installed{OFF}")
    print()

    files = files_for(a.set)
    if a.n and a.n < len(files):
        random.Random(a.seed).shuffle(files)
        files = sorted(files[:a.n])

    # Big files out, AFTER sampling, so the same seed still picks the same
    # files and a capped run is the uncapped one minus the long documents. One
    # 586-page file alone held a 30-file run open for over half an hour, and
    # the work that matters is the theses, none longer than 25 pages. Moaz's
    # call, 2026-09-21.
    if a.max_pages:
        long = [f for f in files if _pages_of(f) > a.max_pages]
        if long:
            print(f"{DIM}skipping {len(long)} file(s) over {a.max_pages} pages"
                  f" (--max-pages 0 to include){OFF}")
            files = [f for f in files if f not in long]

    # Longest first. With workers running in parallel the run cannot finish
    # before its slowest file does, so a 432-page document left until last would
    # sit alone on the critical path with everything else already idle.
    files.sort(key=_pages_of, reverse=True)

    # Files the converter refuses (scans, FLAGS.md 1) are not failures and
    # not scores: counted apart, so an average is over files we convert.
    rows, losses, refused = [], [], []
    done = 0
    if a.jobs > 1:
        with ProcessPoolExecutor(max_workers=a.jobs) as pool:
            futures = {pool.submit(score_one, (f, a.work)): f for f in files}
            for fut in as_completed(futures):
                done += 1
                f = futures[fut]
                try:
                    r = fut.result()
                    rows.append(r)
                    losses.append(r["kept"])
                except Refused as e:
                    refused.append({"file": Path(f).name, "why": str(e)})
                except Exception as e:
                    print(f"  {RED}FAIL{OFF} {Path(f).name}: {type(e).__name__}: {e}"[:130])
                if done % 10 == 0:
                    print(f"{DIM}  ...{done}/{len(files)}{OFF}", flush=True)
    else:
        for f in files:
            done += 1
            try:
                r = score_one((f, a.work))
                rows.append(r)
                losses.append(r["kept"])
            except Refused as e:
                refused.append({"file": Path(f).name, "why": str(e)})
            except Exception as e:
                print(f"  {RED}FAIL{OFF} {Path(f).name}: {type(e).__name__}: {e}"[:130])
            if done % 10 == 0:
                print(f"{DIM}  ...{done}/{len(files)}{OFF}", flush=True)

    # Order of completion is arbitrary under a pool; sort so two runs of the
    # same set produce byte-identical json.
    rows.sort(key=lambda r: r["file"])

    if not rows:
        return
    kept = statistics.mean(losses)
    worst = min(losses)
    txt = statistics.mean(r["text_score"] for r in rows)
    pg = statistics.mean(r["page_score"] for r in rows)
    infl = statistics.median(r["pages_out"] / max(1, r["pages_orig"]) for r in rows)

    head = (f"{a.set} set — {len(rows)} files"
            + (f"  [{a.label}]" if a.label else "")
            + (f", {len(refused)} refused as scans" if refused else ""))
    summary = "\n".join([
        head,
        f"  nothing lost   {kept:>7.1%}  (worst file {worst:.1%})",
        f"  words in order {txt:>7.1%}",
        f"  right page     {pg:>7.1%}   (unrelated docs ~13%)",
        f"  page inflation {infl:>7.2f}x",
    ])
    print(f"\n{BOLD}{head}{OFF}")
    print(f"  nothing lost   {GRN if worst >= 0.999 else RED}{kept:>7.1%}{OFF}  "
          f"(worst file {GRN if worst >= 0.999 else RED}{worst:.1%}{OFF})")
    print(f"  words in order {txt:>7.1%}")
    print(f"  right page     {pg:>7.1%}   {DIM}(unrelated docs ~13%){OFF}")
    print(f"  page inflation {infl:>7.2f}x")

    # Every run records itself, whether or not anyone remembered to ask.
    #
    # out/ used to be a flat drawer of 78 items with names like final2, mine
    # and fittest, and no way to tell which number came from which code. This
    # project's central rule is that a score means nothing without knowing how
    # it was produced, so the recording cannot be optional - or the run that
    # matters is the one nobody saved.
    payload = {"env": env, "set": a.set, "label": a.label,
               "n": len(rows), "files_requested": len(files),
               "refused": refused,
               "sample": {"n": a.n, "seed": a.seed} if a.n else None,
               "scores": {"kept": round(kept, 4), "worst_kept": round(worst, 4),
                          "text": round(txt, 4), "page": round(pg, 4),
                          "inflation": round(infl, 4)},
               "results": rows}
    stamp = datetime.date.today().isoformat()
    name = "-".join(x for x in (stamp, a.set, a.label) if x)
    run = Path("out/runs") / name
    n = 2
    while run.exists():
        run = Path("out/runs") / f"{name}-{n}"
        n += 1
    run.mkdir(parents=True)
    (run / "results.json").write_text(json.dumps(payload, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
    (run / "summary.txt").write_text(summary + "\n" + describe(env) + "\n",
                                     encoding="utf-8")
    print(f"\n{DIM}recorded in {run}{OFF}")

    # A run that reports fewer files than it asked for is a story in itself -
    # a crash removes a file from the average instead of failing the run.
    if len(rows) + len(refused) < len(files):
        print(f"{RED}  {len(files) - len(rows) - len(refused)} file(s) crashed "
              f"and are NOT in these numbers{OFF}")

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(payload, ensure_ascii=False,
                                           indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
