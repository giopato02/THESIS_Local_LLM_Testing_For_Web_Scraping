"""
Detect truncated member lists by looking at alphabet coverage.

WHY NOT MARKER MATCHING
-----------------------
The first attempt scanned the HTML for pagination keywords. It failed in both
directions: BDEW scored zero because it paginates with plain `?letter=B` URL
links rather than JavaScript, and SPECTARIS scored 61 purely from CMS
boilerplate while actually listing every member on one page.

Alphabet coverage is a far better signal, and it needs no network access.
Member directories are almost always alphabetical, so:

  * names spread across most of the alphabet  -> the page is complete
  * names clustered on one or two letters     -> we have one page of many

BDEW's snapshot held 43 names, all starting with "A". SPECTARIS holds 285
spanning A-W. The difference is unmistakable, and it is visible from the
cached HTML alone.

This is a heuristic, not proof: a small association may genuinely have members
on only a few letters. Treat a warning as "go and look", not as a verdict.

Run:  .venv/bin/python check_completeness.py            # ground-truth pages
      .venv/bin/python check_completeness.py --all      # every cached page
"""

from __future__ import annotations

import argparse
import collections
import csv
import re
import string

import cleaner
import config
import fetcher

NAME_LINE = re.compile(r"\b(GmbH|mbH|AG|KG|SE|eG|AöR|e\.\s?K\.)\b")

# Below this many distinct initials, with enough names to judge, the list is
# probably a single page of a longer directory.
MIN_LETTERS = 8
MIN_NAMES = 12


def analyse(html: str) -> dict:
    page = cleaner.process(html)
    lines = [l.strip() for l in page.text.split("\n")
             if NAME_LINE.search(l) and len(l.strip()) < 80]
    initials = collections.Counter(
        l[0].upper() for l in lines if l[:1].isalpha())

    total = sum(initials.values())
    top_letter, top_count = initials.most_common(1)[0] if initials else ("-", 0)

    verdict = "ok"
    if total >= MIN_NAMES:
        if len(initials) < MIN_LETTERS:
            verdict = "TRUNCATED?"
        # Two thirds of names sharing one initial is a strong signal.
        elif top_count / total > 0.66:
            verdict = "TRUNCATED?"
    elif total == 0:
        verdict = "no names"
    else:
        verdict = "too few to judge"

    return {
        "names": total, "letters": len(initials),
        "top_letter": top_letter, "top_share": top_count / total if total else 0,
        "verdict": verdict, "words": page.word_count,
        "coverage": "".join(c if c in initials else "."
                            for c in string.ascii_uppercase),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="check every cached page, not just the labelled ten")
    args = ap.parse_args()

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}

    if args.all:
        ids = list(urls)
    else:
        import make_ground_truth
        ids = make_ground_truth.SAMPLE_IDS

    print(f"  {'id':<5}{'names':>6}{'ltrs':>6}{'top':>10}  {'verdict':<18}"
          f"org")
    print("  " + "-" * 88)

    flagged = []
    for uid in ids:
        row = urls.get(uid)
        if not row:
            continue
        path = fetcher.cache_path(row["url"])
        if not path.exists():
            continue

        a = analyse(path.read_text(encoding="utf-8", errors="ignore"))
        if a["verdict"] == "TRUNCATED?":
            flagged.append(uid)

        top = f"{a['top_letter']}={a['top_share']*100:.0f}%" if a["names"] else "-"
        print(f"  {uid:<5}{a['names']:>6}{a['letters']:>6}{top:>10}  "
              f"{a['verdict']:<18}{row['org_name'][:34]}")
        print(f"        {a['coverage']}")

    if flagged:
        print(f"\n  {len(flagged)} page(s) look truncated: {', '.join(flagged)}")
        print("  Check them before labelling:")
        print("      .venv/bin/python show_page.py <id> --names-only")
        print("      .venv/bin/python paginate.py --detect          # URL pages")
        print("      .venv/bin/python browser_fetcher.py --compare <id>")
    else:
        print("\n  no truncation detected in this set")


if __name__ == "__main__":
    main()
