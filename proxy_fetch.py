"""
Retry 403-blocked pages through rotating proxies.

Five sites in this corpus refuse the first request outright (HTTP 403) despite
serving a public member directory. Neovation's own `scraperng` handles the same
problem with `scrapy-rotating-proxies` and a free proxifly list, and Rayen
considers it in scope: the pages are public and could be copied by hand, so
automating that is not gaining access we do not already have (meeting
2026-07-31).

This module implements the same idea directly, without pulling Scrapy in:
download a proxy list, then retry the blocked URL through successive proxies
until one returns usable HTML.

CAVEATS worth stating in the thesis
  * Free proxies are third-party machines run by unknown operators. Use them
    only for fetching public pages -- never anything authenticated.
  * Quality is poor and variable ("some can be good, some can be down"
    -- Rayen). Expect a low success rate per proxy.
  * Any result obtained this way must be reported as proxy-assisted, since it
    is not reproducible from a direct request.

USAGE
    .venv/bin/python proxy_fetch.py --update-list
    .venv/bin/python proxy_fetch.py --blocked        # retry every 403 in the manifest
    .venv/bin/python proxy_fetch.py --ids 003 017
"""

from __future__ import annotations

import argparse
import csv
import random
import time

import requests

import cleaner
import config
import fetcher


def update_proxy_list() -> list[str]:
    """Download the free proxy list (same source as scraperng's shell script)."""
    resp = requests.get(config.PROXY_LIST_URL, timeout=30)
    resp.raise_for_status()
    config.PROXY_LIST_PATH.write_text(resp.text, encoding="utf-8")
    proxies = [l.strip() for l in resp.text.splitlines() if l.strip()]
    print(f"  {len(proxies)} proxies -> {config.PROXY_LIST_PATH}")
    return proxies


def load_proxies() -> list[str]:
    if not config.PROXY_LIST_PATH.exists():
        return update_proxy_list()
    return [l.strip() for l in
            config.PROXY_LIST_PATH.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def fetch_via_proxies(url: str, proxies: list[str],
                      max_attempts: int | None = None) -> tuple[str | None, str]:
    """
    Try `url` through random proxies until one yields a usable page.

    Returns (html or None, note describing the outcome).
    """
    max_attempts = max_attempts or config.PROXY_MAX_ATTEMPTS
    pool = random.sample(proxies, min(len(proxies), max_attempts * 4))

    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }

    tried = 0
    for proxy in pool:
        if tried >= max_attempts:
            break
        # Entries look like "http://1.2.3.4:8080"; skip anything malformed.
        if "://" not in proxy:
            continue
        tried += 1
        try:
            resp = requests.get(
                url, headers=headers, timeout=20,
                proxies={"http": proxy, "https": proxy},
            )
        except requests.RequestException:
            continue

        if resp.status_code != 200:
            continue

        resp.encoding = resp.apparent_encoding or resp.encoding
        html = resp.text
        # A proxy can return its own error page with status 200.
        if cleaner.process(html).word_count < config.THIN_CONTENT_WORD_THRESHOLD:
            continue
        return html, f"ok via {proxy} (attempt {tried})"

    return None, f"no working proxy after {tried} attempts"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-list", action="store_true")
    ap.add_argument("--blocked", action="store_true",
                    help="retry every URL the manifest marks http_error 403")
    ap.add_argument("--ids", nargs="+")
    args = ap.parse_args()

    if args.update_list and not (args.blocked or args.ids):
        update_proxy_list()
        return

    proxies = update_proxy_list() if args.update_list else load_proxies()
    if not proxies:
        raise SystemExit("no proxies available")

    with open(config.URLS_CSV, encoding="utf-8") as fh:
        urls = {r["id"]: r for r in csv.DictReader(fh)}

    if args.blocked:
        with open(config.FETCH_MANIFEST_CSV, encoding="utf-8") as fh:
            targets = [r["id"] for r in csv.DictReader(fh)
                       if r["status"] == "http_error" and r["http_code"] == "403"]
    else:
        targets = args.ids or []

    if not targets:
        raise SystemExit("nothing to do; pass --blocked or --ids")

    print(f"  retrying {len(targets)} blocked page(s) through "
          f"{len(proxies)} proxies\n")

    recovered = 0
    for uid in targets:
        row = urls[uid]
        print(f"  {uid} {row['org_name'][:42]}")
        html, note = fetch_via_proxies(row["url"], proxies)
        if html:
            path = fetcher.cache_path(row["url"])
            path.write_text(html, encoding="utf-8")
            words = cleaner.process(html).word_count
            print(f"      RECOVERED {words} words -- {note}")
            recovered += 1
        else:
            print(f"      failed -- {note}")
        time.sleep(1.0)

    print(f"\n  recovered {recovered}/{len(targets)}")
    if recovered:
        print("  NOTE: these pages were fetched via proxy, not directly. "
              "Record that in the thesis.")
        print("  refresh the manifest:  .venv/bin/python fetcher.py")


if __name__ == "__main__":
    main()
