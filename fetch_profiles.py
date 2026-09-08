"""
Stage 3: open each member's profile page and read the real company details.

link_coverage.py sorts every company into three routes. This handles the
`profile` route: the directory did not print the company's website, but it did
link to a page about that company on the association's own site. That page
usually carries the website, the postal address, a phone number and an email.

Two steps, and they can be run separately:

    --fetch-only   download the profile pages and cache them. Network only,
                   no model, so it can run while a benchmark is using the GPU.

    (default)      extract from whatever is cached, using the same model and
                   the same record prompt as stage 1.

Splitting them matters in practice: fetching 105 pages politely takes minutes
of mostly waiting, and there is no reason for that to compete with a running
experiment.

Why the model rather than a parser: a profile page has no fixed shape either.
The website may be a button labelled "Zur Website", a bare domain in a table,
or the company logo. The same argument that applies to the directory pages
applies here (section 3.13d).

Verification is free, as at stage 1: a returned website either appears in the
fetched page or the model constructed it. Constructed URLs are recorded and
must not reach the database.

Run:  .venv/bin/python fetch_profiles.py --fetch-only
      .venv/bin/python fetch_profiles.py --model llama3.1:8b
      .venv/bin/python fetch_profiles.py --limit 5          # try a few first
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from urllib.parse import urlparse

import requests

import cleaner
import config
import extractor

IN_CSV = config.RESULTS_DIR / "link_coverage.csv"
OUT_CSV = config.RESULTS_DIR / "profile_records.csv"
CACHE = config.RESULTS_DIR / "html_cache_profiles"

FIELDS = [
    "url_id", "org_name", "company", "profile_url",
    "company_url", "url_on_page",
    "street", "postcode", "city", "phone", "email",
    "model_name", "latency_seconds", "error",
]

# A profile page is one company, so it fits the context window whole and the
# record prompt's second worked example is exactly this shape.
STRATEGY = "few_shot_full_record"


def cache_path(url: str) -> str:
    return CACHE / f"{hashlib.sha256(url.encode()).hexdigest()[:16]}.html"


def url_core(url: str) -> str:
    u = url.strip().lower()
    for prefix in ("https://", "http://", "//"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    u = u.split("?")[0].split("#")[0]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


def load_queue(limit: int | None) -> list[dict]:
    if not IN_CSV.exists():
        raise SystemExit(f"run link_coverage.py first: {IN_CSV} is missing")
    with open(IN_CSV, encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["route"] == "profile" and r["target"].startswith("http")]
    # One fetch per distinct page: several members occasionally share one.
    seen, out = set(), []
    for r in rows:
        if r["target"] in seen:
            continue
        seen.add(r["target"])
        out.append(r)
    return out[:limit] if limit else out


def fetch(rows: list[dict], session: requests.Session) -> int:
    """Download and cache anything not already on disk. Returns how many."""
    got = 0
    for i, r in enumerate(rows, start=1):
        path = cache_path(r["target"])
        if path.exists():
            continue
        try:
            resp = session.get(r["target"], timeout=25)
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding or resp.encoding
                path.write_text(resp.text, encoding="utf-8")
                got += 1
                mark = "  "
            else:
                mark = f"! {resp.status_code}"
            print(f"{mark:<6}[{i:>4}/{len(rows)}] {r['company'][:44]}")
        except requests.RequestException as exc:
            print(f"!     [{i:>4}/{len(rows)}] {r['company'][:34]}  "
                  f"{type(exc).__name__}")
        time.sleep(config.REQUEST_DELAY)
    return got


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-only", action="store_true",
                    help="download profile pages and stop, no model needed")
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--json-mode", default="prompt_only",
                    choices=config.JSON_MODES)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--restart", action="store_true",
                    help="ignore what is already in profile_records.csv")
    ap.add_argument("--max-words", type=int, default=5000,
                    help="skip pages whose CLEANED text exceeds this. The "
                         "corpus runs 101 to 16,018 cleaned words with a "
                         "median of 110, so this separates the one outlier "
                         "without touching anything normal")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    rows = load_queue(args.limit)
    print(f"  {len(rows)} profile pages queued")

    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    })

    cached = sum(1 for r in rows if cache_path(r["target"]).exists())
    if cached < len(rows):
        print(f"  fetching {len(rows) - cached} pages "
              f"({cached} already cached)\n")
        fetch(rows, session)
    else:
        print(f"  all {cached} pages already cached")

    if args.fetch_only:
        print(f"\n  cached -> {CACHE}")
        print("  run again without --fetch-only to extract")
        return

    # ---- extraction --------------------------------------------------------
    # Resumable, because a single oversized page can stall the whole run and a
    # restart should not repeat the hundred pages that already worked. One
    # profile page in the ground-truth queue is 16,018 words against a median
    # of 110, and it is exactly the kind of outlier that makes a
    # non-resumable script expensive to interrupt.
    done: dict[str, dict] = {}
    if OUT_CSV.exists() and not args.restart:
        with open(OUT_CSV, encoding="utf-8-sig") as fh:
            done = {r["profile_url"]: r for r in csv.DictReader(fh)}
        print(f"\n  {len(done)} profile pages already extracted, skipping those")

    print(f"\n  extracting with {args.model} / {STRATEGY} / {args.json_mode}\n")
    out, verified, invented = list(done.values()), 0, 0

    for i, r in enumerate(rows, start=1):
        path = cache_path(r["target"])
        if not path.exists() or r["target"] in done:
            continue

        html = path.read_text(encoding="utf-8", errors="ignore")
        page = cleaner.process(html, r["target"])
        haystack = page.text.lower()

        # Measured on the CLEANED text, not raw HTML. Every profile page in
        # this corpus is roughly 6,900 words of raw markup regardless of its
        # content, so a raw-HTML threshold separates nothing: the real spread
        # is 101 to 16,018 cleaned words. A page far larger than the rest costs
        # minutes and still returns one company, so skipping it is the better
        # trade, and it is recorded rather than silently dropped.
        words = page.word_count
        if args.max_words and words > args.max_words:
            # dict(**a, **b) rather than a | b: the GPU node's interpreter is
            # Python 3.8, where the dict union operator does not exist. The
            # same version gap silently aborted an earlier pip install.
            blank = {f: "" for f in FIELDS}
            blank.update({
                "url_id": r["url_id"], "org_name": r["org_name"],
                "company": r["company"], "profile_url": r["target"],
                "error": "skipped: {} cleaned words exceeds --max-words".format(words),
            })
            out.append(blank)
            print(f"- [{i:>4}/{len(rows)}] {r['company'][:36]:<38}"
                  f"skipped, {words:,} cleaned words")
            continue
        page = cleaner.process(html, r["target"])
        haystack = page.text.lower()

        result = extractor.extract(chunks=page.chunks, model=args.model,
                                   strategy=STRATEGY, json_mode=args.json_mode)

        # A profile page is one company. Where the model returns several, the
        # extras are usually contacts or partner organisations listed on the
        # page, so prefer the record whose name matches the company we asked
        # about and fall back to the first.
        import benchmark
        want = benchmark.match_key(r["company"])
        rec = next((x for x in result.records
                    if benchmark.match_key(x.get("name", "")) == want), None)
        rec = rec or (result.records[0] if result.records else {})

        site = (rec.get("url") or "").strip()
        on_page = ""
        if site:
            host = url_core(site).split("/")[0]
            # A link back to the association is the page's own navigation, not
            # the company's website.
            own = url_core(urlparse(r["target"]).netloc)
            if host and host in haystack and host not in own:
                on_page, _ = "yes", verified
                verified += 1
            else:
                on_page = "NO"
                invented += 1

        out.append({
            "url_id": r["url_id"], "org_name": r["org_name"],
            "company": r["company"], "profile_url": r["target"],
            "company_url": site, "url_on_page": on_page,
            "street": rec.get("street", ""), "postcode": rec.get("postcode", ""),
            "city": rec.get("city", ""), "phone": rec.get("phone", ""),
            "email": rec.get("email", ""),
            "model_name": args.model,
            "latency_seconds": round(result.latency_seconds, 1),
            "error": result.error,
        })

        flag = {"yes": "  ", "NO": "! ", "": "- "}[on_page]
        print(f"{flag}[{i:>4}/{len(rows)}] {r['company'][:36]:<38}"
              f"{site[:40]:<42}{result.latency_seconds:>6.1f}s")

        # Written every page so an interrupted run keeps its work.
        with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(out)

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)

    filled = {f: sum(1 for r in out if r[f]) for f in
              ("company_url", "street", "postcode", "city", "phone", "email")}
    n = len(out) or 1
    print(f"\n  {len(out)} profile pages processed")
    print(f"  website found   {filled['company_url']:>4} ({filled['company_url']/n:.0%})"
          f"   verified on page {verified}, not on page {invented}")
    for f in ("street", "postcode", "city", "phone", "email"):
        print(f"  {f:<15} {filled[f]:>4} ({filled[f]/n:.0%})")
    print(f"\n  -> {OUT_CSV}")


if __name__ == "__main__":
    main()
