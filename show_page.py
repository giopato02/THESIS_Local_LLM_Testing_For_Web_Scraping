"""
Print the cleaned text of a cached page -- exactly what the model receives.

Use this while hand-labelling. The live website is not the right reference:
many of these directories are paginated or lazy-loaded, so the snapshot in
results/html_cache/ may hold only part of the member list. If ground truth
were labelled from the live site it would include companies the model never
saw, recall would be wrong, and both models would look far worse than they are.

Rule while labelling: the answer key describes THIS text, not the website.

Run:  .venv/bin/python show_page.py 040
      .venv/bin/python show_page.py 040 --names-only
"""

from __future__ import annotations

import argparse
import csv

import cleaner
import config
import fetcher


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url_id", help="the 3-digit id, e.g. 040")
    ap.add_argument("--names-only", action="store_true",
                    help="hide long description lines, keep short ones")
    args = ap.parse_args()

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        rows = {r["id"]: r for r in csv.DictReader(fh)}

    row = rows.get(args.url_id)
    if not row:
        raise SystemExit(f"no url with id {args.url_id}")

    path = fetcher.cache_path(row["url"])
    if not path.exists():
        raise SystemExit(f"no cached HTML for {args.url_id}; run fetcher.py")

    page = cleaner.process(path.read_text(encoding="utf-8", errors="ignore"),
                          row["url"])

    print("=" * 74)
    print(f"  {row['org_name']}")
    print(f"  {row['url']}")
    print(f"  {page.word_count} words, ~{page.est_tokens} tokens, "
          f"{page.n_chunks} chunk(s)")
    print("  THIS is what the model sees. Label against this, not the website.")
    print("=" * 74)

    for line in page.text.split("\n"):
        # Description paragraphs are long; company names rarely are.
        if args.names_only and len(line) > 70:
            continue
        print(line)


if __name__ == "__main__":
    main()
