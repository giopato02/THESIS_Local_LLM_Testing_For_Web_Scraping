"""
Build the URL list for the production run over the Finalv1 networks.

The research corpus is 30 hand-labelled pages in `data/urls_73.csv`. This is
the other thing: every network Neovation actually wants in the database, with
no answer keys, run once with the winning configuration.

Scope comes from `survey_finalv1.py`, which already fetched all 291 verified
members URLs and sorted them by what the HTML contains:

    directory    153   a member list is present            include
    sparse        85   some content, may hold members      include
    thin          41   median 74 words, nothing to read    skip
    http_error     7                                       skip
    unreachable    5                                       skip

"thin" is skipped because 74 words is a JavaScript shell, not a page a model
can read. "sparse" is included because a page that turns out to hold nothing
costs one cheap call, and excluding it would silently drop real members.

Pages already in the research corpus keep their existing id, so the two runs
can be compared directly on those 30 and the ground truth still applies.
Everything else gets a p-number.

The HTML is already cached by survey_finalv1.py under html_cache_finalv1,
with the same sha256(url)[:16] filename the fetcher uses, so nothing is
downloaded again. Copy that folder into the main cache before running.

Run:  .venv/bin/python build_production_urls.py
      .venv/bin/python build_production_urls.py --include directory
      -> data/urls_production.csv
"""

from __future__ import annotations

import argparse
import csv

import config

FINALV1 = config.THESIS_WORK / "NEOHUB_final_merged_QA_reviewed (1)(Finalv1).csv"
HEALTH = config.RESULTS_DIR / "finalv1_health.csv"
OUT = config.DATA_DIR / "urls_production.csv"

FIELDS = ["id", "org_name", "url", "url_type", "source_file",
          "collected_by", "notes"]

URL_COLUMNS = ("Companies / members URL",
               "Verified / corrected network URL",
               "Network homepage / exact hosted page")


def members_url(row: dict) -> str:
    """The best URL for this network: the members page, then the fallbacks."""
    for column in URL_COLUMNS:
        value = (row.get(column) or "").strip()
        if value.startswith("http"):
            return value
    return ""


def existing_ids() -> dict:
    """{url -> id} for the research corpus, so those 30 keep their ids."""
    out = {}
    if not config.URLS_CSV.exists():
        return out
    with open(config.URLS_CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["url"].strip()] = r["id"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--include", nargs="+", default=["directory", "sparse"],
                    help="which health categories to run on")
    args = ap.parse_args()

    if not HEALTH.exists():
        raise SystemExit(f"run survey_finalv1.py first: {HEALTH} is missing")

    keep = set(args.include)
    with open(HEALTH, encoding="utf-8-sig") as fh:
        health = {r["members_url"].strip(): r for r in csv.DictReader(fh)}

    known = existing_ids()
    rows, n, reused = [], 0, 0
    with open(FINALV1, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            url = members_url(row)
            if not url:
                continue
            h = health.get(url)
            if not h or h["category"] not in keep:
                continue
            if url in known:
                uid, reused = known[url], reused + 1
            else:
                n += 1
                uid = f"p{n:03d}"
            rows.append({
                "id": uid,
                "org_name": (row.get("Netzwerkname") or "").strip(),
                "url": url,
                "url_type": "member_list",
                "source_file": (row.get("Source dataset") or "").strip(),
                "collected_by": "Finalv1",
                "notes": f"{h['category']}, {h['words']} words",
            })

    if not rows:
        raise SystemExit("nothing matched; check --include against the health file")

    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"  {len(rows)} networks -> {OUT}")
    print(f"    {reused} already in the research corpus, keeping their ids")
    from collections import Counter
    for cat, c in Counter(r["notes"].split(",")[0] for r in rows).most_common():
        print(f"    {cat:<14}{c:>5}")
    words = sum(int(health[r["url"]]["words"] or 0) for r in rows)
    print(f"\n  {words:,} words total, roughly {words / 18:,.0f} companies "
          f"at the corpus rate of 18 words each")


if __name__ == "__main__":
    main()
