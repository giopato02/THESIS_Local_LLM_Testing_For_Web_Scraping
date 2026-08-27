"""
Produce a shareable report of which of the 73 collected URLs actually work.

This is not thesis output -- it is for the team. Whoever is merging the
website spreadsheets needs to know which links are dead, blocked, or pointing
at the wrong page BEFORE the merged sheet is finalised, otherwise the same
broken links get baked into the "final" version.

Writes results/url_health_report.csv with a suggested action per URL, and
prints a summary you can read out in a meeting.

Run:  .venv/bin/python url_health.py
"""

from __future__ import annotations

import csv
from collections import Counter

import config

REPORT_CSV = config.RESULTS_DIR / "url_health_report.csv"

# URLs confirmed by manual inspection to return HTTP 200 but not contain a
# member list -- homepages, news feeds, "about us" pages, category taxonomies.
# These are the most dangerous category: nothing automated flags them, because
# from a crawler's point of view the fetch succeeded.
WRONG_PAGE = {
    "002": "product-category taxonomy, no company names (companies sit behind a search form)",
    "035": "association homepage with news, not a member list",
    "044": "'Organisation' page describing the board, not members",
    "047": "association homepage with events and news, not a member list",
    "049": "news/blog listing; the member directory loads via JavaScript",
}

ACTIONS = {
    "http_error_404": "RE-COLLECT: link is dead, find the current member-list URL",
    "http_error_403": "BLOCKED: server refuses automated access; needs manual copy or a browser-based fetch",
    "thin_content": "JS-RENDERED: list is not in the HTML; needs a headless browser or manual copy",
    "wrong_page": "WRONG URL: page loads fine but is not a member list",
    "ok": "",
}


def classify(row: dict) -> tuple[str, str]:
    """Return (category, action) for one manifest row."""
    if row["id"] in WRONG_PAGE:
        return "wrong_page", ACTIONS["wrong_page"]
    if row["status"] == "http_error":
        key = f"http_error_{row['http_code']}"
        return key, ACTIONS.get(key, "RE-COLLECT: unexpected HTTP error")
    if row["status"] == "thin_content":
        return "thin_content", ACTIONS["thin_content"]
    return "ok", ""


def main() -> None:
    with open(config.FETCH_MANIFEST_CSV, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    out = []
    for row in rows:
        category, action = classify(row)
        out.append({
            "id": row["id"],
            "org_name": row["org_name"],
            "url": row["url"],
            "url_type": row["url_type"],
            "http_code": row["http_code"],
            "category": category,
            "words_of_text": row["word_count"],
            "action_needed": action,
            "note": WRONG_PAGE.get(row["id"], ""),
        })

    with open(REPORT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    counts = Counter(r["category"] for r in out)
    broken = [r for r in out if r["category"] != "ok"]

    print("=" * 72)
    print("  URL HEALTH REPORT -- collected association links")
    print("=" * 72)
    print(f"  total URLs checked : {len(out)}")
    print(f"  working            : {counts['ok']}")
    print(f"  needing attention  : {len(broken)}")
    print()
    for cat, n in counts.most_common():
        if cat == "ok":
            continue
        print(f"    {cat:<20} {n:>3}   {ACTIONS.get(cat, '')[:48]}")

    print("\n  URLs needing re-collection:")
    print("  " + "-" * 68)
    for r in sorted(broken, key=lambda r: r["category"]):
        print(f"  {r['id']}  {r['category']:<18} {r['org_name'][:40]}")
        print(f"       {r['url'][:66]}")
        if r["note"]:
            print(f"       -> {r['note']}")

    print(f"\n  full report -> {REPORT_CSV}")
    print("  Share this with whoever is merging the website spreadsheets.")


if __name__ == "__main__":
    main()
