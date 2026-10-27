#!/usr/bin/env python3
"""A test set of random Arabic PDFs from ordinary websites: no answer key.

Moaz, 2026-10-26: besides the UN pairs (harness/un.py), "random files from
elsewhere". Zenodo (corpus/wild, corpus/theses) is academic publishing; these
are what Arab-country websites actually put online - ministries, schools,
companies, notices.

Links come from Common Crawl's index (a public crawl of the web), sampled at
random across country domains. The files themselves are downloaded from the
live site: data.commoncrawl.org refuses this connection (2026-10-26) and the
crawl cuts PDFs at 1MB anyway. So the set is reproducible only while the sites
keep the files - the manifest carries each file's sha256 and `fetch` reports
a file that is gone or changed rather than taking a different one.

    python -m harness.web pick --n 30       # -> corpus/web/
    python -m harness.web fetch             # restore exactly corpus/web/manifest.jsonl

Kept only if it is a digital PDF with Arabic text (scans are out of scope).
"""
import argparse
import hashlib
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path("corpus/web")
MANIFEST = HOME / "manifest.jsonl"
CRAWL = "CC-MAIN-2026-39"
INDEX = f"https://index.commoncrawl.org/{CRAWL}-index?"
AGENT = {"User-Agent": "QirtasTestSet/0.1 (https://github.com/moazalc/Qirtas)"}
TLDS = ["sa", "ae", "eg", "jo", "ma", "dz", "tn", "iq", "kw", "qa", "om",
        "bh", "lb", "sy", "ly", "sd", "ps", "ye"]
MAX_MB = 20
MIN_ARABIC_WORDS = 150
HOLDOUT_SHARE = 0.4
ARABIC = re.compile(r"[ء-ي]{2,}")


def index(params, tries=4):
    """The index answers about half its queries with 504 (2026-10-26); retry."""
    url = INDEX + urllib.parse.urlencode(params, doseq=True)
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=180) as r:
                return r.read().decode("utf-8")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def pages(tld, cache={}):
    if tld not in cache:
        cache[tld] = json.loads(index({"url": f"*.{tld}", "filter": "mime-detected:application/pdf",
                                       "showNumPages": "true"}))["pages"]
    return cache[tld]


def links(tld, page):
    text = index({"url": f"*.{tld}", "filter": ["mime-detected:application/pdf", "status:200"],
                  "output": "json", "page": page})
    return [json.loads(l)["url"] for l in text.splitlines() if l.startswith("{")]


def download(url):
    req = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read(MAX_MB * 1_000_000 + 1)
    if len(data) > MAX_MB * 1_000_000:
        raise ValueError(f"over {MAX_MB}MB")
    return data


def judge(data):
    """Why this file is refused, or its description."""
    import pymupdf
    if not data.startswith(b"%PDF"):
        return "not a PDF"
    d = pymupdf.open(stream=data, filetype="pdf")
    words = sum(len(ARABIC.findall(p.get_text())) for p in d)
    if words < MIN_ARABIC_WORDS:
        return f"{words} Arabic words (scan, or not Arabic)"
    return {"pages": len(d), "arabic_words": words,
            "producer": d.metadata.get("producer", ""), "creator": d.metadata.get("creator", "")}


def holdout(file):
    return int(hashlib.sha256(file.encode()).hexdigest(), 16) % 1000 < HOLDOUT_SHARE * 1000


def pick(n, seed, delay, per_page=2):
    HOME.mkdir(parents=True, exist_ok=True)
    seen = set()
    if MANIFEST.exists():
        seen = {json.loads(l)["url"] for l in MANIFEST.open(encoding="utf-8") if l.strip()}
    rng = random.Random(seed)
    got = tries = 0
    with MANIFEST.open("a", encoding="utf-8") as mf:
        while got < n and tries < n * 30:
            tld = rng.choice(TLDS)
            try:
                pool = links(tld, rng.randrange(pages(tld)))
            except Exception as e:
                print(f"  .{tld} index failed: {e}")
                time.sleep(delay * 5)
                continue
            rng.shuffle(pool)
            kept = 0
            for url in pool[:per_page * 4]:
                if got >= n or kept >= per_page:
                    break
                if url in seen:
                    continue
                seen.add(url)
                tries += 1
                try:
                    data = download(url)
                    row = judge(data)
                except Exception as e:
                    row = f"failed: {str(e)[:60]}"
                time.sleep(delay)
                if isinstance(row, str):
                    print(f"  .{tld:<3} skipped: {row}")
                    continue
                sha = hashlib.sha256(data).hexdigest()
                file = f"w{sha[:10]}.pdf"
                (HOME / file).write_bytes(data)
                row = {"file": file, "url": url, "sha256": sha, "tld": tld, **row,
                       "holdout": holdout(file)}
                mf.write(json.dumps(row, ensure_ascii=False) + "\n")
                mf.flush()
                got += 1
                kept += 1
                print(f"  [{got:>2}/{n}] .{tld:<3} {file} {row['pages']:>3} pages  {row['producer'][:40]}")
    print(f"\n{got} files in {tries} tries -> {HOME}")


def fetch(delay):
    if not MANIFEST.exists():
        sys.exit(f"no manifest at {MANIFEST}")
    lost = []
    for row in (json.loads(l) for l in MANIFEST.open(encoding="utf-8") if l.strip()):
        dest = HOME / row["file"]
        if dest.exists():
            continue
        try:
            data = download(row["url"])
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("the site now serves a different file")
            dest.write_bytes(data)
            print(f"  {row['file']} restored")
        except Exception as e:
            lost.append((row["file"], str(e)))
            print(f"  {row['file']} GONE: {e}")
        time.sleep(delay)
    if lost:
        print(f"\n{len(lost)} could not be restored - the set is NOT the one on record.")
        return 1


def main():
    sys.stdout.reconfigure(encoding="utf-8")   # producers can be Arabic
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--delay", type=float, default=1.0)
    f = sub.add_parser("fetch")
    f.add_argument("--delay", type=float, default=1.0)
    a = ap.parse_args()
    return pick(a.n, a.seed, a.delay) if a.cmd == "pick" else fetch(a.delay)


if __name__ == "__main__":
    sys.exit(main() or 0)
