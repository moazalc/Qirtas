#!/usr/bin/env python3
"""Pull Arabic-language PDFs from Zenodo's open API into a corpus directory.

Polite by construction: one request at a time, a real User-Agent, a delay
between calls, and a size cap so we don't drag down huge scans.

    python -m harness.fetch_corpus --n 100 --out corpus/wild       # new files
    python -m harness.fetch_corpus --from-manifest --out corpus/wild  # THIS corpus

    # the thesis corpus (2026-09-24): every Arabic thesis Zenodo holds
    python -m harness.fetch_corpus --theses --n 200 --out corpus/theses
    python -m harness.fetch_corpus --from-manifest --out corpus/theses

Those two are not the same operation, and the difference matters.

The search is sorted by `mostrecent`, so it returns whatever Arabic publications
Zenodo holds TODAY. Run it again next month and you get a different set of
files. Since the dev/holdout split is a hash of the filename, a different set
means different split membership - and every score ever recorded against this
corpus becomes a number about some other collection of documents.

`--from-manifest` re-downloads exactly the records listed in manifest.jsonl, by
Zenodo ID. That file is the only thing making this corpus reproducible, which is
why it is committed while the 567MB of PDFs beside it are not.
"""
import argparse, json, sys, time, urllib.parse, urllib.request
from pathlib import Path

API = "https://zenodo.org/api/records"
UA = "arabic-pdf2docx-research/0.1 (PDF structure survey; contact: moazdev02@gmail.com)"
MAX_MB = 25


def get(url, params=None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)


def restore(out, delay):
    """Re-download exactly the records in manifest.jsonl, by Zenodo ID.

    Skips what is already on disk, so it is safe to re-run after an interrupted
    transfer. A record withdrawn from Zenodo since the manifest was written
    cannot be recovered - it is reported and counted rather than passed over in
    silence, because a corpus quietly one file short still scores, and the
    score would be a number about a different set of documents.
    """
    manifest = out / "manifest.jsonl"
    if not manifest.exists():
        sys.exit(f"no manifest at {manifest} - nothing to restore from")

    rows = [json.loads(l) for l in manifest.open(encoding="utf-8") if l.strip()]
    have, got, lost = 0, 0, []
    for i, row in enumerate(rows, 1):
        dest = out / row["file"]
        if dest.exists() and dest.stat().st_size > 0:
            have += 1
            continue
        try:
            rec = get(f"{API}/{row['id']}")
            pdfs = [f for f in rec.get("files", [])
                    if f.get("key", "").lower().endswith(".pdf")]
            # The thesis manifest names the file taken; the first corpus
            # always took the first PDF.
            pdfs = [f for f in pdfs if f["key"] == row["key"]] or                 pdfs[:0 if "key" in row else 1]
            if not pdfs:
                raise ValueError("record no longer carries that PDF")
            download(pdfs[0]["links"]["self"], dest)
        except Exception as e:
            dest.unlink(missing_ok=True)
            lost.append((row["file"], str(e)))
            print(f"  [{i:>3}/{len(rows)}] {row['file']}  GONE: {e}")
            continue
        got += 1
        print(f"  [{i:>3}/{len(rows)}] {row['file']}  restored")
        time.sleep(delay)

    print(f"\n{have} already present, {got} restored, {len(lost)} unavailable")
    if lost:
        print("\nThese are no longer on Zenodo. The corpus is NOT the one the")
        print("recorded scores were measured against; say so before quoting them:")
        for name, why in lost:
            print(f"  {name}: {why}")
    return 1 if lost else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", default="corpus/wild")
    ap.add_argument("--query", default="language:ara")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--from-manifest", action="store_true",
                    help="restore exactly this corpus instead of fetching new files")
    ap.add_argument("--theses", action="store_true",
                    help="theses only, largest PDF of each record, up to 60MB")
    a = ap.parse_args()
    max_mb = 60 if a.theses else MAX_MB

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.from_manifest:
        return restore(out, a.delay)

    manifest = out / "manifest.jsonl"
    seen = set()
    if manifest.exists():
        seen = {json.loads(l)["id"] for l in manifest.open(encoding="utf-8")}

    got, page, skipped = 0, 1, 0
    with manifest.open("a", encoding="utf-8") as mf:
        while got < a.n and page <= 100:
            try:
                params = {"q": a.query, "size": 20, "page": page,
                          "sort": "mostrecent", "type": "publication"}
                if a.theses:
                    params["subtype"] = "dissertation"
                data = get(API, params)
            except Exception as e:
                print(f"  page {page} failed: {e}")
                break
            hits = data["hits"]["hits"]
            if not hits:
                break
            for rec in hits:
                if got >= a.n:
                    break
                rid = rec["id"]
                if rid in seen:
                    continue
                pdfs = [f for f in rec.get("files", [])
                        if f.get("key", "").lower().endswith(".pdf")]
                if not pdfs:
                    skipped += 1
                    continue
                # A thesis record can carry its abstract or cover as a
                # separate PDF; the thesis is the largest.
                f = max(pdfs, key=lambda x: x.get("size", 0)) if a.theses else pdfs[0]
                mb = f.get("size", 0) / 1e6
                if mb > max_mb:
                    skipped += 1
                    continue
                dest = out / f"z{rid}.pdf"
                try:
                    download(f["links"]["self"], dest)
                except Exception as e:
                    print(f"  {rid}: {e}")
                    dest.unlink(missing_ok=True)
                    continue
                got += 1
                seen.add(rid)
                md = rec.get("metadata", {})
                mf.write(json.dumps({
                    "id": rid, "file": dest.name, "mb": round(mb, 2),
                    "title": (md.get("title") or "")[:120],
                    "type": md.get("resource_type", {}).get("title", ""),
                    "year": str(md.get("publication_date", ""))[:4],
                    **({"key": f["key"]} if a.theses else {}),
                }, ensure_ascii=False) + "\n")
                mf.flush()
                print(f"  [{got:>3}/{a.n}] {dest.name} {mb:>5.1f}MB  {(md.get('title') or '')[:58]}")
                time.sleep(a.delay)
            page += 1
    print(f"\ndownloaded {got}, skipped {skipped} (no pdf or >{max_mb}MB) -> {out}")


if __name__ == "__main__":
    sys.exit(main() or 0)
