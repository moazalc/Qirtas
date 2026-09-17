#!/usr/bin/env python3
"""Pull Arabic-language PDFs from Zenodo's open API into a corpus directory.

Polite by construction: one request at a time, a real User-Agent, a delay
between calls, and a size cap so we don't drag down huge scans.

    python -m harness.fetch_corpus --n 100 --out corpus/wild
"""
import argparse, json, time, urllib.parse, urllib.request
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", default="corpus/wild")
    ap.add_argument("--query", default="language:ara")
    ap.add_argument("--delay", type=float, default=1.0)
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.jsonl"
    seen = set()
    if manifest.exists():
        seen = {json.loads(l)["id"] for l in manifest.open(encoding="utf-8")}

    got, page, skipped = 0, 1, 0
    with manifest.open("a", encoding="utf-8") as mf:
        while got < a.n and page <= 100:
            try:
                data = get(API, {"q": a.query, "size": 20, "page": page,
                                 "sort": "mostrecent", "type": "publication"})
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
                f = pdfs[0]
                mb = f.get("size", 0) / 1e6
                if mb > MAX_MB:
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
                }, ensure_ascii=False) + "\n")
                mf.flush()
                print(f"  [{got:>3}/{a.n}] {dest.name} {mb:>5.1f}MB  {(md.get('title') or '')[:58]}")
                time.sleep(a.delay)
            page += 1
    print(f"\ndownloaded {got}, skipped {skipped} (no pdf or >{MAX_MB}MB) -> {out}")


if __name__ == "__main__":
    main()
