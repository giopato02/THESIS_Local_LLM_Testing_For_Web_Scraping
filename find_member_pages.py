"""
Member-page discovery: turn a network HOMEPAGE into a member-LIST URL.

WHY THIS EXISTS
---------------
The merged database (NEOHUB_final_merged_QA_reviewed) lists 817 networks but
stores only homepages: of its 332 URLs, just 14 have any path at all, and
none of the 59 deep member-list URLs from the older Verbaende sheet survived
the merge. `https://www.acod.de/mitglieder-und-partner/` became
`https://www.acod.de`.

A homepage is not a member list, so the extraction pipeline cannot use the
merged file directly. This module closes that gap: given a homepage, it
fetches the page, scores every internal link on how likely it is to lead to a
member directory, and reports the best candidates.

It is deliberately a separate step from fetching and extracting, so the
discovery hit-rate can be measured and reported on its own -- "the crawler
located a member page for N of M homepages" is a result in itself.

HOW THE SCORING WORKS
---------------------
Each link earns points for German/English member-directory vocabulary in its
visible text and in its URL path, and loses points for words that signal the
wrong kind of page ("Mitglied werden" = "become a member", a signup form, not
a list). Highest total wins.

USAGE
    .venv/bin/python find_member_pages.py --limit 20     # try 20 homepages
    .venv/bin/python find_member_pages.py --url https://www.acod.de
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config

MERGED_CSV = config.THESIS_WORK / "NEOHUB_final_merged_QA_reviewed (1)(Final merged database).csv"
DISCOVERY_CSV = config.RESULTS_DIR / "member_page_discovery.csv"

# Strong signals: these words in link text or URL almost always mean a list.
STRONG = {
    "mitglieder": 10, "mitgliederliste": 12, "mitgliedsunternehmen": 12,
    "unsere-mitglieder": 12, "unsere mitglieder": 12,
    "members": 10, "member-companies": 12, "memberlist": 12,
    "teilnehmer": 8, "netzwerkpartner": 8, "mitgliederverzeichnis": 12,
    "branchenfuehrer": 8, "branchenführer": 8, "kompetenzatlas": 8,
    "firmenverzeichnis": 10, "mitgliederdatenbank": 12,
}

# Weaker signals: often a member list, often something else.
WEAK = {
    "partner": 4, "netzwerk": 3, "unternehmen": 4, "firmen": 4,
    "beteiligte": 4, "konsortium": 4, "wer-wir-sind": 2, "community": 2,
    "directory": 5, "verzeichnis": 5,
}

# Negative signals: pages ABOUT membership rather than lists OF members.
NEGATIVE = {
    "mitglied werden": -12, "mitglied-werden": -12, "become a member": -12,
    "beitritt": -10, "antrag": -8, "aufnahme": -6, "vorteile": -6,
    "beitrag": -6, "anmeldung": -8, "kontakt": -6, "impressum": -10,
    "datenschutz": -10, "login": -8, "warenkorb": -8, "news": -5,
    "veranstaltung": -5, "termine": -5, "presse": -5, "karriere": -5,
    "jobs": -5, "satzung": -5, "vorstand": -4,
}


@dataclass
class Candidate:
    url: str
    text: str
    score: int
    reason: str


def score_link(text: str, href: str) -> tuple[int, str]:
    """Score one link. Returns (score, which terms fired)."""
    haystack = f"{text.casefold()} {href.casefold()}"
    total = 0
    hits: list[str] = []

    for table in (STRONG, WEAK, NEGATIVE):
        for term, points in table.items():
            if term in haystack:
                total += points
                hits.append(f"{term}{points:+d}")

    # A path segment that IS the keyword is stronger than one that merely
    # contains it: /mitglieder/ beats /mitglied-werden/.
    path = urlparse(href).path.casefold().strip("/")
    if path.split("/")[-1] in ("mitglieder", "members", "mitgliedsunternehmen"):
        total += 6
        hits.append("exact-path+6")

    return total, ",".join(hits)


def discover(homepage: str, session: requests.Session,
             top_n: int = 3) -> list[Candidate]:
    """Fetch a homepage and rank its internal links as member-page candidates."""
    try:
        resp = session.get(homepage, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        resp.encoding = resp.apparent_encoding or resp.encoding
        html = resp.text
    except requests.RequestException:
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    base_host = urlparse(homepage).netloc.replace("www.", "")
    seen: set[str] = set()
    out: list[Candidate] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absolute = urljoin(homepage, href)
        host = urlparse(absolute).netloc.replace("www.", "")
        # Stay on the network's own site; an external link is someone else's.
        if host != base_host:
            continue
        if absolute.rstrip("/") == homepage.rstrip("/"):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)

        text = " ".join(a.get_text(separator=" ").split())[:80]
        score, reason = score_link(text, absolute)
        if score > 0:
            out.append(Candidate(absolute, text, score, reason))

    out.sort(key=lambda c: -c.score)
    return out[:top_n]


def load_homepages() -> list[dict]:
    """Rows of the merged database that carry a usable homepage URL."""
    col = "Network homepage / exact hosted page"
    rows = []
    with open(MERGED_CSV, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            url = (r.get(col) or "").strip()
            if url.lower().startswith("http"):
                rows.append({
                    "network": (r.get("Netzwerkname") or "").strip(),
                    "url": url,
                    "classification": (r.get("URL classification") or "").strip(),
                    "source": (r.get("Source dataset") or "").strip(),
                })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--url", default=None, help="test a single homepage")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    })

    if args.url:
        for c in discover(args.url, session, top_n=6):
            print(f"  {c.score:>4}  {c.url}")
            print(f"        text={c.text!r}  [{c.reason}]")
        return

    rows = load_homepages()
    if args.limit:
        rows = rows[: args.limit]

    results, found = [], 0
    for i, row in enumerate(rows, start=1):
        cands = discover(row["url"], session)
        best = cands[0] if cands else None
        if best:
            found += 1

        results.append({
            "network": row["network"], "homepage": row["url"],
            "classification": row["classification"], "source": row["source"],
            "member_url": best.url if best else "",
            "link_text": best.text if best else "",
            "confidence": best.score if best else 0,
            "matched_terms": best.reason if best else "",
            "alternatives": " | ".join(c.url for c in cands[1:]),
        })

        mark = "  " if best else "! "
        print(f"{mark}[{i:>3}/{len(rows)}] {(best.score if best else 0):>4}  "
              f"{row['network'][:32]:<32} -> "
              f"{(best.url if best else 'NOT FOUND')[:52]}")
        time.sleep(config.REQUEST_DELAY)

    with open(DISCOVERY_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"\n  member page located for {found}/{len(rows)} homepages "
          f"({found/len(rows)*100:.0f}%)")
    print(f"  -> {DISCOVERY_CSV}")


if __name__ == "__main__":
    main()
