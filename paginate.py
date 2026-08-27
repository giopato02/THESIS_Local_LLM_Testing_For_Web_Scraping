"""
Follow URL-based pagination and cache the WHOLE member list, not page one.

THE BUG THIS FIXES
------------------
`fetcher.py` performs one HTTP request per URL. Many member directories split
their list across pages, so one request returns a fraction of the members and
gives no sign that anything is missing -- 200 OK, plenty of text, plausible
company names. Ground truth built on such a snapshot silently describes 5% of
an association's membership.

BDEW is the clearest case: its directory is indexed A-Z via
`?letter=A` ... `?letter=Z`, and the static fetch captured only the "A" page.
43 of 66 hand-labelled names started with "A" before anyone noticed.

TWO KINDS OF PAGINATION
-----------------------
  URL-based   ?letter=B, ?page=2, ?paged=2, /page/2/  -> plain requests works
  JS-based    AJAX "load more" with no usable URL      -> needs browser_fetcher

This module handles the first kind, which is the common and cheap one. It
discovers the pagination links already present in the cached HTML, fetches
each variant politely, and concatenates the results into a single cached
document so the rest of the pipeline is unchanged.

USAGE
    .venv/bin/python paginate.py --detect            # report, change nothing
    .venv/bin/python paginate.py --ids 009
    .venv/bin/python paginate.py --auto              # every detected page
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

import cleaner
import config
import fetcher

# Query parameters that select a slice of a longer list. Covers three
# conventions seen in this corpus: alphabetical indexes (?letter=B), page
# numbers (?page=2), and record ranges/offsets (?start=51, ?from=101).
PAGE_PARAMS = ("letter", "buchstabe", "anfangsbuchstabe", "alpha",
               "page", "paged", "pg", "seite", "pagenum",
               "offset", "start", "from", "begin", "pos", "first", "p", "b")

MAX_PAGES = 40          # safety limit for very long directories


def _same_site(a: str, b: str) -> bool:
    return urlparse(a).netloc.replace("www.", "") == \
           urlparse(b).netloc.replace("www.", "")


def discover_pages(base_url: str, html: str) -> tuple[str, list[str]]:
    """
    Find sibling pages of `base_url` linked from its own HTML.

    Returns (kind, urls) where kind is a short description for logging.
    Only links that differ from the base by a recognised pagination parameter
    (or a /page/N/ path segment) are accepted, so ordinary navigation links
    are never mistaken for pagination.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    base_parts = urlparse(base_url)
    base_path = base_parts.path.rstrip("/")

    found: dict[str, str] = {}
    kinds: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if not _same_site(absolute, base_url):
            continue

        parts = urlparse(absolute)
        qs = parse_qs(parts.query)

        # Case 1: same path, plus a pagination query parameter.
        if parts.path.rstrip("/") == base_path:
            for param in PAGE_PARAMS:
                if param in qs and qs[param] and qs[param][0]:
                    found[absolute] = param
                    kinds.add(param)
                    break
            continue

        # Case 2: /page/2/ style path suffix on the same base path.
        m = re.match(rf"^{re.escape(base_path)}/(?:page|seite)/(\d+)/?$",
                     parts.path.rstrip("/"))
        if m and m.group(1) != "1":
            found[absolute] = "path"
            kinds.add("/page/N/")

    kind = ",".join(sorted(kinds)) if kinds else ""
    return kind, sorted(found)[:MAX_PAGES]


def fetch_all_pages(base_url: str, page_urls: list[str],
                    session: requests.Session) -> tuple[str, dict]:
    """
    Fetch every page and concatenate them into one HTML document.

    The pages are wrapped in <div data-pagination-part> markers so the cleaned
    text keeps them separate and nothing runs together at the seams.
    """
    stats = {"requested": len(page_urls), "ok": 0, "failed": 0}
    parts: list[str] = []

    for url in page_urls:
        try:
            resp = session.get(url, timeout=config.REQUEST_TIMEOUT)
            if resp.status_code != 200:
                stats["failed"] += 1
                continue
            resp.encoding = resp.apparent_encoding or resp.encoding
            parts.append(
                f'<div data-pagination-part="{url}">\n{resp.text}\n</div>')
            stats["ok"] += 1
        except requests.RequestException:
            stats["failed"] += 1
        time.sleep(config.REQUEST_DELAY)

    combined = ("<html><body>\n" + "\n".join(parts) + "\n</body></html>") \
        if parts else ""
    return combined, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect", action="store_true",
                    help="report what would be fetched, change nothing")
    ap.add_argument("--ids", nargs="+")
    ap.add_argument("--auto", action="store_true")
    args = ap.parse_args()

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}

    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    })

    targets = args.ids or list(urls)

    detected: list[tuple[str, str, int]] = []
    for uid in targets:
        row = urls[uid]
        path = fetcher.cache_path(row["url"])
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8", errors="ignore")
        # A combined document already carries its marker; do not re-paginate.
        if 'data-pagination-part=' in html:
            continue
        kind, pages = discover_pages(row["url"], html)
        if pages:
            detected.append((uid, kind, len(pages)))

    if args.detect or (not args.ids and not args.auto):
        print(f"  {len(detected)} page(s) have URL-based pagination\n")
        for uid, kind, n in sorted(detected, key=lambda d: -d[2]):
            print(f"    {uid}  {n:>3} sub-pages  via {kind:<16} "
                  f"{urls[uid]['org_name'][:36]}")
        if not args.ids and not args.auto:
            print("\n  re-run with --auto (or --ids ...) to fetch them")
        return

    todo = [d[0] for d in detected] if args.auto else args.ids

    for uid in todo:
        row = urls[uid]
        path = fetcher.cache_path(row["url"])
        html = path.read_text(encoding="utf-8", errors="ignore")
        kind, pages = discover_pages(row["url"], html)
        if not pages:
            print(f"  {uid}: no URL pagination found, skipping")
            continue

        before = cleaner.process(html).word_count
        print(f"  {uid} {row['org_name'][:38]}: {len(pages)} pages via {kind}")

        combined, stats = fetch_all_pages(row["url"], pages, session)
        if not combined:
            print("      all sub-page fetches failed; leaving cache unchanged")
            continue

        after = cleaner.process(combined).word_count
        if after <= before:
            print(f"      no gain ({before} -> {after} words); "
                  f"leaving cache unchanged")
            continue

        path.write_text(combined, encoding="utf-8")
        print(f"      {stats['ok']}/{stats['requested']} pages ok  "
              f"{before} -> {after} words  ({after/max(before,1):.1f}x)")

    print("\n  refresh the manifest with:  .venv/bin/python fetcher.py")


if __name__ == "__main__":
    main()
